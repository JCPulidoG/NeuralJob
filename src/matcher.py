"""
matcher.py
Motor de Scoring ATS y Selector Inteligente de Viñetas.
Cumple con la regla de CERO HARDCODE:
- Lee los datos dinámicamente desde data/cv_master.json.
- Compara los requerimientos de la vacante contra las keywords, tracks y viñetas del master.
- Selecciona el perfil objetivo más alineado y las viñetas de mayor impacto para el rol.
- Gestiona el historial de postulaciones en data/history.json.
"""

import json
import re
import math
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter

from build_master import build_master
from db import update_job_status_db, save_ats_evaluation_db, get_status_counts
from salary_estimator import estimate_job_salary, detect_seniority


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MASTER_JSON = DATA_DIR / "cv_master.json"
HISTORY_JSON = DATA_DIR / "history.json"


def load_master_data(force_rebuild: bool = False) -> Dict[str, Any]:
    """Carga el cv_master.json o lo compila/inicializa si no existe o se fuerza."""
    if not MASTER_JSON.exists():
        template_file = DATA_DIR / "cv_master.template.json"
        if template_file.exists():
            import shutil
            shutil.copy(template_file, MASTER_JSON)
        return build_master(output_path=MASTER_JSON)
    
    if force_rebuild:
        return build_master(output_path=MASTER_JSON)
    
    with open(MASTER_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history() -> Dict[str, Any]:
    """Carga el historial de vacantes y postulaciones desde data/history.json"""
    if not HISTORY_JSON.exists():
        initial = {
            "records": {},  # job_id -> record
            "updated_at": ""
        }
        with open(HISTORY_JSON, "w", encoding="utf-8") as f:
            json.dump(initial, f, ensure_ascii=False, indent=2)
        return initial

    try:
        with open(HISTORY_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"records": {}, "updated_at": ""}


def save_history(history_data: Dict[str, Any]):
    """Guarda el historial de vacantes."""
    import datetime
    history_data["updated_at"] = datetime.datetime.now().isoformat()
    with open(HISTORY_JSON, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)


def update_job_status(job_id: str, status: str, metadata: Optional[Dict[str, Any]] = None):
    """
    Actualiza el estado de una vacante en la base de datos SQLite y sincroniza history.json.
    Estados válidos: 'nueva', 'revisada', 'cv_generado', 'aplicada', 'descartada'
    """
    # 1. Actualizar en SQLite
    update_job_status_db(job_id, status, metadata)

    # 2. Sincronizar en history.json como respaldo
    history = load_history()
    import datetime
    now_str = datetime.datetime.now().isoformat()

    if job_id not in history["records"]:
        history["records"][job_id] = {
            "job_id": job_id,
            "status": status,
            "created_at": now_str,
            "updated_at": now_str,
            "history_log": [{"status": status, "timestamp": now_str}]
        }
    else:
        record = history["records"][job_id]
        record["status"] = status
        record["updated_at"] = now_str
        if "history_log" not in record:
            record["history_log"] = []
        record["history_log"].append({"status": status, "timestamp": now_str})

    if metadata:
        for k, v in metadata.items():
            history["records"][job_id][k] = v

    save_history(history)
    return history["records"][job_id]


def extract_keywords_and_terms(text: str) -> List[str]:
    """
    Extrae palabras clave y n-gramas relevantes de un texto en español/inglés,
    normalizando acentos y caracteres especiales.
    """
    if not text:
        return []

    # Normalizar texto básico
    t = text.lower()
    # Reemplazar caracteres de puntuación por espacios preservando caracteres técnicos como C++, .NET, C#
    t = re.sub(r'[/\\,;:\(\)\[\]\{\}"\'`_!?]', ' ', t)
    
    # Tokenizar
    tokens = re.split(r'\s+', t)
    tokens = [tok.strip('.').strip('-') for tok in tokens if len(tok.strip('.').strip('-')) > 1]

    # Stopwords comunes español e inglés
    stopwords = {
        'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por', 'un', 'para',
        'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'más', 'mas', 'pero', 'sus', 'le', 'ya', 'o',
        'este', 'sí', 'porque', 'esta', 'son', 'entre', 'está', 'esta', 'sobre', 'también', 'me', 'hasta',
        'hay', 'donde', 'quien', 'desde', 'todo', 'nos', 'durante', 'todos', 'uno', 'les', 'ni', 'contra',
        'the', 'and', 'to', 'of', 'a', 'in', 'is', 'that', 'for', 'it', 'as', 'was', 'with', 'on', 'be',
        'at', 'by', 'this', 'have', 'from', 'or', 'one', 'had', 'by', 'word', 'but', 'not', 'what', 'all',
        'were', 'we', 'when', 'your', 'can', 'said', 'there', 'use', 'an', 'each', 'which', 'she', 'do',
        'how', 'their', 'if', 'will', 'up', 'other', 'about', 'out', 'many', 'then', 'them', 'these', 'so',
        'some', 'her', 'would', 'make', 'like', 'him', 'into', 'time', 'has', 'look', 'two', 'more', 'write',
        'go', 'see', 'number', 'no', 'way', 'could', 'people', 'my', 'than', 'first', 'water', 'been', 'call',
        'who', 'oil', 'its', 'now', 'find', 'long', 'down', 'day', 'did', 'get', 'come', 'made', 'may', 'part',
        'experience', 'experiencia', 'años', 'years', 'trabajo', 'job', 'role', 'position', 'team', 'equipo',
        'skills', 'habilidades', 'responsibilities', 'requisitos', 'requirements', 'responsabilidades',
        'conocimiento', 'knowledge', 'candidate', 'candidato', 'ideal', 'looking', 'buscamos'
    }

    tech_acronyms_2 = {"ai", "ia", "ml", "bi", "qa", "db", "ui", "ux", "it"}
    filtered = [tok for tok in tokens if tok not in stopwords and (len(tok) > 2 or tok in tech_acronyms_2)]
    return filtered


BILINGUAL_MAP = {
    "lead": "líder", "leader": "líder", "líder": "lead", "lider": "lead",
    "architect": "arquitecto", "arquitecto": "architect",
    "manager": "gerente", "gerente": "manager",
    "analyst": "analista", "analista": "analyst",
    "scientist": "científico", "científico": "scientist", "cientifico": "scientist",
    "engineer": "ingeniero", "ingeniero": "engineer",
    "risk": "riesgo", "riesgos": "risk", "riesgo": "risk",
    "data": "datos", "datos": "data",
    "ai": "ia", "ia": "ai",
    "quant": "cuantitativo", "quantitative": "cuantitativo", "cuantitativo": "quant"
}


def get_expanded_tokens(text: str) -> set:
    """Expande tokens con equivalencias bilingües inglés/español comunes en tech"""
    toks = set([t.lower() for t in re.split(r'\W+', text) if len(t) > 1])
    expanded = set(toks)
    for t in toks:
        if t in BILINGUAL_MAP:
            expanded.add(BILINGUAL_MAP[t])
    return expanded


def compute_title_affinity(job_title: str, profile_title: str, profile_tag: str) -> float:
    """Calcula la afinidad entre el título de la vacante y el perfil objetivo"""
    j_toks = get_expanded_tokens(job_title)
    p_toks = get_expanded_tokens(profile_title).union(get_expanded_tokens(profile_tag))

    if not j_toks:
        return 0.0

    matches = 0
    for j in j_toks:
        if j in p_toks:
            matches += 1
        elif any(j[:4] == p[:4] for p in p_toks if len(p) >= 4 and len(j) >= 4):
            matches += 1

    score = (matches / len(j_toks)) * 100.0
    return min(100.0, score)


def calculate_term_overlap(source_terms: List[str], target_text_lower: str) -> Tuple[int, List[str]]:
    """Calcula cuántos términos fuente aparecen en el texto objetivo"""
    matched = []
    for term in source_terms:
        term_clean = term.strip().lower()
        if not term_clean or (len(term_clean) < 2 and term_clean not in {"ai", "ia", "ml", "bi"}):
            continue
        pattern = r'(?:\b|_)' + re.escape(term_clean) + r'(?:\b|_)'
        if re.search(pattern, target_text_lower):
            matched.append(term)
        elif len(term_clean) >= 4 and term_clean in target_text_lower:
            matched.append(term)
    return len(set(matched)), list(set(matched))


def select_best_target_profile(job_text: str, target_profiles: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], float]:
    """
    Selecciona dinámicamente el Target Profile más adecuado a partir de la vacante.
    """
    if not target_profiles:
        return {}, 0.0

    job_lower = job_text.lower()
    best_profile = target_profiles[0]
    best_score = -1.0

    for profile in target_profiles:
        title = profile.get("title", "")
        summary = profile.get("summary", "")
        tag = profile.get("tag", "")
        note = profile.get("note", "")

        score = 0.0

        # Afinidad de título bilingüe
        t_affinity = compute_title_affinity(job_text[:100], title, tag)
        score += t_affinity * 0.50

        # Coincidencia con tag
        if tag:
            tag_toks = get_expanded_tokens(tag)
            for tt in tag_toks:
                if tt in job_lower:
                    score += 25.0
                    break

        # Coincidencia con términos del resumen
        summary_terms = extract_keywords_and_terms(summary)
        matched_sum_count, _ = calculate_term_overlap(summary_terms, job_lower)
        if summary_terms:
            score += (matched_sum_count / len(summary_terms)) * 25.0

        if score > best_score:
            best_score = score
            best_profile = profile

    return best_profile, best_score


