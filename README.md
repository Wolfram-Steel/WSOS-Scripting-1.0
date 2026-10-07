# WSOS Scripting 1.12

**Herramienta de escritorio para búsqueda inteligente de enlaces técnicos y extracción limpia de contenido web.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Flet](https://img.shields.io/badge/UI-Flet-purple)](https://flet.dev/)
[![License](https://img.shields.io/badge/License-Educational-orange)](#aviso-legal)
[![Version](https://img.shields.io/badge/Version-1.12-red)](CHANGELOG.md)
[![Concurrency](https://img.shields.io/badge/Search-Nested%20Parallel-brightgreen)](CHANGELOG.md)

> **Autor:** Wolfram Steel  
> **Idioma de la interfaz:** Español  
> **Plataforma:** Multiplataforma (Windows / Linux / macOS)

---

## Tabla de contenidos

- [Descripción](#descripción)
- [Novedades de la versión 1.11](#novedades-de-la-versión-111)
- [Características principales](#características-principales)
- [Arquitectura del proyecto](#arquitectura-del-proyecto)
- [Requisitos](#requisitos)
- [Instalación rápida](#instalación-rápida)
- [Guía de uso](#guía-de-uso)
- [Modos de búsqueda avanzados](#modos-de-búsqueda-avanzados)
- [Búsqueda anidada (paralela)](#búsqueda-anidada-paralela)
- [Flujo de trabajo recomendado](#flujo-de-trabajo-recomendado)
- [Estructura de archivos generados](#estructura-de-archivos-generados)
- [Configuración (`webs.json`)](#configuración-websjson)
- [Ajuste de rendimiento](#ajuste-de-rendimiento)
- [Solución de problemas](#solución-de-problemas)
- [Aviso legal](#aviso-legal)
- [English summary](#english-summary)

---

## Descripción

**WSOS Scripting** automatiza el ciclo completo de recopilación de información técnica:

1. **Búsqueda** de enlaces relevantes mediante DuckDuckGo (multi-región).
2. **Filtrado** estricto de publicidad, rastreadores y parámetros de tracking.
3. **Organización** de URLs en categorías persistentes (`webs.json`).
4. **Extracción** de contenido limpio (HTML → texto estructurado), preservando bloques de código.
5. **Generación** de datasets por lotes listos para bases de conocimiento, RAG o análisis posterior.

Todo desde una interfaz gráfica moderna en modo oscuro, con consola de logs en tiempo real, control de parada segura y **búsqueda anidada en paralelo** para maximizar la velocidad.

---

## Novedades de la versión 1.12

La versión 1.12 mantiene la arquitectura paralela de 1.11 y añade robustez, rendimiento y trazabilidad: parada cooperativa, timeouts, reintentos con exponential backoff, rate limiting por perfil, sesiones HTTP reutilizables, normalización/deduplicación de URLs, Quality Score, hashes SHA-256, perfiles de recopilación y manifiestos `.wsos.json`. En Windows se prepara además la actualización mediante un proceso auxiliar para no sobrescribir archivos en uso.

### Control y red

- Parada cooperativa mediante `stop_event` en búsqueda, descarga y escritura.
- Los `Future` pendientes se cancelan y los `ThreadPoolExecutor` se cierran sin bloquear la interfaz.
- Peticiones HTTP con timeout, hasta 3 intentos y backoff con jitter.
- Rate limiting compartido entre workers.
- Barra de progreso determinada conectada a tareas completadas.

## Mejoras adicionales de 1.12

- **Perfiles de recopilación**: Rápido, Equilibrado, Seguro y Dataset IA.
- **Objetivo del dataset**: Investigación, Educación, Programación, Documentación técnica, Dataset IA, Archivo web o Personalizado.
- **Identidad del proyecto**: autor, proyecto/Project ID, organización, idioma y descripción.
- **Trazabilidad**: cada dataset recibe `Dataset ID`, `Run ID`, fecha y versión del motor.
- **Quality Score**: cada documento obtiene una puntuación 0–100 antes de entrar al dataset.
- **SHA-256**: cada documento aceptado queda identificado mediante hash de contenido.
- **Deduplicación por contenido**: evita almacenar páginas diferentes con el mismo contenido.
- **Manifiesto WSOS**: junto al `.txt` se genera un `.wsos.json` con metadatos, estadísticas y documentos.
- **Estadísticas**: URLs encontradas/únicas, documentos válidos, descartados, duplicados y caracteres.
- **Normalización de URLs**: eliminación de parámetros de tracking y duplicados antes del scraping.
- **Parser optimizado**: uso de `lxml` cuando está disponible, con fallback a `html.parser`.
- **Límite de HTML**: páginas excesivamente grandes se descartan para proteger rendimiento y memoria.

## Novedades de la versión 1.11

| Cambio | Descripción |
|--------|-------------|
| **Búsqueda anidada (paralela)** | Las keywords ya no se consultan una a una: hasta **8 workers** lanzan consultas DuckDuckGo a la vez. |
| **Dataset en paralelo** | La descarga de páginas para `dataset_wsos_*` / `dataset_dirty_*` usa hasta **6 workers** concurrentes. |
| **Categorías en paralelo** | La extracción de contenido por categoría descarga hasta **6 URLs** simultáneas; la escritura a disco sigue ordenada y particionada. |
| **Motor thread-safe** | Cada hilo abre su propia sesión `DDGS`, evitando conflictos en búsquedas concurrentes. |
| **Versionado** | Banner y título de ventana: **WSOS SCRIPTING 1.11**. |

> Historial completo en [CHANGELOG.md](CHANGELOG.md).

### Resumen de versiones anteriores

| Versión | Enfoque |
|---------|---------|
| **1.0** | Lanzamiento: UI Flet, búsqueda multi-región, Modo WSOS, Búsqueda Sucia, categorías, optimizer en UI. |
| **1.1** | UI más limpia: eliminación del botón JSON Optimizer de la barra de acciones. |
| **1.11** | Rendimiento: búsqueda y scraping anidados en paralelo. |

---

## Características principales

| Característica | Detalle |
|----------------|---------|
| **Interfaz Flet** | Modo oscuro, consola en vivo, barra de progreso y botones con animación. |
| **Búsqueda multi-región** | España (`es-es`), USA (`us-en`), UK (`uk-en`) y Global (`wt-wt`). |
| **Búsqueda anidada** | Keywords en paralelo (hasta 8 hilos) con parada segura. |
| **Filtro de URLs** | Bloqueo de dominios publicitarios y eliminación de `utm_*`, `gclid`, `fbclid`, `mscclkid`, etc. |
| **Modo WSOS** | Expansión semántica de keywords + validación de contenido útil + `dataset_wsos_*.txt`. |
| **Búsqueda Sucia** | Expansión masiva de términos + sin filtros de tracking → máximo volumen de enlaces. |
| **Gestión de categorías** | Crear / eliminar desde diálogo modal; persistencia en `webs.json`. |
| **Extracción inteligente** | BeautifulSoup + limpieza de ruido, preservando bloques de código Markdown. |
| **Scraping paralelo** | Hasta 6 descargas HTTP concurrentes en datasets y categorías. |
| **Salida por lotes** | Archivos `*_part_N.txt` (~500 líneas) para datasets grandes. |
| **Parada segura** | `threading.Event` interrumpe búsquedas y scrapings en cualquier momento. |
| **Auto-configurador** | `actualizador.py` instala dependencias y crea plantilla de `webs.json`. |

---

## Arquitectura del proyecto

```
WSOS Scripting/
├── main.py                 # Punto de entrada (Flet)
├── ui.py                   # Interfaz gráfica, hilos y captura de stdout
├── scraping.py             # Orquestador (búsqueda anidada + categorías + dataset)
├── actualizador.py         # Instalador de dependencias + plantilla webs.json
├── webs.json               # Persistencia de categorías y URLs
├── core/
│   ├── __init__.py
│   ├── buscadores.py       # Motor DuckDuckGo (DDGS) thread-safe
│   ├── bloqueos.py         # Filtro de dominios y trackers
│   ├── buscawebs.py        # Búsqueda auxiliar (legado)
│   ├── procesador.py       # Descarga HTML → texto limpio + código
│   └── categorias.py       # Scraping paralelo por categoría + particionado
├── README.md
└── CHANGELOG.md
```

**Flujo de datos (v1.11):**

```
Usuario (UI)
    │
    ├─► Búsqueda webs
    │       │
    │       ▼
    │   Keywords expandidas (WSOS / Sucia / estándar)
    │       │
    │       ▼
    │   ThreadPoolExecutor (hasta 8 workers)
    │       ├── DDGS keyword 1
    │       ├── DDGS keyword 2
    │       └── DDGS keyword N   ← en paralelo
    │       │
    │       ▼
    │   URLFilter → webs.json + .txt
    │   (+ dataset paralelo si WSOS/Sucia)
    │
    └─► Categoría X
            │
            ▼
        ThreadPoolExecutor (hasta 6 workers)
            ├── scrape URL 1
            ├── scrape URL 2
            └── scrape URL N
            │
            ▼
        *_part_N.txt (escritura ordenada)
```

---

## Requisitos

- **Python** 3.10 o superior
- Conexión a Internet
- Dependencias (instaladas por `actualizador.py`):
  - `flet`
  - `requests`
  - `beautifulsoup4`
  - `lxml`
  - `ddgs`

---

## Instalación rápida

```bash
# 1. Clonar o descargar el repositorio
git clone <url-del-repositorio>
cd <carpeta-del-proyecto>

# 2. Configurar entorno (dependencias + webs.json de ejemplo)
python3 actualizador.py

# 3. Lanzar la aplicación
python3 main.py
```

El script `actualizador.py` genera `instalacion_log.txt` con el historial de la configuración.

---

## Guía de uso

### 1. Crear una categoría (obligatorio antes de buscar)

1. Pulsa el botón morado **Categorías** (arriba a la derecha).
2. Escribe un nombre (ej. `python_docs`, `cpu`, `electronica`).
3. Pulsa **Añadir** y cierra el panel.

### 2. Búsqueda de webs

1. En **Selecciona la Operación** elige **Búsqueda webs**.
2. Rellena keywords, archivo `.txt` de salida, región y categoría de destino.
3. (Opcional) Activa **Modo WSOS** o **Búsqueda Sucia** (excluyentes).
4. Pulsa **Ejecutar Proceso** y observa la consola: verás términos completándose en paralelo.
5. Puedes detener en cualquier momento con **Detener Proceso**.

### 3. Extracción de contenido de una categoría

1. Selecciona la categoría en el desplegable principal.
2. Pulsa **Ejecutar Proceso**.
3. Se generan archivos `categoria_part_1.txt`, `categoria_part_2.txt`, …

### 4. Abrir carpeta de resultados

El botón **Abrir Carpeta** abre el directorio de trabajo del proyecto.

---

## Modos de búsqueda avanzados

| Modo | Qué hace | Cuándo usarlo |
|------|----------|---------------|
| **Estándar** | Keywords tal cual + filtro de trackers. ~5 resultados/término. | Búsquedas precisas. |
| **Modo WSOS** | Expande con `documentation`, `github`, `tutorial`, `source code`, `examples`. Valida contenido (>300 caracteres). Genera `dataset_wsos_*.txt`. | Datasets técnicos de calidad. |
| **Búsqueda Sucia** | Expande con ~20 sufijos. Sin filtro de trackers. Genera `dataset_dirty_*.txt`. | Máximo volumen de enlaces. |

En **1.11**, tanto WSOS como Búsqueda Sucia se benefician especialmente de la búsqueda anidada: más términos = más ganancia de velocidad.

---

## Búsqueda anidada (paralela)

A partir de la **1.11**, el cuello de botella secuencial desaparece:

| Fase | Workers por defecto | Archivo |
|------|---------------------|---------|
| Consultas DuckDuckGo por keyword | **8** | `scraping.py` → `MAX_SEARCH_WORKERS` |
| Descarga de páginas (dataset WSOS/Sucia) | **6** | `scraping.py` → `MAX_SCRAPE_WORKERS` |
| Extracción de categoría | **6** | `core/categorias.py` → `MAX_CATEGORY_WORKERS` |

Cada worker de búsqueda crea su propia instancia de `MultiSearchEngine` / sesión `DDGS`.  
La parada del usuario cancela futures pendientes de forma segura.

---

## Flujo de trabajo recomendado

```
1. Crear categoría(s)          →  Categorías → Añadir
2. Buscar enlaces              →  Búsqueda webs + región + categoría destino
3. (Opcional) Revisar webs.json
4. Extraer contenido           →  Seleccionar categoría → Ejecutar
5. Usar los *_part_N.txt       →  RAG, análisis, documentación, etc.
```

---

## Estructura de archivos generados

| Archivo | Origen | Contenido |
|---------|--------|-----------|
| `enlaces_encontrados.txt` (o el nombre indicado) | Búsqueda webs | Lista de URLs |
| `webs.json` | Persistente | Categorías y URLs |
| `dataset_wsos_*.txt` | Modo WSOS | Contenido limpio validado |
| `dataset_dirty_*.txt` | Búsqueda Sucia | Contenido limpio (búsqueda sin filtro de trackers) |
| `categoria_part_N.txt` | Extracción de categoría | Texto estructurado por fuente |
| `instalacion_log.txt` | `actualizador.py` | Log de instalación |

---

## Configuración (`webs.json`)

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

- Claves = nombres de categoría (minúsculas internamente).
- Valores = listas de URLs.
- Editable a mano o desde la UI (crear / borrar categorías).

---

## Ajuste de rendimiento

Si DuckDuckGo limita peticiones o la red es inestable, reduce los workers en el código:

```python
# scraping.py
MAX_SEARCH_WORKERS = 8   # bajar a 4 si hay rate-limit
MAX_SCRAPE_WORKERS = 6   # bajar a 3–4 en redes lentas

# core/categorias.py
MAX_CATEGORY_WORKERS = 6
```

Si la red es estable y quieres más velocidad, puedes subir a 10–12 con precaución.

---

## Solución de problemas

| Problema | Posible causa / solución |
|----------|---------------------------|
| `No se encuentra webs.json` | Ejecutar `python3 actualizador.py` o crear el archivo manualmente. |
| Error al importar `ddgs` / `flet` | Reejecutar el actualizador o `pip install flet requests beautifulsoup4 ddgs`. |
| Pocos resultados | Probar otra región, activar WSOS o Búsqueda Sucia, ampliar keywords. |
| Errores frecuentes en DDGS | Bajar `MAX_SEARCH_WORKERS` (posible rate-limit). |
| Contenido vacío en extracción | La página puede bloquear el User-Agent; revisar logs en consola. |
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

**WSOS Scripting 1.12** is a desktop tool (Flet GUI) that:

- Searches technical links via DuckDuckGo with multi-region support and strict tracker/ad filtering.
- Organizes URLs into persistent categories (`webs.json`).
- Extracts clean text from pages while preserving code blocks.
- Offers **WSOS** mode (semantic keyword expansion + content validation) and **Dirty Search** (maximum volume).
- **v1.11** introduces **nested parallel search**: up to 8 concurrent DuckDuckGo queries and up to 6 concurrent page downloads for datasets and categories.

```bash
python3 actualizador.py   # install deps + create webs.json template
python3 main.py           # launch the app
```

See the Spanish sections above for full usage, architecture and legal notice.

---

**¿Te resulta útil?** Adáptalo a tus necesidades, ajusta los workers o integra nuevos motores.  
Construido con ❤️ para automatizar el trabajo tedioso de recopilar y limpiar información técnica.


### Refinamiento 1.12
- `requests.Session()` persistente por worker con pooling/keep-alive.
- Rate limiting independiente por dominio.
- Filtrado temprano de extensiones binarias.
- Soporte PDF opcional mediante `pypdf`.
- Limpieza ampliada de boilerplate (cookies, anuncios, popups y sidebars).
- Campo de licencia en los metadatos del dataset.
- WSOS Engine Report con calidad media, velocidad y tiempo.
