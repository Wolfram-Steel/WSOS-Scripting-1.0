# bloqueos.py
import re
from urllib.parse import urlparse


class URLFilter:

  def __init__(self):
    # Lista de dominios de publicidad y distracciones (videojuegos/ocio)
    self.blocked_domains = {
        "bing.com/aclick",
        "ad.doubleclick.net",
        "googleadservices.com",
        "googlesyndication.com",
        "amazon-adsystem.com",
        "adnxs.com",
        "criteo.com",
        "steampowered.com",
        "facepunch.com",
        "playboardgames.org",
        "online-go.com",
    }

    # Patrones de trackers y campañas (precompilados para mayor velocidad)
    self.tracker_patterns = [
        re.compile(r"utm_\w+=", re.I),
        re.compile(r"mscclkid=", re.I),
        re.compile(r"gclid=", re.I),
        re.compile(r"fbclid=", re.I),
        re.compile(r"aclick", re.I),
    ]

  def sanitize_url(self, url: str) -> str:
    """Limpia caracteres basura sobrantes al final de la URL (comillas, signos, etc.)."""
    if not url:
      return ""
    return re.sub(r'[\"\'\?\!\)\.,;]+$', "", url.strip())

  def is_clean_url(self, url: str) -> bool:
    """Evalúa si una URL es limpia y apta para el dataset o si es publicidad/ruido."""
    if not url or not url.startswith(("http://", "https://")):
      return False

    url_lower = url.lower()
    parsed_url = urlparse(url_lower)
    full_path = f"{parsed_url.netloc}{parsed_url.path}"

    # 1. Comprobar dominios o rutas bloqueadas exactas
    for domain in self.blocked_domains:
      if domain in full_path:
        return False

    # 2. Comprobar patrones de trackers activos
    for pattern in self.tracker_patterns:
      if pattern.search(url_lower):
        return False

    return True

  def clean_and_validate(self, urls: list) -> list:
    """Sanitiza, filtra una lista de URLs y elimina duplicados internos."""
    valid_urls = []
    seen = set()

    for url in urls:
      clean_url = self.sanitize_url(url)
      if self.is_clean_url(clean_url):
        if clean_url not in seen:
          seen.add(clean_url)
          valid_urls.append(clean_url)

    return valid_urls