## 1.12c — corrección de persistencia de Búsqueda webs

- **Búsqueda webs estándar:** deja de generar `enlaces_encontrados.txt` o cualquier otro archivo de salida.
- Las URLs encontradas se guardan **exclusivamente en `config/webs.json`**, dentro de la categoría de destino seleccionada, usando la deduplicación normalizada existente.
- La interfaz **oculta el campo Carpeta de salida y su icono** durante la Búsqueda webs estándar.
- La ejecución estándar ya no crea físicamente la carpeta `salida/` por efecto de la búsqueda.
- La carpeta de salida queda reservada para operaciones que realmente producen archivos: extracción de categorías y datasets WSOS/Búsqueda Sucia.
- Se mantiene `config/webs.json` como fuente persistente y única de las categorías de URLs.
- Se mantiene la versión **1.12c** y no se modifica el motor de búsqueda ni sus límites de concurrencia.

# Changelog

## [1.12c] — 2026-10-08

### Resumen

Versión de **consolidación** de 1.12. Se mantiene la arquitectura basada en `ThreadPoolExecutor` y se corrigen los puntos que afectaban directamente a la calidad de extracción, el ritmo de búsqueda y la seguridad de escritura de datasets.

### Organización final de archivos

- Se reorganiza la distribución de **1.12c sin modificar el motor**. La raíz queda reservada a `main.py`, `README.md` y `CHANGELOG.md` como únicos archivos normales de primer nivel.
- `app/ui.py`, `app/scraping.py` y `app/actualizador.py` pasan a `app/`; se añade `app/__init__.py` y los imports cambian a `app.ui`, `app.scraping` y `app.actualizador`.
- `webs.json`, el futuro `settings.json`, `requirements.txt` y `pyproject.toml` pasan a `config/webs.json`, `config/settings.json`, `config/requirements.txt` y `config/pyproject.toml`.
- `core/config.py` usa ahora `config/webs.json` y `config/settings.json`; la salida por defecto continúa en `salida/`.
- `app/actualizador.py` lee `config/requirements.txt`, crea/verifica `config/webs.json` y guarda el log de instalación en `config/instalacion_log.txt`.
- GitHub Actions instala desde `config/requirements.txt` y ejecuta Ruff con `--config config/pyproject.toml`.
- Los tests se actualizan para importar el orquestador y el actualizador desde `app/`.
- Se retiran caches compiladas `__pycache__` del paquete de distribución.
- La reorganización no cambia `SCHEMA_VERSION = 1.12c`, los límites de concurrencia, el Quality Score, los formatos de dataset ni el comportamiento de búsqueda/extracción.

### Added
- La ventana inicial de la interfaz se abre con mayor altura para dejar una zona de consola de ejecución visible desde el inicio.

- Corpus local de **20 páginas HTML** para regresión de extracción.
- Tests específicos para `<form>`, `<aside>`, navegación, líneas técnicas cortas, referencias, PDF en categorías y sufijo `pdf` de Búsqueda Sucia.
- `AdaptiveRateLimiter` para búsquedas: intervalo base de 1 s, penalización progresiva hasta 8 s y recuperación gradual.
- `config/pyproject.toml` con Ruff.
- GitHub Actions para Ruff y tests offline.
- Cola de eventos para agrupar actualizaciones de la consola Flet.
- Icono compacto junto al campo **Carpeta de salida** para seleccionar una carpeta mediante el selector nativo; la ruta elegida se aplica y se guarda automáticamente.

### Performance

- Se mantiene la búsqueda DuckDuckGo en un pool independiente de **hasta 3 workers** y la descarga de documentos en un pool separado controlado por el perfil, con tope global de **16 workers**.
- `core/paralelo.py` cambia de una cola ilimitada de futures a una **ventana acotada al número de workers**. Se conserva el orden de resultados y la parada cooperativa, pero se reduce la memoria y el trabajo pendiente en ejecuciones masivas.
- Se mantiene `requests.Session()` por worker con keep-alive/connection pooling y `DomainRateLimiter` independiente por host.
- Los manifiestos de dataset incorporan `stats.timings` para medir búsqueda, filtrado/deduplicación, preparación de salida, dataset y tiempo total, además de `stats.parallelism` con los workers realmente utilizados.
- Esta telemetría no cambia `SCHEMA_VERSION`: sigue siendo **1.12c**.

