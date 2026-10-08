import unittest

from core.bloqueos import URLFilter, strip_tracking_params


class UrlFilterTests(unittest.TestCase):
    def setUp(self):
        self.f = URLFilter()

    def test_sanitize_keeps_balanced_parentheses(self):
        url = "https://es.wikipedia.org/wiki/Python_(lenguaje_de_programación)"
        self.assertEqual(self.f.sanitize_url(url), url)

    def test_sanitize_strips_unbalanced_trailing_punctuation(self):
        self.assertEqual(self.f.sanitize_url("https://a.com/x)."), "https://a.com/x")
        self.assertEqual(self.f.sanitize_url("https://a.com/x),"), "https://a.com/x")

    def test_tracking_params_are_stripped_not_dropped(self):
        cleaned = self.f.clean_and_validate(["https://example.com/page?id=5&utm_source=x&msclkid=abc"])
        self.assertEqual(cleaned, ["https://example.com/page?id=5"])
        self.assertEqual(strip_tracking_params("https://a.com/?gclid=1"), "https://a.com/")

    def test_ad_redirectors_blocked(self):
        for url in ("https://www.bing.com/aclick?ld=1", "https://ad.doubleclick.net/x",
                    "https://site.com/aclick/abc"):
            self.assertTrue(self.f.is_ad_url(url), url)
            self.assertFalse(self.f.is_fetchable(url), url)

    def test_slug_containing_aclick_is_not_blocked(self):
        self.assertFalse(self.f.is_ad_url("https://site.com/blog/aclick-tips"))

    def test_domain_matching_is_by_host(self):
        self.assertTrue(self.f.is_blocked_domain("https://store.steampowered.com/app/1"))
        self.assertFalse(self.f.is_blocked_domain("https://mi-steampowered.com.evil/x"))  # host distinto
        self.assertFalse(self.f.is_blocked_domain("https://example.com/steampowered.com"))

    def test_wikipedia_js_articles_are_not_binary_assets(self):
        self.assertTrue(self.f.is_supported_resource("https://es.wikipedia.org/wiki/Node.js"))
        self.assertFalse(self.f.is_supported_resource("https://cdn.site.com/app.js"))
        self.assertFalse(self.f.is_supported_resource("https://site.com/doc.pdf"))
        self.assertTrue(self.f.is_supported_resource("https://site.com/doc.pdf", allow_pdf=True))

    def test_dirty_mode_still_blocks_ads_but_not_extra_domains(self):
        self.assertTrue(self.f.is_fetchable("https://store.steampowered.com/app/1"))
        self.assertFalse(self.f.is_clean_url("https://store.steampowered.com/app/1"))


if __name__ == "__main__":
    unittest.main()
