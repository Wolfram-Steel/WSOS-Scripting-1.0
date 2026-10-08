"""Pruebas de extremo a extremo con servidor local y motor de búsqueda simulado."""
import json
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path

sys.modules.setdefault("ddgs", types.SimpleNamespace(DDGS=object))  # ddgs no hace falta en tests

from core import buscadores  # noqa: E402
from core.categorias import run_category_scraping  # noqa: E402
from app.scraping import IntegratedCodeScraper  # noqa: E402
from tests.helpers import LocalServer  # noqa: E402


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LocalServer().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.server.__exit__()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "webs.json").write_text(json.dumps({"CPU": []}), encoding="utf-8")
        self.scraper = IntegratedCodeScraper(self.dir / "webs.json", output_dir=self.dir / "salida")
        base = self.server.base
        self.urls = [f"{base}/a", f"{base}/b", f"{base}/dup", f"{base}/junk", f"{base}/404",
                     f"{base}/a?utm_source=x", f"{base}/c.css"]
        self._orig = buscadores.MultiSearchEngine.fetch_urls
        buscadores.MultiSearchEngine.fetch_urls = lambda s, kw, max_results=5: list(self.urls)

    def tearDown(self):
        buscadores.MultiSearchEngine.fetch_urls = self._orig
        self.tmp.cleanup()

    def test_wsos_search_builds_dataset_manifest_and_saves_to_existing_category(self):
        self.scraper.search_custom_gui(
            "../fuera/enlaces.txt", "cpu", wsos_mode=True, save_category="cpu",
            profile="Equilibrado", author="Ana", project="Demo 1", stop_event=threading.Event(),
        )
        out = self.dir / "salida"
        self.assertTrue((out / "enlaces.txt").exists())          # el nombre no escapa de la carpeta
        runs = sorted((out / "runs").iterdir())
        self.assertEqual(len(runs), 1)
        dataset = next(runs[0].glob("dataset_wsos_*.txt"))
        manifest = json.loads(next(runs[0].glob("*.wsos.json")).read_text(encoding="utf-8"))
        text = dataset.read_text(encoding="utf-8")
        self.assertIn("/a ", text)
        self.assertIn("/b ", text)
        self.assertEqual(text.count("FUENTE VALIDADA"), 2)        # /a y /b; /dup duplicado; /junk, /404 descartados
        stats = manifest["stats"]
        self.assertEqual(stats["status"], "completed")
        self.assertEqual(stats["documents_accepted"], 2)
        self.assertEqual(stats["duplicates"], 1)
        self.assertEqual(stats["rejections"].get("error_descarga"), 1)
        self.assertGreaterEqual(stats["rejections"].get("baja_calidad", 0) + stats["rejections"].get("vacio", 0), 1)
        self.assertIn("timings", stats)
        self.assertIn("search_seconds", stats["timings"])
        self.assertIn("filter_dedup_seconds", stats["timings"])
        self.assertIn("output_prepare_seconds", stats["timings"])
        self.assertIn("dataset_seconds", stats["timings"])
        self.assertIn("total_seconds", stats["timings"])
        self.assertEqual(stats["parallelism"]["search_workers"], 3)
        self.assertEqual(stats["parallelism"]["download_workers"], 5)
        self.assertEqual(manifest["engine_version"], "1.12c")
        self.assertEqual(manifest["project_id"], "Demo-1")
        self.assertEqual(manifest["documents"][0]["title"], "Página a")
        # la categoría "CPU" recibió las URLs; no se creó una "cpu" duplicada y .css se filtró
        cfg = json.loads((self.dir / "webs.json").read_text(encoding="utf-8"))
        self.assertEqual(list(cfg), ["CPU"])
        self.assertFalse(any(u.endswith(".css") for u in cfg["CPU"]))
        self.assertEqual(len([u for u in cfg["CPU"] if u.endswith("/a")]), 1)  # utm normalizado

    def test_profile_controls_quality_threshold(self):
        # Con "Rápido" (min 50) el documento basura sigue descartado; con Dataset IA (1000 chars) también pasan los buenos
        self.scraper.search_custom_gui("o.txt", "cpu", wsos_mode=True, save_category="cpu",
                                       profile="Dataset IA", stop_event=threading.Event())
        run = sorted((self.dir / "salida" / "runs").iterdir())[-1]
        manifest = json.loads(next(run.glob("*.wsos.json")).read_text(encoding="utf-8"))
        self.assertEqual(manifest["profile"], "Dataset IA")
        self.assertEqual(manifest["stats"]["documents_accepted"], 2)

    def test_category_run_uses_profile_dedup_and_writes_clean_parts(self):
        base = self.server.base
        out = self.dir / "salida"
        out.mkdir()
        (out / "cpu_part_9.txt").write_text("antiguo", encoding="utf-8")  # parte vieja de otra ejecución
        stats = run_category_scraping("CPU", [f"{base}/a", f"{base}/a/", f"{base}/b", f"{base}/dup", f"{base}/junk"],
                                      threading.Event(), None, profile="Equilibrado", output_dir=out)
        self.assertEqual(stats["documents_accepted"], 2)
        files = sorted(p.name for p in out.glob("cpu_part_*.txt"))
        self.assertEqual(files, ["cpu_part_1.txt"])               # sin partes obsoletas ni vacías
        content = (out / "cpu_part_1.txt").read_text(encoding="utf-8")
        self.assertIn("=== DATASET: CPU (Parte 1) ===", content)
        self.assertEqual(content.count("--- FUENTE:"), 2)

    def test_category_without_valid_docs_creates_no_files_and_keeps_old_ones(self):
        out = self.dir / "salida"
        out.mkdir()
        (out / "cpu_part_1.txt").write_text("previo", encoding="utf-8")
        run_category_scraping("cpu", [f"{self.server.base}/404"], threading.Event(), None, output_dir=out)
        self.assertEqual((out / "cpu_part_1.txt").read_text(encoding="utf-8"), "previo")

    def test_stop_marks_manifest_interrupted_or_skips_dataset(self):
        stop = threading.Event()
        stop.set()
        self.scraper.search_custom_gui("s.txt", "cpu", wsos_mode=True, save_category="cpu", stop_event=stop)
        self.assertFalse((self.dir / "salida" / "runs").exists())

    def test_dirty_mode_does_not_add_pdf_search_suffix_when_pdf_disabled(self):
        captured = []
        original = buscadores.MultiSearchEngine.fetch_urls
        buscadores.MultiSearchEngine.fetch_urls = lambda s, kw, max_results=5: captured.append(kw) or []
        try:
            self.scraper.search_custom_gui("dirty.txt", "cpu", dirty_mode=True, allow_pdf=False, stop_event=threading.Event())
        finally:
            buscadores.MultiSearchEngine.fetch_urls = original
        self.assertTrue(captured)
        self.assertFalse(any(kw.endswith(" pdf") for kw in captured))

    def test_run_ids_prevent_dataset_overwrite(self):
        for name in ("uno.txt", "dos.txt"):
            self.scraper.search_custom_gui(name, "cpu", wsos_mode=True, stop_event=threading.Event())
        runs = list((self.dir / "salida" / "runs").iterdir())
        self.assertEqual(len(runs), 2)
        self.assertEqual(len(list((self.dir / "salida").glob("dataset_wsos_*.txt"))), 0)


if __name__ == "__main__":
    unittest.main()
