# scraping.py
import os
import time
from pathlib import Path

from core import bloqueos, buscadores, categorias
from core.config import ConfigStore, DEFAULT_CONFIG, atomic_write_json, load_settings, output_path
from core.dataset import (
    REASON_LABELS, build_metadata, get_profile, normalize_url, select_documents, write_manifest,
)
from core.paralelo import run_parallel
from core.procesador import WebProcessor
from core.red import AdaptiveRateLimiter, DomainRateLimiter, RateLimiter, request_with_retry

# Workers concurrentes para búsqueda anidada (keywords en paralelo).
# Los workers de descarga los define el perfil de recopilación.
MAX_SEARCH_WORKERS = 3
HARD_WORKER_CAP = 16  # tope de seguridad para cualquier perfil

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


class IntegratedCodeScraper:

    def __init__(self, config_file=None, output_dir=None):
        settings = load_settings()
        self.store = ConfigStore(config_file or DEFAULT_CONFIG)
        self.config_file = self.store.path
        self.url_filter = bloqueos.URLFilter(settings.get("extra_blocked_domains"))
        self.search_engine = buscadores.MultiSearchEngine()
        self.output_dir = Path(output_dir or settings["output_dir"])

    # ------------------------------------------------------------------ categorías
    def load_config(self) -> dict:
        if not self.config_file.exists():
            print(f"[!] No se encuentra el archivo '{self.config_file}'. Créalo primero.")
            return {}
        return self.store.load()

    def create_category(self, category_name: str) -> bool:
        """Crea una categoría vacía en webs.json si no existe (sin distinguir mayúsculas)."""
        created = self.store.create_category(category_name)
        if created:
            print(f"[+] Categoría '{category_name.strip().lower()}' creada con éxito en '{self.config_file}'.")
        return created

    def delete_category(self, category_name: str) -> bool:
        """Elimina una categoría existente de webs.json."""
        key = self.store.resolve_key(category_name)
        if key is not None and self.store.delete_category(category_name):
            print(f"[-] Categoría '{key}' eliminada de '{self.config_file}'.")
            return True
        return False

    def add_urls_to_category(self, category_name: str, urls: list):
        """Añade URLs a una categoría evitando duplicados (comparación normalizada)."""
        if not category_name or not urls:
            return 0
        added = self.store.add_urls(category_name, urls)
        key = self.store.resolve_key(category_name) or category_name.strip().lower()
        if added:
            print(f"[+] Se han guardado {added} URLs nuevas en la categoría '{key}' del JSON.")
        return added

    def optimize_webs_json(self, stop_event=None):
        """Comprueba las URLs de webs.json y elimina solo las que devuelven 404/410.

        Los errores de conexión, 403 o 429 NO se consideran enlaces rotos (pueden ser un
        bloqueo, un corte de red o un límite temporal), así que esas URLs se conservan.
        """
        if not self.config_file.exists():
            print(f"[!] No se encuentra el archivo '{self.config_file}'.")
            return
        data = self.store.load()
        bak_file = self.config_file.with_name(self.config_file.name + ".bak")
        atomic_write_json(bak_file, data)
        print(f"[*] Copia de seguridad creada en: {bak_file}")

        limiter = DomainRateLimiter(0.10)
        optimized, checked, removed = {}, 0, 0
        for category, urls in data.items():
            if stop_event and stop_event.is_set():
                print("[!] Optimización detenida por el usuario.")
                optimized[category] = list(urls)
                continue
            print(f"\n[🔍] Verificando categoría: {category.upper()}")
            kept = []
            for index, url in enumerate(urls):
                if stop_event and stop_event.is_set():
                    kept.extend(urls[index:])
                    break
                checked += 1
                status = self._probe(url, limiter, stop_event)
                if status in (404, 410):
                    print(f"  [✘] Rota ({status}): {url}")
                    removed += 1
                    continue
                label = f"OK ({status})" if status and status < 400 else f"se conserva, no verificable ({status or 'sin respuesta'})"
                print(f"  [✔] {label}: {url}")
                kept.append(url)
            optimized[category] = kept
        self.store.save(optimized)
        print(f"\n[+] Optimización finalizada. URLs revisadas: {checked} | Eliminadas: {removed}")

    @staticmethod
    def _probe(url, limiter, stop_event):
        """Código HTTP de la URL (HEAD y, si no es concluyente, GET); None si no responde."""
        status = None
        for method in ("HEAD", "GET"):
            try:
                response = request_with_retry(
                    method, url, headers=HEADERS, timeout=(5, 8), attempts=2,
                    rate_limiter=limiter, stop_event=stop_event, stream=(method == "GET"),
                )
            except Exception:  # noqa: BLE001
                return status
            if response is None:
                return status
            status = response.status_code
            response.close()
            if status < 400 or status in (404, 410) and method == "GET":
                return status
            if method == "HEAD" and status not in (400, 403, 404, 405, 501):
                return status
        return status

    # ------------------------------------------------------------------ búsqueda
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
        """Búsqueda personalizada por región; con WSOS/Sucia genera además un dataset validado."""
        run_started = time.monotonic()
        stage_started = run_started
        stage_timings = {}
        self.search_engine.region = region
        profile_cfg = get_profile(profile)

        base_keywords = [kw.strip() for kw in raw_keywords.split(",") if kw.strip()]
        keywords_list = list(base_keywords)

        if dirty_mode:
            print("[🔥 BÚSQUEDA SUCIA] Generando matriz masiva de expansiones para aspirar cientos de URLs...")
            sufijos_masivos = [
                "", "wiki", "docs", "api", "tutorial", "blog", "forum", "download",
                "examples", "github", "code", "index", "resources", "community",
                "posts", "articles", "guide", "manual", "reference",
            ]
            expanded = []
            for kw in base_keywords:
                for suf in sufijos_masivos:
                    term = f"{kw} {suf}".strip()
                    if term not in expanded:
                        expanded.append(term)
            keywords_list = expanded
            print(f"[🔥 BÚSQUEDA SUCIA] Matriz generada: {len(keywords_list)} combinaciones de búsqueda preparadas.")
        elif wsos_mode:
            print("[🧠 WSOS] Activando expansión de palabras clave por sufijos técnicos...")
            for kw in base_keywords:
                for ext in ("documentation", "github", "tutorial", "source code", "examples"):
                    expanded_kw = f"{kw} {ext}"
                    if expanded_kw not in keywords_list:
                        keywords_list.append(expanded_kw)
            print(f"[🧠 WSOS] Términos expandidos automáticamente: {len(keywords_list)} keywords en total.")

        print(
            f"[*] Iniciando búsqueda ANIDADA (paralela) [Región: {region}] "
            f"(Modo WSOS: {'ACTIVADO' if wsos_mode else 'DESACTIVADO'} | "
            f"Búsqueda Sucia: {'ACTIVADA' if dirty_mode else 'DESACTIVADA'})"
        )
        max_res = 15 if dirty_mode else (10 if wsos_mode else 5)
        workers = min(MAX_SEARCH_WORKERS, max(1, len(keywords_list)))
        print(f"[⚡] Búsqueda anidada: {len(keywords_list)} términos con {workers} workers concurrentes...")

        search_rate_limiter = AdaptiveRateLimiter(1.00, 8.00)

        def _search_one(kw: str) -> list:
            if stop_event and stop_event.is_set():
                return []
            engine = buscadores.MultiSearchEngine(
                region=region, safesearch=self.search_engine.safesearch,
                rate_limiter=search_rate_limiter, stop_event=stop_event,
            )
            urls = engine.fetch_urls(kw, max_results=max_res)
            print(f"  [✔] Término completado: '{kw}' → {len(urls)} enlaces")
            return urls

        found = run_parallel(
            keywords_list, _search_one, max_workers=workers, stop_event=stop_event,
            progress=progress_callback, label="Búsqueda", on_error=lambda kw, exc: [],
        )
        all_found_urls = [url for urls in found if urls for url in urls]
        stage_timings["search_seconds"] = round(time.monotonic() - stage_started, 3)
        stage_started = time.monotonic()

        # Normalización + deduplicación temprana: evita trabajo de red redundante.
        print(f"[⚙] Perfil: {profile} | Objetivo: {objective} | Calidad mínima: {profile_cfg['quality_min']}")
        if dirty_mode:
            source_urls = [u for u in all_found_urls if self.url_filter.is_fetchable(u, allow_pdf=allow_pdf)]
        else:
            source_urls = self.url_filter.clean_and_validate(all_found_urls, allow_pdf=allow_pdf)
        clean_urls, seen = [], set()
        for u in source_urls:
            nu = normalize_url(u)
            if nu and nu.startswith(("http://", "https://")) and nu not in seen:
                seen.add(nu)
                clean_urls.append(nu)
        print(f"[⚡] URLs únicas tras normalización: {len(clean_urls)}")
        stage_timings["filter_dedup_seconds"] = round(time.monotonic() - stage_started, 3)
        stage_started = time.monotonic()

        # En Búsqueda webs, las URLs no generan un archivo de salida: la fuente
        # persistente es exclusivamente config/webs.json y la categoría seleccionada.
        # La carpeta de salida se reserva para datasets generados por WSOS/Sucia o
        # para la extracción explícita de una categoría. No se llama a output_path()
        # en la búsqueda estándar porque esa función crea físicamente el directorio.
        if wsos_mode or dirty_mode:
            out_path = output_path(self.output_dir, output_filename)
            if out_path.suffix.lower() != ".txt":
                out_path = out_path.with_name(out_path.name + ".txt")
        else:
            out_path = Path(output_filename or "enlaces_encontrados.txt").name
            out_path = Path(out_path)

        # Solo los modos que generan dataset conservan además el archivo de URLs.
        # En Búsqueda webs estándar el destino es exclusivamente config/webs.json.
        if wsos_mode or dirty_mode:
            try:
                out_path.write_text("".join(f"{url}\n" for url in clean_urls), encoding="utf-8")
                print(f"[+] Resultados auxiliares del dataset guardados en '{out_path}' ({len(clean_urls)} enlaces).")
            except OSError as e:
                print(f"[!] Error al guardar el archivo auxiliar de URLs: {e}")

        # Guardar en la categoría elegida (sin duplicar por mayúsculas ni por barra final)
        added_count = 0
        if save_category and clean_urls:
            added_count = self.store.add_urls(save_category, clean_urls)
            key = self.store.resolve_key(save_category) or save_category.strip().lower()
            if dirty_mode:
                print(f"[+] [BÚSQUEDA SUCIA] ¡Volcado masivo completado! {added_count} URLs nuevas añadidas a la categoría '{key}' ({len(clean_urls)} totales procesadas).")
            else:
                print(f"[+] Se han guardado {added_count} URLs nuevas en la categoría '{key}' del JSON.")

        stage_timings["output_prepare_seconds"] = round(time.monotonic() - stage_started, 3)

        # Dataset (descarga paralela de páginas)
        total_chars_dataset = 0
        if (wsos_mode or dirty_mode) and clean_urls and not (stop_event and stop_event.is_set()):
            stage_started = time.monotonic()
            mode_label = "WSOS" if wsos_mode else "BÚSQUEDA SUCIA"
            scrape_workers = min(profile_cfg["workers"], HARD_WORKER_CAP, len(clean_urls))
            print(f"[🚀 {mode_label}] Pipeline de Dataset en paralelo ({scrape_workers} workers)...")
            processor = WebProcessor(
                stop_event=stop_event, rate_limiter=DomainRateLimiter(profile_cfg["rate_limit"]),
                retries=profile_cfg["retries"], max_chars=profile_cfg["max_chars"],
            )
            # La identidad de la ejecución se crea antes de escribir: cada dataset
            # queda aislado y una ejecución posterior nunca pisa otra.
            metadata = build_metadata(
                author=author, project=project, organization=organization, description=description,
                language=language, objective=objective, profile=profile, keywords=raw_keywords,
                mode=mode_label, license_name=license_name,
            )
            run_dir = self.output_dir / "runs" / metadata["run_id"]
            run_dir.mkdir(parents=True, exist_ok=True)
            dataset_path = run_dir / f"dataset_{'wsos' if wsos_mode else 'dirty'}_{out_path.stem}.txt"

            results = run_parallel(
                clean_urls,
                lambda url: processor.scrape_url_details(url, stop_event=stop_event, allow_pdf=allow_pdf),
                max_workers=scrape_workers, stop_event=stop_event, progress=progress_callback,
                label="Dataset",
                on_error=lambda url, exc: {"url": url, "content": "", "quality": 0, "sha256": "", "reason": "error"},
            )
            not_processed = sum(1 for r in results if r is None)
            accepted, rejections, rejected = select_documents(results, profile_cfg)
            for url, key, quality in rejected:
                if key != "interrumpido":
                    print(f"  [✘ {mode_label} Descartado] {REASON_LABELS[key].capitalize()} ({quality}/100): {url}")

            documents = []
            tmp_dataset = dataset_path.with_suffix(dataset_path.suffix + ".tmp")
            try:
                with open(tmp_dataset, "w", encoding="utf-8") as ds_file:
                    ds_file.write(
                        f"=== DATASET AUTOMÁTICO {mode_label} - KEYWORDS: {raw_keywords} ===\n"
                        f"=== PERFIL: {profile} | OBJETIVO: {objective} | RUN: {metadata['run_id']} ===\n\n"
                    )
                    for item in accepted:
                        content, quality, digest = item["content"], item["quality"], item["sha256"]
                        ds_file.write(f"\n\n--- FUENTE VALIDADA: {item['url']} | QUALITY: {quality}/100 | SHA256: {digest} ---\n\n{content}")
                        total_chars_dataset += len(content)
                        documents.append({
                            "url": item["url"], "title": item.get("title", ""), "quality": quality,
                            "sha256": digest, "chars": len(content), "truncated": item.get("truncated", False),
                        })
                    ds_file.flush()
                    os.fsync(ds_file.fileno())
                os.replace(tmp_dataset, dataset_path)
            except BaseException:
                try:
                    tmp_dataset.unlink(missing_ok=True)
                except OSError:
                    pass
                raise

            interrupted = bool(stop_event and stop_event.is_set())
            duplicates = rejections.get("duplicado", 0)
            rejected_total = sum(rejections.values()) - duplicates
            elapsed = max(0.001, time.monotonic() - run_started)
            total_bytes = sum(int((r or {}).get("bytes", 0) or 0) for r in results)
            avg_quality = round(sum(d["quality"] for d in documents) / max(1, len(documents)), 1)
            stats = {
                "status": "interrupted" if interrupted else "completed",
                "urls_found": len(all_found_urls), "urls_unique": len(clean_urls),
                "documents_accepted": len(accepted), "documents_rejected": rejected_total,
                "duplicates": duplicates, "rejections": dict(rejections), "not_processed": not_processed,
                "characters": total_chars_dataset,
                "quality_min": profile_cfg["quality_min"], "average_quality": avg_quality,
                "download_bytes": total_bytes, "elapsed_seconds": round(elapsed, 2),
                "urls_per_second": round(len(clean_urls) / elapsed, 2),
                "pdf_enabled": bool(allow_pdf),
            }
            # La telemetría se añade antes de publicar el manifiesto; solo se escribe
            # una vez y sigue usando publicación atómica.
            print(f"[🆔] Dataset ID: {metadata['dataset_id']} | Run ID: {metadata['run_id']}")
            print(f"[📊] Dataset: {len(accepted)} válidos | {duplicates} duplicados | {rejected_total} descartados | {total_chars_dataset} caracteres")
            if rejections:
                print("[📊] Motivos de descarte: " + ", ".join(f"{n} {REASON_LABELS[k]}" for k, n in rejections.items()))
            print("\n╔══════════════════════════════════════╗")
            print("║          WSOS ENGINE REPORT          ║")
            print("╠══════════════════════════════════════╣")
            print(f"║ URLs encontradas : {len(all_found_urls):>16} ║")
            print(f"║ URLs únicas      : {len(clean_urls):>16} ║")
            print(f"║ Docs aceptados   : {len(accepted):>16} ║")
            print(f"║ Duplicados       : {duplicates:>16} ║")
            print(f"║ Calidad media    : {avg_quality:>15}/100 ║")
            print(f"║ Velocidad        : {stats['urls_per_second']:>12} URL/s ║")
            print(f"║ Tiempo           : {stats['elapsed_seconds']:>13} s ║")
            print("╚══════════════════════════════════════╝")
            stage_timings["dataset_seconds"] = round(time.monotonic() - stage_started, 3)
            stage_timings["total_seconds"] = round(time.monotonic() - run_started, 3)
            stats["timings"] = dict(stage_timings)
            stats["parallelism"] = {
                "search_workers": workers,
                "download_workers": scrape_workers,
            }
            manifest_path = write_manifest(str(dataset_path), metadata, stats, documents)
            print(f"[+] Manifiesto WSOS generado: {manifest_path}")
            if stats_callback:
                stats_callback(metadata, stats)
            state = "interrumpido, parcial" if interrupted else "generado con éxito"
            print(f"[+] ¡Dataset {mode_label} {state} en '{dataset_path}'! ({total_chars_dataset} caracteres).")

        print("\n" + "=" * 50)
        print("📊 RESUMEN FINAL DE LA BÚSQUEDA:")
        print(f"   • Total de webs/enlaces añadidos: {added_count if save_category else len(clean_urls)}")
        print(f"   • Caracteres totales añadidos al dataset: {total_chars_dataset}")
        print("=" * 50 + "\n")

    # ------------------------------------------------------------------ categoría
    def run_category_gui(self, selected_category, stop_event=None, progress_callback=None,
                         profile="Equilibrado", allow_pdf=False):
        """Extrae el contenido de una categoría aplicando el perfil elegido."""
        categories = self.load_config()
        key = self.store.resolve_key(selected_category, categories) or selected_category
        urls_to_sample = categories.get(key, [])

        print(f"[*] Iniciando categoría '{key.upper()}' ({len(urls_to_sample)} URLs)...")
        start_time = time.time()
        try:
            categorias.run_category_scraping(
                key, urls_to_sample, stop_event, progress_callback,
                profile=profile, output_dir=self.output_dir, allow_pdf=allow_pdf,
            )
            print(f"[+] Categoría '{key.upper()}' finalizada en {time.time() - start_time:.2f} segundos.")
        except Exception as e:  # noqa: BLE001
            print(f"[!] Error en categoría '{key.upper()}' tras {time.time() - start_time:.2f} segundos: {e}")
