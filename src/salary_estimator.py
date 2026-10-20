"""
salary_estimator.py
Motor inteligente de estimación y extracción salarial para el mercado mexicano.
Especializado en perfiles de Ciencia de Datos, Arquitectura Cloud y Riesgo Cuantitativo.

Cumple con la regla de CERO HARDCODE:
- Detecta sueldos declarados explícitamente en el texto de la vacante mediante regex.
- Cuando el sueldo es confidencial, calcula un rango heurístico basado en:
  1. Seniority del puesto (Trainee, Junior, Especialista/Mid, Senior, Lead/Arquitecto, Gerente/Subdirector, Director).
  2. Especialización técnica (Riesgo Financiero/AMIB, Big Data/Cloud, Machine Learning, BI/Analítica).
  3. Tier empresarial (Banca Institucional, Big Tech/Consultora Global, Corporativo estándar).
  4. Moneda y modalidad (USD / MXN / Remoto Internacional).
- Evalúa alertas de sobrecalificación frente a perfiles directivos/senior (15+ años).
"""

import re
from typing import Dict, Any, Optional, Tuple


# Tabuladores base mensuales en MXN para roles de Tecnología y Datos en México (2025/2026)
SENIORITY_BASE_RANGES = {
    "intern": (12000, 22000, "Becario / Trainee"),
    "junior": (22000, 38000, "Junior / Asociado"),
    "mid_especialista": (38000, 60000, "Especialista / Analista"),
    "senior": (60000, 85000, "Senior / Consultor"),
    "lead_architect": (80000, 115000, "Líder Técnico / Arquitecto"),
    "manager": (95000, 145000, "Gerente / Subdirector"),
    "director": (145000, 240000, "Director / C-Level")
}

# Primas técnicas sobre el sueldo base
TRACK_MULTIPLIERS = {
    "quant_risk": 1.20,     # +20% por riesgo cuantitativo, AMIB 3, derivados, trading bursátil
    "big_data_cloud": 1.18, # +18% por Databricks, PySpark, Lakehouse, Arquitectura Cloud
    "data_science_ml": 1.12,# +12% por Machine Learning, Modelos Predictivos, IA
    "bi_analytics": 1.0     # Base estándar para analítica y reportería
}

# Empresas con tabuladores institucionales superiores (+15%)
TIER1_COMPANIES = {
    "santander", "bbva", "banorte", "citi", "banamex", "actinver", "profuturo",
    "hsbc", "scotiabank", "jp morgan", "inbursa", "banco azteca", "monex",
    "capgemini", "accenture", "globant", "microsoft", "amazon", "aws", "google", "oracle"
}


def detect_declared_salary(text: str) -> Optional[Dict[str, Any]]:
    """
    Busca patrones de salario explícito en el texto (ej. $35,000 - $45,000, 50k a 60k, $3,000 USD).
    """
    if not text or len(text.strip()) < 5:
        return None

    clean_text = text.lower()

    # Detección de USD
    is_usd = bool(re.search(r'\b(usd|dólares|dolares|dollars|\$\s*usd)\b', clean_text))
    exchange_rate = 20.0 if is_usd else 1.0

    # Patrón 1: Rango explícito con signos de pesos o k (ej. "$45,000 - $60,000", "45k - 60k", "50,000 a 70,000")
    range_pattern = r'(?:\$|\bs/\.|\beur|\busd)?\s*(\d{1,3}(?:[,\.]\d{3})*|\d{2,3}k)\s*(?:-|–|a|hasta)\s*(?:\$|\bs/\.|\beur|\busd)?\s*(\d{1,3}(?:[,\.]\d{3})*|\d{2,3}k)\s*(?:mxn|usd|pesos|netos|brutos|mensuales|mensual|\/mes)?'
    m_range = re.search(range_pattern, clean_text)
    if m_range:
        v1_str, v2_str = m_range.group(1), m_range.group(2)
        try:
            v1 = _parse_salary_number(v1_str)
            v2 = _parse_salary_number(v2_str)
            if v1 and v2 and 8000 <= v1 * exchange_rate <= 350000 and 8000 <= v2 * exchange_rate <= 350000:
                s_min = min(v1, v2) * exchange_rate
                s_max = max(v1, v2) * exchange_rate
                return {
                    "salary_min": round(s_min, -2),
                    "salary_max": round(s_max, -2),
                    "currency": "USD" if is_usd else "MXN",
                    "display": f"${s_min:,.0f} - ${s_max:,.0f} {'USD' if is_usd else 'MXN'}/mes (Declarado)",
                    "is_declared": True
                }
        except Exception:
            pass

    # Patrón 2: Sueldo único explícito (ej. "Sueldo: $55,000 brutos", "Salario: 45k mensuales")
    single_pattern = r'(?:sueldo|salario|remuneración|compensación|pago)(?:\s*(?:de|mensual|bruto|neto|estimado)?\s*:\s*|\s+(?:de|hasta)\s+)(?:\$)?\s*(\d{1,3}(?:[,\.]\d{3})*|\d{2,3}k)\s*(?:mxn|usd|pesos|netos|brutos|mensuales|mensual|\/mes)?'
    m_single = re.search(single_pattern, clean_text)
    if m_single:
        v_str = m_single.group(1)
        val = _parse_salary_number(v_str)
        if val and 8000 <= val * exchange_rate <= 350000:
            s_val = val * exchange_rate
            return {
                "salary_min": round(s_val * 0.9, -2),
                "salary_max": round(s_val * 1.1, -2),
                "currency": "USD" if is_usd else "MXN",
                "display": f"${s_val:,.0f} {'USD' if is_usd else 'MXN'}/mes (Declarado)",
                "is_declared": True
            }

    return None


