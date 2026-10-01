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
  required_packages = ["flet", "requests", "beautifulsoup4", "ddgs"]

  log_msg("[*] Verificando dependencias de Python para WSOS Scripting...")

  for package in required_packages:
    try:
      __import__(package)
      log_msg(f"  [✔] Paquete '{package}' -> Ya instalado en el entorno.")
    except ImportError:
      log_msg(f"  [!] Paquete '{package}' -> No encontrado. Instalando vía pip...")
      try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package]
        )
        log_msg(f"  [+] Paquete '{package}' -> Instalado correctamente.")
      except Exception as e:
        log_msg(
            f"  [✘] ERROR CRÍTICO al instalar '{package}': {e}. Instálalo manualmente."
        )


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