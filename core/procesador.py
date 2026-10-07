# procesador.py
import html
import re
from io import BytesIO
from bs4 import BeautifulSoup

from .dataset import content_hash, quality_score, normalized_content_hash
from .red import DomainRateLimiter, get_thread_session, request_with_retry


class WebProcessor:
  """Descarga y extracción cooperativa de contenido web."""

  def __init__(self, stop_event=None, rate_limiter=None, retries=3, max_chars=None):
    self.stop_event = stop_event
    self.rate_limiter = rate_limiter or DomainRateLimiter(0.20)
    self.retries = max(1, int(retries))
    self.max_chars = max_chars
    self.headers = {
        "User-Agent": "WSOS-Scripting/1.12 (+dataset extraction; contact via project metadata)",
        "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
    }

    # Solo patrones que representan líneas/elementos claramente ajenos al contenido.
    self.raw_noise_patterns = [
        r"^ir al contenido$",
        r"^de wikipedia, la enciclopedia libre$",
        r"^busca fuentes:?$",
        r"^control de autoridades$",
        r"^proyectos wikimedia$",
        r"^enlaces externos$",
        r"^véase también$",
        r"^referencias$",
        r"^navigation$",
        r"^modules$",
        r"^theme$",
        r"^copyright(?:\s|$)",
        r"^last updated on(?:\s|$)",
        r"^created using sphinx$",
        r"^found a bug(?:\s|$)",
        r"^wikimedia commons alberga$",
        r"^wikilibros alberga$",
        r"^\d+(?:[ \t]+\d+)+$",
        r"^[0-9]+\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+,$",
        # Detecta una línea casi exclusivamente compuesta de texto fusionado,
        # sin romper palabras legítimas como JavaScript/GitHub/iPhone.
        r"^.{0,24}\s+[a-záéíóúñ][A-ZÁÉÍÓÚÑ].*$",
    ]
    self.compiled_noise_patterns = [re.compile(pattern) for pattern in self.raw_noise_patterns]

  def is_noise_line(self, line: str) -> bool:
    line_clean = line.strip()
    if len(line_clean) < 3:
      return True

    # No eliminar títulos/listas solo por ser cortos. Solo filtramos líneas muy
    # cortas que son claramente controles de interfaz.
    words = line_clean.split()
    if len(words) <= 2 and not re.search(r"[.!?:]$", line_clean):
      lower = line_clean.lower()
      if lower in {"menu", "home", "login", "search", "next", "previous", "navigation"}:
        return True

    for pattern in self.compiled_noise_patterns:
      if pattern.search(line_clean):
        return True
    return False

  def clean_text_preserving_code(self, text: str) -> str:
    if not text:
      return ""
    text = html.unescape(text)
    text = re.sub(r"[\u200b-\u200d\uFEFF]", "", text)
    lines = text.splitlines()
    cleaned_lines = []
    inside_code_block = False

    for line in lines:
      if "```" in line:
        inside_code_block = not inside_code_block
        cleaned_lines.append(line.strip())
        continue
      if inside_code_block:
        cleaned_lines.append(line.rstrip())
        continue
      line_clean = re.sub(r"[ \t]+", " ", line).strip()
      if line_clean and not self.is_noise_line(line_clean):
        cleaned_lines.append(line_clean)

    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

  def _read_limited(self, response, max_bytes: int, stop_event=None) -> bytes | None:
    if response is None:
      return None
    try:
      content_length = response.headers.get("Content-Length")
      if content_length and int(content_length) > max_bytes:
        return None
    except (TypeError, ValueError):
      pass

    chunks = []
    total = 0
    try:
      for chunk in response.iter_content(chunk_size=64 * 1024):
        if stop_event and stop_event.is_set():
          return None
        if not chunk:
          continue
        total += len(chunk)
        if total > max_bytes:
          return None
        chunks.append(chunk)
      return b"".join(chunks)
    finally:
      response.close()

  def _finalize_content(self, content: str) -> str:
    content = self.clean_text_preserving_code(content)
    if self.max_chars and len(content) > self.max_chars:
      content = content[:self.max_chars].rstrip()
    return content

  def scrape_url(self, url: str, stop_event=None, allow_pdf=False) -> str:
    return self.scrape_url_details(url, stop_event=stop_event, allow_pdf=allow_pdf).get("content", "")

  def scrape_url_details(self, url: str, stop_event=None, allow_pdf=False) -> dict:
    active_stop = stop_event or self.stop_event
    empty = {"url": url, "content": "", "quality": 0, "sha256": "", "normalized_sha256": ""}
    try:
      if active_stop and active_stop.is_set():
        return {**empty, "status": "interrupted"}

      print(f"  [*] Analizando fuente: {url}")
      response = request_with_retry(
          "GET", url, session=get_thread_session(), headers=self.headers,
          timeout=(5, 10), attempts=self.retries, rate_limiter=self.rate_limiter,
          stop_event=active_stop, stream=True,
      )
      if response is None:
        return {**empty, "status": "interrupted" if active_stop and active_stop.is_set() else "request_failed"}
      if response.status_code != 200:
        status = response.status_code
        response.close()
        print(f"      [!] Error de acceso (Status: {status})")
        return {**empty, "status": status}

      content_type = (response.headers.get("Content-Type") or "").lower()
      is_pdf = url.lower().split("?", 1)[0].endswith(".pdf") or "application/pdf" in content_type
      max_bytes = 15_000_000 if is_pdf else 2_000_000
      raw_bytes = self._read_limited(response, max_bytes, active_stop)
      if raw_bytes is None:
        if active_stop and active_stop.is_set():
          return {**empty, "status": "interrupted"}
        print(f"      [!] Recurso demasiado grande; descartado (límite {max_bytes // 1_000_000} MB).")
        return {**empty, "status": "too_large"}

      if is_pdf:
        if not allow_pdf:
          return {**empty, "status": "pdf_skipped", "type": "pdf", "bytes": len(raw_bytes)}
        try:
          from pypdf import PdfReader
          reader = PdfReader(BytesIO(raw_bytes))
          pages = []
          for page in reader.pages:
            if active_stop and active_stop.is_set():
              return {**empty, "status": "interrupted", "type": "pdf", "bytes": len(raw_bytes)}
            pages.append(page.extract_text() or "")
          content = self._finalize_content("\n\n".join(pages))
          return {
              **empty, "content": content, "quality": quality_score(content),
              "sha256": content_hash(content) if content else "",
              "normalized_sha256": normalized_content_hash(content) if content else "",
              "status": 200, "bytes": len(raw_bytes), "type": "pdf", "pages": len(reader.pages),
          }
        except Exception as exc:
          print(f"      [!] Error leyendo PDF: {exc}")
          return {**empty, "status": "pdf_error", "bytes": len(raw_bytes), "type": "pdf"}

      try:
        soup = BeautifulSoup(raw_bytes, "lxml")
      except Exception:
        soup = BeautifulSoup(raw_bytes, "html.parser")

      # Preservar bloques <pre>; el <code> inline conserva su forma `x`.
      for pre in soup.find_all("pre"):
        code_content = pre.get_text("\n")
        pre.replace_with(f"\n\n```\n{code_content}\n```\n\n")
      for code in soup.find_all("code"):
        if code.find_parent("pre") is None:
          code.replace_with(f" `{code.get_text(' ', strip=True)}` ")

      # No eliminamos <header>: puede contener el título principal.
      for element in soup(["script", "style", "nav", "footer", "aside", "form", "iframe", "noscript", "menu"]):
        element.decompose()

      boilerplate_re = re.compile(
          r"(?:cookie|consent|advertisement|(?:^|[-_])ads?(?:[-_]|$)|popup|modal|sidebar|social[-_]share|newsletter)",
          re.I,
      )
      for attr in ("class", "id"):
        for element in soup.find_all(attrs={attr: boilerplate_re}):
          element.decompose()

      raw_text = soup.get_text("\n")
      content = self._finalize_content(raw_text)
      return {
          **empty, "content": content, "quality": quality_score(content),
          "sha256": content_hash(content) if content else "",
          "normalized_sha256": normalized_content_hash(content) if content else "",
          "status": 200, "bytes": len(raw_bytes),
      }
    except Exception as exc:
      print(f"      [!] Error al raspar {url}: {exc}")
      return {**empty, "status": "error"}
