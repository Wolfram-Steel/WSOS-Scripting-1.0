"""Metadata, perfiles, scoring e identificación de datasets WSOS 1.12."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
import os
import tempfile

PROFILES = {
    "Rápido": {"quality_min": 50, "min_chars": 250, "max_chars": 2_000_000, "workers": 10, "rate_limit": 0.05, "retries": 2, "deduplicate": True},
    "Equilibrado": {"quality_min": 65, "min_chars": 300, "max_chars": 2_000_000, "workers": 8, "rate_limit": 0.10, "retries": 3, "deduplicate": True},
    "Seguro": {"quality_min": 75, "min_chars": 400, "max_chars": 1_500_000, "workers": 5, "rate_limit": 0.20, "retries": 3, "deduplicate": True},
    "Dataset IA": {"quality_min": 75, "min_chars": 1_000, "max_chars": 2_000_000, "workers": 8, "rate_limit": 0.10, "retries": 3, "deduplicate": True},
}

OBJECTIVES = ["Investigación", "Educación", "Programación", "Documentación técnica", "Dataset IA", "Archivo web", "Personalizado"]


def make_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:6].upper()}"


def normalize_url(url: str) -> str:
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    try:
        p = urlsplit(url.strip())
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                 if not (k.lower().startswith("utm_") or k.lower() in {"gclid", "fbclid", "msclkid", "mc_cid", "mc_eid"})]
        path = p.path.rstrip("/") or "/"
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, urlencode(query), ""))
    except Exception:
        return url.strip()


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()


def normalized_content_hash(content: str) -> str:
    normalized = re.sub(r"\s+", " ", content).strip().lower()
    return content_hash(normalized)


def quality_score(content: str) -> int:
    """Puntúa contenido útil; la longitud deja de dominar el resultado."""
    if not content or not content.strip():
        return 0
    text = content.strip()
    length = len(text)
    # 0-25 puntos, con crecimiento suave y techo para evitar premiar basura larga.
    length_score = min(25, max(0, int(length / 800)))
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    unique_ratio = len(set(lines)) / max(1, len(lines))
    repetition_score = round(unique_ratio * 20)
    sentence_count = len(re.findall(r"[.!?](?:\s|$)", text))
    sentence_score = min(20, sentence_count)
    structure_score = min(15, len(lines) // 4)
    code_score = min(5, text.count("```") // 2)
    return max(0, min(100, 15 + length_score + repetition_score + sentence_score + structure_score + code_score))


def build_metadata(*, author: str, project: str, organization: str, description: str,
                   language: str, objective: str, profile: str, keywords: str,
                   mode: str, license_name: str = "", engine_version: str = "1.12") -> dict:
    return {
        "wsos_schema": "1.12",
        "engine_version": engine_version,
        "project_id": project.strip() or "WSOS-PROJECT",
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


def atomic_json_dump(path: str | Path, payload: dict) -> None:
    """Escritura JSON atómica: evita dejar webs.json corrupto si el proceso cae."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, target)
    finally:
        try:
            Path(temp_name).unlink(missing_ok=True)
        except OSError:
            pass


def write_manifest(path: str, metadata: dict, stats: dict, documents: list[dict]) -> str:
    manifest_path = str(Path(path).with_suffix(".wsos.json"))
    payload = dict(metadata)
    payload["stats"] = stats
    payload["documents"] = documents
    atomic_json_dump(manifest_path, payload)
    return manifest_path