def _parse_salary_number(num_str: str) -> Optional[float]:
    """Parsea representaciones como '45,000', '45.000', '45k' a float"""
    if not num_str:
        return None
    s = num_str.strip().lower()
    if s.endswith('k'):
        try:
            return float(s[:-1]) * 1000.0
        except ValueError:
            return None
    s = s.replace(',', '').replace('.', '')
    try:
        val = float(s)
        # Si es un número anual (ej. 600,000), dividir entre 12
        if val > 350000:
            val = val / 12.0
        return val
    except ValueError:
        return None


def detect_seniority(title: str, description: str = "") -> Tuple[str, str]:
    """
    Identifica el nivel de seniority a partir del título y el texto de la vacante.
    Retorna (seniority_key, human_label).
    """
    text = f"{title} {description[:400]}".lower()

    # Director / C-Level
    if re.search(r'\b(director|vp|vicepresidente|c-level|cto|cdo|head of)\b', text):
        return "director", SENIORITY_BASE_RANGES["director"][2]

    # Gerente / Subdirector / Manager
    if re.search(r'\b(gerente|subdirector|manager|subgerente|jefe de|lead manager)\b', text):
        return "manager", SENIORITY_BASE_RANGES["manager"][2]

    # Líder Técnico / Arquitecto / Principal
    if re.search(r'\b(líder|lider|architect|arquitecto|tech lead|technical lead|principal|team lead)\b', text):
        return "lead_architect", SENIORITY_BASE_RANGES["lead_architect"][2]

    # Senior / Consultor Sr
    if re.search(r'\b(senior|sr|sr\.|consultor sr|consultor senior|investigador sr)\b', text):
        return "senior", SENIORITY_BASE_RANGES["senior"][2]

    # Becario / Trainee / Intern
    if re.search(r'\b(becario|trainee|intern|pasante|practicante|estudiante)\b', text):
        return "intern", SENIORITY_BASE_RANGES["intern"][2]

    # Junior
    if re.search(r'\b(junior|jr|jr\.|entry level|asociado jr|analista jr)\b', text):
        return "junior", SENIORITY_BASE_RANGES["junior"][2]

    # Especialista / Analista / Mid (Nivel operativo bancario)
    if re.search(r'\b(especialista|specialist|analista|analyst|ingeniero|desarrollador|consultor|coordinador)\b', text):
        return "mid_especialista", SENIORITY_BASE_RANGES["mid_especialista"][2]

    return "mid_especialista", SENIORITY_BASE_RANGES["mid_especialista"][2]


