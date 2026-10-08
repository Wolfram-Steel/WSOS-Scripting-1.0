# WSOS Scripting 1.12c

**Herramienta de escritorio para búsqueda inteligente de enlaces técnicos y extracción limpia de contenido web.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Flet](https://img.shields.io/badge/UI-Flet-purple)](https://flet.dev/)
[![License](https://img.shields.io/badge/License-Educational-orange)](#aviso-legal)
[![Version](https://img.shields.io/badge/Version-1.12c-red)](CHANGELOG.md)
[![Concurrency](https://img.shields.io/badge/Search-Nested%20Parallel-brightgreen)](CHANGELOG.md)

> **Autor:** Wolfram Steel  
> **Idioma de la interfaz:** Español  
> **Plataforma:** Multiplataforma (Windows / Linux / macOS)

---

## Tabla de contenidos

- [Descripción](#descripción)
- [Novedades de la versión 1.12c](#novedades-de-la-versión-112c)
- [Novedades de la versión 1.12](#novedades-de-la-versión-112)
- [Características principales](#características-principales)
- [Arquitectura del proyecto](#arquitectura-del-proyecto)
- [Requisitos](#requisitos)
- [Instalación rápida](#instalación-rápida)
- [Guía de uso](#guía-de-uso)
- [Modos de búsqueda avanzados](#modos-de-búsqueda-avanzados)
- [Perfiles de recopilación](#perfiles-de-recopilación)
- [Búsqueda anidada (paralela)](#búsqueda-anidada-paralela)
- [Flujo de trabajo recomendado](#flujo-de-trabajo-recomendado)
- [Estructura de archivos generados](#estructura-de-archivos-generados)
- [Configuración (`config/webs.json`)](#configuración-websjson)
- [Ajuste de rendimiento](#ajuste-de-rendimiento)
- [Solución de problemas](#solución-de-problemas)
- [Aviso legal](#aviso-legal)
- [English summary](#english-summary)

---

## Descripción

**WSOS Scripting** automatiza el ciclo completo de recopilación de información técnica:

1. **Búsqueda** de enlaces relevantes mediante DuckDuckGo (multi-región).
2. **Filtrado** estricto de publicidad, rastreadores, parámetros de tracking y extensiones binarias.
3. **Organización** de URLs en categorías persistentes (`config/webs.json`).
4. **Extracción** de contenido limpio (HTML → texto estructurado), preservando bloques de código; soporte opcional de PDF.
5. **Generación** de datasets por lotes listos para bases de conocimiento, RAG o análisis posterior, con metadatos, Quality Score y manifiesto `.wsos.json`.

Todo desde una interfaz gráfica moderna en modo oscuro, con consola de logs en tiempo real, control de parada segura, **búsqueda anidada en paralelo** y perfiles de recopilación configurables.

---

## Novedades de la versión 1.12c

1.12c es una versión de **consolidación**: mantiene `ThreadPoolExecutor` y la arquitectura de 1.12, y se concentra en extracción DOM, búsqueda más conservadora, pruebas de regresión y escritura segura. No introduce `asyncio`, Playwright, SQLite, embeddings, plugins ni reorganización mayor.

### Extracción DOM

- `<form>` ya no se elimina por defecto: se conserva cuando contiene contenido documental útil, incluyendo escenarios WebForms.
- `<nav>` y `<aside>` se evalúan **antes de aplanar el HTML**, usando densidad de enlaces y estructura DOM; un bloque `<p>`/`article`/`section` útil no se descarta por ser corto.
- Se conservan líneas técnicas cortas como `CPU`, `HTTP 200` o `E = mc²`.
- La eliminación de secciones finales (`Referencias`, `Notas`, etc.) ya no se decide sobre texto aplanado: solo se elimina una sección DOM cuando existe evidencia suficiente de alta densidad de enlaces.
- Se añadió un corpus local de 20 páginas HTML para regresión de WebForms, navegación, aside, código, tablas, fórmulas y referencias.

### Búsqueda y estabilidad

- La búsqueda anidada se limita a **3 workers** y parte de **1 petición/segundo** mediante un limitador compartido adaptativo; ante errores aumenta temporalmente el intervalo y lo recupera gradualmente.
- La Búsqueda Sucia ya no añade el sufijo `pdf` cuando `allow_pdf=False`. Los redirectores publicitarios continúan bloqueados.
- `fetch_urls_with_fallbacks()` se renombra a `fetch_urls()` porque 1.12c usa un único motor y no contiene fallbacks reales.

### Rendimiento del motor

- La búsqueda DuckDuckGo y la descarga de documentos utilizan **pools separados**: la búsqueda queda limitada a **3 workers** por seguridad frente a rate-limit; las descargas utilizan los workers definidos por el perfil, con un tope global de **16**.
- `core/paralelo.py` mantiene una **ventana acotada de futures**: nunca se encolan más tareas que workers disponibles. Esto reduce memoria y trabajo pendiente en búsquedas masivas/categorías grandes sin cambiar el orden de resultados.
- Las descargas reutilizan `requests.Session()` por worker, mantienen keep-alive/connection pooling y aplican rate limiting independiente por dominio.
- Los manifiestos de dataset incluyen telemetría `stats.timings` (`search_seconds`, `filter_dedup_seconds`, `output_prepare_seconds`, `dataset_seconds`, `total_seconds`) y `stats.parallelism`, para localizar cuellos de botella sin activar herramientas externas de profiling.

### Datasets y ejecución segura

- Cada ejecución automática recibe su propio `Run ID` y directorio `salida/runs/<RUN-ID>/`.
- El dataset se escribe primero en un temporal y se publica mediante `os.replace`; una escritura interrumpida no sustituye un dataset válido anterior.
- Las ejecuciones ya no comparten el mismo `dataset_wsos_*.txt` ni su manifiesto.
- `SCHEMA_VERSION` pasa a `1.12c` y la versión del motor pasa a `1.12c`.

### UI y calidad del proyecto

- La consola Flet utiliza una cola de eventos y actualiza los mensajes en lotes para reducir repintados por cada `print()`.
- El campo **Carpeta de salida** incorpora un **icono pequeño de carpeta** a su derecha; al pulsarlo se abre el selector nativo de carpetas, y la carpeta elegida se escribe automáticamente en el campo y queda guardada en los ajustes.
- Se añade `config/pyproject.toml` con configuración Ruff y GitHub Actions para ejecutar Ruff y la batería offline de tests.
- La batería pasa de 54 a **62 tests**.
- `app/actualizador.py` continúa disponible, pero sus funciones específicas de actualización de Windows se consideran experimentales/no probadas fuera de Windows.



## Novedades de la versión 1.12b

Versión de **corrección y robustez**: arregla fallos que impedían obtener contenido útil y hace que los perfiles controlen de verdad lo que prometían.

### Correcciones importantes

- **Filtro de ruido**: antes descartaba prácticamente todo el texto (un patrón con `re.I` casaba con cualquier par de letras). Ahora la prosa se conserva y solo se eliminan líneas de menú, copyright, referencias numéricas y secciones finales (*Referencias*, *Enlaces externos*…).
- **Párrafos intactos**: los enlaces y el texto en cursiva ya no parten un párrafo en fragmentos; `<code>` en línea queda como `` `código` ``; se conservan títulos (`#`), listas y tablas.
- **URLs de Wikipedia**: ya no se corta el `)` final de `.../Python_(lenguaje)`; los artículos tipo `/wiki/Node.js` no se confunden con ficheros `.js`.
- **Quality Score recalibrado**: mide variedad, densidad de frases y proporción de texto (no solo longitud). Prosa real: 83–96 puntos; texto repetido o listas de enlaces: menos de 55. Los umbrales de los perfiles (50 / 70 / 80) ahora tienen sentido.
- **Categorías**: `CPU` y `cpu` ya son la misma categoría (antes se creaba una duplicada). Los nombres de archivo salen del nombre exacto de la categoría y se sanean.
- **`config/webs.json` seguro**: escritura atómica, copia `webs.json.corrupt-…` si el JSON está dañado (en vez de cerrar la app) y deduplicación por URL normalizada.
- **Actualizador**: `beautifulsoup4` ya se detecta bien (módulo `bs4`) y no se reinstala en cada ejecución; ahora usa `config/requirements.txt`.

### Los perfiles controlan de verdad

- Cada perfil define **workers, intentos, límite de caracteres, calidad mínima y deduplicación**, tanto en búsquedas como en la **extracción de categorías** (antes ignoraba el perfil).
- El selector de perfil está visible también al elegir una categoría.
- Los descartes se desglosan por motivo (error de descarga, PDF omitido, demasiado grande, vacío, corto, calidad insuficiente, duplicado) en consola y en el manifiesto.

### Red y rendimiento

- Las descargas se leen en *streaming* con **tope de tamaño real** y **plazo total** (30 s); un servidor lento o una página enorme ya no bloquean un worker. El botón **Detener** corta también una descarga en curso.
- Se respeta la cabecera `Retry-After`.
- El *rate limiter* ya no espera dentro del lock (los hilos no se bloquean entre sí).
- La búsqueda sucia sigue sin filtrar trackers, pero **nunca descarga redirectores de anuncios**.
- Parámetros de tracking (`utm_*`, `msclkid`…) se **eliminan de la URL** en lugar de descartar el enlace.

### Interfaz y proyecto

- **Carpeta de salida configurable** (por defecto `salida/`), y **ajustes recordados** entre sesiones (`config/settings.json`). El icono de carpeta junto al campo permite seleccionar una carpeta mediante el selector nativo; la ruta elegida se guarda automáticamente.
- Consola con tope de 1.500 líneas y captura de `print` segura entre hilos.
- *Detener* deja el manifiesto con `status: "interrupted"`.
- Versión única en `core/version.py`; sangría unificada a 4 espacios; `config/requirements.txt`; batería de **62 tests** (`python -m unittest discover -s tests -t .`).

> Migración desde 1.12: no sobrescribas tu `config/webs.json`. Los archivos `*_part_N.txt` ahora se llaman según la categoría exacta (p. ej. `cpu_arquitectura_part_1.txt`) y se guardan en la carpeta de salida.

## Novedades de la versión 1.12

La versión 1.12 mantiene la arquitectura paralela de 1.11 y añade **robustez, rendimiento y trazabilidad**.

### Control y red

- Parada cooperativa reforzada con checkpoints en búsqueda, descarga y escritura.
- Los `Future` pendientes se cancelan y los `ThreadPoolExecutor` se cierran sin bloquear la interfaz.
- Peticiones HTTP con timeout explícito, hasta 3 intentos y **exponential backoff con jitter**.
- **Rate limiting independiente por dominio** (paraleliza hosts distintos sin saturar uno solo).
- `requests.Session()` **persistente por worker** con connection pooling / keep-alive.
- Barra de progreso determinada conectada al número real de tareas completadas.

### Motor y trazabilidad

- **Perfiles de recopilación**: Rápido, Equilibrado, Seguro y Dataset IA (calidad mínima, workers, rate limit y reintentos).
- **Objetivo del dataset**: Investigación, Educación, Programación, Documentación técnica, Dataset IA, Archivo web o Personalizado.
- **Identidad del proyecto**: autor, proyecto/Project ID, organización, idioma, descripción y **licencia**.
- **Trazabilidad**: cada dataset recibe `Dataset ID`, `Run ID`, fecha y versión del motor.
- **Quality Score** 0–100 por documento antes de entrar al dataset.
- **SHA-256** del contenido y **deduplicación por hash**.
- **Normalización de URLs** (eliminación de `utm_*`, `gclid`, etc.) antes del scraping.
- **Manifiesto WSOS** (`.wsos.json`) con identidad, estadísticas y documentos aceptados.
- **WSOS Engine Report**: calidad media, velocidad y tiempo en la consola.
- Estadísticas finales visibles (válidos, descartados, duplicados, caracteres).

### Extracción y limpieza

- **Filtrado temprano de extensiones binarias** (imágenes, archivos, ejecutables, etc.).
- **Soporte PDF opcional** mediante `pypdf`.
- **Limpieza ampliada de boilerplate**: cookies, anuncios, popups y sidebars.
- Parser preferente `lxml` con fallback a `html.parser`.
- Límite de HTML para proteger rendimiento y memoria.

### Compatibilidad

- Se mantiene `ThreadPoolExecutor`; no se introduce `asyncio` en esta versión.
- Se mantiene la estructura general de WSOS Scripting 1.11.

> Historial completo en [CHANGELOG.md](CHANGELOG.md).

### Resumen de versiones anteriores

| Versión | Enfoque |
|---------|---------|
| **1.0** | Lanzamiento: UI Flet, búsqueda multi-región, Modo WSOS, Búsqueda Sucia, categorías. |
| **1.1** | UI más limpia: eliminación del botón JSON Optimizer de la barra de acciones. |
| **1.11** | Rendimiento: búsqueda y scraping anidados en paralelo. |
| **1.12** | Robustez, perfiles, Quality Score, manifiestos, rate limiting por dominio y refinamientos de red. |
| **1.12b** | Correcciones: filtro de ruido, Quality Score, categorías, descargas acotadas, perfiles efectivos y carpeta de salida. |

---

## Características principales

| Característica | Detalle |
|----------------|---------|
| **Interfaz Flet** | Modo oscuro, consola en vivo, barra de progreso y botones con animación. |
| **Búsqueda multi-región** | España (`es-es`), USA (`us-en`), UK (`uk-en`) y Global (`wt-wt`). |
| **Búsqueda anidada** | Keywords en paralelo (hasta 3 hilos) con parada segura. |
| **Filtro de URLs** | Bloqueo de dominios publicitarios, trackers y extensiones binarias. |
| **Modo WSOS** | Expansión semántica de keywords + validación de contenido + `dataset_wsos_*.txt`. |
| **Búsqueda Sucia** | Expansión masiva de términos + sin filtro de trackers → máximo volumen. |
| **Perfiles de recopilación** | Rápido / Equilibrado / Seguro / Dataset IA (calidad, workers, rate limit). |
| **Gestión de categorías** | Crear / eliminar desde diálogo modal; persistencia en `config/webs.json`. |
| **Extracción inteligente** | BeautifulSoup + limpieza de ruido y boilerplate; preservación de código Markdown. |
| **Soporte PDF** | Extracción opcional de texto de PDFs con `pypdf`. |
| **Scraping paralelo** | De 5 a 10 descargas HTTP concurrentes según perfil. |
| **Manifiesto WSOS** | `.wsos.json` con Dataset ID, Run ID, Quality Score, SHA-256 y estadísticas. |
| **Parada segura** | `threading.Event` interrumpe búsquedas y descargas (incluida una descarga en curso); una consulta de DuckDuckGo ya lanzada termina antes de parar. |
| **Auto-configurador** | `app/actualizador.py` instala dependencias y crea plantilla de `config/webs.json`. |

---

## Arquitectura del proyecto

La raíz se mantiene deliberadamente limpia: los únicos archivos de usuario visibles en ella son `main.py`, `README.md` y `CHANGELOG.md`. El código de aplicación, configuración, pruebas y documentación auxiliar se agrupa por responsabilidad.

```text
WSOS Scripting/
├── main.py                 # Punto de entrada; importa la UI desde app/
├── README.md               # Manual principal
├── CHANGELOG.md            # Historial de cambios
├── app/
│   ├── __init__.py
│   ├── ui.py               # Interfaz Flet, hilos y consola
│   ├── scraping.py         # Orquestador de búsqueda, categorías y dataset
│   └── actualizador.py     # Instalación/verificación y plantilla de configuración
├── core/
│   ├── __init__.py
│   ├── buscadores.py       # Motor DuckDuckGo (DDGS) thread-safe
│   ├── bloqueos.py         # Filtros de URL, trackers y dominios
│   ├── procesador.py       # Descarga HTML/PDF y extracción de texto
│   ├── categorias.py       # Scraping de categorías y particionado
│   ├── config.py           # Persistencia y rutas de config/
│   ├── paralelo.py         # Paralelismo acotado y parada cooperativa
│   ├── version.py          # Versión única 1.12c
│   ├── dataset.py          # Perfiles, calidad, metadatos y manifiestos
│   └── red.py              # Sesiones HTTP, rate limit y reintentos
├── config/
│   ├── webs.json           # Categorías y URLs persistentes
│   ├── settings.json       # Ajustes de UI; se crea al ejecutar
│   ├── requirements.txt    # Dependencias Python
│   └── pyproject.toml      # Configuración Ruff
├── tests/                  # 62 pruebas offline/locales
├── docs/                   # Informes y documentación técnica complementaria
└── .github/
    └── workflows/ci.yml    # CI: dependencias, Ruff y tests
```

### Política de rutas de 1.12c

- `main.py` permanece en la raíz para conservar el arranque simple: `python3 main.py`.
- `app/` contiene únicamente la capa de aplicación/orquestación; el motor reusable permanece en `core/`.
- `config/webs.json` sustituye a `webs.json` en la raíz.
- `config/settings.json` sustituye a `settings.json` en la raíz y se crea automáticamente cuando es necesario.
- `config/requirements.txt` y `config/pyproject.toml` concentran dependencias y herramientas de calidad.
- La carpeta de resultados por defecto continúa siendo `salida/` en la raíz del proyecto; es un directorio de datos, no un archivo de código.
- Los informes técnicos se guardan en `docs/`; las pruebas y fixtures permanecen en `tests/`.
- `.github/` continúa en la raíz porque GitHub Actions exige esa ubicación convencional.

**Flujo de datos (v1.12c):**

```text
main.py
  └─ app.ui.ScraperUI
       └─ app.scraping.IntegratedCodeScraper
            ├─ core.buscadores / core.red / core.procesador
            ├─ core.config → config/webs.json + config/settings.json
            ├─ core.dataset / core.paralelo / core.categorias
            └─ salida/ y salida/runs/<RUN-ID>/
```

En búsqueda web, DuckDuckGo usa como máximo 3 workers. La descarga de documentos usa un pool independiente definido por el perfil, con tope global de 16 workers. La cola de trabajo de `core/paralelo.py` permanece acotada al número de workers.

### Migración interna desde la estructura plana anterior

La reorganización no cambia el formato WSOS, `SCHEMA_VERSION`, los perfiles, el algoritmo de extracción ni la semántica del pipeline. Solo cambia la ubicación física de archivos. Para una copia existente de 1.12c, las equivalencias son:

| Antes | Ahora |
| --- | --- |
| `ui.py` | `app/ui.py` |
| `scraping.py` | `app/scraping.py` |
| `actualizador.py` | `app/actualizador.py` |
| `webs.json` | `config/webs.json` |
| `settings.json` | `config/settings.json` |
| `requirements.txt` | `config/requirements.txt` |
| `pyproject.toml` | `config/pyproject.toml` |

`main.py` y los módulos de `core/` conservan su función. Los imports internos y los tests se han actualizado para usar `app.*`.

---

## Requisitos

- **Python** 3.10 o superior
- Conexión a Internet
- Dependencias (listadas en `config/requirements.txt` e instaladas por `app/actualizador.py`; se recomienda un entorno virtual):
  - `flet`
  - `requests`
  - `beautifulsoup4`
  - `lxml`
  - `pypdf` (soporte PDF opcional)
  - `ddgs`

---

## Instalación rápida

```bash
# 1. Clonar o descargar el repositorio
git clone <url-del-repositorio>
cd <carpeta-del-proyecto>

# 2. Configurar entorno (dependencias + `config/webs.json` de ejemplo)
python3 app/actualizador.py   # o: pip install -r config/requirements.txt

# 3. Lanzar la aplicación
python3 main.py
```

El script `app/actualizador.py` genera `config/instalacion_log.txt` con el historial de la configuración.

---

## Guía de uso

### 1. Crear una categoría (obligatorio antes de buscar)

1. Pulsa el botón morado **Categorías** (arriba a la derecha).
2. Escribe un nombre (ej. `python_docs`, `cpu`, `electronica`).
3. Pulsa **Añadir** y cierra el panel.

### 2. Búsqueda de webs

1. En **Selecciona la Operación** elige **Búsqueda webs**.
2. Rellena keywords, región y categoría de destino. La Búsqueda webs estándar no solicita carpeta ni archivo de salida: las URLs se guardan directamente en `config/webs.json`.
3. (Opcional) Activa **Modo WSOS** o **Búsqueda Sucia** (excluyentes).
4. Configura el **perfil de recopilación**, objetivo e identidad del proyecto (autor, licencia, etc.).
5. Pulsa **Ejecutar Proceso** y observa la consola: verás términos completándose en paralelo.
6. Puedes detener con **Detener Proceso** (corta las descargas en curso; una consulta de búsqueda ya enviada termina antes).

### 3. Extracción de contenido de una categoría

1. Selecciona la categoría en el desplegable principal.
2. Pulsa **Ejecutar Proceso**.
3. Se aplica el **perfil elegido** y se generan `categoria_part_1.txt`, `categoria_part_2.txt`, … en la carpeta de salida (las partes de ejecuciones anteriores de esa categoría se reemplazan).

### 4. Abrir carpeta de resultados

La **Búsqueda webs estándar no muestra el campo Carpeta de salida ni su icono**. Las URLs encontradas se incorporan directamente a la categoría seleccionada de `config/webs.json`, que es la fuente persistente de categorías.

El campo **Carpeta de salida** y su **icono de carpeta** se reservan para operaciones que realmente generan archivos: extracción de una categoría y los modos WSOS/Búsqueda Sucia cuando generan datasets y manifiestos.

---

## Modos de búsqueda avanzados

| Modo | Qué hace | Cuándo usarlo |
|------|----------|---------------|
| **Estándar** | Keywords tal cual + filtro de trackers. ~5 resultados/término. | Búsquedas precisas. |
| **Modo WSOS** | Expande con `documentation`, `github`, `tutorial`, `source code`, `examples`. Valida contenido y Quality Score. Genera `dataset_wsos_*.txt` + manifiesto. | Datasets técnicos de calidad. |
| **Búsqueda Sucia** | Expande con ~19 sufijos. Sin filtro de trackers. Genera `dataset_dirty_*.txt` + manifiesto. | Máximo volumen de enlaces. |

En **1.11+**, tanto WSOS como Búsqueda Sucia se benefician de la búsqueda anidada. En **1.12** se suman perfiles, scoring y manifiestos. En **1.12c** la concurrencia de búsqueda queda deliberadamente limitada a 3 workers por seguridad frente a rate-limit, mientras que la descarga mantiene un pool independiente controlado por perfil.

---

## Perfiles de recopilación

Disponibles desde la interfaz (desplegable **Perfil de recopilación**):

| Perfil | Calidad mín. | Chars mín. | Workers | Rate limit | Uso típico |
|--------|--------------|------------|---------|------------|------------|
| **Rápido** | 50 | 250 | 10 | 0.05 s | Exploración rápida |
| **Equilibrado** | 70 | 300 | 8 | 0.10 s | Uso general (por defecto) |
| **Seguro** | 80 | 400 | 5 | 0.20 s | Sitios sensibles / menos agresivo |
| **Dataset IA** | 80 | 1000 | 8 | 0.10 s | Datasets de alta calidad para RAG/IA |

Cada perfil controla calidad mínima, tamaño mínimo y máximo de documento, número de workers, intervalo de rate limiting, intentos por URL y deduplicación. Se aplica tanto a las búsquedas WSOS/Sucia como a la **extracción de categorías**.

---

## Búsqueda anidada (paralela)

A partir de la **1.11**, el cuello de botella secuencial desaparece:

| Fase | Workers por defecto | Archivo |
|------|---------------------|---------|
| Consultas DuckDuckGo por keyword | **hasta 3** | `app/scraping.py` → `MAX_SEARCH_WORKERS` |
| Descarga de páginas (dataset WSOS/Sucia y categorías) | **5–10** según perfil, máximo global 16 | `core/dataset.py` → `PROFILES` + `HARD_WORKER_CAP` |

Cada worker de búsqueda crea su propia instancia de `MultiSearchEngine` / sesión `DDGS`.  
Cada worker de scraping reutiliza una `requests.Session` con pooling y aplica rate limiting por dominio.  
La parada del usuario cancela futures pendientes de forma segura.

---

## Flujo de trabajo recomendado

```
1. Crear categoría(s)          →  Categorías → Añadir
2. Configurar perfil e identidad →  Perfil, autor, licencia, objetivo
3. Buscar enlaces              →  Búsqueda webs + región + categoría destino
4. (Opcional) Revisar `config/webs.json`
5. Extraer contenido           →  Seleccionar categoría → Ejecutar
6. Usar los *_part_N.txt y .wsos.json →  RAG, análisis, documentación, etc.
```

---

## Estructura de archivos generados

| Archivo | Origen | Contenido |
|---------|--------|-----------|
| `config/webs.json` | Búsqueda webs | Categorías y URLs encontradas |
| `config/webs.json` | Persistente | Categorías y URLs |
| `config/settings.json` | Persistente | Ajustes recordados de la interfaz (incl. `extra_blocked_domains`) |
| `salida/runs/<RUN-ID>/dataset_wsos_*.txt` | Modo WSOS | Contenido limpio validado + Quality Score |
| `salida/runs/<RUN-ID>/dataset_dirty_*.txt` | Búsqueda Sucia | Contenido limpio (sin filtro de trackers) |
| `salida/runs/<RUN-ID>/*.wsos.json` | Modo WSOS / Sucia | Manifiesto: metadatos, stats, documentos |
| `<categoria>_part_N.txt` | Extracción de categoría | Texto estructurado por fuente |
| `config/instalacion_log.txt` | `app/actualizador.py` | Log de instalación |

---

## Configuración (`config/webs.json`)

```json
{
    "cpu": [
        "https://es.wikipedia.org/wiki/Unidad_central_de_proceso",
        "https://es.wikipedia.org/wiki/Microprocesador"
    ],
    "programacion": [
        "https://es.wikipedia.org/wiki/Python",
        "https://docs.python.org/3/"
    ]
}
```

- Claves = nombres de categoría; se buscan sin distinguir mayúsculas (`CPU` = `cpu`) y las nuevas se crean en minúsculas.
- Si el archivo se daña, se guarda una copia `webs.json.corrupt-<fecha>` y la aplicación sigue funcionando.
- Valores = listas de URLs.
- Editable a mano o desde la UI (crear / borrar categorías).

---

## Ajuste de rendimiento

Si DuckDuckGo limita peticiones o la red es inestable, elige el perfil **Seguro** (menos workers, más espacio entre peticiones) o reduce la búsqueda en paralelo:

```python
# app/scraping.py
MAX_SEARCH_WORKERS = 3   # búsqueda conservadora; el limitador compartido parte de 1 s
```

Los workers de descarga, el intervalo y los intentos se ajustan editando el perfil en `core/dataset.py` (`PROFILES`). Con red estable puedes usar el perfil **Rápido**.

---

## Solución de problemas

| Problema | Solución |
|----------|----------|
| `No se encuentra config/webs.json` | Ejecutar `python3 app/actualizador.py` o crear `config/webs.json` manualmente. |
| Error al importar `ddgs` / `flet` / `pypdf` | Reejecutar el actualizador o `pip install -r config/requirements.txt`. |
| Pocos resultados | Probar otra región, activar WSOS o Búsqueda Sucia, ampliar keywords. |
| Errores frecuentes en DDGS | Bajar `MAX_SEARCH_WORKERS` o usar perfil **Seguro** (posible rate-limit). |
| Contenido vacío en extracción | La página puede bloquear el User-Agent o cargar el texto con JavaScript (no se ejecuta); revisar logs en consola. |
| Documentos descartados | La consola indica el motivo de cada descarte. Si es calidad, prueba el perfil **Rápido** o revisa la fuente. |
| UI no cierra limpia | Usar **Detener Proceso** antes de cerrar si hay una tarea en curso. |

---

## Aviso legal

El autor **no se hace responsable** del mal uso de esta herramienta.  
WSOS Scripting está diseñado **estrictamente con fines educativos, de investigación y de automatización de flujos de desarrollo personales**.

Es responsabilidad del usuario:

- Cumplir los términos de servicio de los sitios web consultados.
- Respetar las leyes aplicables (incluyendo derechos de autor y privacidad).
- No sobrecargar servidores ajenos con peticiones abusivas.

---

## English summary

**WSOS Scripting 1.12c** is a desktop tool (Flet GUI) that:

- Searches technical links via DuckDuckGo with multi-region support and strict tracker/ad/binary filtering.
- Organizes URLs into persistent categories (`config/webs.json`).
- Extracts clean text from pages (and optionally PDFs) while preserving code blocks.
- Offers **WSOS** mode (semantic keyword expansion + content validation) and **Dirty Search** (maximum volume).
- **v1.11** introduced **nested parallel search**: up to 8 concurrent DuckDuckGo queries and concurrent page downloads.
- **v1.12** adds collection profiles, Quality Score, SHA-256 deduplication, `.wsos.json` manifests, per-domain rate limiting, persistent HTTP sessions, exponential backoff, and expanded boilerplate cleaning.

```bash
python3 app/actualizador.py   # install deps + create config/webs.json template
python3 main.py           # launch the app
```

- **v1.12c** is a consolidation release: DOM-aware extraction, conservative DuckDuckGo pacing, per-run atomic datasets, a 20-page HTML regression corpus, queued UI logs, Ruff and CI. It keeps the 1.12 architecture and does not introduce asyncio, Playwright, SQLite or embeddings. It also separates search/download concurrency, bounds the number of queued futures, records performance timings in dataset manifests, and keeps the offline suite at 62 tests.

See the Spanish sections above for full usage, architecture and legal notice.

---

**¿Te resulta útil?** Adáptalo a tus necesidades, ajusta los workers o integra nuevos motores.  
Construido con ❤️ para automatizar el trabajo tedioso de recopilar y limpiar información técnica.
