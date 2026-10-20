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


def sanitize_filename(name: str) -> str:
    """Limpia cadenas para usar como nombres de archivo válidos"""
    if not name:
        return "cv"
    s = re.sub(r'[\\/*?:"<>| ]', '_', name)
    return re.sub(r'_+', '_', s).strip('_')


def generate_markdown(cv_data: Dict[str, Any], output_path: Optional[Path] = None) -> str:
    """
    Genera la versión en Markdown estructurado del CV tailoreado.
    """
    contact_info = cv_data.get("contact_info", {})
    chosen_profile = cv_data.get("chosen_profile", {})
    experiences = cv_data.get("tailored_experiences", [])
    skills_by_cat = cv_data.get("skills_by_category", {})
    education = cv_data.get("education", [])
    certifications = cv_data.get("certifications", [])

    # Obtener nombre dinámicamente
    full_name = ""
    for k, v in contact_info.items():
        if "nombre" in k.lower():
            full_name = v
            break
    if not full_name and contact_info:
        full_name = list(contact_info.values())[0]

    # Barra de contacto
    contact_items = []
    for k, v in contact_info.items():
        if "nombre" not in k.lower() and v:
            contact_items.append(v)
    contact_line = " | ".join(contact_items)

    lines = []
    lines.append(f"# {full_name}")
    if contact_line:
        lines.append(f"**{contact_line}**\n")

    # Título profesional
    title = chosen_profile.get("title", "")
    if title:
        lines.append(f"## {title}\n")

    # Resumen
    summary = chosen_profile.get("summary", "")
    if summary:
        lines.append("### Perfil Profesional")
        lines.append(f"{summary}\n")

    # Experiencia profesional
    if experiences:
        lines.append("### Experiencia Profesional")
        for exp in experiences:
            company = exp.get("company", "")
            role = exp.get("role", "")
            period = exp.get("period", "")
            bullets = exp.get("selected_bullets", [])

            if not bullets:
                continue

            lines.append(f"#### **{role}** — *{company}* ({period})")
            for b in bullets:
                b_text = b.get("text", "") or b.get("bullet", "")
                metric = b.get("metric", "")
                if metric:
                    lines.append(f"- {b_text} *[Impacto: {metric}]*")
                else:
                    lines.append(f"- {b_text}")
            lines.append("")

    # Habilidades técnicas
    if skills_by_cat:
        lines.append("### Habilidades & Competencias Técnicas")
        for cat, sk_list in skills_by_cat.items():
            if not sk_list:
                continue
            skill_strs = []
            for s in sk_list:
                s_name = s.get("skill", "")
                s_lvl = s.get("level", "")
                if s_lvl and s_lvl != "General":
                    skill_strs.append(f"{s_name} ({s_lvl})")
                else:
                    skill_strs.append(s_name)
            lines.append(f"- **{cat}:** {', '.join(skill_strs)}")
        lines.append("")

    # Educación & Certificaciones
    if education or certifications:
        lines.append("### Formación Académica & Certificaciones")
        for edu in education:
            val = edu.get("value", "")
            if val:
                lines.append(f"- {val}")
        for cert in certifications:
            val = cert.get("value", "")
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


def generate_pdf(cv_data: Dict[str, Any], output_path: Path) -> Path:
    """
    Compila el CV en PDF profesional ATS-friendly utilizando ReportLab.
    """
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
        if "nombre" not in k.lower() and v:
            # Acortar URLs largas para visualización elegante
            clean_val = v.replace("https://www.", "").replace("https://", "")
            contact_parts.append(clean_val)
    
    if contact_parts:
        story.append(Paragraph(" • ".join(contact_parts), style_contact))
        story.append(Spacer(1, 4))

    # 3. Título del Perfil Objetivo
    title = chosen_profile.get("title", "")
    if title:
        story.append(Paragraph(title.upper(), style_target_title))
        story.append(Spacer(1, 6))

    story.append(HRFlowable(width="100%", thickness=1, color=LINE_COLOR, spaceBefore=2, spaceAfter=6))

    # 4. Resumen Ejecutivo
    summary = chosen_profile.get("summary", "")
    if summary:
        story.append(Paragraph("RESUMEN PROFESIONAL", style_section_title))
        story.append(Paragraph(summary, style_body))
        story.append(Spacer(1, 6))

    # 5. Experiencia Laboral
    if experiences:
        story.append(Paragraph("EXPERIENCIA PROFESIONAL", style_section_title))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceBefore=1, spaceAfter=4))

        for exp in experiences:
            company = exp.get("company", "")
            role = exp.get("role", "")
            period = exp.get("period", "")
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
                b_text = b.get("text", "") or b.get("bullet", "")
                metric = b.get("metric", "")
                if metric:
                    full_bullet = f"• {b_text} <i>(Impacto: {metric})</i>"
                else:
                    full_bullet = f"• {b_text}"
                story.append(Paragraph(full_bullet, style_bullet))

            story.append(Spacer(1, 5))

    # 6. Habilidades Técnicas
    if skills_by_cat:
        story.append(Spacer(1, 3))
        story.append(Paragraph("HABILIDADES & COMPETENCIAS TÉCNICAS", style_section_title))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceBefore=1, spaceAfter=4))

        skills_table_data = []
        for cat, sk_list in skills_by_cat.items():
            if not sk_list:
                continue
            # Mostrar habilidades (destacando con negrita si hicieron match)
            items_formatted = []
            for s in sk_list:
                s_name = s.get("skill", "")
                if s.get("matched"):
                    items_formatted.append(f"<b>{s_name}</b>")
                else:
                    items_formatted.append(s_name)
            
            row_left = Paragraph(f"• <b>{cat}:</b>", style_skill_cat)
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
        story.append(Paragraph("EDUCACIÓN & CERTIFICACIONES", style_section_title))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceBefore=1, spaceAfter=4))

        for edu in education:
            val = edu.get("value", "")
            if val:
                story.append(Paragraph(f"• {val}", style_bullet))

        for cert in certifications:
            val = cert.get("value", "")
            if val:
                story.append(Paragraph(f"• {val}", style_bullet))

    doc.build(story)
    return output_path


def compile_cv_package(cv_data: Dict[str, Any], job_id: str, company: str) -> Dict[str, str]:
    """
    Genera tanto el archivo Markdown como el archivo PDF en el directorio outputs/
    """
    clean_id = sanitize_filename(job_id)
    clean_comp = sanitize_filename(company)
    base_name = f"{clean_id}_{clean_comp}" if clean_comp else clean_id

    md_path = OUTPUTS_DIR / f"{base_name}.md"
    pdf_path = OUTPUTS_DIR / f"{base_name}.pdf"

    generate_markdown(cv_data, md_path)
    generate_pdf(cv_data, pdf_path)

    return {
        "markdown_path": str(md_path),
        "pdf_path": str(pdf_path),
        "base_name": base_name
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
