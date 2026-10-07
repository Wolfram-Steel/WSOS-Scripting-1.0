# Changelog

Todos los cambios relevantes de **WSOS Scripting** se documentan en este archivo.

El formato está inspirado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),  
y este proyecto sigue [Versionado Semántico](https://semver.org/lang/es/).

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
  buscawebs.py   → búsqueda auxiliar
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

[1.11.0]: https://github.com/<usuario>/<repo>/compare/v1.1.0...v1.11.0  
[1.1.0]: https://github.com/<usuario>/<repo>/compare/v1.0.0...v1.1.0  
[1.0.0]: https://github.com/<usuario>/<repo>/releases/tag/v1.0.0
