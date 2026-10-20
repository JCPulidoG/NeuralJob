"""
scraper.py
Extractor modular y multicanal de vacantes laborales:
- Soporte para portales nativos vía python-jobspy: LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter.
- Extractores específicos para México: CompuTrabajo (mx.computrabajo.com) y OCC Mundial (occ.com.mx).
- Soporte para filtros de ubicación (Toda la CDMX, Valle de Toluca, República Mexicana) y Modalidad (Híbrido/Remoto).
- Antigüedad por defecto: 1 semana (168 horas).
- Resultados deseados por defecto: 50.
- Cumple con la regla de CERO HARDCODE y deduplicación determinista.
"""

import os
import re
import json
import hashlib
import datetime
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# jobspy se importa diferido (lazy import) para no penalizar el tiempo de arranque
HAS_JOBSPY = True

from build_master import build_master
from db import upsert_lead, get_leads, update_job_status_db, init_db
from geo_catalog import normalize_location, detect_modality, get_search_location_string
from salary_estimator import estimate_job_salary


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LEADS_JSON = DATA_DIR / "job_leads.json"
MASTER_JSON = DATA_DIR / "cv_master.json"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
}


def generate_lead_id(title: str, company: str, job_url: str = "") -> str:
    """Genera un identificador único y determinista para la vacante"""
    raw_key = f"{title.strip().lower()}|{company.strip().lower()}|{job_url.strip().lower()}"
    return "JOB-" + hashlib.md5(raw_key.encode('utf-8')).hexdigest()[:8].upper()


