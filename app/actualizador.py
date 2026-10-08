# actualizador.py
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent
CONFIG_DIR = BASE_DIR / "config"
REQUIREMENTS_FILE = CONFIG_DIR / "requirements.txt"

# Si falta requirements.txt se usa esta lista
DEFAULT_REQUIREMENTS = ["flet", "requests", "beautifulsoup4", "lxml", "pypdf", "ddgs"]
# Nombre en pip -> nombre del módulo al importarlo (no siempre coinciden)
IMPORT_NAMES = {"beautifulsoup4": "bs4"}

# Lista global para acumular los mensajes del log
LOG_BUFFER = []


def log_msg(mensaje: str):
    """Imprime por pantalla y guarda en el buffer para el archivo log.txt."""
    print(mensaje)
    LOG_BUFFER.append(mensaje)


def guardar_log_en_archivo():
    """Vuelca todo el buffer de mensajes a un archivo instalacion_log.txt."""
    log_path = CONFIG_DIR / "instalacion_log.txt"
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("=== LOG DE INSTALACIÓN Y CONFIGURACIÓN WSOS SCRIPTING ===\n")
            f.write(f"Fecha y hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Sistema: {platform.system()} ({platform.machine()})\n")
            f.write("=" * 65 + "\n\n")
            for linea in LOG_BUFFER:
                f.write(linea + "\n")
        print(f"\n[📝 LOG] Historial guardado correctamente en '{log_path}'")
    except Exception as e:
        print(f"[!] No se pudo generar el archivo de log: {e}")


def leer_requisitos(ruta: Path = REQUIREMENTS_FILE) -> list:
    """Líneas de requirements.txt (sin comentarios ni vacías), o la lista por defecto."""
    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
    except OSError:
        return list(DEFAULT_REQUIREMENTS)
    specs = [l.split("#", 1)[0].strip() for l in lineas]
    return [s for s in specs if s] or list(DEFAULT_REQUIREMENTS)


def nombre_paquete(spec: str) -> str:
    """'beautifulsoup4>=4.12' -> 'beautifulsoup4'."""
    return re.split(r"[<>=!~\[;\s]", spec, maxsplit=1)[0].strip().lower()


def esta_instalado(paquete: str) -> bool:
    modulo = IMPORT_NAMES.get(paquete, paquete.replace("-", "_"))
    try:
        return importlib.util.find_spec(modulo) is not None
    except (ImportError, ValueError):
        return False


def check_and_install_dependencies():
    """Verifica e instala las librerías de requirements.txt que falten."""
    log_msg("[*] Verificando dependencias de Python para WSOS Scripting...")
    if sys.prefix == sys.base_prefix:
        log_msg("  [i] Consejo: usa un entorno virtual (python -m venv .venv) para no tocar el Python del sistema.")

    for spec in leer_requisitos():
        paquete = nombre_paquete(spec)
        if esta_instalado(paquete):
            log_msg(f"  [✔] Paquete '{paquete}' -> Ya instalado en el entorno.")
            continue
        log_msg(f"  [!] Paquete '{paquete}' -> No encontrado. Instalando '{spec}' vía pip...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", spec])
            log_msg(f"  [+] Paquete '{paquete}' -> Instalado correctamente.")
        except Exception as e:
            log_msg(f"  [✘] ERROR CRÍTICO al instalar '{paquete}': {e}. Instálalo manualmente.")


def check_config_file():
    """Verifica la existencia de webs.json y crea una plantilla si no existe (nunca lo sobrescribe)."""
    config_path = CONFIG_DIR / "webs.json"
    if not config_path.exists():
        log_msg(f"\n[!] Archivo 'webs.json' no encontrado en: {config_path}")
        log_msg("    Creando plantilla inicial de ejemplo...")
        default_data = {
            "cpu": [
                "https://es.wikipedia.org/wiki/Unidad_central_de_proceso",
                "https://es.wikipedia.org/wiki/Microprocesador",
            ],
            "programacion": [
                "https://es.wikipedia.org/wiki/Python",
                "https://es.wikipedia.org/wiki/Flet",
            ],
        }
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_data, f, indent=4, ensure_ascii=False)
            log_msg(f"  [+] Plantilla 'webs.json' creada con éxito en: {config_path}")
        except Exception as e:
            log_msg(f"  [✘] No se pudo crear el archivo de configuración: {e}")
    else:
        log_msg(f"\n[✔] Archivo de configuración detectado en: {config_path}")


