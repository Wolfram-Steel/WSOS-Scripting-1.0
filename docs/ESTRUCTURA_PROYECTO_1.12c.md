# WSOS Scripting 1.12c — organización del proyecto

## Objetivo

Esta reorganización reduce el ruido visual de la raíz sin alterar el motor de WSOS Scripting 1.12c. Los únicos archivos normales que permanecen en la raíz son `main.py`, `README.md` y `CHANGELOG.md`.

## Mapa de responsabilidades

- `main.py`: único punto de arranque de la aplicación.
- `app/`: interfaz y orquestación de alto nivel.
- `core/`: motor de búsqueda, red, extracción, dataset, configuración y paralelismo.
- `config/`: datos/configuración persistente y configuración de herramientas.
- `tests/`: batería offline/local y fixtures.
- `docs/`: informes técnicos y documentación complementaria.
- `.github/`: workflow de integración continua, mantenido en la ubicación requerida por GitHub.

## Rutas persistentes

| Recurso | Ruta 1.12c reorganizada | Comportamiento |
| --- | --- | --- |
| Categorías/URLs | `config/webs.json` | Persistente, escritura atómica |
| Ajustes UI | `config/settings.json` | Se crea/actualiza al ejecutar |
| Dependencias | `config/requirements.txt` | Leído por actualizador y CI |
| Ruff | `config/pyproject.toml` | Usado con `ruff --config` |
| Log de instalación | `config/instalacion_log.txt` | Creado por `app/actualizador.py` |
| Resultados | `salida/` | Carpeta por defecto, configurable |
| Runs WSOS | `salida/runs/<RUN-ID>/` | Dataset + manifiesto por ejecución |

## Imports principales

```python
# main.py
from app.ui import ScraperUI

# app/ui.py
from app.scraping import IntegratedCodeScraper
```

Los módulos de `core/` siguen importándose como `core.*`. No se ha introducido una nueva capa de motor ni se ha cambiado el modelo de concurrencia.

## Compatibilidad funcional

La reorganización conserva:

- versión de aplicación 1.12c;
- `SCHEMA_VERSION = 1.12c`;
- búsqueda DuckDuckGo con máximo 3 workers;
- pool independiente de descargas, hasta 16 workers globales;
- `ThreadPoolExecutor`;
- rate limit adaptativo y por dominio;
- extracción HTML/PDF;
- Quality Score y deduplicación;
- Run ID, Dataset ID y publicación atómica de datasets;
- carpeta de salida configurable.

## Ejecución

```bash
python3 -m pip install -r config/requirements.txt
python3 app/actualizador.py   # opcional: verifica dependencias/configuración
python3 main.py
```

## Calidad y CI

```bash
ruff check --config config/pyproject.toml .
python3 -m unittest discover -s tests -t . -q
```

El workflow `.github/workflows/ci.yml` usa esas mismas rutas.

## Archivos auxiliares de desarrollo

El ZIP de distribución no incluye `.gitignore`, para cumplir la política de mantener en la raíz únicamente `main.py`, `README.md` y `CHANGELOG.md`. Esto no afecta a la ejecución de WSOS Scripting. Un repositorio de desarrollo puede añadir su propio `.gitignore` localmente.

### Regla de persistencia de Búsqueda webs

La Búsqueda webs estándar no utiliza carpeta de salida ni genera un `.txt` de enlaces.
Su destino obligatorio es `config/webs.json`, concretamente la categoría seleccionada en la interfaz.
El campo **Carpeta de salida** y su icono solo deben aparecer cuando la operación necesita generar archivos, como la extracción de una categoría o los datasets de WSOS/Búsqueda Sucia.

Esta separación evita duplicar la misma información en un archivo temporal y en el catálogo persistente de categorías.
