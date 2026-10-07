# ui.py
import io
import os
import subprocess
import sys
import threading
import time
import flet as ft
from scraping import IntegratedCodeScraper


class ScraperUI:

  def __init__(self, page: ft.Page):
    self.page = page
    self.scraper = IntegratedCodeScraper()
    self.categories = self.scraper.load_config()

    self.stop_event = threading.Event()

    # Mapeo de regiones legibles a los códigos que acepta DuckDuckGo
    self.regions_map = {
        "España": "es-es",
        "Estados Unidos (USA)": "us-en",
        "Reino Unido (UK)": "uk-en",
        "Global / Todo el mundo": "wt-wt",
    }

    self.setup_page()
    self.build_layout()

  def setup_page(self):
    self.page.title = "WSOS"
    self.page.padding = 20
    self.page.spacing = 15
    self.page.theme_mode = ft.ThemeMode.DARK
    self.page.window_width = 900
    self.page.window_height = 860

  def build_layout(self):
    banner_text = ft.Text(
        "WSOS SCRIPTING 1.11",
        size=20,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.RED_700,
    )

    self.mode_dropdown = ft.Dropdown(
        label="Selecciona la Operación",
        hint_text="Elige búsqueda webs o una categoría...",
        value="0",
        options=[ft.dropdown.Option("0", "Búsqueda webs")]
        + [
            ft.dropdown.Option(cat, f"Categoría: {cat.upper()}")
            for cat in self.categories.keys()
        ],
        on_select=self.on_mode_change,
        border_color=ft.Colors.RED_400,
        expand=True,
    )

    self.btn_manage_categories = ft.ElevatedButton(
        content=ft.Text("Categorías", color=ft.Colors.WHITE),
        icon="create_new_folder",
        bgcolor=ft.Colors.PURPLE_700,
        on_click=self.open_category_dialog,
        tooltip="Gestionar (crear y borrar) categorías del archivo JSON",
    )

    top_row_operations = ft.Row(
        controls=[self.mode_dropdown, self.btn_manage_categories],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        spacing=10,
    )

    is_init_zero = True

    self.txt_keywords = ft.TextField(
        label="Palabras clave (separadas por comas)",
        hint_text="ej. python, flet, scraping",
        visible=is_init_zero,
    )
    self.txt_output_file = ft.TextField(
        label="Nombre del archivo .txt de salida",
        value="enlaces_encontrados.txt",
        visible=is_init_zero,
    )

    self.region_dropdown = ft.Dropdown(
        label="Región de búsqueda",
        value="España",
        options=[ft.dropdown.Option(name) for name in self.regions_map.keys()],
        visible=is_init_zero,
        border_color=ft.Colors.RED_400,
    )

    self.target_category_dropdown = ft.Dropdown(
        label="Categoría de destino (Obligatoria para guardar)",
        hint_text="Selecciona dónde guardar las webs encontradas...",
        options=[
            ft.dropdown.Option(cat, cat.upper())
            for cat in self.categories.keys()
        ],
        visible=is_init_zero,
        border_color=ft.Colors.PURPLE_400,
    )

    # Funciones de exclusión mutua para Modo WSOS y Búsqueda Sucia
    def on_wsos_changed(e):
      if self.wsos_mode_checkbox.value:
        self.dirty_mode_checkbox.value = False
        self.dirty_mode_checkbox.update()

    def on_dirty_changed(e):
      if self.dirty_mode_checkbox.value:
        self.wsos_mode_checkbox.value = False
        self.wsos_mode_checkbox.update()

    self.wsos_mode_checkbox = ft.Checkbox(
        label="Modo WSOS",
        value=False,
        visible=is_init_zero,
        on_change=on_wsos_changed,
        tooltip=(
            "Auto-Expansión de Palabras Clave por Algoritmo Semántico, "
            "Validación de Contenido Útil al Vuelo y Datasets estructurados."
        ),
    )

    self.dirty_mode_checkbox = ft.Checkbox(
        label="Búsqueda Sucia",
        value=False,
        visible=is_init_zero,
        on_change=on_dirty_changed,
        tooltip=(
            "Busca absolutamente sin filtros (ignora el filtrado de publicidad"
            " y rastreadores). Incompatible con Modo WSOS."
        ),
    )

    # Fila que agrupa los checkboxes avanzados
    self.advanced_modes_row = ft.Row(
        controls=[
            self.wsos_mode_checkbox,
            self.dirty_mode_checkbox,
        ],
        spacing=15,
        visible=is_init_zero,
    )

    self.progress_bar = ft.ProgressBar(
        value=0, color=ft.Colors.RED_500, bgcolor=ft.Colors.GREY_800, visible=False
    )

    self.btn_run = ft.ElevatedButton(
        content=ft.Text("Ejecutar Proceso", color=ft.Colors.WHITE),
        icon="play_arrow",
        bgcolor=ft.Colors.RED_700,
        on_click=self.run_process,
        scale=1.0,
        animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
    )

    self.btn_stop = ft.ElevatedButton(
        content=ft.Text("Detener Proceso", color=ft.Colors.WHITE),
        icon="stop",
        bgcolor=ft.Colors.GREY_800,
        on_click=self.stop_process,
        disabled=True,
    )

    self.btn_open_folder = ft.ElevatedButton(
        content=ft.Text("Abrir Carpeta", color=ft.Colors.WHITE),
        icon="folder_open",
        bgcolor=ft.Colors.BLUE_GREY_800,
        on_click=self.open_output_folder,
    )

    # Barra de acciones
    action_buttons = ft.Row(
        controls=[
            self.btn_run,
            self.btn_stop,
            self.btn_open_folder,
        ],
        spacing=10,
    )

    self.log_view = ft.ListView(expand=True, spacing=5, auto_scroll=True)

    console_container = ft.Container(
        content=self.log_view,
        border=ft.Border(
            top=ft.BorderSide(1, ft.Colors.GREY_700),
            bottom=ft.BorderSide(1, ft.Colors.GREY_700),
            left=ft.BorderSide(1, ft.Colors.GREY_700),
            right=ft.BorderSide(1, ft.Colors.GREY_700),
        ),
        border_radius=8,
        padding=10,
        bgcolor=ft.Colors.GREY_900,
        expand=True,
    )

    main_column = ft.Column(
        controls=[
            banner_text,
            ft.Divider(),
            top_row_operations,
            self.txt_keywords,
            self.txt_output_file,
            self.region_dropdown,
            self.target_category_dropdown,
            self.advanced_modes_row,
            self.progress_bar,
            action_buttons,
            ft.Text("Consola de Ejecución:", weight=ft.FontWeight.BOLD),
            console_container,
        ],
        expand=True,
        spacing=12,
    )

    self.page.add(main_column)

  def open_category_dialog(self, e):
    categories_list_column = ft.Column(
        spacing=8, scroll=ft.ScrollMode.AUTO, height=220
    )

    def reload_categories_ui():
      categories_list_column.controls.clear()
      current_cats = self.scraper.load_config()

      if not current_cats:
        categories_list_column.controls.append(
            ft.Text(
                "No hay categorías creadas.",
                italic=True,
                color=ft.Colors.GREY_400,
            )
        )
      else:
        for cat in current_cats.keys():

          def make_delete_handler(c_name):
            return lambda _: delete_cat_action(c_name)

          row_cat = ft.Row(
              controls=[
                  ft.Text(
                      cat.upper(),
                      weight=ft.FontWeight.BOLD,
                      color=ft.Colors.WHITE,
                      expand=True,
                  ),
                  ft.IconButton(
                      icon=ft.Icons.DELETE_OUTLINE,
                      icon_color=ft.Colors.RED_400,
                      tooltip=f"Borrar categoría {cat}",
                      on_click=make_delete_handler(cat),
                  ),
              ],
              alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
          )
          categories_list_column.controls.append(row_cat)
      try:
        categories_list_column.update()
      except Exception:
        pass

    txt_new_cat = ft.TextField(
        label="Nueva categoría",
        hint_text="ej. inteligencia_artificial",
        expand=True,
    )

    def save_new_cat(e):
      cat_name = txt_new_cat.value.strip().lower()
      if cat_name:
        success = self.scraper.create_category(cat_name)
        if success:
          self.log_message(f"[+] Categoría '{cat_name}' añadida con éxito.")
          txt_new_cat.value = ""
          txt_new_cat.update()
          self.categories = self.scraper.load_config()
          self.refresh_dropdown_options()
          reload_categories_ui()
        else:
          self.log_message(
              f"[!] La categoría '{cat_name}' ya existe o no es válida."
          )

    def delete_cat_action(cat_name):
      success = self.scraper.delete_category(cat_name)
      if success:
        self.log_message(f"[-] Categoría '{cat_name}' eliminada con éxito.")
        self.categories = self.scraper.load_config()
        self.refresh_dropdown_options()
        reload_categories_ui()

    reload_categories_ui()

    add_row = ft.Row(
        controls=[
            txt_new_cat,
            ft.ElevatedButton(
                "Añadir",
                icon="add",
                on_click=save_new_cat,
                bgcolor=ft.Colors.PURPLE_700,
                color=ft.Colors.WHITE,
            ),
        ],
        spacing=10,
    )

    def close_sheet(e=None):
      bs.open = False
      self.page.update()

    bs = ft.BottomSheet(
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Gestión de Categorías (JSON)",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.PURPLE_400,
                    ),
                    ft.Divider(),
                    ft.Text(
                        "Añadir nueva categoría:", weight=ft.FontWeight.BOLD
                    ),
                    add_row,
                    ft.Divider(),
                    ft.Text("Categorías existentes:", weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=categories_list_column,
                        border=ft.Border(
                            top=ft.BorderSide(1, ft.Colors.GREY_700),
                            bottom=ft.BorderSide(1, ft.Colors.GREY_700),
                            left=ft.BorderSide(1, ft.Colors.GREY_700),
                            right=ft.BorderSide(1, ft.Colors.GREY_700),
                        ),
                        border_radius=6,
                        padding=10,
                        bgcolor=ft.Colors.GREY_900,
                    ),
                    ft.Row(
                        controls=[
                            ft.ElevatedButton(
                                "Cerrar",
                                on_click=close_sheet,
                                bgcolor=ft.Colors.GREY_800,
                                color=ft.Colors.WHITE,
                            )
                        ],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                spacing=10,
                tight=True,
            ),
            padding=20,
            bgcolor=ft.Colors.BLACK,
            width=550,
        ),
        open=True,
    )

    self.page.overlay.append(bs)
    self.page.update()

  def refresh_dropdown_options(self):
    current_val = self.mode_dropdown.value
    current_target_cat = self.target_category_dropdown.value
    self.categories = self.scraper.load_config()

    new_options = [ft.dropdown.Option("0", "Búsqueda webs")] + [
        ft.dropdown.Option(cat, f"Categoría: {cat.upper()}")
        for cat in self.categories.keys()
    ]
    self.mode_dropdown.options = new_options

    cat_options = [
        ft.dropdown.Option(cat, cat.upper()) for cat in self.categories.keys()
    ]
    self.target_category_dropdown.options = cat_options
    if current_target_cat not in self.categories:
      self.target_category_dropdown.value = None

    if current_val != "0" and current_val not in self.categories:
      self.mode_dropdown.value = "0"

    self.mode_dropdown.update()
    self.target_category_dropdown.update()

  def on_mode_change(self, e):
    is_option_zero = self.mode_dropdown.value == "0"
    self.txt_keywords.visible = is_option_zero
    self.txt_output_file.visible = is_option_zero
    self.region_dropdown.visible = is_option_zero
    self.target_category_dropdown.visible = is_option_zero
    self.advanced_modes_row.visible = is_option_zero
    self.page.update()

  def log_message(self, message: str):
    async def update_ui_async():
      self.log_view.controls.append(
          ft.Text(message, font_family="Consolas", size=12)
      )
      self.log_view.update()

    try:
      self.page.run_task(update_ui_async)
    except Exception:
      self.log_view.controls.append(
          ft.Text(message, font_family="Consolas", size=12)
      )
      self.log_view.update()

  def open_output_folder(self, e):
    current_path = os.getcwd()
    try:
      if os.name == "nt":
        os.startfile(current_path)
      elif os.name == "posix":
        subprocess.run(
            [
                "xdg-open" if sys.platform.startswith("linux") else "open",
                current_path,
            ]
        )
      self.log_message(f"[*] Carpeta abierta: {current_path}")
    except Exception as ex:
      self.log_message(f"[!] No se pudo abrir la carpeta automáticamente: {ex}")

  def run_process(self, e):
    choice = self.mode_dropdown.value
    if not choice:
      self.log_message("[!] Error: Debes seleccionar una opción o categoría.")
      return

    self.stop_event.clear()
    self.btn_run.disabled = True
    self.btn_open_folder.disabled = True
    self.btn_stop.disabled = False
    self.progress_bar.visible = True
    self.progress_bar.value = None
    self.btn_run.scale = 0.93
    self.page.update()

    def restore_btn_scale():
      time.sleep(0.15)
      self.btn_run.scale = 1.0
      try:
        self.page.update()
      except Exception:
        pass

    threading.Thread(target=restore_btn_scale, daemon=True).start()
    threading.Thread(
        target=self._execute_task, args=(choice,), daemon=True
    ).start()

  def stop_process(self, e):
    self.stop_event.set()
    self.log_message("[!] Solicitud de parada enviada por el usuario...")
    self.btn_stop.disabled = True
    try:
      self.page.update()
    except Exception:
      pass

  def _execute_task(self, choice):
    self._run_with_captured_stdout(
        lambda: self.scraper.run_category_gui(choice, self.stop_event)
        if choice != "0"
        else self._execute_custom_search()
    )

  def _execute_custom_search(self):
    keywords_val = self.txt_keywords.value
    filename_val = self.txt_output_file.value or "enlaces_encontrados.txt"
    is_wsos = self.wsos_mode_checkbox.value
    is_dirty = self.dirty_mode_checkbox.value

    target_category = self.target_category_dropdown.value
    if not target_category:
      self.log_message(
          "[!] Error estricto: Es obligatorio seleccionar una categoría de"
          " destino en el desplegable para ejecutar la búsqueda."
      )
      return

    selected_label = self.region_dropdown.value or "España"
    region_code = self.regions_map.get(selected_label, "es-es")

    if not keywords_val:
      self.log_message("[!] Debes introducir al menos una palabra clave.")
    else:
      self.scraper.search_custom_gui(
          output_filename=filename_val,
          raw_keywords=keywords_val,
          wsos_mode=is_wsos,
          dirty_mode=is_dirty,
          region=region_code,
          stop_event=self.stop_event,
          save_category=target_category,
      )

  def _run_with_captured_stdout(self, target_func):
    class StreamRedirector(io.TextIOBase):

      def __init__(self, callback):
        self.callback = callback
        self.buffer = ""

      def write(self, text):
        if text:
          self.buffer += text
          while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if line.strip():
              self.callback(line)
        return len(text)

      def flush(self):
        if self.buffer.strip():
          self.callback(self.buffer.strip())
          self.buffer = ""

      def writable(self):
        return True

    old_stdout = sys.stdout
    old_stderr = sys.stderr

    sys.stdout = StreamRedirector(self.log_message)
    sys.stderr = StreamRedirector(self.log_message)

    try:
      target_func()
    except Exception as ex:
      self.log_message(f"[!] Error crítico en ejecución: {ex}")
    finally:
      sys.stdout = old_stdout
      sys.stderr = old_stderr
      self.progress_bar.visible = False
      self.btn_run.disabled = False
      self.btn_open_folder.disabled = False
      self.btn_stop.disabled = True
      self.btn_run.scale = 1.0
      try:
        self.page.update()
      except Exception:
        pass