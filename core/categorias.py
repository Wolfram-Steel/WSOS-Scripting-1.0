import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from .procesador import WebProcessor
from .red import DomainRateLimiter
from .dataset import PROFILES


def _safe_filename(category: str) -> str:
  value = re.sub(r"[^A-Za-z0-9_-]+", "_", category.strip(), flags=re.ASCII).strip("._-")
  return value.lower() or "categoria"


def run_category_scraping(selected_category: str, urls_to_scrape: list, stop_event=None,
                          progress_callback=None, profile="Equilibrado"):
  """Descarga una categoría usando el perfil seleccionado y escritura segura."""
  cfg = PROFILES.get(profile, PROFILES["Equilibrado"])
  rate_limiter = DomainRateLimiter(cfg["rate_limit"])
  processor = WebProcessor(
      stop_event=stop_event,
      rate_limiter=rate_limiter,
      retries=cfg["retries"],
      max_chars=cfg["max_chars"],
  )
  base_filename = _safe_filename(selected_category)

  print(f"[🚀] Extracción PARALELA para '{selected_category.upper()}' ({len(urls_to_scrape)} fuentes)...")
  start_time = time.monotonic()
  total_chars = 0
  if not urls_to_scrape:
    print("[!] No hay URLs en esta categoría.")
    return

  workers = min(cfg["workers"], max(1, len(urls_to_scrape)))
  print(f"[⚡] {workers} workers | perfil {profile} | {cfg['retries']} reintentos...")

  def _scrape_one(url: str):
    if stop_event and stop_event.is_set():
      return url, ""
    return url, processor.scrape_url(url, stop_event=stop_event)

  ordered_results = [None] * len(urls_to_scrape)
  executor = ThreadPoolExecutor(max_workers=workers)
  futures = {executor.submit(_scrape_one, url): (i, url) for i, url in enumerate(urls_to_scrape)}
  completed = 0
  try:
    for future in as_completed(futures):
      i, url = futures[future]
      if stop_event and stop_event.is_set():
        for f in futures:
          if not f.done():
            f.cancel()
        print("[!] Proceso detenido por el usuario.")
        break
      try:
        u, content = future.result()
        ordered_results[i] = (u, content)
      except Exception as exc:
        print(f"      [!] Error al raspar {url}: {exc}")
        ordered_results[i] = (url, "")
      completed += 1
      if progress_callback:
        progress_callback(completed, len(urls_to_scrape), f"Descarga: {completed}/{len(urls_to_scrape)}")
  finally:
    executor.shutdown(wait=False, cancel_futures=True)

  part_num = 1
  max_lines_per_file = 500
  current_path = Path(f"{base_filename}_part_{part_num}.txt")
  current_path = Path(__file__).resolve().parent.parent / current_path
  f_out = current_path.open("w", encoding="utf-8")
  f_out.write(f"=== DATASET: {selected_category.upper()} (Parte {part_num}) ===\n\n")
  current_lines = 2
  try:
    for item in ordered_results:
      if stop_event and stop_event.is_set():
        print("[!] Escritura final detenida por el usuario.")
        break
      if not item:
        continue
      url, content = item
      if not content or len(content) < cfg["min_chars"]:
        continue
      block = f"\n\n--- FUENTE: {url} ---\n\n{content}"
      block_lines = block.splitlines()
      if current_lines + len(block_lines) > max_lines_per_file:
        f_out.close()
        part_num += 1
        current_path = Path(__file__).resolve().parent.parent / f"{base_filename}_part_{part_num}.txt"
        f_out = current_path.open("w", encoding="utf-8")
        f_out.write(f"=== DATASET: {selected_category.upper()} (Parte {part_num}) ===\n\n")
        current_lines = 2
      f_out.write(block)
      current_lines += len(block_lines)
      total_chars += len(content)
      print(f"      [+] Extraído con éxito de: {url}")
  finally:
    f_out.close()

  status = "interrumpido" if stop_event and stop_event.is_set() else "finalizado"
  print(f"[+] ¡Proceso {status}! {total_chars} caracteres procesados en {time.monotonic() - start_time:.2f}s.")
