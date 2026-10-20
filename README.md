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
│   └── scraper.py                  # Extractor multicanal de vacantes (JobSpy + CompuTrabajo + OCC)
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

## 🌐 Generación Bilingüe de CVs (Español & English)

NeuralJob soporta de forma nativa la generación de CVs tanto en **Español** como en **Inglés**:

1. **Campos Bilingües en el JSON Master:**
   - En `data/cv_master.json`, puedes agregar opcionalmente los campos correspondientes en inglés:
     - `title_en` y `summary_en` para perfiles objetivo.
     - `role_en`, `period_en`, `bullet_en` y `metric_en` para cada viñeta y experiencia.
     - `value_en` para educación y certificaciones.
     - `Ubicación_en` en la información de contacto.
   - **Fallback Inteligente:** Si alguna viñeta o campo no tiene traducción definida, el motor utiliza automáticamente la versión en español sin interrumpir la compilación.
2. **Encabezados y Fechas Adaptadas:**
   - Al compilar en inglés, los encabezados de sección cambian automáticamente (*"PROFESSIONAL EXPERIENCE"*, *"TECHNICAL SKILLS & COMPETENCIES"*, etc.) y los periodos adaptan términos como `PRESENT`.
3. **Nomenclatura Automática:**
   - Al compilar en inglés, los archivos PDF y Markdown se guardan con el sufijo `_EN` (ej. `JOB-0807BA7B_Empresa_EN.pdf`).
4. **Selector en Dashboard:**
   - En la pestaña de previsualización de Streamlit, dispones de un selector `🌐 Idioma del CV` para alternar entre Español e Inglés y ver los cambios en tiempo real antes de descargar.

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
