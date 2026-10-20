"""
translator.py
Módulo de traducción automática y enriquecimiento bilingüe para el Motor de Empleo.
Cumple con la regla de CERO HARDCODE:
- Traduce automáticamente texto de Español (ES) a Inglés (EN) utilizando el servicio de traducción sin requerir API keys.
- Utiliza una caché local en disco (data/translation_cache.json) para evitar llamadas repetidas y acelerar la compilación.
- Soporta tanto la traducción al vuelo del CV tailoreado para compilar PDF/MD como la traducción completa de archivos JSON maestros.
"""

import os
import re
import json
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_FILE = DATA_DIR / "translation_cache.json"

# Términos técnicos que deben preservarse intactos
TECH_TERMS = {
    "var": "VaR",
    "cvar": "CVaR",
    "monte carlo": "Monte Carlo",
    "databricks": "Databricks",
    "pyspark": "PySpark",
    "delta lake": "Delta Lake",
    "finops": "FinOps",
    "consar": "CONSAR",
    "amib": "AMIB",
    "rfm": "RFM",
    "llm": "LLM",
    "llms": "LLMs",
    "etl": "ETL",
    "elt": "ELT",
    "sql": "SQL",
    "dwh": "DWH",
    "bi": "BI",
    "ats": "ATS",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "scikit-learn": "Scikit-Learn",
    "k-means": "K-Means",
    "dbscan": "DBSCAN"
}


