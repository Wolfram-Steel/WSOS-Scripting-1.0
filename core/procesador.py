# procesador.py
from datetime import datetime
from .dataset import content_hash, quality_score
import html
import os
from pathlib import Path
import re
from bs4 import BeautifulSoup
import requests

from .red import DomainRateLimiter, get_thread_session, request_with_retry


class WebProcessor:
  """Clase encargada de descargar páginas web, limpiar el contenido basura

  respetando bloques de código y filtrando ruido irrelevante.
  """

  def __init__(self, stop_event=None, rate_limiter=None):
    # Cabeceras HTTP estándar para simular un navegador real y evitar bloqueos básicos
    self.stop_event = stop_event
    self.rate_limiter = rate_limiter or DomainRateLimiter(0.20)

    self.headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
            " like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    # Patrones de ruido precompilados globalmente.
    # Al usar re.compile aquí, evitamos recompilar las expresiones regulares
    # línea por línea, lo que acelera drásticamente el rendimiento general.
    raw_noise_patterns = [
        r"ir al contenido",
        r"de wikipedia, la enciclopedia libre",
        r"busca fuentes:",
        r"control de autoridades",
        r"proyectos wikimedia",
        r"enlaces externos",
        r"véase también",
        r"referencias",
        r"navigation",
        r"index",
        r"modules",
        r"theme",
        r"copyright",
        r"last updated on",
        r"created using sphinx",
        r"found a bug",
        r"wikimedia commons alberga",
        r"wikilibros alberga",
        r"asociación de robótica",
        r"instituto de ingenieros eléctricos",
        r"foro de robótica",
        r"multimedia: electronics",
        r"^\d+([ \t]+\d+)+",  # Líneas de números sueltos o referencias numéricas
        r"^[0-9]+\s+[A-Z][a-z]+,",  # Patrones tipo notas bibliográficas
        r"[a-z][A-Z]",  # Detección básica de palabras fusionadas por tablas
    ]
    self.compiled_noise_patterns = [
        re.compile(pattern, re.I) for pattern in raw_noise_patterns
    ]

  def is_noise_line(self, line: str) -> bool:
    """Evalúa si una línea de texto individual es considerada 'ruido'

    (menús, botones, avisos repetitivos o texto irrelevante).
    """
    line_lower = line.lower().strip()

    # Filtro rápido 1: Descartar líneas extremadamente cortas (menos de 3 caracteres)
    # Excepción: si pertenecen a un bloque de código markdown (```).
    if len(line_lower) < 3 and not line_lower.startswith("```"):
      return True

    # Filtro rápido 2: Descartar líneas con pocas palabras (menos de 4 palabras)
    # Esto elimina botones de navegación sueltos o títulos de interfaz.
    words = line_lower.split()
    if len(words) < 4 and not line_lower.startswith("```"):
      return True

    # Comprobación principal: compara la línea contra los patrones de ruido compilados
    for pattern in self.compiled_noise_patterns:
      if pattern.search(line_lower):
        return True

    return False

  def clean_text_preserving_code(self, text: str) -> str:
    """Limpia el texto extraído eliminando espacios extra y ruido,

    pero respetando intactas las líneas que se encuentren dentro de bloques de código.
    """
    if not text:
      return ""

    # Descodifica entidades HTML (&amp;, &quot;, etc.) y elimina caracteres invisibles de espacio
    text = html.unescape(text)
    text = re.sub(r"[\u200b-\u200d\uFEFF]", "", text)

    lines = text.splitlines()
    cleaned_lines = []
    inside_code_block = (
        False  # Interruptor para saber si estamos dentro de un bloque de código
    )

    for line in lines:
      # Detecta el inicio o final de un bloque de código delimitado por triple tilde (```)
      if "```" in line:
        inside_code_block = not inside_code_block
        cleaned_lines.append(line)
        continue

      # Si estamos dentro de un bloque de código, guardamos la línea tal cual sin filtrar ruido
      if inside_code_block:
        cleaned_lines.append(line)
      else:
        # Fuera de bloques de código, normalizamos espacios y aplicamos filtro de ruido
        line_clean = re.sub(r"[ \t]+", " ", line).strip()
        if line_clean and not self.is_noise_line(line_clean):
          cleaned_lines.append(line_clean)

    # Reconstruye el texto final uniendo las líneas limpias y compactando saltos de línea excesivos
    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

  def scrape_url(self, url: str, stop_event=None, allow_pdf=False) -> str:
    """Compatibilidad: devuelve únicamente el texto limpio."""
    return self.scrape_url_details(url, stop_event=stop_event, allow_pdf=allow_pdf).get("content", "")

  def scrape_url_details(self, url: str, stop_event=None, allow_pdf=False) -> dict:
    """Descarga y procesa una URL devolviendo contenido + metadatos de calidad."""
    active_stop = stop_event or self.stop_event
    try:
      if active_stop and active_stop.is_set():
        return {"url": url, "content": "", "quality": 0, "sha256": ""}
      print(f"  [*] Analizando fuente: {url}")
      response = request_with_retry(
          "GET", url, session=get_thread_session(), headers=self.headers, timeout=(5, 10), attempts=3,
          rate_limiter=self.rate_limiter, stop_event=active_stop
      )
      if response is None or response.status_code != 200:
        if response is not None:
          print(f"      [!] Error de acceso (Status: {response.status_code})")
        return {"url": url, "content": "", "quality": 0, "sha256": ""}

      content_type = (response.headers.get("Content-Type") or "").lower()
      is_pdf = url.lower().split("?", 1)[0].endswith(".pdf") or "application/pdf" in content_type
      if is_pdf:
        if not allow_pdf:
          return {"url": url, "content": "", "quality": 0, "sha256": "", "type": "pdf_skipped"}
        if len(response.content) > 15_000_000:
          print("      [!] PDF demasiado grande; descartado para proteger el rendimiento.")
          return {"url": url, "content": "", "quality": 0, "sha256": "", "type": "pdf"}
        try:
          from io import BytesIO
          from pypdf import PdfReader
          reader = PdfReader(BytesIO(response.content))
          pages = []
          for page in reader.pages:
            if active_stop and active_stop.is_set():
              break
            pages.append(page.extract_text() or "")
          content = self.clean_text_preserving_code("\n\n".join(pages))
          return {
              "url": url, "content": content, "quality": quality_score(content),
              "sha256": content_hash(content) if content else "", "status": response.status_code,
              "bytes": len(response.content), "type": "pdf", "pages": len(reader.pages),
          }
        except Exception as exc:
          print(f"      [!] Error leyendo PDF: {exc}")
          return {"url": url, "content": "", "quality": 0, "sha256": "", "type": "pdf"}

      if len(response.content) > 2_000_000:
        print("      [!] Página demasiado grande; descartada para proteger el rendimiento.")
        return {"url": url, "content": "", "quality": 0, "sha256": ""}

      parser = "lxml"
      try:
        soup = BeautifulSoup(response.content, parser)
      except Exception:
        soup = BeautifulSoup(response.text, "html.parser")

      for pre in soup.find_all(["pre", "code"]):
        if pre.name == "code" and pre.find_parent("pre"):
          continue
        code_content = pre.get_text()
        pre.replace_with(f"\n\n```\n{code_content}\n```\n\n")

      for element in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript", "menu"]):
        element.decompose()

      # Boilerplate adicional: banners de cookies, anuncios, popups y barras laterales comunes.
      boilerplate_re = re.compile(r"cookie|consent|advert|ads-|advertisement|banner|popup|modal|sidebar|social-share|newsletter", re.I)
      for element in soup.find_all(attrs={"class": boilerplate_re}):
        element.decompose()
      for element in soup.find_all(attrs={"id": boilerplate_re}):
        element.decompose()

      raw_text = soup.get_text("\n")
      content = self.clean_text_preserving_code(raw_text)
      return {
          "url": url,
          "content": content,
          "quality": quality_score(content),
          "sha256": content_hash(content) if content else "",
          "status": response.status_code,
          "bytes": len(response.content),
      }
    except Exception as e:
      print(f"      [!] Error al raspar {url}: {e}")
      return {"url": url, "content": "", "quality": 0, "sha256": ""}