def score_bullet(bullet_data: Dict[str, Any], job_text_lower: str, profile_tag: str) -> Tuple[float, List[str]]:
    """
    Evalúa la relevancia de un logro atómico frente a la vacante y el perfil elegido.
    """
    score = 0.0
    matched_keywords = []

    bullet_text = bullet_data.get("text", "") or bullet_data.get("bullet", "")
    metric = bullet_data.get("metric", "")
    keywords = bullet_data.get("keywords", [])
    tracks = [t.lower() for t in bullet_data.get("tracks", [])]

    # 1. Coincidencia de Keywords explícitas ATS
    if keywords:
        k_count, k_matched = calculate_term_overlap(keywords, job_text_lower)
        matched_keywords.extend(k_matched)
        score += (k_count / max(1, len(keywords))) * 50.0

    # 2. Coincidencia con tracks aplicables del perfil mediante raíces
    if profile_tag:
        clean_tag = profile_tag.lower().replace(" ", "_")
        tag_roots = [tok[:4].lower() for tok in re.split(r'\W+', profile_tag) if len(tok) >= 4]
        for track in tracks:
            track_clean = track.lower().replace("_", " ")
            if clean_tag in track or track in clean_tag or any(r in track_clean for r in tag_roots):
                score += 25.0
                break

    # 3. Presencia de métrica cuantificable sólida
    if metric and any(char.isdigit() for char in metric):
        score += 15.0

    # 4. Coincidencia de texto directo de la viñeta con la descripción
    bullet_terms = extract_keywords_and_terms(bullet_text)
    if bullet_terms:
        b_count, b_matched = calculate_term_overlap(bullet_terms, job_text_lower)
        score += min(20.0, (b_count / max(1, len(bullet_terms))) * 25.0)
        for bm in b_matched:
            if len(bm) >= 4:
                matched_keywords.append(bm)

    return score, list(set(matched_keywords))


