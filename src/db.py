"""
db.py
Gestor de Base de Datos Relacional Local SQLite para el Motor de Empleo.
Cumple con la regla de CERO HARDCODE:
- Gestiona el catálogo de vacantes extraídas (leads) con coordenadas y ubicaciones normalizadas.
- Gestiona la ficha de Inteligencia Empresarial (companies): sector, tamaño, crecimiento, tech stack.
- Gestiona el ciclo de vida (job_history), auditoría de cambios (job_status_log) y caché de scoring (ats_evaluations).
"""

import os
import json
import sqlite3
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from geo_catalog import normalize_location, detect_modality
from company_intel import enrich_company_profile
from salary_estimator import estimate_job_salary


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "jobs.db"
LEADS_JSON = DATA_DIR / "job_leads.json"
HISTORY_JSON = DATA_DIR / "history.json"


def get_connection() -> sqlite3.Connection:
    """Devuelve una conexión a la base de datos SQLite con row_factory configurado"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Inicializa el esquema de base de datos relacional y sus índices"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Tabla de Empresas (Company Intelligence)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            company_name TEXT PRIMARY KEY,
            sector TEXT,
            company_size TEXT,
            growth_stage TEXT,
            tech_stack TEXT,
            headquarters TEXT,
            description TEXT,
            is_verified INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 2. Tabla de Vacantes (Leads)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            job_url TEXT,
            description TEXT,
            date_posted TEXT,
            source TEXT DEFAULT 'web',
            search_term TEXT,
            normalized_location TEXT,
            state TEXT,
            city TEXT,
            latitude REAL,
            longitude REAL,
            is_remote INTEGER DEFAULT 0,
            modality TEXT DEFAULT 'no_especificado',
            salary_min REAL,
            salary_max REAL,
            salary_currency TEXT DEFAULT 'MXN',
            salary_display TEXT,
            seniority_level TEXT,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Asegurar columnas nuevas en leads si la tabla ya existía
        cursor.execute("PRAGMA table_info(leads)")
        existing_cols = [r["name"] for r in cursor.fetchall()]
        for col, col_type in [
            ("normalized_location", "TEXT"),
            ("state", "TEXT"),
            ("city", "TEXT"),
            ("latitude", "REAL"),
            ("longitude", "REAL"),
            ("is_remote", "INTEGER DEFAULT 0"),
            ("modality", "TEXT DEFAULT 'no_especificado'"),
            ("salary_min", "REAL"),
            ("salary_max", "REAL"),
            ("salary_currency", "TEXT DEFAULT 'MXN'"),
            ("salary_display", "TEXT"),
            ("seniority_level", "TEXT")
        ]:
            if col not in existing_cols:
                cursor.execute(f"ALTER TABLE leads ADD COLUMN {col} {col_type}")

        # 3. Tabla de Estado y Postulación (Job History)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_history (
            job_id TEXT PRIMARY KEY,
            status TEXT NOT NULL CHECK (status IN ('nueva', 'revisada', 'cv_generado', 'aplicada', 'descartada')),
            cv_pdf_path TEXT,
            cv_md_path TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES leads(id) ON DELETE CASCADE
        )
        """)

        # 4. Tabla de Auditoría / Línea de Tiempo (Status Log)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_status_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            status TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES leads(id) ON DELETE CASCADE
        )
        """)

        # 5. Tabla de Evaluaciones de Scoring ATS (Cache)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ats_evaluations (
            job_id TEXT PRIMARY KEY,
            target_profile_title TEXT,
            ats_score REAL,
            matched_keywords TEXT,
            missing_keywords TEXT,
            evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES leads(id) ON DELETE CASCADE
        )
        """)

        # Índices para consultas de alto rendimiento
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_company ON leads(company)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_state ON leads(state)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_extracted_at ON leads(extracted_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_status ON job_history(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_log_job ON job_status_log(job_id, timestamp DESC)")

        conn.commit()

    # Enriquecer registros existentes que aún no tengan coordenadas o inteligencia empresarial
    enrich_existing_leads_db()


def save_company_intel(intel: Dict[str, Any]):
    """Guarda o actualiza la ficha de inteligencia de una empresa en SQLite"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO companies (company_name, sector, company_size, growth_stage, tech_stack, headquarters, description, is_verified, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(company_name) DO UPDATE SET
            sector=excluded.sector,
            company_size=excluded.company_size,
            growth_stage=excluded.growth_stage,
            tech_stack=excluded.tech_stack,
            headquarters=excluded.headquarters,
            description=excluded.description,
            is_verified=excluded.is_verified,
            updated_at=excluded.updated_at
        """, (
            intel.get("company_name", ""),
            intel.get("sector", ""),
            intel.get("size", ""),
            intel.get("growth_stage", ""),
            intel.get("tech_focus", ""),
            intel.get("headquarters", ""),
            intel.get("description", ""),
            1 if intel.get("is_verified") else 0,
            datetime.datetime.now().isoformat()
        ))
        conn.commit()


def enrich_existing_leads_db():
    """Recorre las vacantes en SQLite y enriquece coordenadas, modalidad, salarios y datos empresariales si faltan"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, company, location, description, latitude, modality, salary_display FROM leads")
        rows = cursor.fetchall()
        
        for r in rows:
            j_id = r["id"]
            title = r["title"]
            comp = r["company"]
            loc = r["location"]
            desc = r["description"] or ""
            current_lat = r["latitude"]
            current_mod = r["modality"]
            current_salary = r["salary_display"]

            # Si le falta salario, calcular estimación
            sal_data = None
            if not current_salary:
                sal_data = estimate_job_salary(title, comp, desc)

            # Si le falta latitud, ubicación o modalidad, calcular
            geo = None
            mod = None
            if current_lat is None or not current_mod or current_mod == "no_especificado":
                geo = normalize_location(loc)
                mod = detect_modality(desc, loc)

            if sal_data or geo or mod:
                norm_loc = geo["catalog_name"] if geo else None
                state = geo["state"] if geo else None
                city = geo["city"] if geo else None
                lat = geo["lat"] if geo else None
                lon = geo["lon"] if geo else None
                is_rem = (1 if (geo["is_remote"] or mod == "remoto") else 0) if (geo or mod) else None
                mod_val = mod if mod else None

                sal_min = sal_data["salary_min"] if sal_data else None
                sal_max = sal_data["salary_max"] if sal_data else None
                sal_curr = sal_data["salary_currency"] if sal_data else None
                sal_disp = sal_data["salary_display"] if sal_data else None
                sen_lvl = sal_data["seniority_label"] if sal_data else None

                cursor.execute("""
                UPDATE leads SET
                    normalized_location = COALESCE(?, normalized_location),
                    state = COALESCE(?, state),
                    city = COALESCE(?, city),
                    latitude = COALESCE(?, latitude),
                    longitude = COALESCE(?, longitude),
                    is_remote = COALESCE(?, is_remote),
                    modality = COALESCE(?, modality),
                    salary_min = COALESCE(?, salary_min),
                    salary_max = COALESCE(?, salary_max),
                    salary_currency = COALESCE(?, salary_currency),
                    salary_display = COALESCE(?, salary_display),
                    seniority_level = COALESCE(?, seniority_level)
                WHERE id = ?
                """, (
                    norm_loc, state, city, lat, lon, is_rem, mod_val,
                    sal_min, sal_max, sal_curr, sal_disp, sen_lvl,
                    j_id
                ))

            # Enriquecer ficha empresarial si no está registrada
            cursor.execute("SELECT company_name FROM companies WHERE company_name = ?", (comp,))
            if not cursor.fetchone():
                c_info = enrich_company_profile(comp, desc)
                save_company_intel(c_info)

        conn.commit()


def upsert_lead(lead_dict: Dict[str, Any]) -> str:
    """Inserta o actualiza una vacante en SQLite con normalización geoespacial, modalidad, salarios y empresa"""
    init_db()
    j_id = lead_dict.get("id")
    now_str = datetime.datetime.now().isoformat()
    raw_loc = lead_dict.get("location", "")
    comp_name = lead_dict.get("company", "Empresa Confidencial")
    desc = lead_dict.get("description", "")
    title = lead_dict.get("title", "")

    # Normalizar ubicación y coordenadas
    geo = normalize_location(raw_loc)

    # Determinar modalidad
    modality = lead_dict.get("modality")
    if not modality or modality == "no_especificado":
        modality = detect_modality(desc, raw_loc)

    # Estimar o extraer salario
    sal_data = estimate_job_salary(title, comp_name, desc)
    sal_min = lead_dict.get("salary_min") or sal_data["salary_min"]
    sal_max = lead_dict.get("salary_max") or sal_data["salary_max"]
    sal_curr = lead_dict.get("salary_currency") or sal_data["salary_currency"]
    sal_disp = lead_dict.get("salary_display") or sal_data["salary_display"]
    sen_lvl = lead_dict.get("seniority_level") or sal_data["seniority_label"]

    # Enriquecer empresa
    c_info = enrich_company_profile(comp_name, desc)
    save_company_intel(c_info)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO leads (
            id, title, company, location, job_url, description, 
            date_posted, source, search_term, normalized_location,
            state, city, latitude, longitude, is_remote, modality,
            salary_min, salary_max, salary_currency, salary_display, seniority_level,
            extracted_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            company=excluded.company,
            location=excluded.location,
            job_url=excluded.job_url,
            description=excluded.description,
            date_posted=excluded.date_posted,
            normalized_location=excluded.normalized_location,
            state=excluded.state,
            city=excluded.city,
            latitude=excluded.latitude,
            longitude=excluded.longitude,
            is_remote=excluded.is_remote,
            modality=excluded.modality,
            salary_min=excluded.salary_min,
            salary_max=excluded.salary_max,
            salary_currency=excluded.salary_currency,
            salary_display=excluded.salary_display,
            seniority_level=excluded.seniority_level
        """, (
            j_id,
            title,
            comp_name,
            raw_loc,
            lead_dict.get("job_url", ""),
            desc,
            lead_dict.get("date_posted", ""),
            lead_dict.get("source", "web"),
            lead_dict.get("search_term", ""),
            geo["catalog_name"],
            geo["state"],
            geo["city"],
            geo["lat"],
            geo["lon"],
            1 if (geo["is_remote"] or modality == "remoto") else 0,
            modality,
            sal_min,
            sal_max,
            sal_curr,
            sal_disp,
            sen_lvl,
            lead_dict.get("extracted_at", now_str)
        ))

        # Crear registro en history si no existe
        cursor.execute("""
        INSERT OR IGNORE INTO job_history (job_id, status, created_at, updated_at)
        VALUES (?, 'nueva', ?, ?)
        """, (j_id, now_str, now_str))

        conn.commit()
    return j_id


