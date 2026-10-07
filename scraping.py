# scraping.py
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import time
import requests

from core import bloqueos, buscadores, categorias
from core.red import RateLimiter, DomainRateLimiter
from core.dataset import PROFILES, OBJECTIVES, build_metadata, normalize_url, write_manifest

# Workers concurrentes para búsqueda anidada (keywords en paralelo)
MAX_SEARCH_WORKERS = 8
# Workers concurrentes para descarga de páginas (dataset / categorías)
MAX_SCRAPE_WORKERS = 10


# Habilitar soporte para colores ANSI en la terminal de Windows
if os.name == "nt":
  os.system("")


class IntegratedCodeScraper:

  def __init__(self, config_file: str = "webs.json"):
    self.config_file = Path(config_file)
    self.url_filter = bloqueos.URLFilter()
    self.search_engine = buscadores.MultiSearchEngine()

    self.RED = "\033[91m"
    self.BOLD = "\033[1m"
    self.RESET = "\033[0m"

  def load_config(self) -> dict:
    if not self.config_file.exists():
      print(f"[!] No se encuentra el archivo '{self.config_file}'. Créalo primero.")
      return {}
    with open(self.config_file, "r", encoding="utf-8") as f:
      return json.load(f)

  def create_category(self, category_name: str) -> bool:
    """Crea una nueva categoría vacía en el archivo webs.json si no existe."""
    data = self.load_config()
    cat_key = category_name.strip().lower()
    if not cat_key:
      return False
    
    if cat_key not in data:
      data[cat_key] = []
      with open(self.config_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
      print(f"[+] Categoría '{cat_key}' creada con éxito en '{self.config_file}'.")
      return True
    return False

  def delete_category(self, category_name: str) -> bool:
    """Elimina una categoría existente del archivo webs.json."""
    data = self.load_config()
    cat_key = category_name.strip().lower()
    
    if cat_key in data:
      del data[cat_key]
      with open(self.config_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
      print(f"[-] Categoría '{cat_key}' eliminada de '{self.config_file}'.")
      return True
    return False

  def add_urls_to_category(self, category_name: str, urls: list):
    """Añade una lista de URLs a una categoría en el JSON evitando duplicados."""
    if not category_name or not urls:
      return
      
    data = self.load_config()
    cat_key = category_name.strip().lower()
    
    if cat_key not in data:
      data[cat_key] = []

    added = 0
    for url in urls:
      if url not in data[cat_key]:
        data[cat_key].append(url)
        added += 1

    if added > 0:
      with open(self.config_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
      print(f"[+] Se han guardado {added} URLs nuevas directamente en la categoría '{cat_key}' del JSON.")

  def optimize_webs_json(self, stop_event=None):
    """Verifica todas las URLs del JSON, hace un respaldo y elimina las rotas (404, etc.)."""
    if not self.config_file.exists():
      print(f"[!] No se encuentra el archivo '{self.config_file}'.")
      return

    bak_file = self.config_file.with_suffix(".json.bak")
    shutil.copy(self.config_file, bak_file)
    print(f"[*] Copia de seguridad creada en: {bak_file}")

    data = self.load_config()
    optimized_data = {}
    total_checked = 0
    total_removed = 0

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }

    for category, urls in data.items():
      if stop_event and stop_event.is_set():
        print("[!] Optimización detenida por el usuario.")
        break

      print(f"\n[🔍] Verificando categoría: {category.upper()}")
      valid_urls = []
      for url in urls:
        if stop_event and stop_event.is_set():
          break
        total_checked += 1
        try:
          res = requests.head(
              url, headers=headers, timeout=5, allow_redirects=True
          )
          if res.status_code == 405:  # Si HEAD no está permitido, probamos GET
            res = requests.get(url, headers=headers, timeout=5, stream=True)
            res.close()

          if res.status_code < 400:
            print(f"  [✔] OK ({res.status_code}): {url}")
            valid_urls.append(url)
          else:
            print(f"  [✘] Rota/Error ({res.status_code}): {url}")
            total_removed += 1
        except Exception as e:
          print(f"  [✘] Error de conexión: {url}")
          total_removed += 1

      optimized_data[category] = valid_urls

    with open(self.config_file, "w", encoding="utf-8") as f:
      json.dump(optimized_data, f, indent=4, ensure_ascii=False)

    print(
        f"\n[+] Optimización finalizada. URLs revisadas: {total_checked} |"
        f" Eliminadas: {total_removed}"
    )

  def search_custom_gui(
      self,
      output_filename,
      raw_keywords,
      wsos_mode=False,
      dirty_mode=False,
      region="es-es",
      stop_event=None,
      save_category=None,
      progress_callback=None,
      profile="Equilibrado",
      author="",
      project="",
      organization="",
      description="",
      language="es",
      objective="Investigación",
      stats_callback=None,
      allow_pdf=False,
      license_name="",
  ):
    """Realiza una búsqueda personalizada utilizando la región especificada.

    Si dirty_mode está activado, realiza pasadas masivas encadenadas para raspar
    cientos de URLs a cascoporro.
    """
    run_started = time.monotonic()
    # Asignar la región elegida al motor de búsqueda
    self.search_engine.region = region

    base_keywords = [kw.strip() for kw in raw_keywords.split(",") if kw.strip()]
    keywords_list = list(base_keywords)

    # Si es Búsqueda Sucia, generamos automáticamente variaciones masivas de sufijos para aspirar cientos de resultados únicos
    if dirty_mode:
      print("[🔥 BÚSQUEDA SUCIA] Generando matriz masiva de expansiones para aspirar cientos de URLs...")
      sufijos_masivos = [
          "", "wiki", "docs", "api", "tutorial", "blog", "forum", "download", 
          "examples", "github", "code", "index", "resources", "community", 
          "posts", "articles", "guide", "manual", "reference", "pdf"
      ]
      expanded_dirty_list = []
      for kw in base_keywords:
        for suf in sufijos_masivos:
          term = f"{kw} {suf}".strip()
          if term not in expanded_dirty_list:
            expanded_dirty_list.append(term)
      keywords_list = expanded_dirty_list
      print(f"[🔥 BÚSQUEDA SUCIA] Matriz generada: {len(keywords_list)} combinaciones de búsqueda preparadas.")

    # 1. PILAR WSOS: Auto-Expansión de Palabras Clave por Algoritmo Semántico (solo si no está en modo sucio)
    elif wsos_mode:
      print("[🧠 WSOS] Activando Auto-Expansión Semántica de Palabras Clave...")
      semantic_extensions = [
          "documentation",
          "github",
          "tutorial",
          "source code",
          "examples",
      ]
      for kw in base_keywords:
        for ext in semantic_extensions:
          expanded_kw = f"{kw} {ext}"
          if expanded_kw not in keywords_list:
            keywords_list.append(expanded_kw)
      print(
          "[🧠 WSOS] Términos expandidos automáticamente:"
          f" {len(keywords_list)} keywords en total."
      )

    all_found_urls = []

    print(
        f"[*] Iniciando búsqueda ANIDADA (paralela) [Región: {region}] "
        f"(Modo WSOS: {'ACTIVADO' if wsos_mode else 'DESACTIVADO'} | "
        f"Búsqueda Sucia: {'ACTIVADA' if dirty_mode else 'DESACTIVADA'})"
    )

    max_res = 15 if dirty_mode else (10 if wsos_mode else 5)
    workers = min(MAX_SEARCH_WORKERS, max(1, len(keywords_list)))
    print(
        f"[⚡] Búsqueda anidada: {len(keywords_list)} términos "
        f"con {workers} workers concurrentes..."
    )

    def _search_one(kw: str) -> list:
      """Worker: lanza una consulta DDGS independiente por keyword."""
      if stop_event and stop_event.is_set():
        return []
      # Cada hilo usa su propia instancia de motor para evitar conflictos
      engine = buscadores.MultiSearchEngine(
          region=region, safesearch=self.search_engine.safesearch,
          rate_limiter=search_rate_limiter, stop_event=stop_event
      )
      return engine.fetch_urls_with_fallbacks(kw, max_results=max_res)

    # --- Búsqueda anidada: todas las keywords en paralelo ---
    search_rate_limiter = RateLimiter(0.20)
    executor = ThreadPoolExecutor(max_workers=workers)
    future_map = {executor.submit(_search_one, kw): kw for kw in keywords_list}
    completed_searches = 0
    try:
      for future in as_completed(future_map):
        if stop_event and stop_event.is_set():
          for f in future_map:
            if not f.done():
              f.cancel()
          print("[!] Búsqueda detenida por el usuario.")
          break
        kw = future_map[future]
        try:
          urls = future.result()
          all_found_urls.extend(urls)
          print(f"  [✔] Término completado: '{kw}' → {len(urls)} enlaces")
        except Exception as exc:
          print(f"  [!] Error en término '{kw}': {exc}")
        completed_searches += 1
        if progress_callback:
          progress_callback(completed_searches, len(keywords_list), f"Búsqueda: {completed_searches}/{len(keywords_list)}")
    finally:
      executor.shutdown(wait=False, cancel_futures=True)

    # Normalización + deduplicación temprana: evita trabajo de red redundante.
    profile_cfg = PROFILES.get(profile, PROFILES["Equilibrado"])
    print(f"[⚙] Perfil: {profile} | Objetivo: {objective} | Calidad mínima: {profile_cfg['quality_min']}")
    normalized = []
    seen = set()
    source_urls = (
        [u for u in all_found_urls if self.url_filter.is_supported_resource(u, allow_pdf=allow_pdf)]
        if dirty_mode else self.url_filter.clean_and_validate(all_found_urls, allow_pdf=allow_pdf)
    )
    for u in source_urls:
      if stop_event and stop_event.is_set():
        break
      nu = normalize_url(u)
      if nu and nu.startswith(("http://", "https://")) and nu not in seen:
        seen.add(nu)
        normalized.append(nu)
    clean_urls = normalized
    print(f"[⚡] URLs únicas tras normalización: {len(clean_urls)}")

    # Guardar resultados en el archivo de salida base .txt
    try:
      with open(output_filename, "w", encoding="utf-8") as f:
        for url in clean_urls:
          f.write(f"{url}\n")
      print(
          f"[+] Resultados guardados en '{output_filename}'"
          f" ({len(clean_urls)} enlaces masivos)."
      )
    except Exception as e:
      print(f"[!] Error al guardar el archivo de salida: {e}")

    # Si se indicó una categoría de destino, guardar en el JSON estrictamente en la categoría elegida
    added_count = 0
    if save_category and clean_urls:
      cat_key = save_category.strip().lower()
      data = self.load_config()
      if cat_key not in data:
        data[cat_key] = []
      
      for url in clean_urls:
        if url not in data[cat_key]:
          data[cat_key].append(url)
          added_count += 1

      with open(self.config_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
      
      if dirty_mode:
        print(f"[+] [BÚSQUEDA SUCIA] ¡Volcado masivo completado! {added_count} URLs nuevas añadidas a la categoría '{cat_key}' ({len(clean_urls)} totales procesadas).")
      else:
        print(f"[+] Se han guardado {added_count} URLs nuevas en la categoría '{cat_key}' del JSON.")

    # 2. PROCESAMIENTO DE DATASET (paralelo: descarga anidada de páginas)
    total_chars_dataset = 0
    if (wsos_mode or dirty_mode) and clean_urls:
      mode_label = "WSOS" if wsos_mode else "BÚSQUEDA SUCIA"
      print(
          f"[🚀 {mode_label}] Pipeline de Dataset en paralelo "
          f"({min(MAX_SCRAPE_WORKERS, len(clean_urls))} workers)..."
      )
      from core.procesador import WebProcessor

      processor = WebProcessor(stop_event=stop_event, rate_limiter=DomainRateLimiter(profile_cfg["rate_limit"]))
      dataset_filename = f"dataset_{'wsos' if wsos_mode else 'dirty'}_{output_filename}"

      def _scrape_one(url: str):
        if stop_event and stop_event.is_set():
          return {"url": url, "content": "", "quality": 0, "sha256": ""}
        return processor.scrape_url_details(url, stop_event=stop_event, allow_pdf=allow_pdf)

      results = []
      scrape_workers = min(MAX_SCRAPE_WORKERS, max(1, len(clean_urls)))
      executor = ThreadPoolExecutor(max_workers=scrape_workers)
      futures = {executor.submit(_scrape_one, url): url for url in clean_urls}
      completed_scrapes = 0
      try:
        for future in as_completed(futures):
          if stop_event and stop_event.is_set():
            for f in futures:
              if not f.done():
                f.cancel()
            print("[!] Pipeline detenido por el usuario.")
            break
          try:
            results.append(future.result())
          except Exception as exc:
            url = futures[future]
            print(f"  [!] Error al raspar {url}: {exc}")
            results.append({"url": url, "content": "", "quality": 0, "sha256": ""})
          completed_scrapes += 1
          if progress_callback:
            progress_callback(completed_scrapes, len(clean_urls), f"Dataset: {completed_scrapes}/{len(clean_urls)}")
      finally:
        executor.shutdown(wait=False, cancel_futures=True)

      documents = []
      accepted_hashes = set()
      duplicates = 0
      rejected_quality = 0
      accepted = 0
      with open(dataset_filename, "w", encoding="utf-8") as ds_file:
        ds_file.write(
            f"=== DATASET AUTOMÁTICO {mode_label} - KEYWORDS: {raw_keywords} ===\n"
            f"=== PERFIL: {profile} | OBJETIVO: {objective} ===\n\n"
        )
        for item in results:
          url = item.get("url", "")
          content = item.get("content", "")
          quality = item.get("quality", 0)
          digest = item.get("sha256", "")
          if content and len(content) >= profile_cfg["min_chars"] and quality >= profile_cfg["quality_min"]:
            if profile_cfg["deduplicate"] and digest in accepted_hashes:
              duplicates += 1
              continue
            accepted_hashes.add(digest)
            ds_file.write(f"\n\n--- FUENTE VALIDADA: {url} | QUALITY: {quality}/100 | SHA256: {digest} ---\n\n{content}")
            total_chars_dataset += len(content)
            accepted += 1
            documents.append({"url": url, "quality": quality, "sha256": digest, "chars": len(content)})
          else:
            rejected_quality += 1
            print(f"  [✘ {mode_label} Descartado] Calidad insuficiente ({quality}/100): {url}")

      metadata = build_metadata(
          author=author, project=project, organization=organization, description=description,
          language=language, objective=objective, profile=profile, keywords=raw_keywords,
          mode=mode_label, license_name=license_name,
      )
      elapsed = max(0.001, time.monotonic() - run_started)
      total_bytes = sum(int(item.get("bytes", 0) or 0) for item in results)
      avg_quality = round(sum(d["quality"] for d in documents) / max(1, len(documents)), 1)
      stats = {
          "urls_found": len(all_found_urls), "urls_unique": len(clean_urls),
          "documents_accepted": accepted, "documents_rejected": rejected_quality,
          "duplicates": duplicates, "characters": total_chars_dataset,
          "quality_min": profile_cfg["quality_min"], "average_quality": avg_quality,
          "download_bytes": total_bytes, "elapsed_seconds": round(elapsed, 2),
          "urls_per_second": round(len(clean_urls) / elapsed, 2),
          "pdf_enabled": bool(allow_pdf),
      }
      manifest_path = write_manifest(dataset_filename, metadata, stats, documents)
      print(f"[+] Manifiesto WSOS generado: {manifest_path}")
      print(f"[🆔] Dataset ID: {metadata['dataset_id']} | Run ID: {metadata['run_id']}")
      print(f"[📊] Dataset: {accepted} válidos | {duplicates} duplicados | {rejected_quality} descartados | {total_chars_dataset} caracteres")
      print("\n╔══════════════════════════════════════╗")
      print("║          WSOS ENGINE REPORT          ║")
      print("╠══════════════════════════════════════╣")
      print(f"║ URLs encontradas : {len(all_found_urls):>16} ║")
      print(f"║ URLs únicas      : {len(clean_urls):>16} ║")
      print(f"║ Docs aceptados   : {accepted:>16} ║")
      print(f"║ Duplicados       : {duplicates:>16} ║")
      print(f"║ Calidad media    : {avg_quality:>15}/100 ║")
      print(f"║ Velocidad        : {stats['urls_per_second']:>12} URL/s ║")
      print(f"║ Tiempo           : {stats['elapsed_seconds']:>13} s ║")
      print("╚══════════════════════════════════════╝")
      if stats_callback:
        stats_callback(metadata, stats)

      print(
          f"[+] ¡Dataset {mode_label} generado con éxito en"
          f" '{dataset_filename}'! ({total_chars_dataset} caracteres)."
      )

    # 📊 RESUMEN FINAL COMPLETO PARA AMBOS MODOS
    print("\n" + "=" * 50)
    print("📊 RESUMEN FINAL DE LA BÚSQUEDA:")
    print(f"   • Total de webs/enlaces añadidos: {added_count if save_category else len(clean_urls)}")
    print(f"   • Caracteres totales añadidos al dataset: {total_chars_dataset}")
    print("=" * 50 + "\n")

  def run_category_gui(self, selected_category, stop_event=None, progress_callback=None):
    """Ejecuta el scraping midiendo el tiempo transcurrido y delegando en el módulo unificado de categorías."""
    categories = self.load_config()
    urls_to_sample = categories.get(selected_category, [])

    print(
        f"[*] Iniciando categoría '{selected_category.upper()}'"
        f" ({len(urls_to_sample)} URLs)..."
    )
    start_time = time.time()

    try:
      categorias.run_category_scraping(
          selected_category, urls_to_sample, stop_event, progress_callback
      )
      elapsed = time.time() - start_time
      print(
          f"[+] Categoría '{selected_category.upper()}' finalizada con éxito en"
          f" {elapsed:.2f} segundos."
      )
    except Exception as e:
      elapsed = time.time() - start_time
      print(
          f"[!] Error en categoría '{selected_category.upper()}' tras"
          f" {elapsed:.2f} segundos: {e}"
      )