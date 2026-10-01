# buscawebs.py
import time
from pathlib import Path
import random
from .buscadores import MultiSearchEngine
from .bloqueos import URLFilter


class WebSearcher:

  def __init__(self, region: str = "es-es"):
    self.search_manager = MultiSearchEngine(region=region)
    self.url_filter = URLFilter()

  def search_custom_gui(
      self, output_filename, raw_keywords, auto_mode, region="es-es", stop_event=None
  ):
    """Ejecuta la búsqueda multi-motor con soporte de interrupción, región personalizable y manejo seguro de archivos."""
    # Actualizar la región del buscador con la seleccionada
    if region:
      self.search_manager.region = region

    if not output_filename.endswith(".txt"):
      output_filename += ".txt"

    keywords = [k.strip() for k in raw_keywords.split(",") if k.strip()]
    batch_size = 20
    session_urls = set()
    total_added_session = 0

    txt_path = Path(output_filename)
    if txt_path.exists():
      try:
        with open(txt_path, "r", encoding="utf-8") as f_in:
          for line in f_in:
            clean_l = line.strip().strip('"').strip("'").rstrip(",")
            if clean_l.startswith("http"):
              session_urls.add(clean_l)
      except Exception as e:
        print(f"[!] Aviso al leer el archivo previo de resultados: {e}")

    print(
        "[🚀] Iniciando búsqueda multi-motor en región "
        f"[{region.upper()}] en modo {'AUTOMÁTICO' if auto_mode else 'ESTÁNDAR'}..."
    )

    for idx, keyword in enumerate(keywords, 1):
      if stop_event and stop_event.is_set():
        print("[!] Proceso detenido por el usuario.")
        break

      print(
          f"[🔍 Término {idx}/{len(keywords)}] Buscando: '{keyword.upper()}'"
      )
      current_limit = batch_size
      while True:
        if stop_event and stop_event.is_set():
          print("[!] Proceso detenido por el usuario.")
          break

        raw_results_urls = self.search_manager.fetch_urls_with_fallbacks(
            keyword, current_limit
        )

        if stop_event and stop_event.is_set():
          print("[!] Proceso detenido por el usuario.")
          break

        results_urls = self.url_filter.clean_and_validate(raw_results_urls)

        new_urls = []
        for link in results_urls:
          if stop_event and stop_event.is_set():
            break
          if link not in session_urls:
            session_urls.add(link)
            new_urls.append(link)
            total_added_session += 1
            try:
              with open(output_filename, "a", encoding="utf-8") as f_txt:
                f_txt.write(f'"{link}",\n')
              print(f"  [+] Enlace guardado: {link}")
            except Exception as ex:
              print(f"  [!] Error al escribir el enlace en disco: {ex}")

        if stop_event and stop_event.is_set():
          break

        if not new_urls or not auto_mode:
          break
        current_limit += batch_size
        time.sleep(0.5)

    print(
        f"[+] Proceso finalizado. Total URLs guardadas: {total_added_session}"
    )