### Changed

- Extracción DOM: `<form>` y `<aside>` ya no se descartan ciegamente; la decisión usa estructura y densidad de enlaces.
- La poda de secciones finales se realiza en el DOM y requiere evidencia de una sección dominada por enlaces.
- Las líneas cortas dejan de descartarse por número mínimo de palabras.
- DuckDuckGo: **3 workers** máximos y limitador compartido de **1 petición/s** con adaptación ante errores.
- `fetch_urls_with_fallbacks()` pasa a llamarse `fetch_urls()`: no existían fallbacks reales.
- Búsqueda Sucia: se elimina el sufijo `pdf` cuando `allow_pdf=False`; los redirectores publicitarios siguen filtrados.
- Datasets automáticos: cada `Run ID` usa `salida/runs/<RUN-ID>/` y la publicación se realiza mediante temporal + `os.replace`.
- `SCHEMA_VERSION` pasa de `1.12` a `1.12c`.
- La batería de pruebas queda en **62 tests**.

### Removed

- `core/buscawebs.py`, módulo auxiliar que no participaba en el pipeline actual.

### Experimental

- Las funciones específicas de actualización de Windows de `app/actualizador.py` siguen sin formar parte del flujo principal y no se consideran validadas fuera de Windows.

### Not in 1.12c

No se introduce `asyncio`, Playwright, SQLite/SQLAlchemy, embeddings/vector DB, plugins, proxies, nuevos motores de búsqueda ni una reescritura mayor de arquitectura. La reorganización física `app/` + `config/` sí forma parte del cierre de 1.12c.

Todos los cambios relevantes de **WSOS Scripting** se documentan en este archivo.

