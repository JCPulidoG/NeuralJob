"""
company_intel.py
Módulo de Inteligencia Empresarial.
Proporciona enriquecimiento contextual sobre las empresas empleadoras:
- Tamaño de la empresa (Enterprise, Scale-up, Mid-market)
- Sector / Industria
- Etapa de crecimiento
- Enfoque tecnológico y stack principal
- Resumen ejecutivo del negocio y modelo operativo
"""

import re
from typing import Dict, Any, Optional

# Base de conocimiento enriquecida de empleadores conocidos
COMPANY_DATABASE = {
    "Netflix": {
        "sector": "Entretenimiento Digital & Big Tech",
        "size": "Enterprise (13,000+ empleados)",
        "growth_stage": "Big Tech Global (S&P 100)",
        "tech_focus": "Sistemas Distribuidos, ML Avanzado, Microservicios, Cloud Nativo (AWS), Algoritmos de Recomendación",
        "headquarters": "Los Gatos, California, EE. UU.",
        "description": "Líder mundial en servicios de entretenimiento por streaming con presencia en más de 190 países y fuerte cultura de ingeniería basada en datos."
    },
    "Banamex": {
        "sector": "Banca Múltiple & Servicios Financieros",
        "size": "Enterprise (40,000+ empleados)",
        "growth_stage": "Institución Financiera Sistémica",
        "tech_focus": "Core Bancario, Big Data, SQL Server, Cumplimiento Regulatorio (CNBV/Banxico), Modelos de Riesgo",
        "headquarters": "Ciudad de México, México",
        "description": "Uno de los bancos más antiguos y representativos de México, con sólida infraestructura en crédito, banca corporativa y de consumo."
    },
    "Citi": {
        "sector": "Banca Global & Mercados de Capital",
        "size": "Enterprise (240,000+ empleados)",
        "growth_stage": "Gigante Financiero Global",
        "tech_focus": "FinTech Corporativo, Trading Desk, Riesgo Cuantitativo, Python, Databricks, Cloud Híbrida",
        "headquarters": "Nueva York, EE. UU.",
        "description": "Banco de inversión y servicios financieros global con operaciones en más de 160 países y liderazgo en transacciones transfronterizas."
    },
    "EY": {
        "sector": "Consultoría Financiera, Auditoría & Riesgos (Big 4)",
        "size": "Enterprise (395,000+ empleados)",
        "growth_stage": "Líder Global de Servicios Profesionales",
        "tech_focus": "Modelos Cuantitativos de Riesgo, Finanzas Corporativas, Power BI, Python, Transformación Digital",
        "headquarters": "Londres, Reino Unido",
        "description": "Firma multinacional de servicios profesionales y auditoría líder en consultoría de riesgos de mercado, crédito y normatividad financiera."
    },
    "MSCI Inc.": {
        "sector": "FinTech Cuantitativo, Índices Bursátiles & ESG",
        "size": "Enterprise (5,500+ empleados)",
        "growth_stage": "Alto Margen & Sólido Crecimiento (NYSE: MSCI)",
        "tech_focus": "RiskMetrics, VaR/CVaR, Analítica Bursátil, Python, C++, Modelado Financiero de Portafolios",
        "headquarters": "Nueva York, EE. UU.",
        "description": "Proveedor global de herramientas de soporte a la toma de decisiones para inversores institucionales, reconocido mundialmente por sus índices y modelos de riesgo."
    },
    "SURA México": {
        "sector": "Gestión de Activos, Afores & Seguros",
        "size": "Enterprise (10,000+ empleados)",
        "growth_stage": "Líder Institucional en Pensiones y Ahorro",
        "tech_focus": "Regulatorio CONSAR, DWH Financiero, Series de Tiempo, Power BI, Python para Inversiones",
        "headquarters": "Medellín, Colombia / CDMX, México",
        "description": "Compañía multinacional de servicios financieros líder en gestión de activos, pensiones obligatorias y voluntarias en América Latina."
    },
    "Boston Consulting Group (BCG)": {
        "sector": "Consultoría Estratégica & Inteligencia Artificial (BCG X)",
        "size": "Enterprise (32,000+ empleados)",
        "growth_stage": "Top 3 Consultoría Estratégica Global (MBB)",
        "tech_focus": "IA Generativa, Deep Tech, Machine Learning Avanzado, MLOps, Python, Cloud Computing",
        "headquarters": "Boston, Massachusetts, EE. UU.",
        "description": "Firma global de consultoría de gestión pionera en estrategia de negocios, innovación tecnológica y despliegue de soluciones de IA a gran escala."
    },
    "Accenture México": {
        "sector": "Consultoría Tecnológica & Servicios Digitales",
        "size": "Enterprise (730,000+ empleados)",
        "growth_stage": "Líder Mundial en Servicios IT y Cloud",
        "tech_focus": "Multi-cloud (Azure, AWS, GCP), Databricks, PySpark, Arquitecturas Empresariales, Data & AI",
        "headquarters": "Dublín, Irlanda / CDMX, México",
        "description": "Líder global en servicios profesionales con capacidades avanzadas en tecnología, operaciones, nube e inteligencia artificial para corporativos globales."
    },
    "Takeda": {
        "sector": "Farmacéutica Global & Biotecnología",
        "size": "Enterprise (50,000+ empleados)",
        "growth_stage": "Top 10 Farmacéutica Mundial",
        "tech_focus": "Bioestadística, Data Science para I+D, R, Python, Analítica Clínica y Epidemiológica",
        "headquarters": "Tokio, Japón",
        "description": "Compañía biofarmacéutica global centrada en I+D orientada a terapias avanzadas en oncología, enfermedades raras y neurociencia."
    },
    "Johnson Controls": {
        "sector": "Tecnología Industrial & Edificación Inteligente",
        "size": "Enterprise (100,000+ empleados)",
        "growth_stage": "Líder Global en Automatización Inteligente",
        "tech_focus": "Edge AI, Industrial IoT, Machine Learning, Series de Tiempo, Optimización de Energía",
        "headquarters": "Cork, Irlanda / Milwaukee, EE. UU.",
        "description": "Líder mundial en edificios inteligentes, soluciones de sostenibilidad, infraestructura crítica y sistemas de climatización e incendios."
    },
    "Magna International": {
        "sector": "Manufactura Automotriz Tier 1 & Movilidad",
        "size": "Enterprise (170,000+ empleados)",
        "growth_stage": "Líder Global Automotriz (Fortune 500)",
        "tech_focus": "Visión Artificial, Mantenimiento Predictivo, Robótica, Industrial IoT, Python",
        "headquarters": "Aurora, Ontario, Canadá",
        "description": "Uno de los mayores proveedores automotrices del mundo, suministrador de sistemas de propulsión, chasis y electrónica a los principales fabricantes de autos."
    },
    "Ingredion": {
        "sector": "Manufactura & Alimentos (Fortune 500)",
        "size": "Enterprise (12,000+ empleados)",
        "growth_stage": "Líder Global en Ingredientes y Alimentos",
        "tech_focus": "SAP, Salesforce CRM, Analítica de Cadena de Suministro, Power BI, Automatización",
        "headquarters": "Westchester, Illinois, EE. UU.",
        "description": "Proveedor global de soluciones de ingredientes con presencia en más de 120 países, enfocado en texturizantes y edulcorantes de origen vegetal."
    },
    "PayJoy": {
        "sector": "FinTech & Inclusión Financiera",
        "size": "Scale-up (500 - 1,000 empleados)",
        "growth_stage": "Scale-up de Alto Crecimiento y Rentabilidad",
        "tech_focus": "Machine Learning para Scoring Crediticio, Python, Microservicios, Mobile Tech, Cloud AWS",
        "headquarters": "San Francisco, California, EE. UU.",
        "description": "Fintech global de alto impacto que permite a clientes en mercados emergentes acceder a crédito y smartphones mediante tecnología patentada."
    },
    "Quora": {
        "sector": "Tecnología de Consumo & Plataforma de IA (Poe)",
        "size": "Scale-up (500 - 1,000 empleados)",
        "growth_stage": "Scale-up Consolidada e Innovadora",
        "tech_focus": "LLMs, Modelos de Lenguaje, Sistemas de Recomendación, Python, PyTorch, Infraestructura AI",
        "headquarters": "Mountain View, California, EE. UU.",
        "description": "Plataforma de preguntas y respuestas y creadores de Poe, ecosistema abierto para interacción y monetización con agentes y modelos de IA generativa."
    },
    "Elsevier": {
        "sector": "Información Científica, Médica & Analítica",
        "size": "Enterprise (9,000+ empleados)",
        "growth_stage": "Líder Global en Publicaciones Científicas",
        "tech_focus": "NLP, Grafos de Conocimiento, Big Data, Python, Scikit-learn, AWS",
        "headquarters": "Ámsterdam, Países Bajos",
        "description": "Empresa global de análisis de información que ayuda a instituciones y profesionales médicos y científicos a mejorar la salud y la ciencia."
    },
    "RELX": {
        "sector": "Analítica de Datos & Herramientas de Decisión",
        "size": "Enterprise (35,000+ empleados)",
        "growth_stage": "Gigante de Información y Analítica (FTSE 100)",
        "tech_focus": "Big Data Analytics, Prevención de Fraude, Machine Learning, Cloud Híbrida",
        "headquarters": "Londres, Reino Unido",
        "description": "Matriz de Elsevier y LexisNexis, proveedor global de analítica basada en información y herramientas de toma de decisiones para clientes profesionales."
    },
    "Stand8 Technology Consulting": {
        "sector": "Consultoría IT & Staffing Especializado",
        "size": "Mid-Market (200 - 500 empleados)",
        "growth_stage": "Firma Consultora en Expansión",
        "tech_focus": "SQL Server, Migración a Nube, FinTech Data Solutions, Python",
        "headquarters": "Los Ángeles, California, EE. UU.",
        "description": "Firma de consultoría de tecnología que provee soluciones integrales de infraestructura, ingeniería de datos y talento especializado."
    },
    "World Vision": {
        "sector": "Organización Humanitaria & Desarrollo Global",
        "size": "Enterprise (34,000+ empleados)",
        "growth_stage": "ONG Internacional de Gran Escala",
        "tech_focus": "Sistemas de Información Geográfica, Modelado Estadístico, Power BI, Monitoreo de Impacto",
        "headquarters": "Uxbridge, Reino Unido",
        "description": "Organización global humanitaria y de desarrollo dedicada a mejorar la calidad de vida de niños y comunidades vulnerables en casi 100 países."
    },
    "dss+": {
        "sector": "Consultoría Operativa, Riesgos & Seguridad",
        "size": "Mid-Market (1,000 - 5,000 empleados)",
        "growth_stage": "Firma Global Especializada (Ex DuPont)",
        "tech_focus": "Evaluación Cuantitativa de Riesgo Operacional, Metodologías de Seguridad, Data Analytics",
        "headquarters": "Ginebra, Suiza",
        "description": "Firma consultora global líder en gestión de riesgos operativos, transformación de cultura de seguridad y sustentabilidad industrial."
    }
}


