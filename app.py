"""
app.py
Dashboard interactivo local para el Motor de Prospección de Empleo y Generador Dinámico de CV.
Cumple con la regla de CERO HARDCODE:
- Toda la información y perfiles se cargan dinámicamente desde cv_master.json / Motor Job.xlsx.
- Permite prospección en menos de 20 minutos al día.
- Genera y descarga CVs adaptados en formato Markdown y PDF ATS-friendly en 1 clic.
"""

import os
import sys
import json
import datetime
from pathlib import Path
import pandas as pd
import streamlit as st

# Asegurar que el directorio src está en sys.path
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = BASE_DIR / "outputs"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import importlib
import geo_catalog
importlib.reload(geo_catalog)
import company_intel
importlib.reload(company_intel)
import db
importlib.reload(db)
import matcher
importlib.reload(matcher)
import scraper
importlib.reload(scraper)

from build_master import build_master, find_excel_file
from matcher import (
    load_master_data,
    load_history,
    update_job_status,
    match_and_tailor_cv
)
from scraper import (
    load_job_leads,
    scrape_vacancies,
    add_manual_lead,
    get_default_search_params
)
from pdf_engine import compile_cv_package, generate_markdown, generate_pdf, sanitize_filename
from db import (
    init_db,
    get_leads,
    get_lead_by_id,
    update_job_status_db,
    get_status_counts,
    get_audit_log,
    DB_PATH
)
from geo_catalog import (
    get_catalog_options,
    get_states_options,
    SEARCH_LOCATION_PRESETS,
    get_search_location_string
)

# Inicializar esquema SQLite
init_db()


