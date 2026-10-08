# ui.py
import io
import queue
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
import flet as ft
from app.scraping import IntegratedCodeScraper
from core.config import load_settings, save_settings
from core.dataset import PROFILES, OBJECTIVES
from core.version import APP_TITLE


class ScraperUI:

    def __init__(self, page: ft.Page):
        self.page = page
        self.settings = load_settings()
        self.scraper = IntegratedCodeScraper(output_dir=self.settings["output_dir"])
        self.categories = self.scraper.load_config()

        self.stop_event = threading.Event()
        self._log_queue = queue.SimpleQueue()
        self._log_drain_lock = threading.Lock()
        self._log_drain_running = False

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
        self.page.title = APP_TITLE
        self.page.padding = 20
        self.page.spacing = 15
        self.page.theme_mode = ft.ThemeMode.DARK
        window = getattr(self.page, "window", None)
        if window is not None and hasattr(window, "width"):  # Flet reciente
            window.width = 900
            window.height = 1100
        else:  # Flet antiguo
            self.page.window_width = 900
            self.page.window_height = 1100

    def build_layout(self):
        banner_text = ft.Text(
                APP_TITLE,
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
                label="Nombre base del dataset (.txt)",
                value="enlaces_encontrados.txt",
                visible=is_init_zero,
        )

        self.region_dropdown = ft.Dropdown(
                label="Región de búsqueda",
                value=self.settings.get("region", "España"),
                options=[ft.dropdown.Option(name) for name in self.regions_map.keys()],
                visible=is_init_zero,
                border_color=ft.Colors.RED_400,
        )

        # Identidad y perfil del dataset: datos persistentes en el manifiesto WSOS.
        # El perfil se aplica también a la extracción de categorías (workers, intentos,
        # límites, calidad y deduplicación), por eso está visible en ambos modos.
        self.profile_dropdown = ft.Dropdown(
                label="Perfil de recopilación",
                value=self.settings.get("profile", "Equilibrado"),
                options=[ft.dropdown.Option(name) for name in PROFILES.keys()],
                border_color=ft.Colors.BLUE_400,
        )
        self.objective_dropdown = ft.Dropdown(
                label="Objetivo del dataset",
                value=self.settings.get("objective", "Investigación"),
                options=[ft.dropdown.Option(name) for name in OBJECTIVES],
                visible=is_init_zero, border_color=ft.Colors.BLUE_400,
        )
        self.txt_project = ft.TextField(
                label="Proyecto / Project ID", hint_text="ej. INF-NUMS-MATH",
                value=self.settings.get("project", ""),
                visible=is_init_zero, width=185, border_color=ft.Colors.CYAN_400,
        )
        self.txt_author = ft.TextField(
                label="Autor", hint_text="Tu nombre",
                value=self.settings.get("author", ""),
                visible=is_init_zero, width=185, border_color=ft.Colors.GREEN_400,
        )
        self.txt_organization = ft.TextField(
                label="Organización", hint_text="Opcional",
                value=self.settings.get("organization", ""),
                visible=is_init_zero, width=185, border_color=ft.Colors.AMBER_400,
        )
        self.txt_license = ft.TextField(
                label="Licencia", hint_text="ej. CC BY 4.0",
                value=self.settings.get("license", ""),
                visible=is_init_zero, width=185, border_color=ft.Colors.PURPLE_400,
        )
        self.txt_language = ft.Dropdown(
                label="Idioma", value=self.settings.get("language", "es"), width=150, visible=is_init_zero,
                options=[
                        ft.dropdown.Option("es", "Español"),
                        ft.dropdown.Option("en", "English"),
                        ft.dropdown.Option("fr", "Français"),
                        ft.dropdown.Option("de", "Deutsch"),
                        ft.dropdown.Option("it", "Italiano"),
                        ft.dropdown.Option("pt", "Português"),
                ],
                border_color=ft.Colors.TEAL_400,
        )
        self.txt_description = ft.TextField(
                label="Descripción del dataset",
                hint_text="Describe para qué se recopila este material",
                visible=is_init_zero, multiline=True, min_lines=1, max_lines=3, width=760,
                border_color=ft.Colors.BLUE_GREY_400,
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

        self.txt_output_dir = ft.TextField(
                label="Carpeta de salida",
                hint_text="Donde se guardan los .txt, datasets y manifiestos",
                value=self.settings.get("output_dir", ""),
                border_color=ft.Colors.GREY_500,
                expand=True,
        )

        # FilePicker es un servicio nativo de Flet en las versiones actuales.
        # No se añade a page.overlay: hacerlo provoca "Unknown control: FilePicker".
        self.output_folder_picker = ft.FilePicker()

        self.btn_open_output_folder_inline = ft.IconButton(
                icon=ft.Icons.FOLDER_OPEN,
                icon_color=ft.Colors.BLUE_400,
                tooltip="Seleccionar carpeta de salida",
                on_click=self.select_output_folder,
        )
        self.output_dir_row = ft.Row(
                controls=[self.txt_output_dir, self.btn_open_output_folder_inline],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                visible=False,  # Búsqueda webs estándar no usa carpeta de salida.
        )

        # Funciones de exclusión mutua para Modo WSOS y Búsqueda Sucia
        def on_wsos_changed(e):
            if self.wsos_mode_checkbox.value:
                self.dirty_mode_checkbox.value = False
                self.dirty_mode_checkbox.update()
            self._update_output_controls_visibility()

        def on_dirty_changed(e):
            if self.dirty_mode_checkbox.value:
                self.wsos_mode_checkbox.value = False
                self.wsos_mode_checkbox.update()
            self._update_output_controls_visibility()

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

        self.pdf_checkbox = ft.Checkbox(
                label="Añadir PDF", value=False, visible=is_init_zero,
                tooltip="Incluye PDFs en el dataset. Puede aumentar el tiempo de procesamiento.",
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
                        self.pdf_checkbox,
                ],
                spacing=15,
                visible=is_init_zero,
        )

        self.progress_bar = ft.ProgressBar(
                value=0, color=ft.Colors.RED_500, bgcolor=ft.Colors.GREY_800, visible=False
        )

        self.stats_text = ft.Text(
                "Dataset: pendiente de ejecución", size=12, color=ft.Colors.GREY_400, visible=True
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

        # Barra de acciones
        action_buttons = ft.Row(
                controls=[
                        self.btn_run,
                        self.btn_stop,
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

        # El formulario mantiene un ancho fijo para que maximizar la ventana no
        # desplace los controles de categoría y metadatos. La consola es la zona
        # que absorbe el espacio adicional.
        form_column = ft.Column(
                controls=[
                        top_row_operations,
                        self.txt_keywords,
                        self.txt_output_file,
                        self.region_dropdown,
                        ft.Row(controls=[self.profile_dropdown, self.objective_dropdown], spacing=10),
                        ft.Row(controls=[self.txt_project, self.txt_author, self.txt_organization, self.txt_license], spacing=8),
                        ft.Row(controls=[self.txt_language], spacing=8),
                        self.txt_description,
                        self.target_category_dropdown,
                        self.output_dir_row,
                        self.advanced_modes_row,
                        self.progress_bar,
                        self.stats_text,
                        action_buttons,
                ],
                width=760,
                spacing=10,
        )

        form_area = ft.Row(
                controls=[form_column],
                alignment=ft.MainAxisAlignment.START,
        )

        main_column = ft.Column(
                controls=[
                        banner_text,
                        ft.Divider(),
                        form_area,
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

    def _update_output_controls_visibility(self):
        # La Búsqueda webs estándar persiste exclusivamente en config/webs.json.
        # Solo los modos que generan dataset necesitan la carpeta de salida.
        is_search = self.mode_dropdown.value == "0"
        needs_dataset_output = is_search and bool(
            self.wsos_mode_checkbox.value or self.dirty_mode_checkbox.value
        )
        self.output_dir_row.visible = self.mode_dropdown.value != "0" or needs_dataset_output
        self.txt_output_file.visible = needs_dataset_output

    def on_mode_change(self, e):
        is_option_zero = self.mode_dropdown.value == "0"
        self.txt_keywords.visible = is_option_zero
        self.region_dropdown.visible = is_option_zero
        self.target_category_dropdown.visible = is_option_zero
        self.advanced_modes_row.visible = is_option_zero
        for control in (self.objective_dropdown, self.txt_author,
                                        self.txt_project, self.txt_organization, self.txt_license, self.txt_language, self.txt_description):
            control.visible = is_option_zero
        self._update_output_controls_visibility()
        self.page.update()

    def log_message(self, message: str):
        """Encola mensajes y actualiza la consola en lotes para reducir repintados Flet."""
        self._log_queue.put(str(message))
        with self._log_drain_lock:
            if self._log_drain_running:
                return
            self._log_drain_running = True

        async def drain():
            try:
                while True:
                    batch = []
                    while True:
                        try:
                            batch.append(self._log_queue.get_nowait())
                        except Exception:
                            break
                    if batch:
                        for line in batch:
                            self.log_view.controls.append(
                                ft.Text(line, font_family="Consolas", size=12)
                            )
                        if len(self.log_view.controls) > 1500:
                            del self.log_view.controls[:300]
                        self.log_view.update()
                    with self._log_drain_lock:
                        if self._log_queue.empty():
                            self._log_drain_running = False
                            return
                    await __import__("asyncio").sleep(0.10)
            except Exception:
                with self._log_drain_lock:
                    self._log_drain_running = False

        try:
            self.page.run_task(drain)
        except Exception:
            # Fallback mínimo para entornos Flet sin run_task.
            try:
                line = self._log_queue.get_nowait()
                self.log_view.controls.append(ft.Text(line, font_family="Consolas", size=12))
                self.log_view.update()
            except Exception:
                pass
            with self._log_drain_lock:
                self._log_drain_running = False

    def update_progress(self, completed, total, label=""):
        """Actualiza de forma segura la barra de progreso desde el hilo de trabajo."""
        try:
            value = 0 if total <= 0 else min(1.0, completed / total)
            self.progress_bar.value = value
            if label:
                self.progress_bar.tooltip = label
            self.progress_bar.update()
        except Exception:
            pass

    def update_stats(self, metadata, stats):
        """Muestra la identidad y métricas del último dataset generado."""
        text = (
                f"Dataset {metadata.get('dataset_id', '-')} | "
                f"Run {metadata.get('run_id', '-')} | "
                f"{stats.get('documents_accepted', 0)} docs | "
                f"{stats.get('duplicates', 0)} duplicados | "
                f"{stats.get('characters', 0):,} caracteres | "
                f"Q {stats.get('average_quality', 0)}/100 | "
                f"{stats.get('urls_per_second', 0)} URL/s"
        )
        self.stats_text.value = text
        try:
            self.stats_text.update()
        except Exception:
            pass

    def _output_dir(self) -> str:
        path = (self.txt_output_dir.value or "").strip() or self.settings["output_dir"]
        os.makedirs(path, exist_ok=True)
        return path

    def _apply_settings(self, include_output=True):
        """Guarda ajustes; la Búsqueda webs estándar no crea ni modifica la salida."""
        out_dir = self.settings["output_dir"]
        if include_output:
            try:
                out_dir = self._output_dir()
            except OSError as ex:
                out_dir = self.settings["output_dir"]
                self.log_message(f"[!] Carpeta de salida no válida ({ex}); se usa: {out_dir}")
            self.scraper.output_dir = Path(out_dir)
        self.settings.update({
                "output_dir": out_dir,
                "region": self.region_dropdown.value,
                "profile": self.profile_dropdown.value,
                "objective": self.objective_dropdown.value,
                "author": self.txt_author.value or "",
                "project": self.txt_project.value or "",
                "organization": self.txt_organization.value or "",
                "license": self.txt_license.value or "",
                "language": self.txt_language.value,
        })
        try:
            save_settings(self.settings)
        except OSError as ex:
            self.log_message(f"[!] No se pudieron guardar los ajustes: {ex}")

    def select_output_folder(self, e):
        """Abre el selector nativo y guarda la carpeta elegida en el campo de salida."""
        async def pick_folder():
            try:
                current_path = (self.txt_output_dir.value or "").strip()
                if not current_path:
                    current_path = self.settings.get("output_dir", "")

                selected_path = await self.output_folder_picker.get_directory_path(
                        dialog_title="Seleccionar carpeta de salida",
                        initial_directory=current_path or None,
                )
                if not selected_path:
                    return

                selected_path = os.path.abspath(selected_path)
                os.makedirs(selected_path, exist_ok=True)
                self.txt_output_dir.value = selected_path
                self.settings["output_dir"] = selected_path
                self.scraper.output_dir = Path(selected_path)
                try:
                    save_settings(self.settings)
                except OSError as ex:
                    self.log_message(f"[!] No se pudo guardar la ruta de salida: {ex}")
                self.txt_output_dir.update()
                self.log_message(f"[*] Carpeta de salida seleccionada: {selected_path}")
            except Exception as ex:
                self.log_message(f"[!] No se pudo seleccionar la carpeta de salida: {ex}")

        try:
            self.page.run_task(pick_folder)
        except Exception as ex:
            self.log_message(f"[!] No se pudo abrir el selector de carpetas: {ex}")

    def run_process(self, e):
        choice = self.mode_dropdown.value
        if not choice:
            self.log_message("[!] Error: Debes seleccionar una opción o categoría.")
            return

        is_standard_web_search = (
            self.mode_dropdown.value == "0"
            and not self.wsos_mode_checkbox.value
            and not self.dirty_mode_checkbox.value
        )
        self._apply_settings(include_output=not is_standard_web_search)
        self.stop_event.clear()
        self.btn_run.disabled = True
        self.btn_stop.disabled = False
        self.progress_bar.visible = True
        self.progress_bar.value = 0
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
                lambda: self.scraper.run_category_gui(
                        choice, self.stop_event, self.update_progress,
                        profile=self.profile_dropdown.value or "Equilibrado",
                )
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
                    progress_callback=self.update_progress,
                    profile=self.profile_dropdown.value or "Equilibrado",
                    author=self.txt_author.value or "",
                    project=self.txt_project.value or "",
                    organization=self.txt_organization.value or "",
                    description=self.txt_description.value or "",
                    language=self.txt_language.value or "es",
                    objective=self.objective_dropdown.value or "Investigación",
                    stats_callback=self.update_stats,
                    allow_pdf=bool(self.pdf_checkbox.value),
                    license_name=self.txt_license.value or "",
            )

    def _run_with_captured_stdout(self, target_func):
        class StreamRedirector(io.TextIOBase):
            """Redirige print() a la consola de la UI; seguro con varios hilos escribiendo."""

            def __init__(self, callback):
                self.callback = callback
                self.buffer = ""
                self._lock = threading.Lock()

            def write(self, text):
                if not text:
                    return 0
                with self._lock:
                    self.buffer += text
                    *lines, self.buffer = self.buffer.split("\n")
                for line in lines:
                    if line.strip():
                        self.callback(line)
                return len(text)

            def flush(self):
                with self._lock:
                    pending, self.buffer = self.buffer.strip(), ""
                if pending:
                    self.callback(pending)

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
            self.btn_stop.disabled = True
            self.btn_run.scale = 1.0
            try:
                self.page.update()
            except Exception:
                pass