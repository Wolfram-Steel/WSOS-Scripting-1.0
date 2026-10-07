import re
from urllib.parse import urlparse


class URLFilter:

  def __init__(self):
    self.blocked_domains = {
        "bing.com/aclick", "ad.doubleclick.net", "googleadservices.com",
        "googlesyndication.com", "amazon-adsystem.com", "adnxs.com",
        "criteo.com", "steampowered.com", "facepunch.com",
        "playboardgames.org", "online-go.com",
    }
    self.tracker_patterns = [
        re.compile(r"utm_\w+=", re.I), re.compile(r"mscclkid=", re.I),
        re.compile(r"gclid=", re.I), re.compile(r"fbclid=", re.I),
        re.compile(r"aclick", re.I),
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
    return re.sub(r'["\'\?\!\)\.,;]+$', "", url.strip())

  def is_supported_resource(self, url: str, allow_pdf: bool = False) -> bool:
    try:
      path = urlparse(url.lower()).path
      ext = "." + path.rsplit(".", 1)[-1] if "." in path.rsplit("/", 1)[-1] else ""
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
    url_lower = url.lower()
    parsed_url = urlparse(url_lower)
    full_path = f"{parsed_url.netloc}{parsed_url.path}"
    if any(domain in full_path for domain in self.blocked_domains):
      return False
    if any(pattern.search(url_lower) for pattern in self.tracker_patterns):
      return False
    return True

  def clean_and_validate(self, urls: list, allow_pdf: bool = False) -> list:
    valid_urls, seen = [], set()
    for url in urls:
      clean_url = self.sanitize_url(url)
      if self.is_clean_url(clean_url, allow_pdf=allow_pdf) and clean_url not in seen:
        seen.add(clean_url)
        valid_urls.append(clean_url)
    return valid_urls