def get_leads(
    status_filter: Optional[str] = None,
    search_query: Optional[str] = None,
    state_filter: Optional[str] = None,
    city_filter: Optional[str] = None,
    modality_filter: Optional[str] = None,
    min_score: Optional[float] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = 0,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Obtiene las vacantes combinando datos de leads, job_history, companies y ats_evaluations
    con filtros SQL eficientes (estado, búsqueda, ubicación/región, modalidad y score mínimo ATS).
    """
    init_db()
    query = """
    SELECT 
        l.id, l.title, l.company, l.location, l.job_url, l.description, 
        l.date_posted, l.source, l.search_term, l.extracted_at,
        l.normalized_location, l.state, l.city, l.latitude, l.longitude, l.is_remote,
        COALESCE(l.modality, 'no_especificado') AS modality,
        l.salary_min, l.salary_max, l.salary_currency, l.salary_display, l.seniority_level,
        COALESCE(h.status, 'nueva') AS status,
        h.cv_pdf_path, h.cv_md_path, h.updated_at AS history_updated_at,
        e.ats_score, e.target_profile_title,
        c.sector AS company_sector,
        c.company_size AS company_size,
        c.growth_stage AS company_growth,
        c.tech_stack AS company_tech,
        c.headquarters AS company_hq,
        c.description AS company_desc,
        c.is_verified AS company_verified
    FROM leads l
    LEFT JOIN job_history h ON l.id = h.job_id
    LEFT JOIN ats_evaluations e ON l.id = e.job_id
    LEFT JOIN companies c ON l.company = c.company_name
    WHERE 1=1
    """
    params = []

    if status_filter and status_filter.lower() != "todos":
        query += " AND COALESCE(h.status, 'nueva') = ?"
        params.append(status_filter.lower())

    if state_filter and state_filter.lower() != "todos los estados":
        query += " AND l.state = ?"
        params.append(state_filter)

    if city_filter and city_filter.strip() and city_filter.lower() not in ["todas", "todas las ubicaciones"]:
        cf_clean = city_filter.strip()
        cf_lower = cf_clean.lower()
        if "cdmx y valle de toluca" in cf_lower:
            query += " AND (l.state IN ('Ciudad de México', 'Estado de México') OR l.normalized_location LIKE '%CDMX%' OR l.normalized_location LIKE '%Toluca%')"
        elif "toda la cdmx" in cf_lower or "ciudad de méxico" in cf_lower:
            query += " AND (l.state = 'Ciudad de México' OR l.normalized_location LIKE '%CDMX%' OR l.normalized_location LIKE '%Ciudad de México%')"
        elif "valle de toluca" in cf_lower or "toluca" in cf_lower:
            query += " AND (l.normalized_location LIKE '%Toluca%' OR l.city IN ('Toluca', 'Metepec', 'Lerma', 'San Mateo Atenco', 'Zinacantepec', 'Ocoyoacac'))"
        elif "toda la república" in cf_lower or "toda la republica" in cf_lower:
            # Abarca cualquier estado nacional
            pass
        else:
            query += " AND l.normalized_location = ?"
            params.append(cf_clean)

    if modality_filter and modality_filter.strip() and modality_filter.lower() not in ["todas", "todas las modalidades", "todos"]:
        mf_lower = modality_filter.strip().lower()
        if "híbrido y remoto" in mf_lower or "hibrido y remoto" in mf_lower or "remoto_hibrido" in mf_lower:
            query += " AND (l.modality IN ('remoto', 'hibrido') OR l.is_remote = 1)"
        elif "solo remoto" in mf_lower or mf_lower == "remoto":
            query += " AND (l.modality = 'remoto' OR l.is_remote = 1)"
        elif "solo híbrido" in mf_lower or "solo hibrido" in mf_lower or mf_lower == "hibrido":
            query += " AND l.modality = 'hibrido'"
        elif "presencial" in mf_lower:
            query += " AND (l.modality = 'presencial' OR (l.modality = 'no_especificado' AND l.is_remote = 0))"

    if min_score is not None and min_score > 0:
        query += " AND e.ats_score >= ?"
        params.append(min_score)

    if search_query and search_query.strip():
        term = f"%{search_query.strip().lower()}%"
        query += " AND (LOWER(l.title) LIKE ? OR LOWER(l.company) LIKE ? OR LOWER(l.description) LIKE ? OR LOWER(l.normalized_location) LIKE ?)"
        params.extend([term, term, term, term])

    query += " ORDER BY l.extracted_at DESC"

    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset or 0])

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_lead_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    """Obtiene una vacante específica por su ID con datos de empresa, modalidad y coordenadas"""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT 
            l.id, l.title, l.company, l.location, l.job_url, l.description, 
            l.date_posted, l.source, l.search_term, l.extracted_at,
            l.normalized_location, l.state, l.city, l.latitude, l.longitude, l.is_remote,
            COALESCE(l.modality, 'no_especificado') AS modality,
            l.salary_min, l.salary_max, l.salary_currency, l.salary_display, l.seniority_level,
            COALESCE(h.status, 'nueva') AS status,
            h.cv_pdf_path, h.cv_md_path, h.updated_at AS history_updated_at,
            e.ats_score, e.target_profile_title,
            c.sector AS company_sector,
            c.company_size AS company_size,
            c.growth_stage AS company_growth,
            c.tech_stack AS company_tech,
            c.headquarters AS company_hq,
            c.description AS company_desc
        FROM leads l
        LEFT JOIN job_history h ON l.id = h.job_id
        LEFT JOIN ats_evaluations e ON l.id = e.job_id
        LEFT JOIN companies c ON l.company = c.company_name
        WHERE l.id = ?
        """, (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_job_status_db(job_id: str, status: str, metadata: Optional[Dict[str, Any]] = None):
    """Actualiza el estado de una vacante y registra el cambio en la tabla de auditoría"""
    init_db()
    now_str = datetime.datetime.now().isoformat()
    cv_pdf = metadata.get("cv_pdf", "") if metadata else ""
    cv_md = metadata.get("cv_md", "") if metadata else ""
    notes = metadata.get("notes", "") if metadata else ""

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO job_history (job_id, status, cv_pdf_path, cv_md_path, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
            status=excluded.status,
            cv_pdf_path = CASE WHEN excluded.cv_pdf_path != '' THEN excluded.cv_pdf_path ELSE job_history.cv_pdf_path END,
            cv_md_path = CASE WHEN excluded.cv_md_path != '' THEN excluded.cv_md_path ELSE job_history.cv_md_path END,
            notes = CASE WHEN excluded.notes != '' THEN excluded.notes ELSE job_history.notes END,
            updated_at = excluded.updated_at
        """, (job_id, status, cv_pdf, cv_md, notes, now_str, now_str))

        cursor.execute("""
        INSERT INTO job_status_log (job_id, status, timestamp)
        VALUES (?, ?, ?)
        """, (job_id, status, now_str))

        conn.commit()


def save_ats_evaluation_db(
    job_id: str,
    target_profile_title: str,
    ats_score: float,
    matched_keywords: List[str],
    missing_keywords: List[str]
):
    """Guarda o actualiza la evaluación de compatibilidad ATS en la base de datos"""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO ats_evaluations (job_id, target_profile_title, ats_score, matched_keywords, missing_keywords, evaluated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
            target_profile_title=excluded.target_profile_title,
            ats_score=excluded.ats_score,
            matched_keywords=excluded.matched_keywords,
            missing_keywords=excluded.missing_keywords,
            evaluated_at=excluded.evaluated_at
        """, (
            job_id,
            target_profile_title,
            ats_score,
            json.dumps(matched_keywords, ensure_ascii=False),
            json.dumps(missing_keywords, ensure_ascii=False),
            datetime.datetime.now().isoformat()
        ))
        conn.commit()


def get_status_counts() -> Dict[str, int]:
    """Obtiene los conteos agrupados de vacantes por estado mediante una sola consulta SQL agregada"""
    init_db()
    counts = {"nueva": 0, "revisada": 0, "cv_generado": 0, "aplicada": 0, "descartada": 0, "total": 0}
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT COALESCE(h.status, 'nueva') AS st, COUNT(*) as cnt
        FROM leads l
        LEFT JOIN job_history h ON l.id = h.job_id
        GROUP BY st
        """)
        rows = cursor.fetchall()
        total = 0
        for r in rows:
            st_name = r["st"]
            cnt = r["cnt"]
            counts[st_name] = cnt
            total += cnt
        counts["total"] = total
    return counts


def get_distinct_db_locations() -> List[str]:
    """Devuelve las ubicaciones normalizadas únicas presentes en las vacantes activas"""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT normalized_location FROM leads WHERE normalized_location IS NOT NULL ORDER BY normalized_location")
        rows = cursor.fetchall()
        return [r[0] for r in rows if r[0]]


def get_distinct_db_states() -> List[str]:
    """Devuelve los estados únicos presentes en las vacantes activas"""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT state FROM leads WHERE state IS NOT NULL ORDER BY state")
        rows = cursor.fetchall()
        return [r[0] for r in rows if r[0]]


def get_audit_log(limit: int = 50) -> List[Dict[str, Any]]:
    """Obtiene el log de cambios de estado más recientes con título y empresa"""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT 
            sl.id, sl.job_id, sl.status, sl.timestamp,
            l.title, l.company
        FROM job_status_log sl
        JOIN leads l ON sl.job_id = l.id
        ORDER BY sl.timestamp DESC
        LIMIT ?
        """, (limit,))
        return [dict(r) for r in cursor.fetchall()]


if __name__ == "__main__":
    init_db()
    stats = get_status_counts()
    states = get_distinct_db_states()
    locs = get_distinct_db_locations()
    leads = get_leads()
    print(f"✅ SQLite jobs.db inicializado con Geo e Inteligencia Empresarial")
    print(f"📊 Estadísticas: {stats}")
    print(f"📍 Estados detectados en BD: {states}")
    print(f"🏢 Total empresas con inteligencia: {len(leads)}")
    if leads:
        sample = leads[0]
        print(f"  Ejemplo: {sample['company']} -> Sector: {sample.get('company_sector')} | Ubicación: {sample.get('normalized_location')} ({sample.get('latitude')}, {sample.get('longitude')})")
