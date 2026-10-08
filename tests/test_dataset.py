import re
import unittest

from core.dataset import PROFILES, normalize_url, quality_score, select_documents, get_profile


def article(n=30):
    return "\n".join(
        f"Sección {i}: el procesador {i * 7} ejecuta instrucciones distintas y coordina {i + 3} unidades "
        f"internas mientras la caché guarda datos recientes para acelerar el trabajo." for i in range(n)
    )


class QualityScoreTests(unittest.TestCase):
    def test_varied_prose_passes_every_profile_threshold_range(self):
        self.assertGreaterEqual(quality_score(article()), 70)

    def test_junk_scores_below_balanced_profile(self):
        self.assertLess(quality_score("palabra. " * 400), PROFILES["Equilibrado"]["quality_min"])
        self.assertLess(quality_score("\n".join(["Inicio Blog Tienda Contacto"] * 50)), 50)
        self.assertLess(quality_score("a\n" * 5000), 50)
        self.assertEqual(quality_score(""), 0)

    def test_score_is_bounded(self):
        self.assertTrue(0 <= quality_score(article(500)) <= 100)


class NormalizeTests(unittest.TestCase):
    def test_trackers_fragment_and_trailing_slash(self):
        self.assertEqual(normalize_url("HTTPS://A.com/x/?utm_source=1&b=2#frag"), "https://a.com/x?b=2")
        self.assertEqual(normalize_url("https://a.com/?msclkid=1"), "https://a.com/")


class SelectDocumentsTests(unittest.TestCase):
    def doc(self, url, content, quality=90, digest=None, reason="ok"):
        return {"url": url, "content": content, "quality": quality, "sha256": digest or url, "reason": reason}

    def test_reasons_and_dedup(self):
        cfg = get_profile("Equilibrado")
        text = "x" * 400
        results = [
            self.doc("a", text), self.doc("b", text, digest="a"),      # duplicado
            self.doc("c", "corto"), self.doc("d", text, quality=10),
            self.doc("e", "", reason="http_404"), self.doc("f", "", reason="pdf_skipped"),
            self.doc("g", ""), None,
        ]
        accepted, rejections, _ = select_documents(results, cfg)
        self.assertEqual([d["url"] for d in accepted], ["a"])
        self.assertEqual(dict(rejections), {
            "duplicado": 1, "corto": 1, "baja_calidad": 1,
            "error_descarga": 1, "pdf_omitido": 1, "vacio": 1,
        })

    def test_unknown_profile_falls_back(self):
        self.assertEqual(get_profile("no existe"), PROFILES["Equilibrado"])


if __name__ == "__main__":
    unittest.main()
