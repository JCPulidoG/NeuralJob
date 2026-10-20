# 🎯 NeuralJob: Motor Local de Prospección Laboral & Generador Dinámico de CVs ATS

Herramienta privada, 100% local, modular y orientada a la privacidad, diseñada para prospección laboral estratégica, análisis de afinidad ATS y generación automatizada de CVs adaptados por rol en **menos de 20 minutos al día**, cumpliendo estrictamente con el **Principio Rector de Cero Hardcode**.

---

## ⚡ Principio Rector: Cero Hardcode & Privacidad Primero

1. **Separación Total de Datos y Lógica:** Ningún script de Python, motor de renderizado o plantilla contiene datos personales, nombres, teléfonos, enlaces, empresas o viñetas de logros escritas en duro en el código.
2. **Configuración Ágil vía JSON (Reemplazo de Excel):**
   - El sistema opera canónicamente a partir de `data/cv_master.template.json` (plantilla pública de ejemplo).
   - Al inicializar el entorno, puedes crear tu propio archivo `data/cv_master.json` con tu perfil real.
   - `data/cv_master.json` y los documentos generados en `outputs/` están estrictamente ignorados en `.gitignore` para garantizar que tus datos personales nunca se publiquen en Git.
3. **Sincronización Dinámica:**
   - Todos los módulos (`scraper.py`, `matcher.py`, `pdf_engine.py`, `app.py`) consumen la estructura dinámicamente.
   - Cualquier modificación en el JSON de perfil se refleja de inmediato sin tocar código.

---

## 📂 Arquitectura del Proyecto

```text
neural-job/
├── app.py                          # Dashboard interactivo local en Streamlit
├── requirements.txt                # Dependencias del proyecto
├── .gitignore                      # Reglas de exclusión para privacidad y archivos temporales
├── data/
│   ├── cv_master.template.json     # Plantilla canónica pública con estructura del perfil
│   ├── cv_master.json              # Tu perfil activo local (ignorado en Git por privacidad)
│   ├── jobs.db                     # Base de datos relacional SQLite (leads, historial, empresas)
│   ├── job_leads.json              # Respaldo JSON de vacantes extraídas
│   └── history.json                # Respaldo JSON del historial de postulaciones
├── outputs/                        # CVs compilados en Markdown y PDF listos para postular (.gitkeep)
├── src/
│   ├── build_master.py             # Validador y compilador de perfil (JSON nativo y compatibilidad Excel)
│   ├── company_intel.py            # Enriquecedor de Inteligencia Empresarial y catálogo corporativo
│   ├── db.py                       # Gestor de base de datos relacional SQLite (CRUD, auditoría, stats)
│   ├── geo_catalog.py              # Normalizador geográfico y clasificador de modalidad (Presencial/Híbrido/Remoto)
│   ├── matcher.py                  # Algoritmo de scoring semántico ATS y selector de viñetas de impacto
│   ├── pdf_engine.py               # Generador de alta fidelidad Markdown & PDF (ReportLab)
│   ├── salary_estimator.py         # Estimador salarial heurístico y detector de sobrecalificación
│   ├── scraper.py                  # Extractor multicanal de vacantes (JobSpy + CompuTrabajo + OCC)
│   └── translator.py               # Motor de auto-traducción ESP ➔ ENG con caché y preservación técnica
└── tests/
    └── test_pipeline.py            # Suite de pruebas automatizadas end-to-end
```

---

## 🚀 Instalación y Puesta en Marcha

### 1. Clonar el Repositorio
```bash
git clone https://github.com/JCPulidoG/NeuralJob.git
cd NeuralJob
```

### 2. Crear y Activar Entorno Virtual (Python 3.10+)
```bash
python3 -m venv .venv
source .venv/bin/activate
```
*(En Windows: `.venv\Scripts\activate`)*

### 3. Instalar Dependencias
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configurar tu Perfil de CV (Fuente Única de Verdad en JSON)
El repositorio incluye una plantilla en `data/cv_master.template.json`. Puedes inicializar tu archivo de trabajo ejecutando:
```bash
python3 src/build_master.py data/cv_master.template.json
```
Esto creará automáticamente `data/cv_master.json`. Edita `data/cv_master.json` con tu información real (datos de contacto, perfiles objetivo, logros cuantificables y habilidades).

> [!NOTE]
> Si en el futuro prefieres sincronizar desde una hoja de cálculo Excel (`Motor Job.xlsx`), simplemente coloca el archivo en `data/` y ejecuta `python3 src/build_master.py`. El sistema lo detectará automáticamente.

