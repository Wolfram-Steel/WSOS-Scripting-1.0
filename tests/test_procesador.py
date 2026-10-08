import unittest

from bs4 import BeautifulSoup

from core.procesador import WebProcessor


class NoiseFilterTests(unittest.TestCase):
    def setUp(self):
        self.p = WebProcessor()

    def test_normal_prose_is_kept(self):
        # Regresión 1.12: el patrón [a-z][A-Z] con re.I descartaba TODAS las líneas
        text = "Python es un lenguaje de programación interpretado muy popular"
        self.assertEqual(self.p.clean_text_preserving_code(text), text)

    def test_generic_words_inside_sentences_are_kept(self):
        for text in (
            "The index of the array starts at zero in most languages",
            "Los modules de Python se importan con la palabra clave import",
            "Este tema trata sobre la arquitectura de los procesadores modernos",
        ):
            self.assertFalse(self.p.is_noise_line(text), text)

    def test_boilerplate_lines_are_removed(self):
        for text in ("Ir al contenido", "Copyright 2024 Acme Inc.", "Index", "Menú",
                     "12 Smith, J. (2010). Un libro", "2020 2021 2022"):
            self.assertTrue(self.p.is_noise_line(text), text)

    def test_short_headings_are_kept(self):
        self.assertFalse(self.p.is_noise_line("# Introducción"))
        self.assertFalse(self.p.is_noise_line("- Instalar Python ahora"))

    def test_code_blocks_are_preserved_verbatim(self):
        text = "Intro con suficientes palabras para pasar el filtro\n```\nx = 1\n\ny = 2\n```"
        out = self.p.clean_text_preserving_code(text)
        self.assertIn("```\nx = 1\n\ny = 2\n```", out)

    def test_text_only_reference_heading_is_preserved_without_dom_evidence(self):
        body = "\n".join(f"Párrafo {i} con bastante texto para ser contenido real." for i in range(10))
        text = body + "\n## Referencias [editar]\nSmith, J. Un libro cualquiera sobre el tema\nOtro libro de consulta general"
        out = self.p.clean_text_preserving_code(text)
        self.assertIn("Párrafo 9", out)
        self.assertIn("Un libro cualquiera", out)


class HtmlToTextTests(unittest.TestCase):
    HTML = """<html><head><title>Demo</title></head><body>
    <nav>Inicio Blog Contacto</nav>
    <header><h1>Guía de Python</h1></header>
    <div class="threads-list"><p>Python es un <a href="x">lenguaje</a> de <em>programación</em>
    muy usado, y se usa <code>print</code> para mostrar texto en pantalla.</p></div>
    <h2>Instalación</h2>
    <ul><li>Descargar el instalador oficial</li><li>Ejecutar el instalador</li></ul>
    <pre><code>def hola():
    print("hola")
</code></pre>
    <div class="cookie-banner">Aceptar cookies</div>
    </body></html>"""

    def setUp(self):
        p = WebProcessor()
        title, raw = p.html_to_text(BeautifulSoup(self.HTML, "html.parser"))
        self.title = title
        self.out = p.clean_text_preserving_code(raw)

    def test_title_and_structure(self):
        self.assertEqual(self.title, "Demo")
        self.assertIn("# Guía de Python", self.out)
        self.assertIn("## Instalación", self.out)
        self.assertIn("- Descargar el instalador oficial", self.out)

    def test_inline_tags_do_not_split_paragraphs(self):
        self.assertIn(
            "Python es un lenguaje de programación muy usado, y se usa `print` para mostrar texto en pantalla.",
            self.out,
        )

    def test_code_block_keeps_indentation(self):
        self.assertIn('```\ndef hola():\n    print("hola")\n```', self.out)

    def test_boilerplate_removed_but_similar_class_kept(self):
        self.assertNotIn("Inicio Blog", self.out)
        self.assertNotIn("Aceptar cookies", self.out)
        self.assertIn("Python es un", self.out)  # class="threads-list" NO es publicidad


if __name__ == "__main__":
    unittest.main()
