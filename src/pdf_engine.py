"""
pdf_engine.py
Compilador agnóstico de CV a formatos Markdown y PDF (ReportLab).
Cumple con la regla de CERO HARDCODE:
- No contiene nombres, datos de contacto ni viñetas en el código.
- Recibe la estructura de datos tailoreada por matcher.py y genera documentos de alta fidelidad.
- Formato optimizado para filtros ATS y legibilidad humana.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"


# Cadenas de texto localizadas para encabezados de sección
SECTION_HEADERS = {
    "es": {
        "summary": "RESUMEN PROFESIONAL",
        "experience": "EXPERIENCIA PROFESIONAL",
        "skills": "HABILIDADES & COMPETENCIAS TÉCNICAS",
        "education": "EDUCACIÓN & CERTIFICACIONES",
        "impact_label": "Impacto",
        "present": "PRESENTE"
    },
    "en": {
        "summary": "PROFESSIONAL SUMMARY",
        "experience": "PROFESSIONAL EXPERIENCE",
        "skills": "TECHNICAL SKILLS & COMPETENCIES",
        "education": "EDUCATION & CERTIFICATIONS",
        "impact_label": "Impact",
        "present": "PRESENT"
    }
}

# Mapeos bilingües de apoyo para niveles y categorías si no vienen explícitos en el JSON
LEVEL_MAP_EN = {
    "experto": "Expert",
    "avanzado": "Advanced",
    "intermedio": "Intermediate",
    "básico": "Basic",
    "basico": "Basic",
    "general": "General",
    "en progreso": "In Progress"
}

CATEGORY_MAP_EN = {
    "métodos cuantitativos & finanzas": "Quantitative Methods & Finance",
    "metodos cuantitativos & finanzas": "Quantitative Methods & Finance",
    "arquitectura de datos & cloud": "Data Architecture & Cloud",
    "machine learning & analítica": "Machine Learning & Analytics",
    "machine learning & analitica": "Machine Learning & Analytics",
    "visualización & bi": "Visualization & BI",
    "visualizacion & bi": "Visualization & BI",
    "gestión & liderazgo": "Management & Leadership",
    "gestion & liderazgo": "Management & Leadership"
}

LOCATION_MAP_EN = {
    "méxico": "Mexico",
    "mexico": "Mexico",
    "estado de méxico": "State of Mexico",
    "estado de mexico": "State of Mexico",
    "ciudad de méxico": "Mexico City",
    "ciudad de mexico": "Mexico City"
}


def sanitize_filename(name: str) -> str:
    """Limpia cadenas para usar como nombres de archivo válidos"""
    if not name:
        return "cv"
    s = re.sub(r'[\\/*?:"<>| ]', '_', name)
    return re.sub(r'_+', '_', s).strip('_')


def get_localized_field(data: Dict[str, Any], key: str, lang: str = "es") -> str:
    """Obtiene un valor con fallback bilingüe (prioriza _en si lang='en')"""
    if not isinstance(data, dict):
        return ""
    if lang == "en":
        for en_key in [f"{key}_en", f"{key}En", f"{key}_EN"]:
            if data.get(en_key):
                return str(data[en_key]).strip()
    return str(data.get(key) or "").strip()


def format_period_localized(period: str, period_en: Optional[str] = None, lang: str = "es") -> str:
    """Formatea el periodo de empleo en el idioma seleccionado"""
    if lang == "en":
        if period_en:
            return period_en.strip()
        # Fallback de reemplazos comunes
        p = period or ""
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
    return period or ""


def generate_markdown(cv_data: Dict[str, Any], output_path: Optional[Path] = None, lang: str = "es") -> str:
    """
    Genera la versión en Markdown estructurado del CV tailoreado.
    Soporta idiomas 'es' (Español) y 'en' (Inglés).
    """
    lang = lang.lower() if lang in ["es", "en"] else "es"
    headers = SECTION_HEADERS.get(lang, SECTION_HEADERS["es"])

    contact_info = cv_data.get("contact_info", {})
    chosen_profile = cv_data.get("chosen_profile", {})
    experiences = cv_data.get("tailored_experiences", [])
    skills_by_cat = cv_data.get("skills_by_category", {})
    education = cv_data.get("education", [])
    certifications = cv_data.get("certifications", [])

    # Obtener nombre dinámicamente
    full_name = ""
    for k, v in contact_info.items():
        if "nombre" in k.lower() or "name" in k.lower():
            full_name = v
            break
    if not full_name and contact_info:
        full_name = list(contact_info.values())[0]

    # Barra de contacto
    contact_items = []
    for k, v in contact_info.items():
        k_lower = k.lower()
        if "nombre" in k_lower or "name" in k_lower or not v:
            continue
        # Localización de ubicación
        val_str = str(v).strip()
        if ("ubicación" in k_lower or "ubicacion" in k_lower or "location" in k_lower) and lang == "en":
            en_loc = contact_info.get("Ubicación_en") or contact_info.get("location_en")
            if en_loc:
                val_str = en_loc
            else:
                for es_word, en_word in LOCATION_MAP_EN.items():
                    val_str = re.sub(rf'\b{re.escape(es_word)}\b', en_word, val_str, flags=re.IGNORECASE)
        contact_items.append(val_str)

    contact_line = " | ".join(contact_items)

    lines = []
    lines.append(f"# {full_name}")
    if contact_line:
        lines.append(f"**{contact_line}**\n")

    # Título profesional
    title = get_localized_field(chosen_profile, "title", lang)
    if title:
        lines.append(f"## {title}\n")

    # Resumen
    summary = get_localized_field(chosen_profile, "summary", lang)
    if summary:
        lines.append(f"### {headers['summary'].title() if lang == 'es' else 'Professional Summary'}")
        lines.append(f"{summary}\n")

    # Experiencia profesional
    if experiences:
        lines.append(f"### {headers['experience'].title() if lang == 'es' else 'Professional Experience'}")
        for exp in experiences:
            company = exp.get("company", "")
            role = get_localized_field(exp, "role", lang)
            period = format_period_localized(exp.get("period", ""), exp.get("period_en"), lang)
            bullets = exp.get("selected_bullets", [])

            if not bullets:
                continue

            lines.append(f"#### **{role}** — *{company}* ({period})")
            for b in bullets:
                b_text = get_localized_field(b, "bullet", lang) or get_localized_field(b, "text", lang)
                metric = get_localized_field(b, "metric", lang)
                if metric:
                    impact_lbl = headers["impact_label"]
                    lines.append(f"- {b_text} *[{impact_lbl}: {metric}]*")
                else:
                    lines.append(f"- {b_text}")
            lines.append("")

    # Habilidades técnicas
    if skills_by_cat:
        lines.append(f"### {headers['skills'].title() if lang == 'es' else 'Technical Skills & Competencies'}")
        for cat, sk_list in skills_by_cat.items():
            if not sk_list:
                continue
            cat_display = CATEGORY_MAP_EN.get(cat.lower(), cat) if lang == "en" else cat
            skill_strs = []
            for s in sk_list:
                s_name = get_localized_field(s, "skill", lang)
                s_lvl = s.get("level", "")
                if lang == "en":
                    s_lvl = s.get("level_en") or LEVEL_MAP_EN.get(s_lvl.lower(), s_lvl)
                if s_lvl and s_lvl != "General":
                    skill_strs.append(f"{s_name} ({s_lvl})")
                else:
                    skill_strs.append(s_name)
            lines.append(f"- **{cat_display}:** {', '.join(skill_strs)}")
        lines.append("")

    # Educación & Certificaciones
    if education or certifications:
        lines.append(f"### {headers['education'].title() if lang == 'es' else 'Education & Certifications'}")
        for edu in education:
            val = get_localized_field(edu, "value", lang)
            if val:
                lines.append(f"- {val}")
        for cert in certifications:
            val = get_localized_field(cert, "value", lang)
            if val:
                lines.append(f"- {val}")
        lines.append("")

    md_content = "\n".join(lines)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)

    return md_content


def generate_pdf(cv_data: Dict[str, Any], output_path: Path, lang: str = "es") -> Path:
    """
    Compila el CV en PDF profesional ATS-friendly utilizando ReportLab.
    Soporta idiomas 'es' (Español) y 'en' (Inglés).
    """
    lang = lang.lower() if lang in ["es", "en"] else "es"
    headers = SECTION_HEADERS.get(lang, SECTION_HEADERS["es"])

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Configuración de márgenes precisos (0.5 pulgadas para maximizar espacio ATS)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Paleta de colores corporativa
    PRIMARY = colors.HexColor("#0F2942")     # Deep Navy
    SECONDARY = colors.HexColor("#2B6CB0")   # Slate Blue
    BODY_COLOR = colors.HexColor("#1A202C")  # Dark Charcoal
    LIGHT_GRAY = colors.HexColor("#718096")  # Subtitle gray
    LINE_COLOR = colors.HexColor("#CBD5E0")  # Subtle line

    # Definir estilos tipográficos
    style_name = ParagraphStyle(
        'CVName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        textColor=PRIMARY
    )

    style_contact = ParagraphStyle(
        'CVContact',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        alignment=TA_CENTER,
        textColor=LIGHT_GRAY
    )

    style_target_title = ParagraphStyle(
        'CVTargetTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=15,
        alignment=TA_CENTER,
        textColor=SECONDARY
    )

    style_section_title = ParagraphStyle(
        'CVSectionTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=PRIMARY,
        spaceBefore=8,
        spaceAfter=2
    )

    style_body = ParagraphStyle(
        'CVBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        alignment=TA_JUSTIFY,
        textColor=BODY_COLOR
    )

    style_job_header = ParagraphStyle(
        'CVJobHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=PRIMARY
    )

    style_job_period = ParagraphStyle(
        'CVJobPeriod',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12,
        alignment=TA_RIGHT,
        textColor=LIGHT_GRAY
    )

    style_bullet = ParagraphStyle(
        'CVBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=BODY_COLOR,
        leftIndent=12,
        firstLineIndent=-8,
        spaceBefore=2
    )

    style_skill_cat = ParagraphStyle(
        'CVSkillCategory',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=PRIMARY
    )

    style_skill_val = ParagraphStyle(
        'CVSkillValue',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=BODY_COLOR
    )

    story = []

    # Extraer datos dinámicamente
    contact_info = cv_data.get("contact_info", {})
    chosen_profile = cv_data.get("chosen_profile", {})
    experiences = cv_data.get("tailored_experiences", [])
    skills_by_cat = cv_data.get("skills_by_category", {})
    education = cv_data.get("education", [])
    certifications = cv_data.get("certifications", [])

    # 1. Nombre Completo
    full_name = ""
    for k, v in contact_info.items():
        if "nombre" in k.lower():
            full_name = v
            break
    if not full_name and contact_info:
        full_name = list(contact_info.values())[0]

    story.append(Paragraph(full_name, style_name))
    story.append(Spacer(1, 3))

    # 2. Información de Contacto
    contact_parts = []
    for k, v in contact_info.items():
        k_lower = k.lower()
        if "nombre" not in k_lower and "name" not in k_lower and v:
            clean_val = str(v).strip()
            # Localizar ubicación si aplica
            if ("ubicación" in k_lower or "ubicacion" in k_lower or "location" in k_lower) and lang == "en":
                en_loc = contact_info.get("Ubicación_en") or contact_info.get("location_en")
                if en_loc:
                    clean_val = en_loc
                else:
                    for es_word, en_word in LOCATION_MAP_EN.items():
                        clean_val = re.sub(rf'\b{re.escape(es_word)}\b', en_word, clean_val, flags=re.IGNORECASE)
            clean_val = clean_val.replace("https://www.", "").replace("https://", "")
            contact_parts.append(clean_val)
    
    if contact_parts:
        story.append(Paragraph(" • ".join(contact_parts), style_contact))
        story.append(Spacer(1, 4))

    # 3. Título del Perfil Objetivo
    title = get_localized_field(chosen_profile, "title", lang)
    if title:
        story.append(Paragraph(title.upper(), style_target_title))
        story.append(Spacer(1, 6))

    story.append(HRFlowable(width="100%", thickness=1, color=LINE_COLOR, spaceBefore=2, spaceAfter=6))

    # 4. Resumen Ejecutivo
    summary = get_localized_field(chosen_profile, "summary", lang)
    if summary:
        story.append(Paragraph(headers["summary"], style_section_title))
        story.append(Paragraph(summary, style_body))
        story.append(Spacer(1, 6))

    # 5. Experiencia Laboral
    if experiences:
        story.append(Paragraph(headers["experience"], style_section_title))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceBefore=1, spaceAfter=4))

        for exp in experiences:
            company = exp.get("company", "")
            role = get_localized_field(exp, "role", lang)
            period = format_period_localized(exp.get("period", ""), exp.get("period_en"), lang)
            bullets = exp.get("selected_bullets", [])

            if not bullets:
                continue

            # Encabezado del puesto: Dos columnas (Rol / Empresa a la izq, Periodo a la der)
            left_text = f"<b>{role}</b>  |  {company}"
            job_table_data = [[
                Paragraph(left_text, style_job_header),
                Paragraph(period, style_job_period)
            ]]
            job_table = Table(job_table_data, colWidths=[400, 140])
            job_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            story.append(job_table)

            # Viñetas seleccionadas
            for b in bullets:
                b_text = get_localized_field(b, "bullet", lang) or get_localized_field(b, "text", lang)
                metric = get_localized_field(b, "metric", lang)
                if metric:
                    impact_lbl = headers["impact_label"]
                    full_bullet = f"• {b_text} <i>({impact_lbl}: {metric})</i>"
                else:
                    full_bullet = f"• {b_text}"
                story.append(Paragraph(full_bullet, style_bullet))

            story.append(Spacer(1, 5))

    # 6. Habilidades Técnicas
    if skills_by_cat:
        story.append(Spacer(1, 3))
        story.append(Paragraph(headers["skills"], style_section_title))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceBefore=1, spaceAfter=4))

        skills_table_data = []
        for cat, sk_list in skills_by_cat.items():
            if not sk_list:
                continue
            cat_display = CATEGORY_MAP_EN.get(cat.lower(), cat) if lang == "en" else cat
            # Mostrar habilidades (destacando con negrita si hicieron match)
            items_formatted = []
            for s in sk_list:
                s_name = get_localized_field(s, "skill", lang)
                if s.get("matched"):
                    items_formatted.append(f"<b>{s_name}</b>")
                else:
                    items_formatted.append(s_name)
            
            row_left = Paragraph(f"• <b>{cat_display}:</b>", style_skill_cat)
            row_right = Paragraph(", ".join(items_formatted), style_skill_val)
            skills_table_data.append([row_left, row_right])

        if skills_table_data:
            sk_table = Table(skills_table_data, colWidths=[180, 360])
            sk_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            story.append(sk_table)

    # 7. Formación Académica & Certificaciones
    if education or certifications:
        story.append(Spacer(1, 4))
        story.append(Paragraph(headers["education"], style_section_title))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceBefore=1, spaceAfter=4))

        for edu in education:
            val = get_localized_field(edu, "value", lang)
            if val:
                story.append(Paragraph(f"• {val}", style_bullet))

        for cert in certifications:
            val = get_localized_field(cert, "value", lang)
            if val:
                story.append(Paragraph(f"• {val}", style_bullet))

    doc.build(story)
    return output_path


def compile_cv_package(cv_data: Dict[str, Any], job_id: str, company: str, lang: str = "es") -> Dict[str, str]:
    """
    Genera tanto el archivo Markdown como el archivo PDF en el directorio outputs/
    Soporta los idiomas 'es' (Español) y 'en' (Inglés).
    Para 'en' agrega el sufijo '_EN' al nombre del archivo.
    """
    lang = lang.lower() if lang in ["es", "en"] else "es"
    clean_id = sanitize_filename(job_id)
    clean_comp = sanitize_filename(company)
    base_name = f"{clean_id}_{clean_comp}" if clean_comp else clean_id
    if lang == "en":
        base_name = f"{base_name}_EN"

    md_path = OUTPUTS_DIR / f"{base_name}.md"
    pdf_path = OUTPUTS_DIR / f"{base_name}.pdf"

    generate_markdown(cv_data, md_path, lang=lang)
    generate_pdf(cv_data, pdf_path, lang=lang)

    return {
        "markdown_path": str(md_path),
        "pdf_path": str(pdf_path),
        "base_name": base_name,
        "lang": lang
    }


if __name__ == "__main__":
    from matcher import match_and_tailor_cv
    sample_job = """
    Líder de Riesgo Cuantitativo / Portfolio Risk Analyst
    Buscamos profesional con experiencia en modelado de riesgo financiero (VaR, CVaR),
    simulaciones de Monte Carlo, PySpark en Databricks y cumplimiento regulatorio CONSAR.
    Conocimientos sólidos en Python, FinOps y arquitectura Medallion.
    """
    tailored = match_and_tailor_cv("Senior Quant Risk Lead", sample_job, "Profuturo_Test")
    result = compile_cv_package(tailored, "JOB-001", "Profuturo")
    print(f"✅ Compilación completada:")
    print(f"   - Markdown: {result['markdown_path']}")
    print(f"   - PDF: {result['pdf_path']}")
