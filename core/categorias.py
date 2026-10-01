# core/categorias.py
import time
from .procesador import WebProcessor


def run_category_scraping(selected_category: str, urls_to_scrape: list, stop_event=None):
  """Ejecuta el scraping y fraccionamiento para cualquier categoría de forma unificada."""
  processor = WebProcessor()
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
      f"[🚀] Extracción para '{selected_category.upper()}'"
      f" ({len(urls_to_scrape)} fuentes)..."
  )
  start_time = time.time()
  total_chars = 0
  part_num = 1
  max_lines_per_file = 500
  current_output_filename = f"{base_filename}_part_{part_num}.txt"

  f_out = open(current_output_filename, "w", encoding="utf-8")
  f_out.write(
      f"=== DATASET: {selected_category.upper()} (Parte {part_num}) ===\n\n"
  )
  current_lines_in_file = 2

  for url in urls_to_scrape:
    if stop_event and stop_event.is_set():
      print("[!] Proceso detenido por el usuario.")
      break

    content = processor.scrape_url(url)

    if stop_event and stop_event.is_set():
      print("[!] Proceso detenido por el usuario.")
      break

    if content:
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