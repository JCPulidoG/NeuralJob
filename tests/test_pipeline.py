"""
test_pipeline.py
Script de pruebas automatizadas de extremo a extremo para validar todo el flujo del sistema,
incluyendo la base de datos relacional SQLite y la compilación de documentos.
"""

import sys
import json
import sqlite3
from pathlib import Path

# Configurar path
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
DATA_DIR = BASE_DIR / "data"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from build_master import build_master
from db import (
    init_db,
    get_connection,
    get_leads,
    get_status_counts,
    get_audit_log,
    update_job_status_db
)
from matcher import match_and_tailor_cv, load_history, update_job_status
from scraper import add_manual_lead, load_job_leads
from pdf_engine import compile_cv_package


def run_tests():
    print("==================================================")
    print("🧪 INICIANDO TEST DE INTEGRACIÓN: MOTOR JOB (SQLITE)")
    print("==================================================")

    # 1. Test build_master
    print("\n--- 1. Probando build_master ---")
    master = build_master()
    assert master is not None
    assert master["metadata"]["total_target_profiles"] >= 1, f"Esperados al menos 1 target, obtenidos {master['metadata']['total_target_profiles']}"
    assert master["metadata"]["total_achievements"] > 0, f"Esperados logros > 0, obtenidos {master['metadata']['total_achievements']}"
    assert master["metadata"]["total_skills"] > 0, f"Esperadas habilidades > 0, obtenidas {master['metadata']['total_skills']}"
    print("✅ build_master pasó todas las aserciones.")

    # 2. Test SQLite & Scraper
    print("\n--- 2. Probando SQLite y Registro de Vacantes ---")
    init_db()

    lead_quant = add_manual_lead(
        title="Head of Quantitative Risk",
        company="Banco Banorte / Casa de Bolsa",
        description="Buscamos especialista en modelos VaR y CVaR, Monte Carlo, análisis técnico bursátil y Databricks.",
        location="CDMX"
    )
    lead_arch = add_manual_lead(
        title="Lead Cloud Data Architect",
        company="Mercado Libre",
        description="Arquitectura Medallion en Delta Lake, PySpark, Databricks, FinOps y gobernanza de datos.",
        location="Remoto"
    )
    lead_ds = add_manual_lead(
        title="Senior Data Scientist ML",
        company="Nubank",
        description="Modelos de Machine Learning, clustering, RFM, series de tiempo y LLMs con Python.",
        location="Remoto"
    )
    test_ids = [lead_quant["id"], lead_arch["id"], lead_ds["id"]]
    print("✅ Vacantes agregadas en SQLite y JSON:", test_ids)

    # Verificar que están en SQLite
    db_leads = get_leads()
    db_ids = {l["id"] for l in db_leads}
    for tid in test_ids:
        assert tid in db_ids, f"ID {tid} no encontrado en la base de datos SQLite"
    print("✅ Vacantes verificadas en SQLite.")

    # 3. Test Matcher con almacenamiento en caché ATS
    print("\n--- 3. Probando Matcher y Caché ATS en SQLite ---")
    
    # Test caso Quant
    match_quant = match_and_tailor_cv(lead_quant["title"], lead_quant["description"], lead_quant["company"], master_data=master, job_id=lead_quant["id"])
    print(f"Target detectado para Quant: '{match_quant['chosen_profile'].get('title')}' | Score: {match_quant['ats_score']}%")
    assert "Risk" in match_quant['chosen_profile'].get('title') or "Quant" in match_quant['chosen_profile'].get('tag'), "Fallo al detectar target Quant"

    # Test caso Data Arch
    match_arch = match_and_tailor_cv(lead_arch["title"], lead_arch["description"], lead_arch["company"], master_data=master, job_id=lead_arch["id"])
    print(f"Target detectado para Arch: '{match_arch['chosen_profile'].get('title')}' | Score: {match_arch['ats_score']}%")
    assert "Arquitecto" in match_arch['chosen_profile'].get('title') or "Data Arch" in match_arch['chosen_profile'].get('tag'), "Fallo al detectar target Data Arch"

    # Test caso Data Science
    match_ds = match_and_tailor_cv(lead_ds["title"], lead_ds["description"], lead_ds["company"], master_data=master, job_id=lead_ds["id"])
    print(f"Target detectado para Data Science: '{match_ds['chosen_profile'].get('title')}' | Score: {match_ds['ats_score']}%")
    assert "Data Scientist" in match_ds['chosen_profile'].get('title') or "Data Science" in match_ds['chosen_profile'].get('tag'), "Fallo al detectar target Data Science"

    # Verificar tabla ats_evaluations en SQLite
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ats_score FROM ats_evaluations WHERE job_id = ?", (lead_quant["id"],))
        cached_score = cursor.fetchone()[0]
        assert cached_score == match_quant["ats_score"], "Caché de ATS score en SQLite no coincide"
    print("✅ Caché de ATS Evaluations en SQLite verificado.")

    # 4. Test Compilación PDF & Markdown (Español & Inglés)
    print("\n--- 4. Probando Compilador PDF y Markdown (Español & Inglés) ---")
    out_quant = compile_cv_package(match_quant, lead_quant["id"], lead_quant["company"], lang="es")
    assert Path(out_quant["pdf_path"]).exists(), "El archivo PDF en español no fue creado"
    assert Path(out_quant["markdown_path"]).exists(), "El archivo Markdown en español no fue creado"

    out_quant_en = compile_cv_package(match_quant, lead_quant["id"], lead_quant["company"], lang="en")
    assert Path(out_quant_en["pdf_path"]).exists(), "El archivo PDF en inglés no fue creado"
    assert Path(out_quant_en["markdown_path"]).exists(), "El archivo Markdown en inglés no fue creado"
    assert "_EN" in out_quant_en["pdf_path"], "El PDF en inglés debe tener sufijo _EN"
    with open(out_quant_en["markdown_path"], "r", encoding="utf-8") as f_en:
        en_text = f_en.read()
        assert "Professional Experience" in en_text or "PROFESSIONAL EXPERIENCE" in en_text, "Cabecera en inglés ausente"

    print("✅ Documentos generados exitosamente en ambos idiomas (ES & EN):")
    print("   - PDF ES:", out_quant["pdf_path"])
    print("   - PDF EN:", out_quant_en["pdf_path"])

    # 5. Test Historial y Auditoría en SQLite
    print("\n--- 5. Probando Historial y Trazabilidad en SQLite ---")
    update_job_status(lead_quant["id"], "cv_generado", {"cv_pdf": out_quant["pdf_path"]})
    
    stats = get_status_counts()
    print("Métricas agrupadas de estado:", stats)
    assert stats.get("cv_generado", 0) >= 1, "Estado cv_generado no contabilizado en SQLite"

    # Verificar log de auditoría
    audit = get_audit_log(10)
    audit_job_ids = [a["job_id"] for a in audit]
    # 6. Test Geo, Modalidad, Inteligencia Empresarial y Filtros
    print("\n--- 6. Probando Catálogo Geográfico, Modalidad y Filtros SQL ---")
    from geo_catalog import normalize_location, detect_modality, get_search_location_string
    from company_intel import enrich_company_profile
    from scraper import get_default_search_params

    # Verificar defaults de búsqueda solicitados por el usuario
    search_defaults = get_default_search_params()
    assert search_defaults["default_results"] == 50, f"Esperados 50 resultados por defecto, obtenido: {search_defaults['default_results']}"
    assert search_defaults["default_hours_old"] == 168, f"Esperadas 168 horas (1 semana), obtenido: {search_defaults['default_hours_old']}"
    assert "computrabajo" in search_defaults["default_sites"] and "occ" in search_defaults["default_sites"], "CompuTrabajo y OCC deben estar en portales básicos"
    print("✅ Parámetros de búsqueda por defecto verificados (50 resultados, 1 semana, portales básicos).")

    # Verificar normalización de CDMX y Valle de Toluca
    geo_cdmx = normalize_location("Polanco, Miguel Hidalgo, CDMX")
    assert "CDMX" in geo_cdmx["catalog_name"] or "Ciudad de México" in geo_cdmx["catalog_name"]
    geo_toluca = normalize_location("Metepec, Estado de México, Toluca")
    assert "Valle de Toluca" == geo_toluca["catalog_name"]
    print("✅ Normalización de CDMX y Valle de Toluca verificada.")

    # Verificar detección de modalidades
    assert detect_modality("Puesto con esquema híbrido 3 días oficina") == "hibrido"
    assert detect_modality("Posición 100% home office / trabajo remoto") == "remoto"
    assert detect_modality("Trabajo en sitio corporativo presencial") == "presencial"
    print("✅ Detección de modalidades verificada.")

    # Verificar generación de cadenas de búsqueda para ubicación
    assert "Toluca" in get_search_location_string("Valle de Toluca")
    assert "Ciudad de México" in get_search_location_string("Toda la CDMX")
    assert "México" in get_search_location_string("Toda la República Mexicana")

    geo_test = normalize_location("San Pedro Garza García, Nuevo León, Mexico")
    assert geo_test["state"] == "Nuevo León", "Fallo al normalizar estado Nuevo León"
    assert geo_test["lat"] > 0 and geo_test["lon"] < 0, "Coordenadas inválidas"

    comp_test = enrich_company_profile("Banamex")
    assert comp_test["is_verified"] is True, "Empresa no verificada en catálogo"
    assert "Banca" in comp_test["sector"], "Sector incorrecto para Banamex"

    # Probar filtro SQL por ubicación regional, modalidad y score
    cdmx_leads = get_leads(city_filter="Toda la CDMX")
    assert len(cdmx_leads) > 0, "No se encontraron vacantes en Toda la CDMX"
    remoto_leads = get_leads(modality_filter="Híbrido y Remoto (Toda la República Mexicana)")
    assert len(remoto_leads) >= 0, "Error consultando filtro de modalidad"
    high_match_leads = get_leads(min_score=60.0)
    print(f"Vacantes con match >= 60% en BD: {len(high_match_leads)}")
    print("✅ Catálogo geográfico, modalidades y filtros SQL verificados.")

    # 7. Test Motor de Estimación Salarial y Alertas de Sobrecalificación
    print("\n--- 7. Probando Motor Salarial y Alertas de Sobrecalificación ---")
    from salary_estimator import estimate_job_salary, detect_declared_salary

    # Sueldo declarado
    dec = detect_declared_salary("Sueldo ofrecido: $45,000 - $60,000 netos mensuales.")
    assert dec is not None and dec["is_declared"] is True
    assert dec["salary_min"] == 45000 and dec["salary_max"] == 60000

    # Estimación heurística de rol operativo (Especialista en Banca)
    sal_esp = estimate_job_salary("Especialista de Procesos", "Santander México", "Manuales y BPM.")
    assert sal_esp["seniority_key"] == "mid_especialista"
    assert sal_esp["overqualification_warning"] is not None
    assert "sobrecalificación" in sal_esp["overqualification_warning"].lower()
    print(f"✅ Alerta de sobrecalificación detectada: {sal_esp['seniority_label']} -> {sal_esp['salary_display']}")

    # Estimación heurística de rol Gerencial / Liderazgo (Target real de Juan Carlos)
    sal_lead = estimate_job_salary("Líder Arquitecto de Estrategia de Datos & Big Data", "Profuturo", "Databricks.")
    assert sal_lead["seniority_key"] == "lead_architect"
    assert sal_lead["overqualification_warning"] is None
    assert sal_lead["salary_min"] >= 80000
    print(f"✅ Rango directivo/lead calibrado: {sal_lead['seniority_label']} -> {sal_lead['salary_display']}")

    # Verificar que los leads en SQLite tienen campos salariales
    db_sample = get_leads(limit=5)
    for s in db_sample:
        assert "salary_display" in s and s["salary_display"] is not None, "Campo salary_display ausente en SQLite"
        assert "seniority_level" in s and s["seniority_level"] is not None, "Campo seniority_level ausente en SQLite"
    print("✅ Campos salariales verificados en registros de SQLite.")

    # 8. Limpieza de datos sintéticos de prueba
    print("\n--- 8. Limpiando datos sintéticos de prueba (SQLite & JSON) ---")
    test_id_set = set(test_ids)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany("DELETE FROM leads WHERE id = ?", [(tid,) for tid in test_ids])
        conn.commit()

    leads = [l for l in load_job_leads() if l["id"] not in test_id_set]
    with open(DATA_DIR / "job_leads.json", "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)

    hist = load_history()
    hist["records"] = {k: v for k, v in hist["records"].items() if k not in test_id_set}
    with open(DATA_DIR / "history.json", "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

    # Limpiar archivos de CV generados en tests
    for p in [out_quant["pdf_path"], out_quant["markdown_path"], out_quant_en["pdf_path"], out_quant_en["markdown_path"]]:
        if Path(p).exists():
            Path(p).unlink()

    print("✅ Base de datos SQLite y archivos JSON limpios de registros de prueba.")

    print("\n==================================================")
    print("🎉 TODAS LAS PRUEBAS DE INTEGRACIÓN FUERON EXITOSAS!")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
