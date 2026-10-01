# main.py
import flet as ft
from ui import ScraperUI


def main(page: ft.Page):
  # Configuraciones globales opcionales
  page.title = "WSOS SCRIPTING 1.0"
  page.theme_mode = ft.ThemeMode.DARK

  # Instanciamos la interfaz gráfica principal
  ScraperUI(page)


if __name__ == "__main__":
  # Usamos ft.run() tal como pide tu versión actual de Flet
  ft.run(main)