### 5. Verificar la Suite de Pruebas
Valida que todos los componentes, la base de datos relacional SQLite y el generador de PDF funcionen correctamente:
```bash
python3 tests/test_pipeline.py
```

### 6. Iniciar el Dashboard en Streamlit
```bash
streamlit run app.py
```
El panel estará disponible en `http://localhost:8501`.

---

## 🛠️ Estructura del JSON de Perfil (`cv_master.json`)

El archivo JSON canónico se divide en tres bloques fundamentales:

1. **`profile`**:
   - `contact_info`: Nombre, correo, teléfono, ubicación, enlaces a LinkedIn y GitHub.
   - `target_profiles`: Definición de diferentes ángulos profesionales (ej. *Quant / Risk Lead*, *Data Architect*, *Senior Data Scientist*), con su título exacto y resumen ejecutivo adaptado.
   - `education` y `certifications`: Lista de grados y credenciales académicas.
2. **`experiences`**:
   - `items`: Inventario atómico de viñetas y logros laborales con formato:
     - `id`: Identificador único (ej. `EXP-01`).
     - `company`: Nombre de la empresa.
     - `role`: Puesto desempeñado.
     - `period`: Rango temporal (ej. `2022 - 2024`).
     - `bullet`: Descripción redactada con verbo de acción y contexto técnico.
     - `metric`: Métrica de impacto medible (porcentajes, montos, latencias).
     - `tracks`: Lista de etiquetas afines a cada perfil objetivo (ej. `["quant_risk", "data_arch"]`).
     - `keywords`: Palabras clave ATS asociadas.
   - `grouped`: Experiencias agrupadas cronológicamente por rol y empresa (el compilador puede generarlas automáticamente).
3. **`skills`**:
   - `items`: Matriz de competencias agrupadas por categoría (`categoría`, `skill`, `level`, `tags`).

---

---

## 🌐 Generación Bilingüe y Traducción Automática (Español ➔ English)

NeuralJob cuenta con un motor nativo de **traducción automática inteligente y compilación directa** diseñado para postular a vacantes internacionales y remotas sin necesidad de redactar manualmente tu CV en dos idiomas.

```text
┌─────────────────────────┐       ┌────────────────────────┐       ┌──────────────────────────┐
│  data/cv_master.json    │  ───> │   src/translator.py    │  ───> │  outputs/JOB-01_Banorte  │
│  (Perfil en Español)    │       │   (Auto-Traducción EN) │       │  _EN.pdf & _EN.md        │
└─────────────────────────┘       └────────────────────────┘       └──────────────────────────┘
```

### ✨ Características del Motor de Traducción

1. **Cero Dependencias de Pago (Sin API Keys):**
   - Funciona de forma 100% gratuita y sin necesidad de configurar cuentas de OpenAI, Google Cloud o tarjetas de crédito.
2. **Preservación de Terminología Técnica & Acrónimos ATS:**
   - Los términos especializados de finanzas cuantitativas, computación distribuida y analítica avanzada no se deforman ni traducen literalmente.
   - Términos como *VaR, CVaR, Monte Carlo, PySpark, Databricks, Delta Lake, Medallion Architecture, FinOps, CONSAR, AMIB, LLMs, Scikit-Learn, K-Means* conservan su nomenclatura técnica oficial.
3. **Caché Persistente en Disco (`data/translation_cache.json`):**
   - Cada viñeta, logro o resumen traducido se almacena localmente. La primera traducción toma ~1 segundo y las siguientes toman **0 ms (instantáneas)**.
4. **Adaptación de Fechas y Nomenclatura:**
   - Traduce automáticamente términos temporales como `JUL/2025 - ACT` o `PRESENTE` a `JUL/2025 - PRESENT`.
   - Adapta métricas: `[Impacto: ...]` ➔ `[Impact: ...]`.

---

### 🖥️ Modo 1: Desde el Dashboard Interactivo (Streamlit)

1. Abre el dashboard (`streamlit run app.py`) y selecciona cualquier vacante de tu lista.
2. En la pestaña **Compilación y Previsualización**, localiza el selector:
   - Alterna de **`🇪🇸 Español`** a **`🇺🇸 English (EN)`**.
3. **Previsualización en Tiempo Real:** La pestaña *"👁️ Vista Previa del CV Compilado"* mostrará de inmediato la versión traducida al inglés.
4. **Compilación Directa:**
   - Haz clic en el botón principal:  
     👉 **`🌐 Compilar CV en Inglés (Auto-Traducir a PDF & MD)`**
   - En segundos, se generarán en la carpeta `outputs/` los archivos:
     - `outputs/JOB-XXXX_Empresa_EN.pdf`
     - `outputs/JOB-XXXX_Empresa_EN.md`
   - Los botones de descarga se habilitarán automáticamente para guardar ambos archivos en tu equipo.

