# core/categorias.py
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from .procesador import WebProcessor
from .red import DomainRateLimiter

# Workers concurrentes para descarga de páginas por categoría
MAX_CATEGORY_WORKERS = 6


def run_category_scraping(selected_category: str, urls_to_scrape: list, stop_event=None, progress_callback=None):
  """Ejecuta el scraping y fraccionamiento para cualquier categoría de forma unificada.

  Las descargas HTTP se lanzan en paralelo (anidadas); la escritura a disco
  se hace al final en orden para mantener el particionado por líneas.
  """
  rate_limiter = DomainRateLimiter(0.20)
  processor = WebProcessor(stop_event=stop_event, rate_limiter=rate_limiter)
  cat_lower = selected_category.lower()

  # Mapeo inteligente del nombre del archivo base de salida
  if "cpu" in cat_lower:
    base_filename = "cpu"
  elif "electronica" in cat_lower or "electronic" in cat_lower:
    base_filename = "electronica"
  elif "programacion" in cat_lower or "programming" in cat_lower:
    base_filename = "programacion"
  elif "trending" in cat_lower:
    base_filename = "trending_topics"
  else:
    base_filename = cat_lower.replace(" ", "_")

  print(
      f"[🚀] Extracción PARALELA para '{selected_category.upper()}'"
      f" ({len(urls_to_scrape)} fuentes)..."
  )
  start_time = time.time()
  total_chars = 0

  if not urls_to_scrape:
    print("[!] No hay URLs en esta categoría.")
    return

  # --- Fase 1: descarga anidada (concurrente) ---
  def _scrape_one(url: str):
    if stop_event and stop_event.is_set():
      return url, ""
    return url, processor.scrape_url(url, stop_event=stop_event)

  workers = min(MAX_CATEGORY_WORKERS, max(1, len(urls_to_scrape)))
  print(f"[⚡] {workers} workers concurrentes descargando páginas...")

  # Conservar orden original de URLs para escritura predecible
  ordered_results = [None] * len(urls_to_scrape)
  url_to_index = {url: i for i, url in enumerate(urls_to_scrape)}

  executor = ThreadPoolExecutor(max_workers=workers)
  futures = {executor.submit(_scrape_one, url): url for url in urls_to_scrape}
  completed = 0
  try:
    for future in as_completed(futures):
      if stop_event and stop_event.is_set():
        for f in futures:
          if not f.done():
            f.cancel()
        print("[!] Proceso detenido por el usuario.")
        break
      url = futures[future]
      try:
        u, content = future.result()
        ordered_results[url_to_index[url]] = (u, content)
      except Exception as exc:
        print(f"      [!] Error al raspar {url}: {exc}")
        ordered_results[url_to_index[url]] = (url, "")
      completed += 1
      if progress_callback:
        progress_callback(completed, len(urls_to_scrape), f"Descarga: {completed}/{len(urls_to_scrape)}")
  finally:
    executor.shutdown(wait=False, cancel_futures=True)

  # --- Fase 2: escritura secuencial con particionado por líneas ---
  part_num = 1
  max_lines_per_file = 500
  current_output_filename = f"{base_filename}_part_{part_num}.txt"

  f_out = open(current_output_filename, "w", encoding="utf-8")
  f_out.write(
      f"=== DATASET: {selected_category.upper()} (Parte {part_num}) ===\n\n"
  )
  current_lines_in_file = 2

  for item in ordered_results:
    if stop_event and stop_event.is_set():
      print("[!] Escritura final detenida por el usuario.")
      break
    if item is None:
      continue
    url, content = item
    if not content:
      continue

    source_block = f"\n\n--- FUENTE: {url} ---\n\n{content}"
    block_lines = source_block.splitlines()

    if current_lines_in_file + len(block_lines) > max_lines_per_file:
      f_out.close()
      part_num += 1
      current_output_filename = f"{base_filename}_part_{part_num}.txt"
      f_out = open(current_output_filename, "w", encoding="utf-8")
      f_out.write(
          f"=== DATASET: {selected_category.upper()} (Parte {part_num}) ===\n\n"
      )
      current_lines_in_file = 2

    f_out.write(source_block)
    current_lines_in_file += len(block_lines)
    total_chars += len(content)
    print(f"      [+] Extraído con éxito de: {url}")

  f_out.close()
  print(
      f"[+] ¡Proceso finalizado! {total_chars} caracteres procesados en"
      f" {time.time() - start_time:.2f}s."
  )
