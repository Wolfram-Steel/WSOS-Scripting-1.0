import unittest
from pathlib import Path
from bs4 import BeautifulSoup
from core.procesador import WebProcessor


class HtmlCorpusRegressionTests(unittest.TestCase):
    def test_all_corpus_pages_produce_nonempty_output(self):
        root = Path(__file__).parent / "fixtures" / "html_corpus"
        processor = WebProcessor()
        for path in sorted(root.glob("*.html")):
            soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
            title, raw = processor.html_to_text(soup)
            out = processor.clean_text_preserving_code(raw)
            self.assertTrue(out, path.name)
            self.assertIn("CPU", out, path.name)

    def test_short_technical_lines_are_preserved(self):
        p = WebProcessor()
        out = p.clean_text_preserving_code("CPU\nHTTP 200\nE = mc²\nPárrafo técnico válido")
        self.assertIn("CPU", out)
        self.assertIn("HTTP 200", out)
        self.assertIn("E = mc²", out)

    def test_webforms_form_and_useful_aside_survive(self):
        p = WebProcessor()
        soup = BeautifulSoup("<html><body><form><p>Contenido útil del formulario WebForms</p></form><aside><p>Alerta importante para el lector</p></aside></body></html>", "html.parser")
        _, raw = p.html_to_text(soup)
        out = p.clean_text_preserving_code(raw)
        self.assertIn("Contenido útil", out)
        self.assertIn("Alerta importante", out)

    def test_navigation_aside_is_removed_by_dom_link_density(self):
        p = WebProcessor()
        soup = BeautifulSoup("<html><body><aside><a>A</a><a>B</a><a>C</a><a>D</a></aside><main><p>Contenido principal suficiente.</p></main></body></html>", "html.parser")
        _, raw = p.html_to_text(soup)
        out = p.clean_text_preserving_code(raw)
        self.assertNotIn("A B C D", out)
        self.assertIn("Contenido principal", out)

    def test_reference_heading_is_not_enough_to_truncate_plain_text(self):
        p = WebProcessor()
        text = "Contenido principal largo y válido.\n# Referencias\nNota breve que sigue siendo contenido real."
        out = p.clean_text_preserving_code(text)
        self.assertIn("Nota breve", out)


if __name__ == "__main__":
    unittest.main()
