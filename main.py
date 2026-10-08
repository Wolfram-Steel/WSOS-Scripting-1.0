# main.py
import flet as ft

from core.version import APP_TITLE
from app.ui import ScraperUI


def main(page: ft.Page):
    page.title = APP_TITLE
    page.theme_mode = ft.ThemeMode.DARK

    # Instanciamos la interfaz gráfica principal
    ScraperUI(page)


if __name__ == "__main__":
    # ft.run() es la API de las versiones actuales de Flet
    ft.run(main)