def _bat_value(value) -> str:
    """Valor seguro dentro de un .bat (los % se duplican)."""
    return str(value).replace("%", "%%")


def preparar_actualizacion_windows(archivos, destino=None):
    """Prepara una actualización para Windows sin sobrescribir archivos en uso.

    `archivos` debe ser un directorio que contenga la versión nueva. Devuelve la ruta
    del .bat generado. El .bat espera al cierre del proceso actual, guarda una copia de
    seguridad, copia los archivos nuevos y, si la copia falla, restaura la copia de
    seguridad. La copia de seguridad se conserva en `.wsos_update/backup`.

    Nota: no se purgan archivos que ya no existan en la versión nueva (así nunca se
    borran tus datos: config/webs.json, config/settings.json o la carpeta de salida).
    """
    if os.name != "nt":
        raise RuntimeError("Esta rutina está destinada a Windows.")

    source = Path(archivos).resolve()
    target = Path(destino or Path.cwd()).resolve()
    if not source.exists() or not source.is_dir():
        raise FileNotFoundError(f"Carpeta de actualización no válida: {source}")

    temp_root = target / ".wsos_update"
    staged = temp_root / "payload"
    backup = temp_root / "backup"
    if temp_root in source.parents or source == temp_root:
        raise ValueError("La carpeta de actualización no puede estar dentro de .wsos_update.")

    temp_root.mkdir(parents=True, exist_ok=True)
    if staged.exists():
        shutil.rmtree(staged)
    shutil.copytree(source, staged)

    script = temp_root / "aplicar_actualizacion.bat"
    python_exe = Path(sys.executable).resolve()
    script_text = f'''@echo off
setlocal EnableExtensions
set "TARGET={_bat_value(target)}"
set "STAGED={_bat_value(staged)}"
set "BACKUP={_bat_value(backup)}"
set "PID={os.getpid()}"
set "PYTHON={_bat_value(python_exe)}"

:WAIT
tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul
if not errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto WAIT
)

if exist "%BACKUP%" rmdir /s /q "%BACKUP%"
mkdir "%BACKUP%"

robocopy "%TARGET%" "%BACKUP%" /E /XD ".wsos_update" /R:1 /W:1 >nul
if errorlevel 8 goto FAIL

robocopy "%STAGED%" "%TARGET%" /E /COPY:DAT /R:3 /W:1 >nul
if errorlevel 8 goto ROLLBACK

rmdir /s /q "%STAGED%" >nul 2>&1
start "" "%PYTHON%" "%TARGET%\\main.py"
exit /b 0

:ROLLBACK
echo [WSOS] Error aplicando la actualizacion. Restaurando la copia de seguridad...
robocopy "%BACKUP%" "%TARGET%" /E /COPY:DAT /R:3 /W:1 >nul

:FAIL
echo [WSOS] La actualizacion no se ha aplicado. La copia de seguridad esta en "%BACKUP%".
pause
exit /b 1
'''
    script.write_text(script_text, encoding="utf-8")
    return script


def lanzar_actualizacion_windows(script_path):
    """Lanza el .bat separado; el proceso actual debe cerrarse después."""
    if os.name != "nt":
        raise RuntimeError("Esta rutina está destinada a Windows.")
    script = Path(script_path).resolve()
    subprocess.Popen(
        ["cmd.exe", "/c", str(script)],
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        close_fds=True,
    )
    return True


if __name__ == "__main__":
    log_msg("==================================================")
    log_msg("       WSOS SCRIPTING - AUTO-CONFIGURADOR")
    log_msg("==================================================\n")

    # 1. Dependencias base y archivo de configuración del programa
    check_and_install_dependencies()
    check_config_file()

    log_msg("\n==================================================")
    log_msg("   ¡CONFIGURACIÓN FINALIZADA!")
    log_msg("==================================================")
    log_msg("\n🤖 INSTRUCCIONES:")
    log_msg("   Revisa arriba que no haya errores. Después ejecuta:")
    log_msg("   python main.py")
    log_msg("==================================================")

    guardar_log_en_archivo()
    if sys.stdin and sys.stdin.isatty():
        input("\nPresiona Enter para cerrar esta ventana...")
