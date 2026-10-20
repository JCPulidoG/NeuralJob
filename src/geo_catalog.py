"""
geo_catalog.py
Catálogo canónico de entidades federativas, ciudades y coordenadas geográficas de México y modalidades de trabajo.
Cumple con la regla de CERO HARDCODE en datos personales.
Permite la normalización determinista de ubicaciones extraídas de portales de empleo y clasificación de modalidad.
"""

import re
from typing import Dict, Any, List, Optional, Tuple

# Catálogo canónico con coordenadas geográficas representativas
LOCATIONS_CATALOG = {
    "Ciudad de México (Toda la CDMX)": {
        "state": "Ciudad de México",
        "city": "Ciudad de México",
        "lat": 19.4326,
        "lon": -99.1332,
        "aliases": [
            "cdmx", "distrito federal", "df", "mexico city", "ciudad de mexico",
            "santa fe", "polanco", "insurgentes", "reforma", "azcapotzalco",
            "benito juarez", "cuauhtemoc", "miguel hidalgo", "alvaro obregon",
            "coyoacan", "tlalpan", "iztapalapa", "gustavo a madero", "venustiano carranza",
            "cuajimalpa", "magdalena contreras", "xochimilco", "tlahuac", "milpa alta"
        ]
    },
    "Valle de Toluca": {
        "state": "Estado de México",
        "city": "Toluca",
        "lat": 19.2826,
        "lon": -99.6557,
        "aliases": [
            "toluca", "metepec", "lerma", "san mateo atenco", "zinacantepec",
            "almoloya", "valle de toluca", "ocoyoacac", "toluca de lerdo", "zona industrial toluca"
        ]
    },
    "Estado de México - Conurbado": {
        "state": "Estado de México",
        "city": "Naucalpan / Tlalnepantla",
        "lat": 19.4785,
        "lon": -99.2396,
        "aliases": [
            "naucalpan", "tlalnepantla", "huixquilucan", "interlomas", "cuautitlan",
            "cuautitlan izcalli", "ecatepec", "nezahualcoyotl", "atizapan", "satelite", "tultitlan"
        ]
    },
    "Jalisco - Guadalajara": {
        "state": "Jalisco",
        "city": "Guadalajara",
        "lat": 20.6597,
        "lon": -103.3496,
        "aliases": ["guadalajara", "gdl", "jalisco", "jal", "zapopan", "tlaquepaque", "tonala", "puerto vallarta"]
    },
    "Nuevo León - Monterrey": {
        "state": "Nuevo León",
        "city": "Monterrey",
        "lat": 25.6866,
        "lon": -100.3161,
        "aliases": ["monterrey", "mty", "nuevo leon", "nl", "san pedro garza garcia", "san pedro", "san nicolas", "santa catarina", "apodaca", "guadalupe"]
    },
    "Querétaro - Santiago de Querétaro": {
        "state": "Querétaro",
        "city": "Querétaro",
        "lat": 20.5888,
        "lon": -100.3899,
        "aliases": ["queretaro", "qro", "santiago de queretaro", "juriquilla", "el marques", "corregidora"]
    },
    "Puebla - Puebla": {
        "state": "Puebla",
        "city": "Puebla",
        "lat": 19.0414,
        "lon": -98.2063,
        "aliases": ["puebla", "cholula", "angelopolis"]
    },
    "Guanajuato - León": {
        "state": "Guanajuato",
        "city": "León",
        "lat": 21.1221,
        "lon": -101.6826,
        "aliases": ["leon", "guanajuato", "gto", "irapuato", "celaya", "silao"]
    },
    "Coahuila - Saltillo / Ramos Arizpe": {
        "state": "Coahuila",
        "city": "Saltillo",
        "lat": 25.4383,
        "lon": -100.9737,
        "aliases": ["saltillo", "coahuila", "ramos arizpe", "torreon", "monclova"]
    },
    "San Luis Potosí - San Luis Potosí": {
        "state": "San Luis Potosí",
        "city": "San Luis Potosí",
        "lat": 22.1565,
        "lon": -100.9855,
        "aliases": ["san luis potosi", "slp", "ciudad valles", "matehuala", "soledad"]
    },
    "Yucatán - Mérida": {
        "state": "Yucatán",
        "city": "Mérida",
        "lat": 20.9674,
        "lon": -89.5926,
        "aliases": ["merida", "yucatan", "yuc", "progreso"]
    },
    "Baja California - Tijuana": {
        "state": "Baja California",
        "city": "Tijuana",
        "lat": 32.5149,
        "lon": -117.0382,
        "aliases": ["tijuana", "baja california", "bc", "mexicali", "ensenada"]
    },
    "Chihuahua - Ciudad Juárez / Chihuahua": {
        "state": "Chihuahua",
        "city": "Chihuahua",
        "lat": 28.6330,
        "lon": -106.0691,
        "aliases": ["chihuahua", "ciudad juarez", "juarez", "chih"]
    },
    "Aguascalientes - Aguascalientes": {
        "state": "Aguascalientes",
        "city": "Aguascalientes",
        "lat": 21.8853,
        "lon": -102.2916,
        "aliases": ["aguascalientes", "ags"]
    },
    "Veracruz - Veracruz / Xalapa": {
        "state": "Veracruz",
        "city": "Veracruz",
        "lat": 19.1738,
        "lon": -96.1342,
        "aliases": ["veracruz", "xalapa", "boca del rio", "coatzacoalcos", "orizaba"]
    },
    "Sinaloa - Culiacán / Mazatlán": {
        "state": "Sinaloa",
        "city": "Culiacán",
        "lat": 24.8091,
        "lon": -107.3940,
        "aliases": ["culiacan", "mazatlan", "sinaloa", "sin", "los mochis"]
    },
    "Remoto - México": {
        "state": "Remoto",
        "city": "México",
        "lat": 23.6345,  # Centro geográfico de México
        "lon": -102.5528,
        "aliases": ["remoto", "remote", "home office", "teletrabajo", "trabajo remoto", "remoto mexico", "remote mexico", "virtual"]
    },
    "Remoto - Global": {
        "state": "Remoto",
        "city": "Internacional",
        "lat": 25.0000,
        "lon": -100.0000,
        "aliases": ["global remote", "worldwide", "remote latam", "latam", "international"]
    }
}