El formato está inspirado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),  
y este proyecto sigue [Versionado Semántico](https://semver.org/lang/es/).

---

> **Nota de historial:** las entradas 1.12b y anteriores conservan las rutas que existían en esas versiones. La reorganización `app/` + `config/` se aplica a 1.12c a partir de la revisión descrita arriba.

## [1.12b] — 2026-10-07

Versión "1.12b": corrección y robustez sobre 1.12.

### Fixed
- **Filtro de ruido** (`core/procesador.py`): el patrón `[a-z][A-Z]` se compilaba con `re.I` y casaba con cualquier par de letras, de modo que se descartaba todo el texto fuera de bloques de código. Se elimina esa heurística. Las palabras genéricas (`index`, `theme`, `modules`, `referencias`…) solo cuentan como ruido si ocupan la línea entera, no como subcadena. Las referencias bibliográficas se detectan con un patrón más estricto.
- **Párrafos partidos**: la conversión usaba `get_text("\n")`, que separaba cada enlace o cursiva en una línea propia. Ahora se convierte por bloques; `<code>` en línea ya no se transforma en bloque ```; se conservan títulos, listas y tablas; `<header>` con título ya no se elimina.
- **Boilerplate**: las clases/ids se comparan por palabra (`threads-list` ya no coincide con `ads`) y `html/body/main/article` nunca se eliminan.
- **`sanitize_url`** ya no corta el `)` final de URLs como `.../Python_(lenguaje)`.
- **Filtro de recursos**: `/wiki/Node.js` y similares ya no se descartan por su extensión.
- **Quality Score**: recalibrado (variedad de líneas/frases/palabras, densidad de frases, proporción de letras, longitud de línea). Antes un artículo de ~10.000 caracteres no superaba ~50 puntos y los perfiles Equilibrado/Seguro/Dataset IA rechazaban casi todo.
- **Categorías**: `CPU` y `cpu` se resuelven como la misma categoría; ya no se crean duplicadas. Los nombres de archivo de salida usan el nombre exacto saneado (se acabaron las colisiones `cpu`/`cpu_arquitectura` y los caracteres inválidos).
- **Partes obsoletas**: la extracción de una categoría elimina las `*_part_N.txt` anteriores de esa misma categoría al escribir y no crea archivos vacíos.
- **`actualizador.py`**: `__import__("beautifulsoup4")` fallaba siempre y reinstalaba el paquete en cada ejecución; ahora se usa el nombre de módulo correcto. Las funciones de actualización de Windows se definen antes del bloque `__main__`; el `.bat` usa el Python en ejecución (no `py`), restaura la copia de seguridad si falla, ya no borra su propia carpeta ni la copia y escapa `%`.
- **`optimize_webs_json`**: solo elimina URLs con 404/410 (los 403, 429 o cortes de red ya no borran enlaces válidos), respeta el rate limit y la parada, y escribe de forma atómica.
- Typo `mscclkid` en el filtro de trackers.

### Changed
- Los **perfiles** controlan workers, intentos, `max_chars`, calidad mínima y deduplicación (antes `workers`, `retries` y `max_chars` no se usaban). La **extracción de categorías** aplica ahora el perfil (calidad, deduplicación y límites) y el selector es visible en ese modo.
- Descargas en *streaming* con límite de tamaño real (HTML 2 MB, PDF 15 MB), plazo total de 30 s y cierre de conexión al pulsar Detener; se respeta `Retry-After`; la codificación se toma de la cabecera `Content-Type` si existe.
- `RateLimiter` reserva su hueco bajo el lock y espera fuera de él.
- Parámetros de tracking se eliminan de la URL en lugar de descartar el enlace. En Búsqueda Sucia siguen sin filtrarse dominios, pero se bloquean los redirectores de anuncios.
- Los dominios bloqueados se comparan por host (no por subcadena) y pueden editarse en `settings.json` (`extra_blocked_domains`).
- `webs.json` se escribe de forma atómica; un JSON dañado se copia a `webs.json.corrupt-<fecha>` en lugar de provocar un error al arrancar; las URLs se deduplican normalizadas.
- Nombre del archivo de salida: se ignora cualquier directorio incluido en él y se guarda en la carpeta de salida.
- Descartes desglosados por motivo; el manifiesto incluye `status` (`completed`/`interrupted`), `rejections`, `not_processed` y el título de cada documento.
- La versión vive en `core/version.py` (UI, banner y manifiestos).

### Added
- Carpeta de salida configurable (por defecto `salida/`) y `settings.json` con los ajustes de la interfaz.
- `core/config.py`, `core/paralelo.py` y `core/version.py`; `requirements.txt`; `.gitignore`.
- Batería de 54 tests (`python -m unittest discover -s tests -t .`), con servidor HTTP local, sin red externa.

### Internal
- Consola de la UI limitada a 1.500 líneas, redirección de `print` segura entre hilos y progreso sin `page.update()` completo.
- Compatibilidad con `page.window.width` (Flet reciente) y `page.window_width` (antiguo).
- Sangría unificada a 4 espacios.

### Known limitations
- Una consulta a DuckDuckGo ya enviada no se puede interrumpir; la parada surte efecto al terminar.
- Las funciones de actualización para Windows (`preparar_actualizacion_windows`) no se llaman desde ningún sitio y no se han probado fuera de Windows.
- No se respeta `robots.txt` ni se detecta la licencia de cada fuente; el campo `license` es solo un metadato que escribe el usuario.

---

## [1.12.0] — 2026-10-07

### Added

#### Motor y trazabilidad
- Perfiles de recopilación: **Rápido**, **Equilibrado**, **Seguro** y **Dataset IA**.
- Objetivo del dataset configurable: Investigación, Educación, Programación, Documentación técnica, Dataset IA, Archivo web o Personalizado.
- Metadatos de identidad del proyecto: autor, proyecto/Project ID, organización, idioma, descripción y **licencia**.
- `Dataset ID` y `Run ID` únicos por ejecución.
- Quality Score 0–100 por documento.
- SHA-256 del contenido y deduplicación por hash.
- Normalización de URLs antes del scraping (elimina `utm_*`, `gclid`, etc.).
- Manifiesto `.wsos.json` con identidad, estadísticas y documentos aceptados.
- **WSOS Engine Report** en consola: calidad media, velocidad y tiempo.
- Estadísticas finales visibles (válidos, descartados, duplicados, caracteres).
- Módulo `core/dataset.py` (perfiles, scoring, metadatos y manifiestos).
- Módulo `core/red.py` (Session pooling, rate limiting por dominio, backoff).

#### Extracción y limpieza
- Filtrado temprano de extensiones binarias (imágenes, archivos, ejecutables, etc.).
- Soporte PDF opcional mediante `pypdf`.
- Limpieza ampliada de boilerplate (cookies, anuncios, popups y sidebars).
- `lxml` como parser preferente con fallback a `html.parser`.
- Dependencias `lxml` y `pypdf` añadidas al auto-configurador.

### Changed

#### Robustez y control
- Parada cooperativa reforzada con checkpoints en búsqueda, descarga y escritura.
- Los futures pendientes se cancelan y los ejecutores se cierran sin bloquear la interfaz.
- Timeouts HTTP explícitos para evitar esperas indefinidas.
- Rate limiting **independiente por dominio** (sustituye el limitador global compartido).
- `requests.Session()` **persistente por worker** con connection pooling / keep-alive.
- Reintentos con exponential backoff y jitter para errores transitorios.
- Barra de progreso determinada conectada al número real de tareas completadas.
- El procesamiento web comparte la señal de parada con las peticiones HTTP.
- Banner y título de ventana: **WSOS SCRIPTING 1.12**.

### Compatibilidad

- Se mantiene `ThreadPoolExecutor`; no se introduce `asyncio` en esta versión.
- Se mantiene la estructura general de WSOS Scripting 1.11.

### Migration notes

| Desde 1.11 | Acción |
|------------|--------|
| Actualizar | Sustituir todos los módulos; nuevos: `core/dataset.py`, `core/red.py`. |
| Dependencias | Ejecutar `python3 actualizador.py` (añade `lxml` y `pypdf`). |
| webs.json | No requiere cambios. |
| UI | Nuevos campos de perfil, objetivo e identidad del dataset. |

---

## [1.11.0] — 2026-10-07

### Resumen

Actualización centrada en **rendimiento**: la búsqueda web y la extracción de contenido pasan de ser secuenciales a **anidadas (paralelas)** mediante `ThreadPoolExecutor`. El impacto es especialmente notable en Modo WSOS y Búsqueda Sucia, donde hay muchas keywords y muchas URLs.

### Added

- **Búsqueda anidada de keywords** en `scraping.py`:
  - Hasta `MAX_SEARCH_WORKERS = 8` consultas DuckDuckGo concurrentes.
  - Cada worker instancia su propio `MultiSearchEngine` (sesión DDGS independiente).
  - Cancelación segura de futures al activar **Detener Proceso**.
  - Logs por término completado: `[✔] Término completado: '...' → N enlaces`.

- **Pipeline de dataset en paralelo** (Modo WSOS / Búsqueda Sucia):
  - Hasta `MAX_SCRAPE_WORKERS = 6` descargas HTTP concurrentes.
  - Resultados consolidados y escritos al archivo `dataset_*` al finalizar.

- **Extracción de categorías en paralelo** en `core/categorias.py`:
  - Hasta `MAX_CATEGORY_WORKERS = 6` scrapes concurrentes.
  - Escritura a disco **ordenada** (respeta el orden original de URLs) y particionado por ~500 líneas.

### Changed

- Banner y título de ventana: `WSOS SCRIPTING 1.1` → **`WSOS SCRIPTING 1.11`**.
- Mensajes de consola: se indica explícitamente búsqueda/extracción **PARALELA** / **ANIDADA**.
- `core/buscadores.py`: documentado como thread-safe; cada llamada a `search_engine_ddg_library` abre y cierra su propia sesión `DDGS`.

### Performance

| Escenario | Antes (secuencial) | Ahora (1.11) |
|-----------|--------------------|--------------|
| N keywords | ~N × tiempo/consulta | ~tiempo/consulta × (N / workers) |
| Dataset / categoría con M URLs | ~M × tiempo/página | ~tiempo/página × (M / workers) |

### Unchanged

- Interfaz de usuario (misma barra de acciones que 1.1: Ejecutar · Detener · Abrir Carpeta).
- Filtros de URL, modos WSOS/Sucia, esquema de `webs.json`.
- Método `optimize_webs_json()` sigue disponible en código (sin botón en UI desde 1.1).

### Migration notes

| Desde 1.1 | Acción |
|-----------|--------|
| Actualizar | Sustituir `scraping.py`, `core/buscadores.py`, `core/categorias.py`, `ui.py`, `main.py`. |
| Ajuste fino | Si hay rate-limit de DuckDuckGo, bajar `MAX_SEARCH_WORKERS` a 4. |
| webs.json | No requiere cambios. |

---

## [1.1.0] — 2026-10-06

### Resumen

Simplificación de la interfaz: se elimina el optimizador JSON de la barra de acciones.

### Changed

- Banner: `WSOS SCRIPTING 1.0` → `WSOS SCRIPTING 1.1`.
- Barra de acciones reducida a: **Ejecutar Proceso**, **Detener Proceso**, **Abrir Carpeta**.

### Removed (UI only)

- Botón **JSON Optimizer**.
- Métodos `run_optimizer()` y `_execute_optimization_task()` en `ScraperUI`.
- Referencias a `self.btn_optimizer` en layout y estados de botones.

### Unchanged / Internal

- `optimize_webs_json()` permanece en `scraping.py` para uso programático.
- Resto de módulos sin cambios funcionales.

---

## [1.0.0] — 2026-10-01

### Added

- Interfaz gráfica completa con **Flet** (modo oscuro).
- Búsqueda multi-región vía **DuckDuckGo** (`ddgs`): España, USA, UK, Global.
- Filtro avanzado de URLs (`core/bloqueos.py`).
- **Modo WSOS**: expansión semántica + validación de contenido + `dataset_wsos_*.txt`.
- **Búsqueda Sucia**: expansión masiva + sin filtros de tracking + `dataset_dirty_*.txt`.
- Gestión de categorías (crear / eliminar) con diálogo modal y `webs.json`.
- Extracción por categoría con particionado (`*_part_N.txt`).
- Procesador HTML inteligente (`core/procesador.py`) con preservación de código.
- Parada segura mediante `threading.Event`.
- Botón **Abrir Carpeta**.
- Script **auto-configurador** (`actualizador.py`).
- Botón **JSON Optimizer** en la barra de acciones (eliminado en UI desde 1.1).
- Consola de logs en tiempo real.
- Documentación inicial bilingüe.

### Architecture

```
main.py          → entrada Flet
ui.py            → UI + hilos + captura de consola
scraping.py      → orquestador
core/
  buscadores.py  → motor DDGS
  bloqueos.py    → filtro de URLs
  procesador.py  → scrape + limpieza
  categorias.py  → pipeline por categoría
actualizador.py  → setup de entorno
webs.json        → persistencia
```

---

## Tipos de cambios usados

- **Added** — funcionalidad nueva
- **Changed** — cambios en funcionalidad existente
- **Deprecated** — funcionalidad que se eliminará pronto
- **Removed** — funcionalidad eliminada
- **Fixed** — corrección de errores
- **Security** — vulnerabilidades
- **Performance** — mejoras de rendimiento

---

[1.12.0]: https://github.com/<usuario>/<repo>/compare/v1.11.0...v1.12.0  
[1.11.0]: https://github.com/<usuario>/<repo>/compare/v1.1.0...v1.11.0  
[1.1.0]: https://github.com/<usuario>/<repo>/compare/v1.0.0...v1.1.0  
[1.0.0]: https://github.com/<usuario>/<repo>/releases/tag/v1.0.0