def load_cache() -> Dict[str, str]:
    """Carga la caché de traducciones desde disco"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache: Dict[str, str]):
    """Guarda la caché de traducciones en disco"""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def restore_tech_terms(text: str) -> str:
    """Asegura la capitalización correcta de acrónimos y términos técnicos"""
    for term_lower, proper_case in TECH_TERMS.items():
        pattern = rf'(?i)\b{re.escape(term_lower)}\b'
        text = re.sub(pattern, proper_case, text)
    return text


def translate_text(text: str, source_lang: str = "es", target_lang: str = "en") -> str:
    """
    Traduce una cadena de texto de source_lang a target_lang.
    Utiliza caché local y fallback seguro en caso de error de red.
    """
    if not text or not text.strip():
        return text

    clean_text = text.strip()
    cache_key = f"{source_lang}->{target_lang}::{clean_text}"
    cache = load_cache()

    if cache_key in cache:
        return cache[cache_key]

    if not HAS_REQUESTS:
        return clean_text

    try:
        # Endpoint directo y ligero de Google Translate
        url = (
            f"https://translate.googleapis.com/translate_a/single?"
            f"client=gtx&sl={source_lang}&tl={target_lang}&dt=t&q={urllib.parse.quote(clean_text)}"
        )
        response = requests.get(url, timeout=6)
        if response.status_code == 200:
            data = response.json()
            translated = "".join([part[0] for part in data[0] if part[0]])
            translated = restore_tech_terms(translated.strip())
            cache[cache_key] = translated
            save_cache(cache)
            return translated
    except Exception as e:
        print(f"⚠️ Error al traducir texto ('{clean_text[:30]}...'): {e}")

    # Fallback al texto original si falla la conexión
    return clean_text


def translate_period(period_str: str) -> str:
    """Traduce formatos de periodo laboral a inglés (ej. 'JUL/2025 - ACT' -> 'JUL/2025 - PRESENT')"""
    if not period_str:
        return ""
    p = period_str.strip()
    p = re.sub(r'\b(act|actual|presente)\b', 'PRESENT', p, flags=re.IGNORECASE)
    p = re.sub(r'\bene\b', 'JAN', p, flags=re.IGNORECASE)
    p = re.sub(r'\bfeb\b', 'FEB', p, flags=re.IGNORECASE)
    p = re.sub(r'\bmar\b', 'MAR', p, flags=re.IGNORECASE)
    p = re.sub(r'\babr\b', 'APR', p, flags=re.IGNORECASE)
    p = re.sub(r'\bmay\b', 'MAY', p, flags=re.IGNORECASE)
    p = re.sub(r'\bjun\b', 'JUN', p, flags=re.IGNORECASE)
    p = re.sub(r'\bjul\b', 'JUL', p, flags=re.IGNORECASE)
    p = re.sub(r'\bago\b', 'AUG', p, flags=re.IGNORECASE)
    p = re.sub(r'\bsep\b', 'SEP', p, flags=re.IGNORECASE)
    p = re.sub(r'\boct\b', 'OCT', p, flags=re.IGNORECASE)
    p = re.sub(r'\bnov\b', 'NOV', p, flags=re.IGNORECASE)
    p = re.sub(r'\bdic\b', 'DEC', p, flags=re.IGNORECASE)
    return p


def translate_cv_data(cv_data: Dict[str, Any], target_lang: str = "en") -> Dict[str, Any]:
    """
    Toma la estructura del CV tailoreado (tailored_cv de matcher.py) y traduce
    automáticamente todos sus campos al inglés, asignando los valores a *_en.
    Retorna una copia profunda con los campos traducidos.
    """
    import copy
    cv_en = copy.deepcopy(cv_data)

    # 1. Perfil Objetivo (Title y Summary)
    chosen_profile = cv_en.get("chosen_profile", {})
    if chosen_profile:
        orig_title = chosen_profile.get("title", "")
        if orig_title and not chosen_profile.get("title_en"):
            chosen_profile["title_en"] = translate_text(orig_title, target_lang=target_lang)

        orig_summary = chosen_profile.get("summary", "")
        if orig_summary and not chosen_profile.get("summary_en"):
            chosen_profile["summary_en"] = translate_text(orig_summary, target_lang=target_lang)

    # 2. Información de Contacto (Ubicación)
    contact_info = cv_en.get("contact_info", {})
    for k in list(contact_info.keys()):
        if any(w in k.lower() for w in ["ubicación", "ubicacion", "location"]) and not contact_info.get("Ubicación_en"):
            contact_info["Ubicación_en"] = translate_text(contact_info[k], target_lang=target_lang)

    # 3. Experiencias y Viñetas
    for exp in cv_en.get("tailored_experiences", []):
        orig_role = exp.get("role", "")
        if orig_role and not exp.get("role_en"):
            exp["role_en"] = translate_text(orig_role, target_lang=target_lang)

        orig_period = exp.get("period", "")
        if orig_period and not exp.get("period_en"):
            exp["period_en"] = translate_period(orig_period)

        for b in exp.get("selected_bullets", []):
            orig_bullet = b.get("bullet") or b.get("text") or ""
            if orig_bullet and not b.get("bullet_en") and not b.get("text_en"):
                trans_b = translate_text(orig_bullet, target_lang=target_lang)
                b["bullet_en"] = trans_b
                b["text_en"] = trans_b

            orig_metric = b.get("metric", "")
            if orig_metric and not b.get("metric_en"):
                b["metric_en"] = translate_text(orig_metric, target_lang=target_lang)

    # 4. Habilidades por Categoría
    skills_by_cat = cv_en.get("skills_by_category", {})
    translated_skills_by_cat = {}
    for cat, sk_list in skills_by_cat.items():
        cat_en = translate_text(cat, target_lang=target_lang)
        new_sk_list = []
        for s in sk_list:
            s_copy = dict(s)
            orig_skill = s.get("skill", "")
            if orig_skill and not s.get("skill_en"):
                s_copy["skill_en"] = translate_text(orig_skill, target_lang=target_lang)
            new_sk_list.append(s_copy)
        translated_skills_by_cat[cat_en] = new_sk_list
    cv_en["skills_by_category"] = translated_skills_by_cat

    # 5. Educación y Certificaciones
    for edu in cv_en.get("education", []):
        orig_val = edu.get("value", "")
        if orig_val and not edu.get("value_en"):
            edu["value_en"] = translate_text(orig_val, target_lang=target_lang)

    for cert in cv_en.get("certifications", []):
        orig_val = cert.get("value", "")
        if orig_val and not cert.get("value_en"):
            cert["value_en"] = translate_text(orig_val, target_lang=target_lang)

    return cv_en


def translate_json_master(source_path: Path, output_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Lee un archivo JSON canónico de perfil (ej. cv_master.json o template),
    traduce automáticamente todos los campos al inglés y genera/actualiza el archivo.
    """
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo fuente: {source_path}")

    with open(source_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"🌐 Iniciando traducción automática de {source_path.name}...")

    # Perfil y Target Profiles
    profile = data.get("profile", {})
    for tp in profile.get("target_profiles", []):
        if tp.get("title") and not tp.get("title_en"):
            tp["title_en"] = translate_text(tp["title"])
        if tp.get("summary") and not tp.get("summary_en"):
            tp["summary_en"] = translate_text(tp["summary"])

    # Contacto
    contact = profile.get("contact_info", {})
    for k in list(contact.keys()):
        if any(w in k.lower() for w in ["ubicación", "ubicacion", "location"]) and not contact.get("Ubicación_en"):
            contact["Ubicación_en"] = translate_text(contact[k])

    # Experiencias (items)
    experiences = data.get("experiences", {})
    items = experiences.get("items", [])
    print(f"   Traduciendo {len(items)} logros atómicos...")
    for item in items:
        if item.get("role") and not item.get("role_en"):
            item["role_en"] = translate_text(item["role"])
        if item.get("period") and not item.get("period_en"):
            item["period_en"] = translate_period(item["period"])
        if item.get("bullet") and not item.get("bullet_en"):
            item["bullet_en"] = translate_text(item["bullet"])
        if item.get("metric") and not item.get("metric_en"):
            item["metric_en"] = translate_text(item["metric"])

    # Experiencias (grouped)
    for g in experiences.get("grouped", []):
        if g.get("role") and not g.get("role_en"):
            g["role_en"] = translate_text(g["role"])
        if g.get("period") and not g.get("period_en"):
            g["period_en"] = translate_period(g["period"])
        for b in g.get("bullets", []):
            if b.get("text") and not b.get("bullet_en"):
                b["bullet_en"] = translate_text(b["text"])
            if b.get("metric") and not b.get("metric_en"):
                b["metric_en"] = translate_text(b["metric"])

    # Educación & Certificaciones
    for edu in profile.get("education", []):
        if edu.get("value") and not edu.get("value_en"):
            edu["value_en"] = translate_text(edu["value"])
    for cert in profile.get("certifications", []):
        if cert.get("value") and not cert.get("value_en"):
            cert["value_en"] = translate_text(cert["value"])

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Archivo traducido guardado en: {output_path}")

    return data


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else str(DATA_DIR / "cv_master.template.json")
    out = sys.argv[2] if len(sys.argv) > 2 else None
    translate_json_master(src, out)