# Opciones canónicas de búsqueda geográfica (presets)
SEARCH_LOCATION_PRESETS = [
    "Toda la CDMX",
    "Valle de Toluca",
    "CDMX y Valle de Toluca",
    "Toda la República Mexicana",
    "Nuevo León - Monterrey",
    "Jalisco - Guadalajara",
    "Querétaro",
    "Personalizada (escribir...)"
]


def get_search_location_string(preset: str, custom_text: str = "") -> str:
    """
    Convierte el preset seleccionado en una cadena de búsqueda óptima para los portales.
    """
    preset_lower = (preset or "").strip().lower()
    if "cdmx y valle de toluca" in preset_lower:
        return "Ciudad de México y Toluca, México"
    elif "toda la cdmx" in preset_lower or "ciudad de méxico" in preset_lower:
        return "Ciudad de México, México"
    elif "valle de toluca" in preset_lower or "toluca" in preset_lower:
        return "Toluca, Estado de México, México"
    elif "república mexicana" in preset_lower or "toda la rep" in preset_lower or "méxico" in preset_lower:
        return "México"
    elif "monterrey" in preset_lower:
        return "Monterrey, Nuevo León, México"
    elif "guadalajara" in preset_lower:
        return "Guadalajara, Jalisco, México"
    elif "querétaro" in preset_lower or "queretaro" in preset_lower:
        return "Querétaro, México"
    elif custom_text and custom_text.strip():
        return custom_text.strip()
    return "Ciudad de México, México"


def get_catalog_options() -> List[str]:
    """Devuelve la lista ordenada de opciones canónicas de ubicación con CDMX y Toluca arriba"""
    priority = [
        "Todas las Ubicaciones",
        "Toda la CDMX",
        "Valle de Toluca",
        "CDMX y Valle de Toluca",
        "Toda la República Mexicana"
    ]
    other_keys = [k for k in sorted(LOCATIONS_CATALOG.keys()) if k not in priority]
    return priority + other_keys


def get_states_options() -> List[str]:
    """Devuelve la lista de estados únicos presentes en el catálogo"""
    states = sorted(list({info["state"] for info in LOCATIONS_CATALOG.values()}))
    return ["Todos los Estados"] + states


def detect_modality(text: str = "", location_text: str = "") -> str:
    """
    Determina determinísticamente si una vacante es 'remoto', 'hibrido' o 'presencial'.
    """
    combined = f"{text or ''} {location_text or ''}".lower()
    # Híbrido tiene prioridad cuando se mencionan esquemas combinados
    if any(term in combined for term in [
        "híbrido", "hibrido", "hybrid", "esquema mixto", "semipresencial",
        "días home office", "dias home office", "días de oficina", "dias de oficina",
        "presencial / remoto", "remoto / presencial"
    ]):
        return "hibrido"
    elif any(term in combined for term in [
        "remoto", "remote", "home office", "teletrabajo", "100% remoto",
        "100% remote", "virtual", "trabajo desde casa", "wfh"
    ]):
        return "remoto"
    elif any(term in combined for term in [
        "presencial", "en sitio", "on-site", "onsite", "en oficina"
    ]):
        return "presencial"
    return "no_especificado"