---

### 💻 Modo 2: En Código Python (Pipeline Automatizado)

Puedes invocar la compilación automática en inglés directamente desde tus propios scripts:

```python
from matcher import match_and_tailor_cv
from pdf_engine import compile_english_cv

# 1. Ajustar el CV a la vacante
tailored_cv = match_and_tailor_cv(
    job_title="Lead Data Architect",
    job_description="Looking for expertise in PySpark, Databricks, and Medallion architecture...",
    company="Fintech Corp"
)

# 2. Traducir automáticamente y compilar en un solo paso (PDF + Markdown con sufijo _EN)
resultado = compile_english_cv(tailored_cv, job_id="JOB-101", company="Fintech Corp")

print("PDF generado:", resultado["pdf_path"])       # outputs/JOB-101_Fintech_Corp_EN.pdf
print("MD generado:", resultado["markdown_path"])  # outputs/JOB-101_Fintech_Corp_EN.md
```

---

### 📂 Modo 3: Auto-Traducir todo el archivo JSON Master

Si prefieres tener tu archivo `cv_master.json` pre-traducido con todos los campos `_en` guardados permanentemente:

- **Por consola / terminal:**
  ```bash
  python3 src/translator.py data/cv_master.json data/cv_master.json
  ```
- **Desde la interfaz web:**
  En la barra lateral de Streamlit, dentro de la sección *"📁 Fuente Única de Verdad"*, haz clic en:  
  👉 **`🌐 Auto-Traducir Perfil (ESP ➔ ENG)`**

---

### 📑 Comparativa de Secciones Traducidas

| Sección del CV | Encabezado en Español | Encabezado en Inglés (`lang="en"`) |
| :--- | :--- | :--- |
| **Resumen Ejecutivo** | `RESUMEN PROFESIONAL` | `PROFESSIONAL SUMMARY` |
| **Experiencia Laboral** | `EXPERIENCIA PROFESIONAL` | `PROFESSIONAL EXPERIENCE` |
| **Competencias Técnicas** | `HABILIDADES & COMPETENCIAS TÉCNICAS` | `TECHNICAL SKILLS & COMPETENCIES` |
| **Formación Académica** | `EDUCACIÓN & CERTIFICACIONES` | `EDUCATION & CERTIFICATIONS` |
| **Etiqueta de Logro** | `(Impacto: +45% optimización...)` | `(Impact: +45% optimization...)` |
| **Rango de Fechas** | `2024 - PRESENTE` / `ACT` | `2024 - PRESENT` |

---

## ⏱️ Rutina Operativa Diaria (Flujo en 20 Minutos)

1. **Minutos 0 - 5: Búsqueda y Captura de Vacantes**
   - Entra al dashboard en `localhost:8501`.
   - Consulta vacantes activas o ejecuta una búsqueda en portales nativos (LinkedIn, Indeed, Glassdoor, CompuTrabajo, OCC) por rol y ubicación.
   - O añade una vacante manualmente pegando el enlace y la descripción desde LinkedIn.
2. **Minutos 5 - 10: Evaluación y Afinidad ATS**
   - El sistema analiza la descripción del empleo, calcula el **ATS Match Score**, destaca **Keywords Coincidentes** y detecta **Gaps (Palabras clave faltantes)**.
   - Selecciona de forma inteligente el perfil objetivo más alineado.
3. **Minutos 10 - 15: Selección de Viñetas de Mayor Impacto**
   - Revisa las 3 mejores viñetas por experiencia seleccionadas por afinidad con la vacante.
   - Revisa la estimación salarial y las alertas de sobrecalificación.
4. **Minutos 15 - 20: Compilación y Postulación**
   - Haz clic en **Compilar Paquete Completo (PDF & Markdown)**.
   - Descarga el PDF generado con formato limpio y tipografía óptima para filtros ATS desde la carpeta `outputs/`.
   - Cambia el estado a **Aplicada** en el tablero para registrar la postulación en la base de datos SQLite y mantener el historial auditado.

---

## 🔒 Privacidad y Seguridad

- **100% Local:** Tus datos no se envían a servidores de terceros ni APIs externas no autorizadas.
- **Git Seguro:** `.gitignore` excluye por defecto tu base de datos poblada, archivos Excel, `cv_master.json` personal y los PDFs generados.
- Puedes compartir, versionar o bifurcar este repositorio con total tranquilidad de que tu información privada permanecerá únicamente en tu máquina local.
