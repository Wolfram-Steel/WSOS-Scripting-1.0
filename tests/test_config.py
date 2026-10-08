import json
import tempfile
import unittest
from pathlib import Path

from core.config import ConfigStore, load_settings, output_path, save_settings, slugify


class ConfigStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.path = self.dir / "webs.json"
        self.store = ConfigStore(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_category_lookup_ignores_case_and_keeps_original_key(self):
        self.path.write_text(json.dumps({"CPU": []}), encoding="utf-8")
        self.assertEqual(self.store.resolve_key("cpu"), "CPU")
        self.assertEqual(self.store.add_urls("cpu", ["https://a.com/x"]), 1)
        self.assertEqual(list(self.store.load()), ["CPU"])  # sin crear una clave "cpu" aparte
        self.assertFalse(self.store.create_category("Cpu"))

    def test_add_urls_dedupes_on_normalized_urls(self):
        self.store.create_category("tema")
        self.assertEqual(self.store.add_urls("tema", ["https://a.com/x", "https://a.com/x/", "https://a.com/x?utm_source=z"]), 1)
        self.assertEqual(self.store.add_urls("tema", ["https://A.com/x#frag"]), 0)

    def test_slug_collisions_are_rejected(self):
        self.assertTrue(self.store.create_category("C++"))
        self.assertFalse(self.store.create_category("C"))

    def test_corrupt_json_is_quarantined_not_fatal(self):
        self.path.write_text("{esto no es json", encoding="utf-8")
        self.assertEqual(self.store.load(), {})
        self.assertTrue(list(self.dir.glob("webs.json.corrupt-*")))

    def test_save_is_atomic_and_leaves_no_temp_files(self):
        self.store.create_category("a")
        self.store.add_urls("a", ["https://a.com"])
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {"a": ["https://a.com"]})
        self.assertEqual([p.name for p in self.dir.iterdir()], ["webs.json"])

    def test_delete_category_case_insensitive(self):
        self.path.write_text(json.dumps({"CPU": ["https://a.com"]}), encoding="utf-8")
        self.assertTrue(self.store.delete_category("cpu"))
        self.assertEqual(self.store.load(), {})


class HelpersTests(unittest.TestCase):
    def test_slugify_is_filename_safe(self):
        self.assertEqual(slugify("Programación/IA: v2"), "programacion_ia_v2")
        self.assertEqual(slugify("../../etc"), "etc")
        self.assertEqual(slugify("???"), "categoria")

    def test_output_path_drops_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(output_path(tmp, "../../evil/out.txt"), Path(tmp) / "out.txt")
            self.assertEqual(output_path(tmp, "").name, "enlaces_encontrados.txt")

    def test_settings_roundtrip_ignores_unknown_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            settings = load_settings(path)
            settings["author"] = "Ana"
            settings["desconocido"] = 1
            save_settings(settings, path)
            loaded = load_settings(path)
            self.assertEqual(loaded["author"], "Ana")
            self.assertNotIn("desconocido", loaded)


if __name__ == "__main__":
    unittest.main()
