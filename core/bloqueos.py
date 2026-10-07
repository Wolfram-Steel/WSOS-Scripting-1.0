import re
from urllib.parse import urlparse


class URLFilter:

  def __init__(self):
    self.blocked_domains = {
        "bing.com/aclick", "ad.doubleclick.net", "googleadservices.com",
        "googlesyndication.com", "amazon-adsystem.com", "adnxs.com",
        "criteo.com",
    }
    self.tracker_patterns = [
        re.compile(r"[?&]utm_\w+=", re.I), re.compile(r"[?&]msclkid=", re.I),
        re.compile(r"[?&]gclid=", re.I), re.compile(r"[?&]fbclid=", re.I),
    ]
    self.blocked_extensions = {
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
        ".mp3", ".wav", ".ogg", ".mp4", ".mkv", ".avi", ".mov", ".webm",
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
        ".exe", ".msi", ".dmg", ".iso", ".apk", ".bin",
        ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
        ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    }

  def sanitize_url(self, url: str) -> str:
    if not url:
      return ""
    value = url.strip().strip("\'\"")
    # Elimina puntuación de una URL pegada al final, pero conserva paréntesis
    # balanceados como los usados habitualmente en Wikipedia.
    while value and value[-1] in "?!.,;":
      value = value[:-1]
    while value.endswith(")") and value.count(")") > value.count("("):
      value = value[:-1]
    return value

  def is_supported_resource(self, url: str, allow_pdf: bool = False) -> bool:
    try:
      path = urlparse(url.lower()).path
      filename = path.rsplit("/", 1)[-1]
      ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
      if ext == ".pdf":
        return allow_pdf
      return ext not in self.blocked_extensions
    except Exception:
      return False

  def is_clean_url(self, url: str, allow_pdf: bool = False) -> bool:
    if not url or not url.startswith(("http://", "https://")):
      return False
    if not self.is_supported_resource(url, allow_pdf=allow_pdf):
      return False
    parsed = urlparse(url.lower())
    host = parsed.hostname or ""
    full_path = f"{host}{parsed.path}"
    if any(blocked in full_path for blocked in self.blocked_domains):
      return False
    url_lower = url.lower()
    if any(pattern.search(url_lower) for pattern in self.tracker_patterns):
      return False
    return True

  def clean_and_validate(self, urls: list, allow_pdf: bool = False) -> list:
    valid_urls, seen = [], set()
    for url in urls:
      clean_url = self.sanitize_url(url)
      if self.is_clean_url(clean_url, allow_pdf=allow_pdf):
        from core.dataset import normalize_url
        normalized = normalize_url(clean_url)
        if normalized not in seen:
          seen.add(normalized)
          valid_urls.append(normalized)
    return valid_urls