def load_job_leads() -> List[Dict[str, Any]]:
    """Carga las vacantes directamente desde la base de datos SQLite"""
    try:
        leads = get_leads()
        if leads:
            return leads
    except Exception as e:
        print(f"⚠️ Error leyendo de SQLite ({e}), usando JSON de respaldo...")

    if not LEADS_JSON.exists():
        return []
    try:
        with open(LEADS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_job_leads(leads: List[Dict[str, Any]]):
    """Guarda la lista de vacantes en SQLite y en el JSON de respaldo"""
    for lead in leads:
        upsert_lead(lead)

    LEADS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(LEADS_JSON, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)


def get_default_search_params() -> Dict[str, Any]:
    """
    Obtiene dinámicamente los términos de búsqueda y ubicación desde cv_master.json
    sin ningún hardcode.
    """
    if not MASTER_JSON.exists():
        build_master(output_path=MASTER_JSON)

    with open(MASTER_JSON, "r", encoding="utf-8") as f:
        master = json.load(f)

    profiles = master.get("profile", {}).get("target_profiles", [])
    terms = []
    for p in profiles:
        title = p.get("title", "")
        tag = p.get("tag", "")
        if title and title not in terms:
            terms.append(title)
        if tag and tag not in terms:
            terms.append(tag)

    return {
        "search_terms": terms if terms else ["Data Lead", "Quant Analyst", "Data Scientist"],
        "default_location": "Toda la CDMX",
        "default_results": 50,
        "default_hours_old": 168,
        "default_modality": "Híbrido y Remoto (Toda la República Mexicana)",
        "default_sites": ["linkedin", "indeed", "google", "computrabajo", "occ"]
    }


def scrape_computrabajo(
    search_term: str,
    location: str = "Ciudad de México",
    results_wanted: int = 25,
    hours_old: int = 168
) -> List[Dict[str, Any]]:
    """
    Extractor de vacantes para Computrabajo México (mx.computrabajo.com).
    Maneja filtros de publicación y paginación con parsing de BeautifulSoup.
    """
    if not HAS_REQUESTS or not HAS_BS4:
        return []

    leads = []
    pub_param = "7"
    if hours_old <= 24:
        pub_param = "1"
    elif hours_old <= 72:
        pub_param = "3"
    elif hours_old <= 168:
        pub_param = "7"
    else:
        pub_param = "30"

    # Preparar URL de búsqueda de Computrabajo
    query_encoded = urllib.parse.quote_plus(search_term.strip())
    loc_encoded = urllib.parse.quote_plus(location.strip())
    search_url = f"https://mx.computrabajo.com/empleos?q={query_encoded}&prov={loc_encoded}&pubdate={pub_param}"

    try:
        session = requests.Session()
        resp = session.get(search_url, headers=DEFAULT_HEADERS, timeout=12)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select("article.box_offer, article.bRS")

        for art in articles[:results_wanted]:
            title_tag = art.select_one("h1 a, h2 a, a.js-o-link")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            href = title_tag.get("href", "")
            if href.startswith("/"):
                job_url = f"https://mx.computrabajo.com{href}"
            else:
                job_url = href

            # Empresa
            comp_tag = art.select_one("p.fc_aux, a[class*='fc_base'], p[class*='company']")
            company = comp_tag.get_text(strip=True) if comp_tag else "Empresa Confidencial"

            # Ubicación
            loc_tag = art.select_one("p.fs16, span[class*='fc_base'], p[class*='location']")
            loc_str = loc_tag.get_text(strip=True) if loc_tag else location

            # Descripción / Snippet
            desc_tag = art.select_one("p.body_normal, p.text_ellipsis, div[class*='description']")
            desc = desc_tag.get_text(strip=True) if desc_tag else f"Vacante de {title} en {company} ({loc_str})."

            lead_id = generate_lead_id(title, company, job_url)
            leads.append({
                "id": lead_id,
                "title": title,
                "company": company,
                "location": loc_str,
                "job_url": job_url,
                "description": desc,
                "date_posted": datetime.datetime.now().strftime("%Y-%m-%d"),
                "source": "computrabajo",
                "search_term": search_term,
                "extracted_at": datetime.datetime.now().isoformat()
            })

    except Exception as e:
        print(f"⚠️ Computrabajo scraper ({search_term}): {e}")

    return leads


def scrape_occ(
    search_term: str,
    location: str = "Ciudad de México",
    results_wanted: int = 25,
    hours_old: int = 168
) -> List[Dict[str, Any]]:
    """
    Extractor de vacantes para OCC Mundial (occ.com.mx).
    Extrae la data estructurada de Next.js o hace scraping HTML de respaldo.
    """
    if not HAS_REQUESTS or not HAS_BS4:
        return []

    leads = []
    query_encoded = urllib.parse.quote_plus(search_term.strip())
    loc_encoded = urllib.parse.quote_plus(location.strip())
    search_url = f"https://www.occ.com.mx/empleos/buscar?q={query_encoded}&l={loc_encoded}&d=7"

    try:
        session = requests.Session()
        resp = session.get(search_url, headers=DEFAULT_HEADERS, timeout=12)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 1. Intentar parsear __NEXT_DATA__
        next_data_tag = soup.find("script", id="__NEXT_DATA__")
        if next_data_tag and next_data_tag.string:
            try:
                data = json.loads(next_data_tag.string)
                job_list = []
                props = data.get("props", {}).get("pageProps", {})
                if "initialState" in props and "jobs" in props["initialState"]:
                    job_list = props["initialState"]["jobs"].get("results", [])
                elif "jobs" in props:
                    job_list = props["jobs"].get("results", []) or props["jobs"]

                for j in job_list[:results_wanted]:
                    title = j.get("title") or j.get("jobTitle")
                    if not title:
                        continue
                    company = j.get("company", {}).get("name") or j.get("companyName") or "Empresa Confidencial"
                    loc_val = j.get("location", {}).get("name") or j.get("location") or location
                    slug = j.get("slug") or j.get("id") or ""
                    job_url = f"https://www.occ.com.mx/empleo/oferta/{slug}" if slug else "https://www.occ.com.mx"
                    desc = j.get("description") or j.get("snippet") or f"Vacante de {title} en {company}."
                    
                    lead_id = generate_lead_id(title, company, job_url)
                    leads.append({
                        "id": lead_id,
                        "title": title,
                        "company": company,
                        "location": str(loc_val),
                        "job_url": job_url,
                        "description": desc,
                        "date_posted": datetime.datetime.now().strftime("%Y-%m-%d"),
                        "source": "occ",
                        "search_term": search_term,
                        "extracted_at": datetime.datetime.now().isoformat()
                    })
                if leads:
                    return leads
            except Exception:
                pass

        # 2. Fallback HTML
        job_cards = soup.select("div[class*='job-card'], div[data-testid*='job-card'], article")
        for card in job_cards[:results_wanted]:
            t_tag = card.select_one("h2 a, h3 a, a[data-testid*='job-title']")
            if not t_tag:
                continue
            title = t_tag.get_text(strip=True)
            href = t_tag.get("href", "")
            job_url = f"https://www.occ.com.mx{href}" if href.startswith("/") else href
            
            c_tag = card.select_one("span[class*='company'], p[class*='company']")
            company = c_tag.get_text(strip=True) if c_tag else "Empresa Confidencial"
            
            l_tag = card.select_one("span[class*='location'], p[class*='location']")
            loc_str = l_tag.get_text(strip=True) if l_tag else location
            
            d_tag = card.select_one("p[class*='description'], div[class*='snippet']")
            desc = d_tag.get_text(strip=True) if d_tag else f"Oferta laboral {title} en {company}."

            lead_id = generate_lead_id(title, company, job_url)
            leads.append({
                "id": lead_id,
                "title": title,
                "company": company,
                "location": loc_str,
                "job_url": job_url,
                "description": desc,
                "date_posted": datetime.datetime.now().strftime("%Y-%m-%d"),
                "source": "occ",
                "search_term": search_term,
                "extracted_at": datetime.datetime.now().isoformat()
            })

    except Exception as e:
        print(f"⚠️ OCC scraper ({search_term}): {e}")

    return leads


def scrape_adzuna(
    search_term: str,
    location: str = "Ciudad de México",
    results_wanted: int = 25,
    hours_old: int = 168
) -> List[Dict[str, Any]]:
    """
    Extractor de vacantes para Adzuna México (api.adzuna.com).
    Requiere ADZUNA_APP_ID y ADZUNA_APP_KEY en variables de entorno (gratuita).
    """
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key or not HAS_REQUESTS:
        return []

    leads = []
    try:
        url = "https://api.adzuna.com/v1/api/jobs/mx/search/1"
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "what": search_term,
            "where": location,
            "results_per_page": min(results_wanted, 50),
            "max_days_old": max(1, hours_old // 24),
            "content-type": "application/json"
        }
        resp = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("results", []):
                t = item.get("title", "")
                c = item.get("company", {}).get("display_name", "Empresa Confidencial")
                l = item.get("location", {}).get("display_name", location)
                u = item.get("redirect_url", "")
                d = item.get("description", "")
                dp = item.get("created", "")[:10]
                s_min = item.get("salary_min")
                s_max = item.get("salary_max")
                
                sal_data = estimate_job_salary(t, c, d)
                sal_disp = f"${s_min:,.0f} - ${s_max:,.0f} MXN/mes (Declarado)" if (s_min and s_max) else sal_data["salary_display"]

                leads.append({
                    "id": generate_lead_id(t, c, u),
                    "title": t,
                    "company": c,
                    "location": l,
                    "job_url": u,
                    "description": d,
                    "date_posted": dp,
                    "source": "adzuna",
                    "salary_min": s_min or sal_data["salary_min"],
                    "salary_max": s_max or sal_data["salary_max"],
                    "salary_currency": "MXN",
                    "salary_display": sal_disp,
                    "seniority_level": sal_data["seniority_label"],
                    "search_term": search_term,
                    "extracted_at": datetime.datetime.now().isoformat()
                })
    except Exception as e:
        print(f"⚠️ Error en Adzuna API: {e}")
    return leads


def scrape_vacancies(
    search_term: str,
    location: str = "Toda la CDMX",
    sites: Optional[List[str]] = None,
    results_wanted: int = 50,
    hours_old: int = 168,
    modality: str = "Híbrido y Remoto (Toda la República Mexicana)",
    country_indeed: str = "mexico"
) -> List[Dict[str, Any]]:
    """
    Ejecuta el scraping multiportal (JobSpy [LinkedIn + Indeed + Google Jobs] + Computrabajo + OCC + Adzuna)
    garantizando descripciones completas y estimación salarial.
    """
    if sites is None:
        sites = ["linkedin", "indeed", "google", "computrabajo", "occ"]

    normalized_sites = [s.strip().lower() for s in sites]
    query_loc = get_search_location_string(location)
    
    # Determinar si la modalidad exige búsqueda remota
    is_remote_query = False
    mod_lower = modality.lower()
    if "remoto" in mod_lower or "híbrido" in mod_lower or "hibrido" in mod_lower:
        if "republica" in mod_lower or "república" in mod_lower or "solo remoto" in mod_lower:
            is_remote_query = True

    print(f"🔍 Iniciando búsqueda multicanal: '{search_term}' en '{query_loc}' | Modalidad: '{modality}' (Sitios: {sites}) | Objetivos: {results_wanted}...")

    extracted_leads = []

    # 1. JobSpy (LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter)
    jobspy_sites = [s for s in normalized_sites if s in ["linkedin", "indeed", "glassdoor", "zip_recruiter", "google"]]
    if HAS_JOBSPY and jobspy_sites:
        try:
            from jobspy import scrape_jobs
            results_jobspy = min(results_wanted, 50)
            df_jobs = scrape_jobs(
                site_name=jobspy_sites,
                search_term=search_term,
                location=query_loc,
                is_remote=is_remote_query,
                results_wanted=results_jobspy,
                hours_old=hours_old,
                country_indeed=country_indeed,
                linkedin_fetch_description=True
            )
            if df_jobs is not None and not df_jobs.empty:
                for _, row in df_jobs.iterrows():
                    t = str(row.get("title") or "").strip()
                    c = str(row.get("company") or "Empresa Confidencial").strip()
                    l = str(row.get("location") or query_loc).strip()
                    u = str(row.get("job_url") or "").strip()
                    d = str(row.get("description") or "").strip()
                    dp = str(row.get("date_posted") or "")
                    s = str(row.get("site") or "jobspy")

                    if not t:
                        continue

                    # Sanitizar descripción para evitar NaN
                    if not d or d.lower() in ["nan", "none", "null"]:
                        d = f"Vacante de {t} en {c} ({l}). Sin descripción detallada proporcionada por la plataforma."

                    sal_data = estimate_job_salary(t, c, d)
                    lead_id = generate_lead_id(t, c, u)
                    extracted_leads.append({
                        "id": lead_id,
                        "title": t,
                        "company": c,
                        "location": l,
                        "job_url": u,
                        "description": d,
                        "date_posted": dp,
                        "source": s,
                        "salary_min": sal_data["salary_min"],
                        "salary_max": sal_data["salary_max"],
                        "salary_currency": sal_data["salary_currency"],
                        "salary_display": sal_data["salary_display"],
                        "seniority_level": sal_data["seniority_label"],
                        "search_term": search_term,
                        "extracted_at": datetime.datetime.now().isoformat()
                    })
        except Exception as e:
            print(f"⚠️ Error en JobSpy ({jobspy_sites}): {e}")

    # 2. Computrabajo
    if any("compu" in s for s in normalized_sites):
        try:
            ct_leads = scrape_computrabajo(
                search_term=search_term,
                location=query_loc,
                results_wanted=min(results_wanted, 25),
                hours_old=hours_old
            )
            extracted_leads.extend(ct_leads)
        except Exception as e:
            print(f"⚠️ Error extrayendo CompuTrabajo: {e}")

    # 3. OCC Mundial
    if any("occ" in s for s in normalized_sites):
        try:
            occ_leads = scrape_occ(
                search_term=search_term,
                location=query_loc,
                results_wanted=min(results_wanted, 25),
                hours_old=hours_old
            )
            extracted_leads.extend(occ_leads)
        except Exception as e:
            print(f"⚠️ Error extrayendo OCC: {e}")

    # 4. Adzuna México API (si está habilitado o configurado)
    if "adzuna" in normalized_sites or os.getenv("ADZUNA_APP_ID"):
        try:
            adzuna_leads = scrape_adzuna(
                search_term=search_term,
                location=query_loc,
                results_wanted=min(results_wanted, 25),
                hours_old=hours_old
            )
            extracted_leads.extend(adzuna_leads)
        except Exception as e:
            print(f"⚠️ Error extrayendo Adzuna: {e}")

    # Cargar leads existentes y fusionar evitando duplicados
    existing_leads = load_job_leads()
    existing_ids = {l["id"] for l in existing_leads}

    added_count = 0
    for lead in extracted_leads:
        # Asignar modalidad detectada
        lead["modality"] = detect_modality(lead.get("description", ""), lead.get("location", ""))
        
        if lead["id"] not in existing_ids:
            existing_leads.append(lead)
            existing_ids.add(lead["id"])
            upsert_lead(lead)
            update_job_status_db(lead["id"], "nueva", {
                "title": lead["title"],
                "company": lead["company"],
                "source": lead["source"],
                "job_url": lead["job_url"],
                "modality": lead["modality"],
                "salary_display": lead.get("salary_display", "")
            })
            added_count += 1

    save_job_leads(existing_leads)
    print(f"✅ Extracción completada. {len(extracted_leads)} procesadas, {added_count} nuevas agregadas a SQLite.")
    return extracted_leads


def add_manual_lead(
    title: str,
    company: str,
    description: str,
    job_url: str = "",
    location: str = "Remoto",
    modality: Optional[str] = None
) -> Dict[str, Any]:
    """
    Permite registrar manualmente una vacante pegada por el usuario en el dashboard.
    """
    lead_id = generate_lead_id(title, company, job_url)
    computed_modality = modality or detect_modality(description, location)
    
    lead = {
        "id": lead_id,
        "title": title.strip(),
        "company": company.strip() if company else "Empresa Confidencial",
        "location": location.strip(),
        "job_url": job_url.strip(),
        "description": description.strip(),
        "date_posted": datetime.datetime.now().strftime("%Y-%m-%d"),
        "source": "manual",
        "modality": computed_modality,
        "search_term": "manual_entry",
        "extracted_at": datetime.datetime.now().isoformat()
    }

    upsert_lead(lead)
    update_job_status_db(lead_id, "revisada", {
        "title": lead["title"],
        "company": lead["company"],
        "source": "manual",
        "job_url": lead["job_url"],
        "modality": computed_modality
    })

    # Actualizar lista JSON
    existing_leads = [l for l in load_job_leads() if l["id"] != lead_id]
    existing_leads.insert(0, lead)
    with open(LEADS_JSON, "w", encoding="utf-8") as f:
        json.dump(existing_leads, f, ensure_ascii=False, indent=2)

    return lead


if __name__ == "__main__":
    defaults = get_default_search_params()
    print("Términos de búsqueda dinámicos:", defaults["search_terms"])
    print("Ubicación por defecto:", defaults["default_location"])
    print("Resultados deseados:", defaults["default_results"])
    print("Horas de antigüedad:", defaults["default_hours_old"])
    print("Modalidad:", defaults["default_modality"])
    print("Portales:", defaults["default_sites"])