# Configuración de página
st.set_page_config(
    page_title="Motor Local de Empleo & Generador de CV",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados
st.markdown("""
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .job-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 18px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .badge-score-high {
        background-color: #DEF7EC;
        color: #03543F;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-score-mid {
        background-color: #FEF08A;
        color: #713F12;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .status-pill {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 500;
        text-transform: uppercase;
    }
    .status-nueva { background-color: #E0F2FE; color: #0369A1; }
    .status-revisada { background-color: #FEF3C7; color: #92400E; }
    .status-cv_generado { background-color: #EDE9FE; color: #6D28D9; }
    .status-aplicada { background-color: #DCFCE7; color: #15803D; }
    .status-descartada { background-color: #F3F4F6; color: #4B5563; }
    
    .badge-sector {
        background-color: #E0E7FF;
        color: #3730A3;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 600;
        display: inline-block;
        margin-right: 4px;
        margin-bottom: 4px;
    }
    .badge-size {
        background-color: #F3E8FF;
        color: #6B21A8;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 600;
        display: inline-block;
        margin-right: 4px;
        margin-bottom: 4px;
    }
    .badge-tech {
        background-color: #DCFCE7;
        color: #166534;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 600;
        display: inline-block;
        margin-right: 4px;
        margin-bottom: 4px;
    }
    .badge-growth {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 600;
        display: inline-block;
        margin-right: 4px;
        margin-bottom: 4px;
    }
    .company-intel-box {
        background-color: #F8FAFC;
        border-left: 3px solid #3B82F6;
        border-radius: 6px;
        padding: 10px 14px;
        margin: 10px 0;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)


# Función para recargar master en session_state
def get_current_master(force_rebuild: bool = False):
    if "master_data" not in st.session_state or force_rebuild:
        try:
            st.session_state["master_data"] = load_master_data(force_rebuild=force_rebuild)
        except Exception as e:
            st.error(f"Error al cargar la fuente canónica: {e}")
            st.session_state["master_data"] = {}
    return st.session_state["master_data"]


master_data = get_current_master()
history_data = load_history()
job_leads = load_job_leads()


# ==========================================
# SIDEBAR: Orquestación & Fuente Canónica
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/briefcase.png", width=64)
    st.title("Motor Job ATS")
    st.caption("Prospección y Generación de CV 100% Local")

    st.divider()

    # Estado de la fuente de verdad
    st.subheader("📁 Fuente Única de Verdad")
    excel_file = find_excel_file(DATA_DIR)
    json_file = DATA_DIR / "cv_master.json"
    template_file = DATA_DIR / "cv_master.template.json"

    if excel_file is not None and excel_file.exists():
        mod_time = datetime.datetime.fromtimestamp(excel_file.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        st.caption(f"**Fuente:** Excel (`{excel_file.name}`)\n\n**Modificado:** {mod_time}")
    elif json_file.exists():
        mod_time = datetime.datetime.fromtimestamp(json_file.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        st.caption(f"**Fuente:** JSON (`cv_master.json`)\n\n**Modificado:** {mod_time}")
    elif template_file.exists():
        st.caption(f"**Fuente:** Plantilla JSON (`cv_master.template.json`)")
    else:
        st.warning("⚠️ No se encontró archivo de perfil en data/")

    button_label = "🔄 Recompilar desde Excel" if excel_file else "🔄 Recargar Perfil Master (JSON)"
    if st.button(button_label, use_container_width=True):
        with st.spinner("Sincronizando perfil canónico..."):
            master_data = get_current_master(force_rebuild=True)
            st.success("cv_master.json sincronizado correctamente!")
            st.rerun()

    if st.button("🌐 Auto-Traducir Perfil (ESP ➔ ENG)", use_container_width=True, help="Traduce automáticamente los campos de tu perfil al inglés"):
        with st.spinner("Traduciendo perfil completo al inglés..."):
            try:
                from translator import translate_json_master
                target_file = json_file if json_file.exists() else template_file
                translate_json_master(target_file, json_file)
                get_current_master(force_rebuild=True)
                st.success("¡Perfil traducido al inglés y guardado en JSON!")
                st.rerun()
            except Exception as ex:
                st.error(f"Error al traducir: {ex}")

    meta = master_data.get("metadata", {})
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric("Logros", meta.get("total_achievements", 0))
    with col_m2:
        st.metric("Habilidades", meta.get("total_skills", 0))

    st.divider()

    # Estado de la Base de Datos SQLite
    st.subheader("💾 Base de Datos Local")
    db_counts = get_status_counts()
    st.caption(f"**Motor:** SQLite (`data/jobs.db`)\n\n**Total Vacantes:** {db_counts.get('total', 0)}")

    st.divider()

    # Contacto del usuario (Cero Hardcode: cargado del perfil)
    contact_dict = master_data.get("profile", {}).get("contact_info", {})
    user_name = next((v for k, v in contact_dict.items() if "nombre" in k.lower()), "Candidato")
    st.write(f"👤 **Candidato:** {user_name}")

    st.divider()
    st.caption("⚡ Operativa diaria: 20 min | Cero Hardcode")


# ==========================================
# CUERPO PRINCIPAL: TABS
# ==========================================
st.markdown('<div class="main-header">🎯 Motor de Prospección de Empleo & Generador de CV</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Flujo diario optimizado: Prospección multicanal, análisis de compatibilidad ATS y generación de CVs a la medida.</div>', unsafe_allow_html=True)

tab_prospeccion, tab_generador, tab_historial, tab_fuente = st.tabs([
    "🔍 1. Prospección & Leads",
    "📄 2. Generador Dinámico de CV",
    "📊 3. Historial & Postulaciones",
    "📚 4. Fuente Canónica (Excel)"
])


# -------------------------------------------------------------
# TAB 1: PROSPECCIÓN & LEADS
# -------------------------------------------------------------
with tab_prospeccion:
    # Estado de sesión para control de búsqueda manual (No buscar al arrancar)
    if "has_searched" not in st.session_state:
        st.session_state["has_searched"] = False

    default_params = get_default_search_params()
    available_profiles = [p.get("title", "") for p in master_data.get("profile", {}).get("target_profiles", [])]

    # PANEL DE BÚSQUEDA MANUAL
    st.markdown("### 🔍 Búsqueda y Prospección de Vacantes")
    st.caption("Configura tus parámetros de búsqueda y presiona el botón para iniciar la prospección multicanal manual.")

    with st.container():
        c_search1, c_search2, c_search3 = st.columns([2, 1.2, 1.2])
        with c_search1:
            query_choice = st.selectbox(
                "Término de Búsqueda (Target Profile):",
                options=available_profiles if available_profiles else ["Data Lead", "Quant Analyst"],
                index=0
            )
            auto_keyword = query_choice.split("|")[0].strip() if "|" in query_choice else query_choice
            custom_query = st.text_input(
                "Término para portales de empleo (auto-optimizado):",
                value=auto_keyword,
                help="Los portales (LinkedIn, Indeed, etc.) arrojan mejores resultados con términos precisos como 'Quantitative Risk' en vez del título compuesto del CV."
            )
            final_query = custom_query.strip() if custom_query.strip() else auto_keyword

        with c_search2:
            loc_preset = st.selectbox(
                "📍 Ubicación:",
                options=SEARCH_LOCATION_PRESETS,
                index=0,
                help="Incluye Toda la CDMX, Valle de Toluca (Toluca, Metepec, Lerma), zonas combinadas o República Mexicana"
            )
            custom_loc = ""
            if loc_preset == "Personalizada (escribir...)":
                custom_loc = st.text_input("Ubicación específica:", value="Ciudad de México")
            effective_location = get_search_location_string(loc_preset, custom_loc)

        with c_search3:
            modality_choice = st.selectbox(
                "💼 Modalidad:",
                options=[
                    "Híbrido y Remoto (Toda la República Mexicana)",
                    "Solo Remoto",
                    "Solo Híbrido",
                    "Presencial",
                    "Todas las modalidades"
                ],
                index=0,
                help="Filtra esquemas de trabajo remoto o híbrido en todo México o por plaza"
            )

        c_row2_1, c_row2_2, c_row2_3 = st.columns([2, 1.2, 1.2])
        with c_row2_1:
            portal_options = {
                "LinkedIn": "linkedin",
                "Indeed": "indeed",
                "Google Jobs": "google",
                "CompuTrabajo": "computrabajo",
                "OCC Mundial": "occ",
                "Adzuna (México)": "adzuna",
                "Glassdoor": "glassdoor"
            }
            portals_selected = st.multiselect(
                "🌐 Portales de Empleo:",
                options=list(portal_options.keys()),
                default=["LinkedIn", "Indeed", "Google Jobs", "CompuTrabajo", "OCC Mundial"],
                help="Portales básicos y agregadores integrados (Google Jobs indexa bolsas corporativas, OCC y CompuTrabajo)"
            )
            sites_selected = [portal_options[p] for p in portals_selected]

        with c_row2_2:
            num_results = st.slider("Resultados deseados:", min_value=10, max_value=100, value=50, step=5)

        with c_row2_3:
            hours_options = [
                (168, "1 semana (7 días)"),
                (72, "3 días (72 horas)"),
                (24, "24 horas (1 día)"),
                (336, "2 semanas (14 días)"),
                (720, "1 mes (30 días)")
            ]
            hours_old = st.selectbox(
                "🗓️ Antigüedad:",
                options=[h[0] for h in hours_options],
                index=0,  # 1 semana por defecto
                format_func=lambda x: dict(hours_options).get(x, f"{x} horas")
            )

        if st.button("🚀 Buscar Vacantes (Extracción Multicanal)", type="primary", use_container_width=True):
            with st.spinner(f"Buscando vacantes para '{final_query}' en '{loc_preset}' ({modality_choice}) en {portals_selected}..."):
                new_jobs = scrape_vacancies(
                    search_term=final_query,
                    location=loc_preset,
                    sites=sites_selected,
                    results_wanted=num_results,
                    hours_old=hours_old,
                    modality=modality_choice
                )
                st.session_state["has_searched"] = True
                st.session_state["target_profile_active"] = query_choice
                if new_jobs:
                    st.success(f"¡Se procesaron y registraron {len(new_jobs)} vacantes correctamente!")
                else:
                    st.info("Búsqueda completada. Si algún portal solicitó validación, puedes ingresar vacantes manualmente abajo o revisar las guardadas en BD.")
                st.rerun()

    # Entrada Manual Rápida
    with st.expander("➕ Pegar Vacante Manualmente (Desde LinkedIn, ATS, etc.)", expanded=False):
        with st.form("manual_lead_form"):
            c_m1, c_m2 = st.columns(2)
            with c_m1:
                man_title = st.text_input("Título de la Vacante *", placeholder="Ej: Senior Quantitative Risk Lead")
                man_company = st.text_input("Empresa *", placeholder="Ej: BlackRock / Actinver / Profuturo")
            with c_m2:
                man_url = st.text_input("URL de la Oferta", placeholder="https://...")
                man_loc = st.text_input("Ubicación", value="Toda la CDMX")
            
            c_m3, c_m4 = st.columns(2)
            with c_m3:
                man_mod = st.selectbox("Modalidad:", ["remoto", "hibrido", "presencial", "no_especificado"], index=1)
            with c_m4:
                st.caption("La modalidad se autodetecta también de la descripción si no se especifica.")

            man_desc = st.text_area("Descripción Completa de la Vacante (Requisitos y Responsabilidades) *", height=180)
            
            submitted = st.form_submit_button("💾 Guardar Vacante para Análisis", type="primary")
            if submitted:
                if not man_title or not man_desc:
                    st.error("Por favor ingresa al menos el título y la descripción de la vacante.")
                else:
                    new_lead = add_manual_lead(man_title, man_company, man_desc, man_url, man_loc, modality=man_mod)
                    st.success(f"Vacante guardada con ID: {new_lead['id']}")
                    st.session_state["selected_job_for_cv"] = new_lead["id"]
                    st.session_state["has_searched"] = True
                    st.rerun()

    st.divider()

    # ESTADO INICIAL O RENDERIZADO DE RESULTADOS
    if not st.session_state["has_searched"]:
        st.info("🎯 **Búsqueda manual en espera**: Al arrancar no se realiza ninguna búsqueda automática. Configura tus criterios arriba y haz clic en **'🚀 Buscar Vacantes (Extracción Multicanal)'**.")
        c_init1, c_init2 = st.columns([3, 1])
        with c_init1:
            st.write(f"💾 Hay **{db_counts.get('total', 0)}** vacantes almacenadas localmente en SQLite (`data/jobs.db`).")
        with c_init2:
            if st.button("📦 Ver vacantes guardadas en BD", use_container_width=True):
                st.session_state["has_searched"] = True
                st.rerun()
    else:
        c_res_t1, c_res_t2 = st.columns([4, 1])
        with c_res_t1:
            st.markdown("### 📋 Oportunidades Registradas (SQLite `jobs.db`)")
        with c_res_t2:
            if st.button("🔄 Ocultar / Nueva búsqueda", use_container_width=True):
                st.session_state["has_searched"] = False
                st.rerun()
        
        # 1. FILTROS AVANZADOS DE PROSPECCIÓN (Perfil Objetivo, Ubicaciones, Búsqueda, Modalidad, Estado y Score ATS)
        f_row1_col1, f_row1_col2, f_row1_col3, f_row1_col4 = st.columns([1.6, 1.6, 1.1, 1.1])
        with f_row1_col1:
            search_filter = st.text_input("🔎 Filtrar por título o empresa:", "")
        with f_row1_col2:
            default_p_idx = 0
            active_p = st.session_state.get("target_profile_active")
            if active_p in available_profiles:
                default_p_idx = available_profiles.index(active_p) + 1
            target_profile_filter = st.selectbox(
                "🎯 Filtrar por Perfil Objetivo:",
                options=["Todos los perfiles"] + available_profiles,
                index=default_p_idx,
                help="Filtra las vacantes que corresponden al perfil profesional seleccionado"
            )
        with f_row1_col3:
            city_filter = st.selectbox("📍 Ubicación / Región:", options=get_catalog_options(), index=0)
        with f_row1_col4:
            modality_filter = st.selectbox(
                "💼 Modalidad:",
                options=["Todas", "Híbrido y Remoto (Toda la República Mexicana)", "Solo Remoto", "Solo Híbrido", "Presencial"],
                index=0
            )

        f_row2_col1, f_row2_col2 = st.columns([1.2, 3.8])
        with f_row2_col1:
            status_filter = st.selectbox("Estado:", ["Todos", "nueva", "revisada", "cv_generado", "aplicada", "descartada"])

        with f_row2_col2:
            st.markdown("**⚡ Umbral de Coincidencia ATS Mínimo (%):**")
            if "min_match_threshold" not in st.session_state:
                st.session_state["min_match_threshold"] = 65

            c_b0, c_b50, c_b65, c_b75, c_b85 = st.columns(5)
            if c_b0.button("Todas (0%)", key="btn_score_0", use_container_width=True):
                st.session_state["min_match_threshold"] = 0
                st.rerun()
            if c_b50.button("Media (50%)", key="btn_score_50", use_container_width=True):
                st.session_state["min_match_threshold"] = 50
                st.rerun()
            if c_b65.button("⭐ Defecto (65%)", key="btn_score_65", use_container_width=True):
                st.session_state["min_match_threshold"] = 65
                st.rerun()
            if c_b75.button("Alta (75%)", key="btn_score_75", use_container_width=True):
                st.session_state["min_match_threshold"] = 75
                st.rerun()
            if c_b85.button("Top (85%)", key="btn_score_85", use_container_width=True):
                st.session_state["min_match_threshold"] = 85
                st.rerun()

            current_thresh = int(st.session_state.get("min_match_threshold", 65))
            min_score_val = st.slider(
                "Ajustar % de coincidencia (desliza o usa los botones de arriba):",
                min_value=0,
                max_value=95,
                value=current_thresh,
                step=5,
                key="min_score_slider_widget",
                help="Muestra vacantes que alcancen al menos este porcentaje de compatibilidad"
            )
            st.session_state["min_match_threshold"] = min_score_val
            effective_min_score = float(min_score_val)

        # Consultar leads desde SQLite (devuelve todas las opciones disponibles)
        leads_raw = get_leads(
            status_filter=status_filter,
            search_query=search_filter,
            city_filter=city_filter,
            modality_filter=modality_filter
        )

        # Calcular y cachear score ATS si aún no está computado
        for l in leads_raw:
            match_res = match_and_tailor_cv(l["title"], (l.get("description") or "")[:600], l["company"], master_data=master_data, job_id=l["id"])
            l["ats_score"] = match_res["ats_score"]
            l["target_profile_title"] = match_res["chosen_profile"]["title"]

        # Filtrar por perfil objetivo si no es "Todos los perfiles"
        if target_profile_filter != "Todos los perfiles":
            leads_for_profile = [l for l in leads_raw if l.get("target_profile_title") == target_profile_filter]
        else:
            leads_for_profile = leads_raw

        total_available_options = len(leads_for_profile)

        # Filtrar por score mínimo solicitado (arriba de 65% por defecto)
        if effective_min_score > 0:
            filtered_leads = [l for l in leads_for_profile if (l.get("ats_score") or 0) >= effective_min_score]
        else:
            filtered_leads = leads_for_profile

        # (MAPA ELIMINADO SEGÚN REQUERIMIENTO DEL USUARIO)

        if not filtered_leads:
            st.warning(f"No hay vacantes con afinidad ≥ {int(effective_min_score)}% para los criterios seleccionados.")
            st.info(f"💡 Tienes **{total_available_options}** vacantes disponibles en total. Puedes pulsar el botón **'Media (50%)'** o **'Todas (0%)'** arriba para verlas.")
        else:
            st.caption(f"Mostrando **{len(filtered_leads)}** de **{total_available_options}** vacantes que superan el **{int(effective_min_score)}%** de afinidad.")

            # 3. RENDERIZADO DE CADA VACANTE CON INTELIGENCIA EMPRESARIAL
            for lead in filtered_leads:
                l_id = lead.get("id")
                l_title = lead.get("title")
                l_comp = lead.get("company")
                l_loc = lead.get("normalized_location") or lead.get("location")
                l_url = lead.get("job_url")
                l_desc = lead.get("description", "")
                l_date = lead.get("date_posted")
                l_src = lead.get("source", "web")
                lead_status = lead.get("status", "nueva")
                score = lead.get("ats_score", 0)
                lead_mod = lead.get("modality", "no_especificado")

                score_badge = f'<span class="badge-score-high">⚡ ATS Score: {score}%</span>' if score >= 60 else f'<span class="badge-score-mid">⚡ ATS Score: {score}%</span>'
                status_class = f"status-{lead_status}"
                status_badge = f'<span class="status-pill {status_class}">{lead_status}</span>'

                if lead_mod == "remoto":
                    mod_badge = '<span class="badge-tech">🏠 Remoto</span>'
                elif lead_mod == "hibrido":
                    mod_badge = '<span class="badge-growth">🏢 Híbrido</span>'
                elif lead_mod == "presencial":
                    mod_badge = '<span class="badge-sector">📍 Presencial</span>'
                else:
                    mod_badge = ''

                lead_target_p = (lead.get("target_profile_title") or "General").split("|")[0].strip()
                target_p_badge = f'<span class="badge-sector" style="background-color: #EEF2FF; color: #4338CA; border: 1px solid #C7D2FE;">🎯 {lead_target_p}</span>'

                # Datos salariales y seniority
                l_salary = lead.get("salary_display") or ""
                l_seniority = lead.get("seniority_level") or ""
                salary_badge = f'<span style="background-color: #ECFDF5; color: #065F46; padding: 2px 7px; border-radius: 6px; font-weight: 600; font-size: 0.78rem; border: 1px solid #A7F3D0;">💰 {l_salary}</span>' if l_salary else ""

                if l_seniority in ["Especialista / Analista", "Junior / Asociado", "Becario / Trainee"]:
                    seniority_badge = f'<span style="background-color: #FEF2F2; color: #991B1B; padding: 2px 7px; border-radius: 6px; font-weight: 600; font-size: 0.78rem; border: 1px solid #FECACA;" title="Rol operativo inferior a tu perfil directivo/senior (Riesgo de sobrecalificación en ATS)">⚠️ Nivel Operativo ({l_seniority})</span>'
                elif l_seniority:
                    seniority_badge = f'<span style="background-color: #EFF6FF; color: #1D4ED8; padding: 2px 7px; border-radius: 6px; font-weight: 600; font-size: 0.78rem; border: 1px solid #BFDBFE;">👔 {l_seniority}</span>'
                else:
                    seniority_badge = ""

                # Ficha empresarial
                c_sector = lead.get("company_sector") or "Tecnología & Servicios"
                c_size = lead.get("company_size") or "Enterprise"
                c_growth = lead.get("company_growth") or "Consolidada"
                c_tech = lead.get("company_tech") or "Python, SQL, Cloud"
                c_hq = lead.get("company_hq") or "México"
                c_desc = lead.get("company_desc") or ""

                badges_line = " &nbsp;•&nbsp; ".join([b for b in [f"🏢 <b>{l_comp}</b>", f"📍 {l_loc}", mod_badge, target_p_badge, salary_badge, seniority_badge, f"🗓️ {l_date}", f"🌐 {l_src.title()}"] if b])

                with st.container():
                    st.markdown(f"""
                    <div class="job-card">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <div>
                                <h4 style="margin: 0; color: #1E293B;">{l_title}</h4>
                                <p style="margin: 3px 0 6px 0; color: #64748B; font-weight: 500; font-size: 0.86rem;">{badges_line}</p>
                            </div>
                            <div>
                                {score_badge} &nbsp; {status_badge}
                            </div>
                        </div>
                        <div class="company-intel-box">
                            <div style="margin-bottom: 6px;">
                                <span class="badge-sector">🏭 {c_sector}</span>
                                <span class="badge-size">👥 {c_size}</span>
                                <span class="badge-growth">📈 {c_growth}</span>
                                <span class="badge-tech">💻 {c_tech}</span>
                            </div>
                            <div style="color: #475569; margin-top: 4px;">
                                <b>Sede:</b> {c_hq} &nbsp;•&nbsp; {c_desc}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    c_act1, c_act2, c_act3, c_act4 = st.columns([2, 1, 1, 1])
                    with c_act1:
                        if l_url and l_url.startswith("http"):
                            st.markdown(f"🔗 [Ver oferta original en {l_src.title()}]({l_url})")
                        else:
                            st.caption("📝 Entrada directa sin enlace")
                    with c_act2:
                        if st.button("📄 Generar CV", key=f"gen_{l_id}", type="primary"):
                            st.session_state["selected_job_for_cv"] = l_id
                            st.info("Vacante seleccionada. Pasa a la pestaña '2. Generador Dinámico de CV'.")
                    with c_act3:
                        if lead_status != "aplicada":
                            if st.button("✅ Aplicada", key=f"app_{l_id}"):
                                update_job_status(l_id, "aplicada")
                                st.rerun()
                    with c_act4:
                        if lead_status != "descartada":
                            if st.button("❌ Descartar", key=f"desc_{l_id}"):
                                update_job_status(l_id, "descartada")
                                st.rerun()

                    with st.expander(f"📋 Ver descripción de la vacante ({l_title} — {l_comp})"):
                        if l_desc and len(l_desc.strip()) > 30:
                            st.markdown(l_desc)
                        else:
                            st.info("ℹ️ Esta vacante fue capturada con información preliminar. Al utilizar la extracción multicanal con Google Jobs o LinkedIn activado, se descarga el desglose completo de requisitos.")


# -------------------------------------------------------------
# TAB 2: GENERADOR DINÁMICO DE CV
# -------------------------------------------------------------
with tab_generador:
    st.markdown("### 🛠️ Compilación Adaptada por Vacante")
    
    all_leads = load_job_leads()
    lead_options = {l["id"]: f"{l['title']} — {l['company']} ({l['id']})" for l in all_leads}

    # Seleccionar vacante
    default_lead_id = st.session_state.get("selected_job_for_cv", list(lead_options.keys())[0] if lead_options else None)
    
    if not lead_options:
        st.warning("No hay vacantes disponibles para adaptar. Por favor agrega una en la pestaña 1.")
        active_lead = None
    else:
        chosen_id = st.selectbox(
            "Selecciona la vacante a la que deseas postularte:",
            options=list(lead_options.keys()),
            index=list(lead_options.keys()).index(default_lead_id) if default_lead_id in lead_options else 0,
            format_func=lambda x: lead_options.get(x, x)
        )
        active_lead = next((l for l in all_leads if l["id"] == chosen_id), None)

    if active_lead:
        # Parámetros de adaptación
        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            target_profs = master_data.get("profile", {}).get("target_profiles", [])
            prof_dict = {tp["id"]: f"{tp.get('title')} ({tp.get('tag', '')})" for tp in target_profs}
            
            # Match preliminar para sugerir el target automáticamente
            pre_match = match_and_tailor_cv(active_lead["title"], active_lead["description"], active_lead["company"], master_data=master_data)
            suggested_prof_id = pre_match["chosen_profile"].get("id", target_profs[0]["id"] if target_profs else "")
            
            selected_prof_id = st.selectbox(
                "Perfil Objetivo Seleccionado:",
                options=list(prof_dict.keys()),
                index=list(prof_dict.keys()).index(suggested_prof_id) if suggested_prof_id in prof_dict else 0,
                format_func=lambda x: prof_dict.get(x, x),
                help="El algoritmo autoselecciona el perfil más idóneo, pero puedes sobrescribirlo."
            )

        with col_opt2:
            max_bullets = st.slider("Viñetas de logro por puesto:", min_value=1, max_value=5, value=3)

        # Ejecutar Match Completo
        tailored_cv = match_and_tailor_cv(
            job_title=active_lead["title"],
            job_description=active_lead["description"],
            company_name=active_lead["company"],
            target_profile_override_id=selected_prof_id,
            max_bullets_per_role=max_bullets,
            master_data=master_data
        )

        # Alerta de Nivel de Puesto / Tabulador Salarial
        sen_warning = tailored_cv.get("seniority_warning")
        sal_info = tailored_cv.get("salary_info", {})
        if sen_warning:
            st.warning(f"{sen_warning}\n\n💡 **Recomendación Estratégica:** En portales corporativos como Workday de Santander o Taleo de BBVA, perfiles con nivel de Gerente/Director aplicando a puestos de 'Especialista' o 'Analista' suelen ser descartados automáticamente por tabulador o riesgo de rotación. Si deseas aplicar, adapta la denominación de tu rol y alinea tu pretensión salarial al rango operativo.")
        elif sal_info.get("salary_display"):
            st.info(f"💰 **Rango Salarial Estimado de Mercado:** {sal_info['salary_display']} &nbsp;|&nbsp; **Nivel de la Posición:** {sal_info.get('seniority_label', 'Senior')}")

        st.divider()

        # Resumen de Métricas ATS
        m_col1, m_col2, m_col3 = st.columns([1, 2, 2])
        with m_col1:
            st.metric("Puntaje ATS Estimado", f"{tailored_cv['ats_score']}%")
        with m_col2:
            matched_kws = tailored_cv.get("matched_keywords", [])
            st.write(f"**Keywords ATS Coincidentes ({len(matched_kws)}):**")
            st.write(", ".join([f"`{k}`" for k in matched_kws[:15]]) if matched_kws else "_Ninguna detectada_")
        with m_col3:
            missing_kws = tailored_cv.get("missing_keywords", [])
            st.write(f"**Gaps / Palabras Clave Faltantes:**")
            st.write(", ".join([f"`{k}`" for k in missing_kws[:10]]) if missing_kws else "_Excelente cobertura_")

        st.divider()

        # Selector de Idioma para el CV
        col_l1, col_l2 = st.columns([1.5, 2.5])
        with col_l1:
            selected_lang = st.radio(
                "🌐 **Idioma del CV / CV Language:**",
                options=["es", "en"],
                format_func=lambda x: "🇪🇸 Español" if x == "es" else "🇺🇸 English (EN)",
                horizontal=True,
                key="cv_lang_selector"
            )
        with col_l2:
            if selected_lang == "en":
                st.caption("ℹ️ *Se compilarán los textos y encabezados en inglés con sufijo `_EN` (usando fallback automático al español si algún logro no tiene traducción).*")
            else:
                st.caption("ℹ️ *Versión estándar en español optimizada para filtros ATS locales y regionales.*")

        # Previsualización y Compilación
        subtab_preview, subtab_bullets = st.tabs(["👁️ Vista Previa del CV Compilado", "🎯 Detalle de Viñetas Seleccionadas"])

        with subtab_preview:
            # Generar contenido Markdown según idioma con auto-traducción si se solicita EN
            md_content = generate_markdown(tailored_cv, lang=selected_lang, auto_translate=(selected_lang == "en"))
            st.markdown(md_content)

        with subtab_bullets:
            st.write("A continuación se detallan las viñetas seleccionadas para cada rol según su relevancia algorítmica:")
            for exp in tailored_cv.get("tailored_experiences", []):
                role_label = exp.get("role_en") if selected_lang == "en" and exp.get("role_en") else exp['role']
                st.markdown(f"**{role_label}** en *{exp['company']}* ({exp['period']})")
                for b in exp.get("selected_bullets", []):
                    b_id = b.get("id", "")
                    b_text = (b.get("bullet_en") or b.get("text_en")) if selected_lang == "en" else (b.get("text", "") or b.get("bullet", ""))
                    if not b_text:
                        b_text = b.get("text", "") or b.get("bullet", "")
                    b_metric = b.get("metric_en") if selected_lang == "en" and b.get("metric_en") else b.get("metric", "")
                    b_kws = ", ".join(b.get("keywords", []))
                    st.markdown(f"- `[{b_id}]` {b_text}")
                    if b_metric:
                        impact_tag = "Impact" if selected_lang == "en" else "Métrica"
                        st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;🎯 *{impact_tag}:* {b_metric} | 🏷️ *Keywords:* {b_kws}")
                st.write("")

        st.divider()

        # Botones de Compilación y Descarga
        c_down1, c_down2, c_down3 = st.columns([1.5, 1, 1])
        
        with c_down1:
            compile_label = "🚀 Compilar Paquete Completo (PDF & Markdown)" if selected_lang == "es" else "🌐 Compilar CV en Inglés (Auto-Traducir a PDF & MD)"
            compile_btn = st.button(compile_label, type="primary", use_container_width=True)

        if compile_btn or "compiled_files" in st.session_state:
            if compile_btn:
                spinner_text = "Compilando documentos en outputs/..." if selected_lang == "es" else "Traduciendo automáticamente al inglés y compilando documentos..."
                with st.spinner(spinner_text):
                    compiled = compile_cv_package(
                        tailored_cv,
                        active_lead["id"],
                        active_lead["company"],
                        lang=selected_lang,
                        auto_translate=(selected_lang == "en")
                    )
                    update_job_status(active_lead["id"], "cv_generado", {
                        "cv_pdf": compiled["pdf_path"],
                        "cv_md": compiled["markdown_path"]
                    })
                    st.session_state["compiled_files"] = compiled
                    st.success(f"¡CV compilado exitosamente ({selected_lang.upper()})!")

            compiled = st.session_state.get("compiled_files")
            if compiled and os.path.exists(compiled["pdf_path"]) and os.path.exists(compiled["markdown_path"]):
                with c_down2:
                    with open(compiled["pdf_path"], "rb") as f_pdf:
                        st.download_button(
                            label="⬇️ Descargar PDF",
                            data=f_pdf.read(),
                            file_name=os.path.basename(compiled["pdf_path"]),
                            mime="application/pdf",
                            use_container_width=True
                        )
                with c_down3:
                    with open(compiled["markdown_path"], "r", encoding="utf-8") as f_md:
                        st.download_button(
                            label="⬇️ Descargar Markdown",
                            data=f_md.read(),
                            file_name=os.path.basename(compiled["markdown_path"]),
                            mime="text/markdown",
                            use_container_width=True
                        )


# -------------------------------------------------------------
# TAB 3: HISTORIAL & POSTULACIONES
# -------------------------------------------------------------
with tab_historial:
    st.markdown("### 📊 Registro de Prospección y Postulaciones (SQLite `jobs.db`)")
    
    # Métricas agregadas directas desde SQL
    status_counts = get_status_counts()

    c_h1, c_h2, c_h3, c_h4, c_h5 = st.columns(5)
    c_h1.metric("Nuevas", status_counts.get("nueva", 0))
    c_h2.metric("Revisadas", status_counts.get("revisada", 0))
    c_h3.metric("CV Generado", status_counts.get("cv_generado", 0))
    c_h4.metric("Aplicadas", status_counts.get("aplicada", 0))
    c_h5.metric("Descartadas", status_counts.get("descartada", 0))

    st.divider()

    sub_h1, sub_h2 = st.tabs(["📋 Catálogo de Vacantes & Estados", "⏱️ Auditoría & Línea de Tiempo"])

    with sub_h1:
        all_db_leads = get_leads()
        if not all_db_leads:
            st.info("No hay registros en la base de datos.")
        else:
            hist_table = []
            for lead in all_db_leads:
                hist_table.append({
                    "ID": lead.get("id"),
                    "Título": lead.get("title", "N/A"),
                    "Empresa": lead.get("company", "N/A"),
                    "Ubicación": lead.get("location", "N/A"),
                    "Estado": lead.get("status", "nueva"),
                    "Score ATS": f"{lead.get('ats_score')}%" if lead.get('ats_score') is not None else "Pendiente",
                    "Fuente": lead.get("source", "N/A"),
                    "Fecha Extracción": str(lead.get("extracted_at", ""))[:16].replace("T", " ")
                })

            df_hist = pd.DataFrame(hist_table)
            st.dataframe(df_hist, use_container_width=True, hide_index=True)

    with sub_h2:
        audit_logs = get_audit_log(limit=50)
        if not audit_logs:
            st.info("No hay eventos de auditoría registrados.")
        else:
            st.caption("Registro de trazabilidad y cambios de estado (Últimos 50 eventos):")
            audit_table = []
            for log in audit_logs:
                audit_table.append({
                    "Fecha / Hora": str(log.get("timestamp", ""))[:19].replace("T", " "),
                    "ID Vacante": log.get("job_id"),
                    "Empresa": log.get("company"),
                    "Puesto": log.get("title"),
                    "Nuevo Estado": log.get("status")
                })
            df_audit = pd.DataFrame(audit_table)
            st.dataframe(df_audit, use_container_width=True, hide_index=True)


# -------------------------------------------------------------
# TAB 4: FUENTE CANÓNICA (EXCEL)
# -------------------------------------------------------------
with tab_fuente:
    st.markdown("### 📚 Explorador de la Fuente Única de Verdad (`Motor Job.xlsx`)")
    st.info("💡 **Regla de Cero Hardcode:** Los datos mostrados provienen directamente del archivo Excel. Para modificar cualquier texto, teléfono, puesto o logro, edita `data/Motor Job.xlsx` y haz clic en 'Recompilar Master' en el panel lateral.")

    tab_f_perf, tab_f_exp, tab_f_hab = st.tabs(["Perfil & Targets", "Inventario de Logros (27)", "Matriz de Habilidades (23)"])

    with tab_f_perf:
        st.subheader("Perfiles Objetivo Detectados")
        for tp in master_data.get("profile", {}).get("target_profiles", []):
            with st.container():
                st.markdown(f"#### 🎯 {tp.get('title')} `[{tp.get('tag')}]`")
                st.write(f"**Resumen:** {tp.get('summary')}")
                st.caption(f"**Nota:** {tp.get('note')}")
                st.divider()

        st.subheader("Datos de Contacto & Formación")
        col_cp1, col_cp2 = st.columns(2)
        with col_cp1:
            st.write("**Contacto:**")
            for k, v in master_data.get("profile", {}).get("contact_info", {}).items():
                st.write(f"- **{k}:** {v}")
        with col_cp2:
            st.write("**Educación & Certificaciones:**")
            for edu in master_data.get("profile", {}).get("education", []):
                st.write(f"- {edu.get('value')}")
            for cert in master_data.get("profile", {}).get("certifications", []):
                st.write(f"- {cert.get('value')}")

    with tab_f_exp:
        st.subheader("Inventario Atómico de Logros")
        raw_exp_items = master_data.get("experiences", {}).get("items", [])
        if raw_exp_items:
            df_exp = pd.DataFrame(raw_exp_items)
            df_exp["tracks"] = df_exp["tracks"].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))
            df_exp["keywords"] = df_exp["keywords"].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))
            st.dataframe(df_exp, use_container_width=True, hide_index=True)

    with tab_f_hab:
        st.subheader("Matriz de Competencias")
        raw_skills = master_data.get("skills", {}).get("items", [])
        if raw_skills:
            df_sk = pd.DataFrame(raw_skills)
            df_sk["tags"] = df_sk["tags"].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))
            st.dataframe(df_sk, use_container_width=True, hide_index=True)
