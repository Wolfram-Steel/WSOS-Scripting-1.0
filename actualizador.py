# actualizador.py
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Lista global para acumular los mensajes del log
LOG_BUFFER = []


def log_msg(mensaje: str):
  """Imprime por pantalla y guarda en el buffer para el archivo log.txt."""
  print(mensaje)
  LOG_BUFFER.append(mensaje)


def guardar_log_en_archivo():
  """Vuelca todo el buffer de mensajes a un archivo instalacion_log.txt."""
  log_path = Path("instalacion_log.txt")
  try:
    with open(log_path, "w", encoding="utf-8") as f:
      f.write(f"=== LOG DE INSTALACIÓN Y CONFIGURACIÓN WSOS SCRIPTING ===\n")
      f.write(f"Fecha y hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
      f.write(f"Sistema: {platform.system()} ({platform.machine()})\n")
      f.write("=" * 65 + "\n\n")
      for linea in LOG_BUFFER:
        f.write(linea + "\n")
    print(f"\n[📝 LOG] Historial guardado correctamente en '{log_path.absolute()}'")
  except Exception as e:
    print(f"[!] No se pudo generar el archivo de log: {e}")


def check_and_install_dependencies():
  """Verifica e instala de forma automática las librerías requeridas."""
  required_packages = [
      ("flet", "flet"),
      ("requests", "requests"),
      ("beautifulsoup4", "bs4"),
      ("lxml", "lxml"),
      ("pypdf", "pypdf"),
      ("ddgs", "ddgs"),
  ]

  log_msg("[*] Verificando dependencias de Python para WSOS Scripting...")

  for package, import_name in required_packages:
    try:
      __import__(import_name)
      log_msg(f"  [✔] Paquete '{package}' -> Ya instalado en el entorno.")
    except ImportError:
      log_msg(f"  [!] Paquete '{package}' -> No encontrado. Instalando vía pip...")
      try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        log_msg(f"  [+] Paquete '{package}' -> Instalado correctamente.")
      except Exception as e:
        log_msg(f"  [✘] ERROR CRÍTICO al instalar '{package}': {e}. Instálalo manualmente.")


def check_config_file():
  """Verifica la existencia del archivo webs.json y crea una plantilla si no existe."""
  config_path = Path("webs.json").absolute()
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


if __name__ == "__main__":
  log_msg("==================================================")
  log_msg("       WSOS SCRIPTING - AUTO-CONFIGURADOR")
  log_msg("==================================================\n")

  # 1. Dependencias base y archivo de configuración del programa
  check_and_install_dependencies()
  check_config_file()

  log_msg("\n==================================================")
  log_msg("   ¡CONFIGURACIÓN FINALIZADA CON ÉXITO!")
  log_msg("==================================================")
  log_msg("\n🤖 INSTRUCCIONES:")
  log_msg("   ¡Entorno listo! Ya puedes ejecutar tu programa principal con:")
  log_msg("   python main.py")
  log_msg("==================================================")

  guardar_log_en_archivo()
  input("\nPresiona Enter para cerrar esta ventana...")

def preparar_actualizacion_windows(archivos, destino=None):
  """Prepara una actualización para Windows sin sobrescribir archivos en uso.

  `archivos` debe ser un directorio temporal que contenga la versión nueva.
  Devuelve la ruta del .bat generado. El .bat espera al cierre del proceso
  actual, crea un backup y reemplaza los archivos de forma atómica por grupos.
  """
  if os.name != "nt":
    raise RuntimeError("Esta rutina está destinada a Windows.")

  source = Path(archivos).resolve()
  target = Path(destino or Path.cwd()).resolve()
  if not source.exists() or not source.is_dir():
    raise FileNotFoundError(f"Carpeta de actualización no válida: {source}")

  temp_root = target / ".wsos_update"
  temp_root.mkdir(parents=True, exist_ok=True)
  staged = temp_root / "payload"
  backup = temp_root / "backup"
  staged.mkdir(parents=True, exist_ok=True)
  backup.mkdir(parents=True, exist_ok=True)

  # Copia el payload al área privada de actualización.
  if staged.exists():
    for item in staged.iterdir():
      if item.is_dir():
        import shutil
        shutil.rmtree(item)
      else:
        item.unlink(missing_ok=True)
  import shutil
  shutil.copytree(source, staged, dirs_exist_ok=True)

  script = temp_root / "aplicar_actualizacion.bat"
  pid = os.getpid()
  python_exe = str(Path(sys.executable).resolve())
  script_text = f'''@echo off
setlocal EnableExtensions
set "TARGET={target}"
set "STAGED={staged}"
set "BACKUP={backup}"
set "PID={pid}"
set "PYTHON={python_exe}"

:WAIT
powershell -NoProfile -ExecutionPolicy Bypass -Command "try {{ $p=Get-Process -Id %PID% -ErrorAction Stop; exit 1 }} catch {{ exit 0 }}" >nul 2>&1
if not errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto WAIT
)

if exist "%BACKUP%" rmdir /s /q "%BACKUP%"
mkdir "%BACKUP%"

robocopy "%TARGET%" "%BACKUP%" /E /XD ".wsos_update" >nul
robocopy "%STAGED%" "%TARGET%" /E /COPY:DAT /R:3 /W:1 >nul
if errorlevel 8 goto FAIL

rmdir /s /q "%STAGED%" >nul 2>&1
start "" py "%TARGET%\\main.py"
rmdir /s /q "%~dp0" >nul 2>&1
exit /b 0

:FAIL
echo [WSOS] Error aplicando la actualizacion. El backup permanece en "%BACKUP%".
pause
exit /b 1
'''
  script.write_text(script_text, encoding="utf-8")
  return script


def lanzar_actualizacion_windows(script_path):
  """Lanza el .bat separado y termina el proceso actual."""
  if os.name != "nt":
    raise RuntimeError("Esta rutina está destinada a Windows.")
  script = Path(script_path).resolve()
  subprocess.Popen(
      ["cmd.exe", "/c", str(script)],
      creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
      close_fds=True,
  )
  return True