def detect_track(title: str, description: str = "") -> Tuple[str, float]:
    """
    Detecta la especialización técnica para aplicar el factor multiplicador correspondiente.
    """
    text = f"{title} {description}".lower()

    if re.search(r'\b(riesgo|risk|quant|cuantitativo|var|cvar|amib|trading|mesa de dinero|bonos|derivados|bursatil|bursátil)\b', text):
        return "quant_risk", TRACK_MULTIPLIERS["quant_risk"]

    if re.search(r'\b(pyspark|databricks|big data|arquitectura de datos|lakehouse|delta lake|data engineer|cloud|medallion)\b', text):
        return "big_data_cloud", TRACK_MULTIPLIERS["big_data_cloud"]

    if re.search(r'\b(machine learning|data scientist|cientifico de datos|deep learning|mlops|ia|ai|nlp)\b', text):
        return "data_science_ml", TRACK_MULTIPLIERS["data_science_ml"]

    return "bi_analytics", TRACK_MULTIPLIERS["bi_analytics"]


def estimate_job_salary(
    title: str,
    company: str,
    description: str = "",
    candidate_seniority_years: int = 15
) -> Dict[str, Any]:
    """
    Calcula el rango salarial estimado para la vacante y evalúa riesgo de sobrecalificación.
    """
    # 1. Verificar si hay sueldo declarado explícitamente
    full_text = f"{title} {description}"
    declared = detect_declared_salary(full_text)
    seniority_key, seniority_label = detect_seniority(title, description)
    track_key, track_mult = detect_track(title, description)

    is_tier1 = any(t in company.lower() for t in TIER1_COMPANIES)
    tier_mult = 1.15 if is_tier1 else 1.0

    if declared:
        salary_min = declared["salary_min"]
        salary_max = declared["salary_max"]
        currency = declared["currency"]
        display_str = declared["display"]
        is_declared = True
    else:
        # 2. Estimación Heurística de Mercado
        base_min, base_max, _ = SENIORITY_BASE_RANGES[seniority_key]
        total_mult = track_mult * tier_mult

        salary_min = round((base_min * total_mult) / 1000.0) * 1000.0
        salary_max = round((base_max * total_mult) / 1000.0) * 1000.0
        currency = "MXN"
        display_str = f"${salary_min:,.0f} - ${salary_max:,.0f} MXN/mes (Estimado)"
        is_declared = False

    # 3. Alerta de Sobrecalificación
    # Si el candidato tiene 15+ años (Senior/Líder/Gerente) y la vacante es operativa (Especialista/Jr/Becario)
    overqualification_warning = None
    if candidate_seniority_years >= 12 and seniority_key in ["intern", "junior", "mid_especialista"]:
        overqualification_warning = (
            f"⚠️ Puesto Operativo ({seniority_label}): Tabulador estimado (${salary_min:,.0f} - ${salary_max:,.0f} MXN) "
            f"inferior a tu nivel de experiencia directiva/gerencial. Alto riesgo de auto-descarte por sobrecalificación en ATS."
        )

    return {
        "salary_min": float(salary_min),
        "salary_max": float(salary_max),
        "salary_currency": currency,
        "salary_display": display_str,
        "is_declared": is_declared,
        "seniority_key": seniority_key,
        "seniority_label": seniority_label,
        "track_key": track_key,
        "is_tier1": is_tier1,
        "overqualification_warning": overqualification_warning
    }


if __name__ == "__main__":
    # Test cases
    test_jobs = [
        ("Especialista de Procesos y Análisis de Datos", "Santander México", "Mapeo de procesos y reportería básica."),
        ("Líder Arquitecto de Estrategia de Datos & Big Data", "Profuturo", "Arquitectura Medallion en Databricks y PySpark."),
        ("Gerente de Riesgos Cuantitativos", "Banco Actinver", "Modelado VaR, CVaR y simulaciones Monte Carlo AMIB 3."),
        ("Data Analyst Jr", "Startup X", "Sueldo: $28,000 - $35,000 netos mensuales."),
        ("Senior Machine Learning Engineer", "Capgemini", "Despliegue de modelos MLOps y Databricks.")
    ]

    for t, c, d in test_jobs:
        res = estimate_job_salary(t, c, d)
        print(f"\n📌 {t} ({c})")
        print(f"   Sueldo: {res['salary_display']}")
        print(f"   Seniority: {res['seniority_label']} | Track: {res['track_key']} | Tier 1: {res['is_tier1']}")
        if res['overqualification_warning']:
            print(f"   {res['overqualification_warning']}")
