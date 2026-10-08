import unittest

from app import actualizador as act


class ActualizadorTests(unittest.TestCase):
    def test_requirement_names(self):
        self.assertEqual(act.nombre_paquete("beautifulsoup4>=4.12"), "beautifulsoup4")
        self.assertEqual(act.nombre_paquete("Flet[all]==0.28; python_version>'3.9'"), "flet")

    def test_beautifulsoup_is_detected_via_its_import_name(self):
        # Regresión 1.12: __import__("beautifulsoup4") fallaba siempre y reinstalaba en cada ejecución
        self.assertEqual(act.IMPORT_NAMES["beautifulsoup4"], "bs4")
        self.assertTrue(act.esta_instalado("beautifulsoup4"))
        self.assertFalse(act.esta_instalado("paquete_que_no_existe_xyz"))

    def test_requirements_file_lists_every_dependency(self):
        names = {act.nombre_paquete(s) for s in act.leer_requisitos()}
        self.assertEqual(names, set(act.DEFAULT_REQUIREMENTS))


if __name__ == "__main__":
    unittest.main()
