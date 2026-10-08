import threading
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
from core.categorias import run_category_scraping


class CategoryPdfTests(unittest.TestCase):
    def test_category_passes_allow_pdf(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            calls = []
            def fake(self, url, stop_event=None, allow_pdf=False):
                calls.append(allow_pdf)
                return {"url": url, "content": "A" * 500, "quality": 90, "sha256": url, "reason": "ok"}
            with patch("core.categorias.WebProcessor.scrape_url_details", fake):
                run_category_scraping("CPU", ["https://example.test/doc.pdf"], threading.Event(), None, output_dir=Path(tmp.name), allow_pdf=True)
            self.assertEqual(calls, [True])
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
