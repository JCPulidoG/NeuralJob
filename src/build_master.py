"""
build_master.py
Compilador agnóstico de Excel a JSON canónico (Single Source of Truth).
Cumple con la regla de CERO HARDCODE:
- No contiene datos personales, nombres, teléfonos ni viñetas en el código.
- Lee dinámicamente las hojas 'Perfil', 'Experiencias' y 'Habilidades'.
- Produce data/cv_master.json consumido por todos los demás módulos.
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List

# openpyxl es opcional y diferido (lazy-loaded) si se procesa un archivo Excel
HAS_OPENPYXL = None

import zipfile
import xml.etree.ElementTree as ET


def find_excel_file(data_dir: Path) -> Optional[Path]:
    """Encuentra el archivo Excel canónico en data/ si existe."""
    preferred_names = ["Motor Job.xlsx", "CV_Master_Modular.xlsx", "data/Motor Job.xlsx"]
    for name in preferred_names:
        candidate = data_dir / name
        if candidate.exists():
            return candidate
    
    # Si no se encuentra con los nombres preferidos, buscar el primer .xlsx
    xlsx_files = [f for f in data_dir.glob("*.xlsx") if not f.name.startswith("~$")]
    if xlsx_files:
        return xlsx_files[0]
    
    return None


def read_excel_zip(file_path: Path):
    """
    Parser nativo de archivos .xlsx mediante zipfile y XML.
    Permite compilar el master sin requerir librerías externas de terceros.
    """
    with zipfile.ZipFile(file_path) as z:
        # Cargar strings compartidos
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            ss_root = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in ss_root.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                t = ''.join([t_node.text or '' for t_node in si.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')])
                shared_strings.append(t)

        # Mapear relaciones de hojas
        wb_rels = {}
        if 'xl/_rels/workbook.xml.rels' in z.namelist():
            rel_root = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
            for rel in rel_root.findall('{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
                wb_rels[rel.attrib.get('Id')] = rel.attrib.get('Target')

        # Cargar nombres de hojas
        wb_root = ET.fromstring(z.read('xl/workbook.xml'))
        sheets = {}
        for s in wb_root.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheets/{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet'):
            s_name = s.attrib.get('name')
            r_id = s.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            target = wb_rels.get(r_id, '')
            if target.startswith('/'):
                sheet_path = target[1:]
            else:
                sheet_path = 'xl/' + target if not target.startswith('xl/') else target
            sheets[s_name] = sheet_path

        def parse_sheet_rows(sheet_file):
            if sheet_file not in z.namelist():
                return []
            s_root = ET.fromstring(z.read(sheet_file))
            sheet_rows = []
            for r in s_root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
                row_data = []
                for c in r.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                    t = c.attrib.get('t')
                    v_el = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                    val = v_el.text if v_el is not None else None
                    if t == 's' and val is not None:
                        val = shared_strings[int(val)]
                    elif t == 'inlineStr':
                        is_t = c.find('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
                        val = is_t.text if is_t is not None else None
                    row_data.append(val)
                sheet_rows.append(row_data)
            return sheet_rows

        return {s_name: parse_sheet_rows(path) for s_name, path in sheets.items()}


def clean_cell_value(val):
    """Limpia cadenas, eliminando apóstrofes o comillas tipográficas iniciales y espacios"""
    if val is None:
        return ""
    s = str(val).strip()
    # Limpiar comillas iniciales usadas en Excel para forzar texto (ej. ´55 1234)
    if s and s[0] in ("'", "´", "`"):
        s = s[1:].strip()
    return s


def parse_perfil(rows):
    """
    Parsea la hoja Perfil (Tabla Clave-Valor Dinámica).
    Estructura esperada: Col A = Clave/Campo, Col B = Valor, Col C = Notas
    """
    profile_data = {
        "raw_fields": {},
        "target_profiles": [],
        "contact_info": {},
        "education": [],
        "certifications": [],
        "other_fields": {}
    }
    
    if not rows:
        return profile_data

    # Iterar omitiendo cabecera si existe
    for row in rows[1:]:
        if not row or len(row) < 2:
            continue
        key = clean_cell_value(row[0])
        val = clean_cell_value(row[1]) if len(row) > 1 else ""
        note = clean_cell_value(row[2]) if len(row) > 2 else ""

        if not key:
            continue

        profile_data["raw_fields"][key] = {
            "value": val,
            "note": note
        }

    # Procesar perfiles objetivo dinámicos (Target Profile X y Summary Target X)
    target_profiles_map = {}
    for key, data in profile_data["raw_fields"].items():
        val = data["value"]
        note = data["note"]
        key_lower = key.lower()

        # Detección de Target Profile
        tp_match = re.search(r'target\s+profile\s*(\d+)?(?:\s*\((.*?)\))?', key, re.IGNORECASE)
        sum_match = re.search(r'summary\s+target\s*(\d+)?(?:\s*\((.*?)\))?', key, re.IGNORECASE)

        if tp_match and not sum_match:
            num = tp_match.group(1) or "1"
            tag = tp_match.group(2) or ""
            if num not in target_profiles_map:
                target_profiles_map[num] = {"id": f"target_{num}", "number": num, "tag": tag, "title": val, "summary": "", "note": note}
            else:
                target_profiles_map[num]["title"] = val
                if tag:
                    target_profiles_map[num]["tag"] = tag
                if note:
                    target_profiles_map[num]["note"] = note

        elif sum_match:
            num = sum_match.group(1) or "1"
            tag = sum_match.group(2) or ""
            if num not in target_profiles_map:
                target_profiles_map[num] = {"id": f"target_{num}", "number": num, "tag": tag, "title": "", "summary": val, "note": note}
            else:
                target_profiles_map[num]["summary"] = val
                if tag and not target_profiles_map[num].get("tag"):
                    target_profiles_map[num]["tag"] = tag

        # Categorización de campos de contacto y educación/certificación
        elif any(w in key_lower for w in ["nombre", "email", "correo", "teléfono", "telefono", "ubicación", "ubicacion", "linkedin", "github"]):
            profile_data["contact_info"][key] = val
        elif any(w in key_lower for w in ["educación", "educacion", "licenciatura", "posgrado", "maestría", "maestria", "doctorado", "diplomado"]):
            profile_data["education"].append({"field": key, "value": val, "note": note})
        elif "certificaci" in key_lower:
            profile_data["certifications"].append({"field": key, "value": val, "note": note})
        else:
            profile_data["other_fields"][key] = val

    profile_data["target_profiles"] = list(target_profiles_map.values())
    return profile_data


def parse_experiencias(rows):
    """
    Parsea la hoja Experiencias (Inventario Atómico de Logros).
    Columnas: ID, Empresa, Rol/Puesto, Periodo, Viñeta / Logro Cuantificable, Métrica de Impacto, Tracks Aplicables, Keywords ATS Principales
    """
    if not rows:
        return {"items": [], "grouped": []}

    headers = [clean_cell_value(h).lower() for h in rows[0]]
    
    # Encontrar índices dinámicamente según encabezados
    def get_col_idx(candidates):
        for c in candidates:
            for idx, h in enumerate(headers):
                if c in h:
                    return idx
        return -1

    idx_id = get_col_idx(["id"])
    idx_empresa = get_col_idx(["empresa", "company"])
    idx_rol = get_col_idx(["rol", "puesto", "title", "role"])
    idx_periodo = get_col_idx(["periodo", "fecha", "date", "period"])
    idx_vineta = get_col_idx(["viñeta", "vineta", "logro", "bullet", "descrip"])
    idx_metrica = get_col_idx(["métrica", "metrica", "impacto", "impact"])
    idx_tracks = get_col_idx(["track", "rama", "perfil"])
    idx_keywords = get_col_idx(["keyword", "ats", "palabra"])

    items = []
    grouped_map = {}

    for row in rows[1:]:
        if not row or not any(row):
            continue
        
        def safe_get(idx):
            if idx >= 0 and idx < len(row):
                return clean_cell_value(row[idx])
            return ""

        exp_id = safe_get(idx_id)
        empresa = safe_get(idx_empresa)
        rol = safe_get(idx_rol)
        periodo = safe_get(idx_periodo)
        vineta = safe_get(idx_vineta)
        metrica = safe_get(idx_metrica)
        tracks_raw = safe_get(idx_tracks)
        keywords_raw = safe_get(idx_keywords)

        if not vineta and not empresa:
            continue

        tracks = [t.strip() for t in tracks_raw.split(",") if t.strip()] if tracks_raw else []
        keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()] if keywords_raw else []

        item = {
            "id": exp_id,
            "company": empresa,
            "role": rol,
            "period": periodo,
            "bullet": vineta,
            "metric": metrica,
            "tracks": tracks,
            "keywords": keywords
        }
        items.append(item)

        # Agrupar por (empresa, rol, periodo) manteniendo el orden de aparición
        group_key = f"{empresa}____{rol}____{periodo}"
        if group_key not in grouped_map:
            grouped_map[group_key] = {
                "company": empresa,
                "role": rol,
                "period": periodo,
                "bullets": []
            }
        
        grouped_map[group_key]["bullets"].append({
            "id": exp_id,
            "text": vineta,
            "metric": metrica,
            "tracks": tracks,
            "keywords": keywords
        })

    return {
        "items": items,
        "grouped": list(grouped_map.values())
    }


def parse_habilidades(rows):
    """
    Parsea la hoja Habilidades (Matriz de Competencias).
    Columnas: Categoría / Dominio, Habilidad / Tecnología Específica, Nivel de Dominio, Tags Relacionados
    """
    if not rows:
        return {"items": [], "categories": {}}

    headers = [clean_cell_value(h).lower() for h in rows[0]]

    def get_col_idx(candidates):
        for c in candidates:
            for idx, h in enumerate(headers):
                if c in h:
                    return idx
        return -1

    idx_cat = get_col_idx(["categor", "dominio", "area"])
    idx_skill = get_col_idx(["habilidad", "tecnolog", "skill", "competencia"])
    idx_level = get_col_idx(["nivel", "dominio", "level", "seniority"])
    idx_tags = get_col_idx(["tag", "relacionad", "track", "keyword"])

    items = []
    categories = {}

    for row in rows[1:]:
        if not row or not any(row):
            continue

        def safe_get(idx):
            if idx >= 0 and idx < len(row):
                return clean_cell_value(row[idx])
            return ""

        cat = safe_get(idx_cat) or "General"
        skill = safe_get(idx_skill)
        level = safe_get(idx_level)
        tags_raw = safe_get(idx_tags)

        if not skill:
            continue

        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

        skill_item = {
            "category": cat,
            "skill": skill,
            "level": level,
            "tags": tags
        }
        items.append(skill_item)

        if cat not in categories:
            categories[cat] = []
        categories[cat].append({
            "skill": skill,
            "level": level,
            "tags": tags
        })

    return {
        "items": items,
        "categories": categories
    }


def load_and_validate_json_master(source_json: Path, output_path: Path = None) -> Dict[str, Any]:
    """
    Carga, valida y sincroniza la estructura canónica desde un archivo JSON.
    Sustituye completamente al archivo Excel, cumpliendo con la regla de Cero Hardcode.
    """
    source_json = Path(source_json)
    if not source_json.exists():
        raise FileNotFoundError(f"No se encontró el archivo JSON maestro: {source_json}")

    print(f"📄 Leyendo fuente canónica JSON desde: {source_json}")
    with open(source_json, "r", encoding="utf-8") as f:
        master = json.load(f)

    # Validar secciones mínimas
    for req_key in ["profile", "experiences", "skills"]:
        if req_key not in master:
            raise ValueError(f"El JSON maestro no contiene la sección requerida: '{req_key}'")

    profile = master.get("profile", {})
    experiences = master.get("experiences", {})
    skills = master.get("skills", {})

    # Auto-agrupar experiencias si solo se proporcionaron items
    if "grouped" not in experiences or not experiences["grouped"]:
        grouped_map = {}
        for item in experiences.get("items", []):
            empresa = item.get("company", "")
            rol = item.get("role", "")
            periodo = item.get("period", "")
            group_key = f"{empresa}____{rol}____{periodo}"
            if group_key not in grouped_map:
                grouped_map[group_key] = {
                    "company": empresa,
                    "role": rol,
                    "period": periodo,
                    "bullets": []
                }
            grouped_map[group_key]["bullets"].append({
                "id": item.get("id", ""),
                "text": item.get("bullet", ""),
                "metric": item.get("metric", ""),
                "tracks": item.get("tracks", []),
                "keywords": item.get("keywords", [])
            })
        experiences["grouped"] = list(grouped_map.values())

    # Recalcular metadata
    target_profiles = profile.get("target_profiles", [])
    exp_items = experiences.get("items", [])
    exp_grouped = experiences.get("grouped", [])
    skill_items = skills.get("items", [])
    skill_categories = skills.get("categories", {})

    master["version"] = master.get("version", "1.0.0")
    master["source_file"] = source_json.name
    master["metadata"] = {
        "total_target_profiles": len(target_profiles),
        "total_achievements": len(exp_items),
        "total_job_roles": len(exp_grouped),
        "total_skills": len(skill_items),
        "total_categories": len(skill_categories)
    }

    if output_path is not None:
        output_path = Path(output_path)
        if output_path != source_json:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(master, f, ensure_ascii=False, indent=2)
            print(f"✅ cv_master.json sincronizado en: {output_path}")

    print(f"✅ Perfil cargado exitosamente desde JSON:")
    print(f"   - Perfiles objetivo: {master['metadata']['total_target_profiles']}")
    print(f"   - Logros atómicos: {master['metadata']['total_achievements']}")
    print(f"   - Roles de experiencia: {master['metadata']['total_job_roles']}")
    print(f"   - Habilidades: {master['metadata']['total_skills']} en {master['metadata']['total_categories']} categorías.")

    return master


def build_master(source_path: Path = None, output_path: Path = None) -> Dict[str, Any]:
    """
    Función orquestadora principal que lee la fuente canónica (Excel o JSON)
    y produce/valida data/cv_master.json.
    """
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"

    if output_path is None:
        output_path = data_dir / "cv_master.json"
    else:
        output_path = Path(output_path)

    # Si se pasó explícitamente un archivo JSON
    if source_path is not None and str(source_path).lower().endswith(".json"):
        return load_and_validate_json_master(source_path, output_path)

    excel_file = None
    if source_path is not None:
        source_p = Path(source_path)
        if source_p.exists() and source_p.suffix.lower() in [".xlsx", ".xlsm"]:
            excel_file = source_p
    else:
        excel_file = find_excel_file(data_dir)

    # Si no hay archivo Excel, operar directamente en modo JSON
    if excel_file is None:
        json_target = data_dir / "cv_master.json"
        if not json_target.exists():
            template_path = data_dir / "cv_master.template.json"
            if template_path.exists():
                print(f"ℹ️ Inicializando cv_master.json a partir de la plantilla: {template_path.name}")
                json_target = template_path
            else:
                raise FileNotFoundError(
                    f"No se encontró archivo Excel ni plantilla JSON en {data_dir}. "
                    f"Crea 'data/cv_master.json' o 'data/cv_master.template.json'."
                )
        return load_and_validate_json_master(json_target, output_path)

    print(f"📖 Leyendo fuente canónica desde Excel: {excel_file}")

    # Leer datos del libro Excel
    sheets_data = {}
    try:
        import openpyxl
        wb = openpyxl.load_workbook(excel_file, data_only=True)
        for name in wb.sheetnames:
            sheet = wb[name]
            rows = []
            for row in sheet.iter_rows(values_only=True):
                rows.append(list(row))
            sheets_data[name] = rows
    except Exception as e:
        print(f"⚠️ openpyxl no disponible o falló ({e}), recurriendo al parser XML nativo...")
        sheets_data = read_excel_zip(excel_file)

    # Buscar hojas (tolerante a mayúsculas/minúsculas y acentos)
    def find_sheet(target_names):
        for target in target_names:
            for actual_name in sheets_data.keys():
                if actual_name.strip().lower() == target.strip().lower():
                    return sheets_data[actual_name]
        return []

    perfil_rows = find_sheet(["Perfil", "Profile"])
    experiencias_rows = find_sheet(["Experiencias", "Experiencia", "Experiences", "Experience"])
    habilidades_rows = find_sheet(["Habilidades", "Skills", "Competencias"])

    perfil = parse_perfil(perfil_rows)
    experiencias = parse_experiencias(experiencias_rows)
    habilidades = parse_habilidades(habilidades_rows)

    master = {
        "source_file": excel_file.name,
        "version": "1.0.0",
        "profile": perfil,
        "experiences": experiencias,
        "skills": habilidades,
        "metadata": {
            "total_target_profiles": len(perfil["target_profiles"]),
            "total_achievements": len(experiencias["items"]),
            "total_job_roles": len(experiencias["grouped"]),
            "total_skills": len(habilidades["items"]),
            "total_categories": len(habilidades["categories"])
        }
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False, indent=2)

    print(f"✅ cv_master.json compilado exitosamente en: {output_path}")
    print(f"   - Perfiles objetivo detectados: {master['metadata']['total_target_profiles']}")
    print(f"   - Logros atómicos cargados: {master['metadata']['total_achievements']}")
    print(f"   - Roles de experiencia agrupados: {master['metadata']['total_job_roles']}")
    print(f"   - Habilidades registradas: {master['metadata']['total_skills']} en {master['metadata']['total_categories']} categorías.")

    return master


if __name__ == "__main__":
    source_arg = sys.argv[1] if len(sys.argv) > 1 else None
    out_arg = sys.argv[2] if len(sys.argv) > 2 else None
    build_master(source_arg, out_arg)
