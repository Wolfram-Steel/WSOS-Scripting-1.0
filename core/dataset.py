"""Perfiles, scoring, selección de documentos, metadatos y manifiestos WSOS."""
from __future__ import annotations

import hashlib
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .bloqueos import is_tracking_param
from .version import SCHEMA_VERSION, __version__

PROFILES = {
    "Rápido": {"quality_min": 50, "min_chars": 250, "max_chars": 2_000_000, "workers": 10, "rate_limit": 0.05, "retries": 2, "deduplicate": True},
    "Equilibrado": {"quality_min": 70, "min_chars": 300, "max_chars": 2_000_000, "workers": 8, "rate_limit": 0.10, "retries": 3, "deduplicate": True},
    "Seguro": {"quality_min": 80, "min_chars": 400, "max_chars": 1_500_000, "workers": 5, "rate_limit": 0.20, "retries": 3, "deduplicate": True},
    "Dataset IA": {"quality_min": 80, "min_chars": 1_000, "max_chars": 2_000_000, "workers": 8, "rate_limit": 0.10, "retries": 3, "deduplicate": True},
}
DEFAULT_PROFILE = "Equilibrado"

OBJECTIVES = ["Investigación", "Educación", "Programación", "Documentación técnica", "Dataset IA", "Archivo web", "Personalizado"]

REASON_LABELS = {
    "error_descarga": "error de descarga",
    "pdf_omitido": "PDF omitido",
    "demasiado_grande": "archivo demasiado grande",
    "interrumpido": "interrumpido por el usuario",
    "vacio": "sin contenido útil",
    "corto": "demasiado corto",
    "baja_calidad": "calidad insuficiente",
    "duplicado": "contenido duplicado",
}


def get_profile(name: str | None) -> dict:
    """Configuración del perfil (copia); si el nombre no existe usa el equilibrado."""
    return dict(PROFILES.get(name or DEFAULT_PROFILE, PROFILES[DEFAULT_PROFILE]))


def make_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:6].upper()}"


def normalize_url(url: str) -> str:
    try:
        p = urlsplit(url.strip())
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not is_tracking_param(k)]
        path = p.path.rstrip("/") or "/"
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, urlencode(query), ""))
    except Exception:
        return url.strip()


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()


_SENTENCE_RE = re.compile(r"[.!?](?:\s|$)")


def quality_score(content: str) -> int:
    """Puntuación 0-100 basada en señales de texto útil (no solo en longitud).

    Longitud (20) + variedad de líneas y frases (15) + variedad de palabras (15) +
    densidad de frases (20) + proporción de letras (15) + longitud media de
    línea (10) + bloques de código (5).
    """
    if not content or not content.strip():
        return 0
    length = len(content)
    lines = [x.strip() for x in content.splitlines() if x.strip()]
    n_lines = max(1, len(lines))

    length_score = 20 * min(1.0, length / 4000)
    sentence_list = [x.strip().lower() for x in _SENTENCE_RE.split(content) if x.strip()]
    sentence_ratio = len(set(sentence_list)) / max(1, len(sentence_list))
    line_diversity = 15 * min(len(set(lines)) / n_lines, sentence_ratio)

    words = content.split()[:1000]
    type_token = len(set(w.lower() for w in words)) / max(1, len(words))
    word_diversity = 15 * min(1.0, type_token / 0.35)

    sentences = len(_SENTENCE_RE.findall(content))
    per_1000 = sentences / max(1.0, length / 1000)
    sentence_score = 20 * min(1.0, per_1000 / 5)

    visible = max(1, length - content.count(" ") - content.count("\n") - content.count("\t"))
    alpha_ratio = sum(1 for c in content if c.isalpha()) / visible
    alpha_score = 15 * min(1.0, alpha_ratio / 0.6)

    avg_words = sum(len(x.split()) for x in lines) / n_lines
    line_score = 10 * min(1.0, avg_words / 8)

    code_score = min(5, content.count("```") // 2)

    total = length_score + line_diversity + word_diversity + sentence_score + alpha_score + line_score + code_score
    if len(words) >= 100 and type_token < 0.1:  # texto casi totalmente repetido
        total = min(total, 40)
    return max(0, min(100, round(total)))


def _fetch_reason_key(reason) -> str | None:
    if reason in (None, "", "ok"):
        return None
    return {"pdf_skipped": "pdf_omitido", "too_large": "demasiado_grande", "stopped": "interrumpido"}.get(reason, "error_descarga")


def select_documents(results, profile_cfg: dict):
    """Aplica el perfil a los resultados del scraping.

    Devuelve (aceptados, contador_de_rechazos, rechazados) donde cada rechazado es
    (url, clave_de_motivo, calidad). Los elementos None (no procesados) se ignoran.
    """
    accepted, rejected, rejections, seen = [], [], Counter(), set()
    for item in results:
        if not item:
            continue
        url = item.get("url", "")
        content = item.get("content") or ""
        quality = item.get("quality", 0)
        key = _fetch_reason_key(item.get("reason"))
        if key is None:
            if not content:
                key = "vacio"
            elif len(content) < profile_cfg["min_chars"]:
                key = "corto"
            elif quality < profile_cfg["quality_min"]:
                key = "baja_calidad"
            elif profile_cfg.get("deduplicate", True) and item.get("sha256") in seen:
                key = "duplicado"
        if key:
            rejections[key] += 1
            rejected.append((url, key, quality))
            continue
        seen.add(item.get("sha256"))
        accepted.append(item)
    return accepted, rejections, rejected


def build_metadata(*, author: str, project: str, organization: str, description: str,
                   language: str, objective: str, profile: str, keywords: str,
                   mode: str, license_name: str = "", engine_version: str = __version__) -> dict:
    project_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", project.strip()).strip("-")
    return {
        "wsos_schema": SCHEMA_VERSION,
        "engine_version": engine_version,
        "project_id": project_id or "WSOS-PROJECT",
        "project_name": project.strip() or "WSOS Project",
        "author": author.strip(),
        "organization": organization.strip(),
        "description": description.strip(),
        "license": license_name.strip(),
        "language": language.strip() or "es",
        "objective": objective,
        "profile": profile,
        "keywords": keywords,
        "mode": mode,
        "dataset_id": make_id("WSOS"),
        "run_id": make_id("RUN"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def write_manifest(path: str, metadata: dict, stats: dict, documents: list[dict]) -> str:
    from .config import atomic_write_json  # import tardío: config depende de este módulo

    source = Path(path)
    manifest_path = source.with_name(source.stem + ".wsos.json")
    payload = dict(metadata)
    payload["stats"] = stats
    payload["documents"] = documents
    atomic_write_json(manifest_path, payload)
    return str(manifest_path)