def match_and_tailor_cv(
    job_title: str,
    job_description: str,
    company_name: str = "",
    target_profile_override_id: Optional[str] = None,
    max_bullets_per_role: int = 3,
    master_data: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Motor principal de Matching y Selección Dinámica de CV.
    - Selecciona el mejor perfil objetivo o usa el indicado por el usuario.
    - Filtra y prioriza las mejores viñetas por experiencia laboral.
    - Cruza las habilidades y detecta matched vs missing keywords.
    - Calcula el ATS Match Score general.
    """
    if master_data is None:
        master_data = load_master_data()

    profile_section = master_data.get("profile", {})
    experiences_section = master_data.get("experiences", {})
    skills_section = master_data.get("skills", {})

    full_job_text = f"{job_title}\n{company_name}\n{job_description}"
    job_text_lower = full_job_text.lower()
    job_tokens = set(extract_keywords_and_terms(full_job_text))

    # 1. Determinar Target Profile
    target_profiles = profile_section.get("target_profiles", [])
    chosen_profile = None

    if target_profile_override_id:
        for tp in target_profiles:
            if tp.get("id") == target_profile_override_id or str(tp.get("number")) == str(target_profile_override_id):
                chosen_profile = tp
                break

    if not chosen_profile:
        chosen_profile, _ = select_best_target_profile(full_job_text, target_profiles)

    profile_tag = chosen_profile.get("tag", "") if chosen_profile else ""

    # 2. Seleccionar Viñetas por Experiencia Agrupada
    grouped_exp = experiences_section.get("grouped", [])
    tailored_experiences = []
    all_matched_keywords = set()
    total_bullet_score = 0.0
    total_bullets_selected = 0

    for exp_group in grouped_exp:
        company = exp_group.get("company", "")
        role = exp_group.get("role", "")
        period = exp_group.get("period", "")
        raw_bullets = exp_group.get("bullets", [])

        # Puntuar cada viñeta
        scored_bullets = []
        for b in raw_bullets:
            b_score, b_matched = score_bullet(b, job_text_lower, profile_tag)
            all_matched_keywords.update(b_matched)
            scored_bullets.append((b_score, b))

        # Ordenar por mayor score
        scored_bullets.sort(key=lambda x: x[0], reverse=True)

        # Seleccionar hasta max_bullets_per_role (mínimo 1 si existen viñetas)
        limit = max(1, min(max_bullets_per_role, len(scored_bullets)))
        selected = [item[1] for item in scored_bullets[:limit]]
        selected_scores = [item[0] for item in scored_bullets[:limit]]

        if selected_scores:
            total_bullet_score += sum(selected_scores) / len(selected_scores)
            total_bullets_selected += 1

        tailored_experiences.append({
            "company": company,
            "role": role,
            "period": period,
            "selected_bullets": selected
        })

    # 3. Match de Habilidades y Clasificación
    skills_items = skills_section.get("items", [])
    skills_by_cat = {}
    candidate_skill_names = []

    for sk in skills_items:
        sk_name = sk.get("skill", "")
        cat = sk.get("category", "General")
        level = sk.get("level", "")
        tags = sk.get("tags", [])

        candidate_skill_names.append(sk_name)
        
        # Verificar coincidencia con la vacante
        is_matched = False
        terms_to_check = [sk_name] + tags
        overlap_count, matched_terms = calculate_term_overlap(terms_to_check, job_text_lower)
        if overlap_count > 0:
            is_matched = True
            all_matched_keywords.update(matched_terms)

        if cat not in skills_by_cat:
            skills_by_cat[cat] = []

        skills_by_cat[cat].append({
            "skill": sk_name,
            "level": level,
            "matched": is_matched,
            "tags": tags
        })

    # Ordenar habilidades dentro de cada categoría (matched primero)
    for cat in skills_by_cat:
        skills_by_cat[cat].sort(key=lambda x: (not x["matched"], x["level"] != "Experto", x["skill"]))

    # 4. Detección de Missing Keywords
    # Palabras técnicas comunes que aparecen en el job pero no están cubiertas por candidate_skill_names ni master keywords
    master_known_terms = set()
    for item in skills_items:
        master_known_terms.add(item.get("skill", "").lower())
        for tag in item.get("tags", []):
            master_known_terms.add(tag.lower())

    for item in experiences_section.get("items", []):
        for kw in item.get("keywords", []):
            master_known_terms.add(kw.lower())

    missing_keywords = []
    for token in job_tokens:
        token_lower = token.lower()
        if len(token_lower) >= 4 and not any(token_lower in known or known in token_lower for known in master_known_terms):
            # Solo añadir si parece un término técnico relevante
            if any(char.isupper() for char in token) or any(t in token_lower for t in ["cloud", "data", "ml", "ai", "risk", "lake", "sql", "api", "flow"]):
                missing_keywords.append(token)

    missing_keywords = list(set(missing_keywords))[:10]

    # 5. Cálculo del ATS Match Score final (0 - 100%)
    title_affinity = compute_title_affinity(job_title, chosen_profile.get("title", ""), chosen_profile.get("tag", ""))
    matched_count = len(all_matched_keywords)

    # Track alignment del perfil frente a empresa y vacante
    p_toks = get_expanded_tokens(chosen_profile.get("title", "")).union(get_expanded_tokens(chosen_profile.get("tag", "")))
    j_toks = get_expanded_tokens(f"{job_title} {job_description} {company_name}")
    track_overlap = len(p_toks.intersection(j_toks))
    track_score = min(100.0, track_overlap * 25.0)

    if len(job_description.strip()) < 50:
        # Para vacantes con descripción breve o solo título extraído del portal
        k_score = min(100.0, matched_count * 25.0 + 50.0) if matched_count > 0 else 50.0
        final_score = 0.50 * title_affinity + 0.30 * track_score + 0.20 * k_score
    else:
        k_score = min(100.0, matched_count * 15.0)
        exp_score = min(100.0, (total_bullet_score / max(1, total_bullets_selected)) * 1.5) if total_bullets_selected else 50.0
        final_score = 0.35 * title_affinity + 0.35 * k_score + 0.15 * track_score + 0.15 * exp_score

    final_score = round(max(20.0, min(99.0, final_score)), 1)
    sal_info = estimate_job_salary(job_title, company_name, job_description)

    result = {
        "job_title": job_title,
        "company_name": company_name,
        "ats_score": final_score,
        "chosen_profile": chosen_profile,
        "contact_info": profile_section.get("contact_info", {}),
        "education": profile_section.get("education", []),
        "certifications": profile_section.get("certifications", []),
        "tailored_experiences": tailored_experiences,
        "skills_by_category": skills_by_cat,
        "matched_keywords": sorted(list(all_matched_keywords)),
        "missing_keywords": sorted(missing_keywords),
        "salary_info": sal_info,
        "seniority_level": sal_info["seniority_label"],
        "seniority_warning": sal_info["overqualification_warning"],
        "is_overqualified": bool(sal_info["overqualification_warning"])
    }

    if job_id:
        try:
            save_ats_evaluation_db(
                job_id=job_id,
                target_profile_title=chosen_profile.get("title", ""),
                ats_score=final_score,
                matched_keywords=result["matched_keywords"],
                missing_keywords=result["missing_keywords"]
            )
        except Exception as e:
            print(f"⚠️ No se pudo guardar evaluación ATS en DB ({e})")

    return result


if __name__ == "__main__":
    # Test básico de ejecución
    master = load_master_data()
    sample_job = """
    Líder de Riesgo Cuantitativo / Portfolio Risk Analyst
    Buscamos profesional con experiencia en modelado de riesgo financiero (VaR, CVaR),
    simulaciones de Monte Carlo, PySpark en Databricks y cumplimiento regulatorio CONSAR.
    Conocimientos sólidos en Python, FinOps y arquitectura Medallion.
    """
    res = match_and_tailor_cv("Senior Quant Risk Lead", sample_job, "Institución Financiera")
    print(f"✅ Match completado:")
    print(f"   - ATS Score: {res['ats_score']}%")
    print(f"   - Perfil elegido: {res['chosen_profile'].get('title')}")
    print(f"   - Keywords detectadas: {res['matched_keywords'][:8]}")
    print(f"   - Roles de experiencia con viñetas: {len(res['tailored_experiences'])}")