def enrich_company_profile(company_name: str, job_description: str = "") -> Dict[str, Any]:
    """
    Obtiene o infiere la ficha de Inteligencia Empresarial para una empresa dada.
    Si la empresa está en la base de conocimiento, devuelve sus datos verificados.
    Si no, infiere heurísticamente su perfil analizando la descripción del empleo.
    """
    clean_name = company_name.strip() if company_name else "Empresa Confidencial"

    # 1. Búsqueda exacta o parcial en la base de conocimiento
    for k, v in COMPANY_DATABASE.items():
        if k.lower() in clean_name.lower() or clean_name.lower() in k.lower():
            return {
                "company_name": clean_name,
                "sector": v["sector"],
                "size": v["size"],
                "growth_stage": v["growth_stage"],
                "tech_focus": v["tech_focus"],
                "headquarters": v["headquarters"],
                "description": v["description"],
                "is_verified": True
            }

    # 2. Inferencia heurística a partir de la descripción y nombre
    desc_lower = job_description.lower() if job_description else ""

    # Inferir sector
    sector = "Tecnología & Servicios Corporativos"
    if any(w in desc_lower for w in ["banco", "financier", "crédito", "credito", "riesgo", "bursátil", "bursatil", "var", "fintech"]):
        sector = "Banca & FinTech"
    elif any(w in desc_lower for w in ["salud", "farmacéutic", "farmaceutic", "médic", "medic", "hospital"]):
        sector = "Salud & Farma"
    elif any(w in desc_lower for w in ["manufactur", "automotriz", "planta", "industrial", "supply chain"]):
        sector = "Manufactura & Operaciones"
    elif any(w in desc_lower for w in ["retail", "ecommerce", "e-commerce", "consumo masivo"]):
        sector = "Consumo Masivo & Retail"
    elif any(w in desc_lower for w in ["consultor", "consulting", "asesor"]):
        sector = "Consultoría de Negocios & IT"

    # Inferir tamaño
    size = "Mediana Empresa / Mid-Market (500 - 2,000)"
    if any(w in desc_lower for w in ["global", "multinacional", "fortune", "world", "miles de empleados"]):
        size = "Enterprise (+5,000 empleados)"
    elif any(w in desc_lower for w in ["startup", "scaleup", "scale-up", "crecimiento acelerado"]):
        size = "Scale-up Tecnológica (100 - 500)"

    # Inferir stack / tech focus
    techs = []
    if "python" in desc_lower: techs.append("Python")
    if "databricks" in desc_lower or "pyspark" in desc_lower: techs.append("Databricks/PySpark")
    if "sql" in desc_lower: techs.append("SQL Avanzado")
    if "aws" in desc_lower or "azure" in desc_lower or "gcp" in desc_lower or "cloud" in desc_lower: techs.append("Cloud Computing")
    if "machine learning" in desc_lower or "ml" in desc_lower: techs.append("Machine Learning")
    if "power bi" in desc_lower or "tableau" in desc_lower: techs.append("BI & Reporting")
    tech_focus = ", ".join(techs) if techs else "Herramientas de Analítica & Negocio"

    return {
        "company_name": clean_name,
        "sector": sector,
        "size": size,
        "growth_stage": "En Expansión / Consolidación",
        "tech_focus": tech_focus,
        "headquarters": "México / Internacional",
        "description": f"Empresa activa en el sector de {sector.lower()} con proyectos de analítica y desarrollo profesional.",
        "is_verified": False
    }


if __name__ == "__main__":
    test_companies = ["Netflix", "Banamex", "MSCI Inc.", "SURA México", "Mercado Libre", "Empresa Innovadora X"]
    print("Probando enriquecedor de empresas:")
    for c in test_companies:
        info = enrich_company_profile(c, "Buscamos Data Scientist con Python, SQL y Machine Learning para fintech.")
        print(f"  {c} -> {info['sector']} | {info['size']} | Tech: {info['tech_focus'][:40]}... (Verificado: {info['is_verified']})")
