"""Persistencia: webs.json (categorías) y settings.json (ajustes de la interfaz)."""

import json
import os
import re
import shutil
import tempfile
import threading
import time
import unicodedata
from pathlib import Path

from .bloqueos import DEFAULT_EXTRA_BLOCKED
from .dataset import normalize_url

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DEFAULT_CONFIG = CONFIG_DIR / "webs.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "output_dir": str(BASE_DIR / "salida"),
    "region": "España",
    "profile": "Equilibrado",
    "objective": "Investigación",
    "author": "",
    "project": "",
    "organization": "",
    "license": "",
    "language": "es",
    "extra_blocked_domains": list(DEFAULT_EXTRA_BLOCKED),
}


def atomic_write_json(path, data) -> None:
    """Escribe a un temporal y lo mueve con os.replace: nunca deja un JSON a medias."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=4, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def slugify(name: str, default: str = "categoria") -> str:
    """Nombre seguro para archivos: 'Programación/IA' -> 'programacion_ia'."""
    text = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return text[:60] or default


def output_path(output_dir, filename: str) -> Path:
    """Ruta dentro de la carpeta de salida; descarta directorios incluidos en el nombre."""
    name = Path(filename or "").name or "enlaces_encontrados.txt"
    directory = Path(output_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


class ConfigStore:
    """Acceso seguro a webs.json. Las categorías se resuelven sin distinguir mayúsculas."""

    def __init__(self, path=DEFAULT_CONFIG):
        self.path = Path(path)
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ lectura/escritura
    def load(self) -> dict:
        with self._lock:
            if not self.path.exists():
                return {}
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise ValueError("el JSON raíz debe ser un objeto")
            except (ValueError, UnicodeDecodeError) as exc:
                self._quarantine(exc)
                return {}
            return {
                str(key): [u for u in value if isinstance(u, str)]
                for key, value in raw.items() if isinstance(value, list)
            }

    def save(self, data: dict) -> None:
        with self._lock:
            atomic_write_json(self.path, data)

    def _quarantine(self, exc) -> None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = self.path.with_name(f"{self.path.name}.corrupt-{stamp}")
        try:
            shutil.copy2(self.path, backup)
            print(f"[!] {self.path.name} no es válido ({exc}). Copia guardada en {backup.name}.")
        except OSError:
            print(f"[!] {self.path.name} no es válido ({exc}).")

    # ------------------------------------------------------------------ categorías
    def resolve_key(self, name: str, data: dict = None):
        data = self.load() if data is None else data
        target = (name or "").strip().casefold()
        for key in data:
            if key.casefold() == target:
                return key
        return None

    def create_category(self, name: str) -> bool:
        key = (name or "").strip().lower()
        if not key:
            return False
        with self._lock:
            data = self.load()
            slug = slugify(key)
            if self.resolve_key(key, data) or any(slugify(k) == slug for k in data):
                return False
            data[key] = []
            self.save(data)
        return True

    def delete_category(self, name: str) -> bool:
        with self._lock:
            data = self.load()
            key = self.resolve_key(name, data)
            if key is None:
                return False
            del data[key]
            self.save(data)
        return True

    def add_urls(self, name: str, urls, create: bool = True) -> int:
        """Añade URLs sin duplicados (comparadas normalizadas). Devuelve cuántas se añadieron."""
        with self._lock:
            data = self.load()
            key = self.resolve_key(name, data)
            created = False
            if key is None:
                key = (name or "").strip().lower()
                if not create or not key:
                    return 0
                data[key] = []
                created = True
            known = {normalize_url(u) for u in data[key]}
            added = 0
            for url in urls:
                norm = normalize_url(url)
                if norm and norm not in known:
                    known.add(norm)
                    data[key].append(url)
                    added += 1
            if added or created:
                self.save(data)
            return added


# ---------------------------------------------------------------------- ajustes de la UI
def load_settings(path=SETTINGS_FILE) -> dict:
    settings = dict(DEFAULT_SETTINGS)
    try:
        stored = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            settings.update({k: v for k, v in stored.items() if k in DEFAULT_SETTINGS})
    except (OSError, ValueError):
        pass
    return settings


def save_settings(settings: dict, path=SETTINGS_FILE) -> None:
    atomic_write_json(path, {k: v for k, v in settings.items() if k in DEFAULT_SETTINGS})