def normalize_location(raw_text: str) -> Dict[str, Any]:
    """
    Normaliza cualquier texto de ubicación extraído de un portal hacia el catálogo canónico.
    Retorna un diccionario con catalog_name, state, city, lat, lon y si es remoto.
    """
    if not raw_text or str(raw_text).strip().lower() in ["nan", "none", ""]:
        entry = LOCATIONS_CATALOG["Ciudad de México (Toda la CDMX)"]
        return {
            "catalog_name": "Ciudad de México (Toda la CDMX)",
            "state": entry["state"],
            "city": entry["city"],
            "lat": entry["lat"],
            "lon": entry["lon"],
            "is_remote": False,
            "raw": ""
        }

    raw_lower = str(raw_text).lower()

    # 1. Verificar si contiene mención explícita de remoto
    if any(alias in raw_lower for alias in LOCATIONS_CATALOG["Remoto - México"]["aliases"]):
        entry = LOCATIONS_CATALOG["Remoto - México"]
        return {
            "catalog_name": "Remoto - México",
            "state": entry["state"],
            "city": entry["city"],
            "lat": entry["lat"],
            "lon": entry["lon"],
            "is_remote": True,
            "raw": raw_text
        }

    # 2. Prioridad a Valle de Toluca si contiene municipios específicos
    for alias in LOCATIONS_CATALOG["Valle de Toluca"]["aliases"]:
        pattern = r'(?:\b|_)' + re.escape(alias) + r'(?:\b|_)'
        if re.search(pattern, raw_lower):
            entry = LOCATIONS_CATALOG["Valle de Toluca"]
            return {
                "catalog_name": "Valle de Toluca",
                "state": entry["state"],
                "city": entry["city"],
                "lat": entry["lat"],
                "lon": entry["lon"],
                "is_remote": False,
                "raw": raw_text
            }

    # 3. Prioridad a CDMX
    for alias in LOCATIONS_CATALOG["Ciudad de México (Toda la CDMX)"]["aliases"]:
        pattern = r'(?:\b|_)' + re.escape(alias) + r'(?:\b|_)'
        if re.search(pattern, raw_lower):
            entry = LOCATIONS_CATALOG["Ciudad de México (Toda la CDMX)"]
            return {
                "catalog_name": "Ciudad de México (Toda la CDMX)",
                "state": entry["state"],
                "city": entry["city"],
                "lat": entry["lat"],
                "lon": entry["lon"],
                "is_remote": False,
                "raw": raw_text
            }

    # 4. Buscar coincidencias en los alias de cada otra ciudad/estado
    for name, info in LOCATIONS_CATALOG.items():
        if name.startswith("Remoto") or name in ["Valle de Toluca", "Ciudad de México (Toda la CDMX)"]:
            continue
        for alias in info["aliases"]:
            pattern = r'(?:\b|_)' + re.escape(alias) + r'(?:\b|_)'
            if re.search(pattern, raw_lower):
                return {
                    "catalog_name": name,
                    "state": info["state"],
                    "city": info["city"],
                    "lat": info["lat"],
                    "lon": info["lon"],
                    "is_remote": False,
                    "raw": raw_text
                }

    # 5. Si solo dice "Mexico" o "México"
    if "mexico" in raw_lower or "méxico" in raw_lower or "mx" in raw_lower:
        entry = LOCATIONS_CATALOG["Ciudad de México (Toda la CDMX)"]
        return {
            "catalog_name": "Ciudad de México (Toda la CDMX)",
            "state": entry["state"],
            "city": entry["city"],
            "lat": entry["lat"],
            "lon": entry["lon"],
            "is_remote": False,
            "raw": raw_text
        }

    # Fallback determinista
    entry = LOCATIONS_CATALOG["Ciudad de México (Toda la CDMX)"]
    return {
        "catalog_name": "Ciudad de México (Toda la CDMX)",
        "state": entry["state"],
        "city": entry["city"],
        "lat": entry["lat"],
        "lon": entry["lon"],
        "is_remote": False,
        "raw": raw_text
    }


if __name__ == "__main__":
    test_cases = [
        "Guadalajara, JAL, MX",
        "Monterrey, Nuevo León, Mexico",
        "Metepec, Estado de México",
        "Toluca de Lerdo, Méx.",
        "Polanco, Miguel Hidalgo, CDMX",
        "Santa Fe, Ciudad de México",
        "Work from home / Remote",
        "Esquema Híbrido, Reforma, CDMX"
    ]
    print("Probando normalizador de ubicaciones y modalidad:")
    for tc in test_cases:
        norm = normalize_location(tc)
        mod = detect_modality(tc, tc)
        print(f"  '{tc}' -> {norm['catalog_name']} ({norm['state']}) | Mod: {mod}")
