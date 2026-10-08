"""Extracción de contenido de una categoría de webs.json a archivos *_part_N.txt."""
import re
import time
from pathlib import Path

from .config import slugify
from .dataset import REASON_LABELS, get_profile, normalize_url, select_documents
from .paralelo import run_parallel
from .procesador import WebProcessor
from .red import DomainRateLimiter

MAX_LINES_PER_FILE = 500
MAX_CATEGORY_WORKERS = 16  # tope de seguridad; el número real lo marca el perfil


class PartWriter:
    """Escribe bloques en archivos *_part_N.txt de hasta `max_lines` líneas.

    Los archivos se crean al escribir el primer bloque (sin partes vacías) y, en ese
    momento, se eliminan las partes de ejecuciones anteriores de la MISMA categoría
    para no mezclar datos antiguos con los nuevos.
    """

    def __init__(self, directory, base: str, title: str, max_lines: int = MAX_LINES_PER_FILE):
        self.directory = Path(directory)
        self.base = base
        self.title = title
        self.max_lines = max_lines
        self.part = 0
        self.lines = 0
        self.files = []
        self._handle = None
        self._purged = False

    def _purge_stale_parts(self):
        pattern = re.compile(rf"{re.escape(self.base)}_part_\d+\.txt")
        for path in self.directory.glob(f"{self.base}_part_*.txt"):
            if pattern.fullmatch(path.name):
                path.unlink(missing_ok=True)

    def _open_next(self):
        if self._handle:
            self._handle.close()
        self.directory.mkdir(parents=True, exist_ok=True)
        if not self._purged:
            self._purge_stale_parts()
            self._purged = True
        self.part += 1
        path = self.directory / f"{self.base}_part_{self.part}.txt"
        self._handle = open(path, "w", encoding="utf-8")
        self._handle.write(f"=== DATASET: {self.title} (Parte {self.part}) ===\n\n")
        self.lines = 2
        self.files.append(path)

    def write_block(self, block: str):
        block_lines = len(block.splitlines())
        if self._handle is None or (self.lines + block_lines > self.max_lines and self.lines > 2):
            self._open_next()
        self._handle.write(block)
        self.lines += block_lines

    def close(self):
        if self._handle:
            self._handle.close()
            self._handle = None


def run_category_scraping(selected_category, urls_to_scrape, stop_event=None, progress_callback=None,
                          *, profile="Equilibrado", output_dir=".", allow_pdf=False):
    """Descarga las URLs de una categoría aplicando el perfil (workers, intentos, límites,
    calidad y deduplicación) y escribe los resultados en *_part_N.txt."""
    cfg = get_profile(profile)
    base = slugify(selected_category)

    unique_urls, seen = [], set()
    for url in urls_to_scrape:
        norm = normalize_url(url)
        if norm and norm not in seen:
            seen.add(norm)
            unique_urls.append(url)
    skipped = len(urls_to_scrape) - len(unique_urls)
    if skipped:
        print(f"[⚡] {skipped} URLs repetidas omitidas.")
    if not unique_urls:
        print("[!] La categoría no tiene URLs que procesar.")
        return {"documents_accepted": 0, "documents_rejected": 0, "files": []}

    workers = min(cfg["workers"], MAX_CATEGORY_WORKERS)
    print(f"[⚙] Perfil: {profile} | Calidad mínima: {cfg['quality_min']} | {min(workers, len(unique_urls))} workers")
    processor = WebProcessor(
        stop_event=stop_event, rate_limiter=DomainRateLimiter(cfg["rate_limit"]),
        retries=cfg["retries"], max_chars=cfg["max_chars"],
    )

    started = time.monotonic()
    results = run_parallel(
        unique_urls,
        lambda url: processor.scrape_url_details(url, stop_event=stop_event, allow_pdf=allow_pdf),
        max_workers=workers, stop_event=stop_event, progress=progress_callback, label="Categoría",
        on_error=lambda url, exc: {"url": url, "content": "", "quality": 0, "sha256": "", "reason": "error"},
    )

    accepted, rejections, rejected = select_documents(results, cfg)
    for url, key, quality in rejected:
        if key != "interrumpido":
            print(f"  [✘ Descartado] {REASON_LABELS[key].capitalize()} ({quality}/100): {url}")

    writer = PartWriter(output_dir, base, selected_category.upper())
    total_chars = 0
    try:
        for doc in accepted:
            writer.write_block(f"\n--- FUENTE: {doc['url']} ---\n\n{doc['content']}\n")
            total_chars += len(doc["content"])
    finally:
        writer.close()

    for path in writer.files:
        print(f"[+] Archivo generado: {path}")
    if not writer.files:
        print("[!] No hubo documentos válidos: no se ha generado ningún archivo.")
    summary = ", ".join(f"{n} {REASON_LABELS[k]}" for k, n in rejections.items()) or "ninguno"
    print(f"[📊] Categoría: {len(accepted)} válidos | descartados: {summary} | {total_chars} caracteres"
          f" | {time.monotonic() - started:.1f} s")
    return {
        "documents_accepted": len(accepted), "documents_rejected": sum(rejections.values()),
        "rejections": dict(rejections), "characters": total_chars,
        "files": [str(p) for p in writer.files],
    }
