"""Filtrado de URLs: trackers, anuncios, recursos binarios y dominios bloqueados."""

import posixpath
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Redes publicitarias / redirectores de anuncios (siempre bloqueados)
AD_DOMAINS = (
    "ad.doubleclick.net",
    "googleadservices.com",
    "googlesyndication.com",
    "amazon-adsystem.com",
    "adnxs.com",
    "criteo.com",
)
AD_URL_PREFIXES = ("bing.com/aclick",)  # host (sin www.) + ruta

# Dominios que el usuario no quiere recopilar (editable en settings.json)
DEFAULT_EXTRA_BLOCKED = (
    "steampowered.com",
    "facepunch.com",
    "playboardgames.org",
    "online-go.com",
)

TRACKING_PARAMS = frozenset({
    "gclid", "fbclid", "msclkid", "mscclkid", "dclid", "gbraid", "wbraid",
    "yclid", "mc_cid", "mc_eid",
})

BLOCKED_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".exe", ".msi", ".dmg", ".iso",
    ".mp3", ".mp4", ".avi", ".mov", ".mkv", ".wav", ".flac",
    ".woff", ".woff2", ".ttf", ".eot", ".css", ".js", ".xml", ".json",
})

_AD_PATH_RE = re.compile(r"(?:^|/)aclick(?:/|$)", re.I)
_TRAILING_JUNK = "\"'?!.,;"


def is_tracking_param(key: str) -> bool:
    key = key.lower()
    return key.startswith("utm_") or key in TRACKING_PARAMS


def strip_tracking_params(url: str) -> str:
    """Elimina parámetros de seguimiento (utm_*, gclid, msclkid...) conservando el resto."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if not parts.query:
        return url
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not is_tracking_param(k)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


class URLFilter:
    def __init__(self, extra_blocked_domains=None):
        domains = DEFAULT_EXTRA_BLOCKED if extra_blocked_domains is None else extra_blocked_domains
        self.extra_blocked_domains = tuple(
            d.strip().lower() for d in domains if isinstance(d, str) and d.strip()
        )
        self.blocked_extensions = BLOCKED_EXTENSIONS

    # ------------------------------------------------------------------ limpieza
    def sanitize_url(self, url: str) -> str:
        """Quita comillas y puntuación final de texto, respetando paréntesis equilibrados
        (p. ej. https://es.wikipedia.org/wiki/Python_(lenguaje))."""
        if not url:
            return ""
        url = url.strip().strip("<>")
        while url:
            last = url[-1]
            if last in _TRAILING_JUNK:
                url = url[:-1]
            elif last == ")" and url.count(")") > url.count("("):
                url = url[:-1]
            else:
                break
        return url

    # ------------------------------------------------------------------ comprobaciones
    def is_supported_resource(self, url: str, allow_pdf: bool = False) -> bool:
        try:
            path = urlsplit(url).path.lower()
        except ValueError:
            return False
        if path.startswith("/wiki/"):  # artículos tipo /wiki/Node.js no son un .js
            return True
        ext = posixpath.splitext(path.rsplit("/", 1)[-1])[1]
        if ext == ".pdf":
            return allow_pdf
        return ext not in self.blocked_extensions

    def is_ad_url(self, url: str) -> bool:
        try:
            parts = urlsplit(url)
        except ValueError:
            return True
        host = (parts.hostname or "").lower()
        if any(_host_matches(host, d) for d in AD_DOMAINS):
            return True
        host_path = (host[4:] if host.startswith("www.") else host) + parts.path.lower()
        if any(host_path.startswith(p) for p in AD_URL_PREFIXES):
            return True
        return bool(_AD_PATH_RE.search(parts.path))

    def is_blocked_domain(self, url: str) -> bool:
        host = _host(url)
        return any(_host_matches(host, d) for d in self.extra_blocked_domains)

    def is_fetchable(self, url: str, allow_pdf: bool = False) -> bool:
        """Mínimo exigible incluso en Búsqueda Sucia: http(s), recurso válido y sin anuncios."""
        if not url.startswith(("http://", "https://")):
            return False
        return self.is_supported_resource(url, allow_pdf) and not self.is_ad_url(url)

    def is_clean_url(self, url: str, allow_pdf: bool = False) -> bool:
        return self.is_fetchable(url, allow_pdf) and not self.is_blocked_domain(url)

    def clean_and_validate(self, urls, allow_pdf: bool = False):
        seen, clean = set(), []
        for raw in urls:
            url = strip_tracking_params(self.sanitize_url(raw))
            if url and url not in seen and self.is_clean_url(url, allow_pdf):
                seen.add(url)
                clean.append(url)
        return clean
