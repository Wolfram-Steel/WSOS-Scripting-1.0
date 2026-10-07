# buscadores.py
from ddgs import DDGS

from .red import RateLimiter, backoff_delay
import time


class MultiSearchEngine:
  """Motor de búsqueda thread-safe: cada llamada crea su propia sesión DDGS."""

  def __init__(self, region: str = "es-es", safesearch: str = "moderate", rate_limiter=None, stop_event=None):
    """Inicializa el motor de búsqueda con parámetros personalizables."""
    self.region = region
    self.safesearch = safesearch
    self.rate_limiter = rate_limiter or RateLimiter(0.20)
    self.stop_event = stop_event

  def search_engine_ddg_library(self, keyword: str, max_results: int) -> list:
    """Buscador principal: Librería DuckDuckGo (DDGS).

    Cada invocación abre y cierra su propia sesión DDGS, lo que permite
    ejecutar varias búsquedas en paralelo (búsqueda anidada) sin conflictos.
    """
    urls = []
    if not keyword or not keyword.strip():
      return urls

    for attempt in range(1, 4):
      if self.stop_event and self.stop_event.is_set():
        return urls
      if not self.rate_limiter.wait(self.stop_event):
        return urls
      try:
        with DDGS() as ddgs:
          results = ddgs.text(
              keyword.strip(),
              region=self.region,
              safesearch=self.safesearch,
              max_results=max_results,
          )
          if results:
            for r in results:
              link = r.get("href")
              if link and link.startswith(("http://", "https://")):
                urls.append(link)
        return urls
      except Exception as e:
        if attempt >= 3 or (self.stop_event and self.stop_event.is_set()):
          print(f"      [!] Error crítico en DuckDuckGo (DDGS): {e}")
          return urls
        delay = backoff_delay(attempt)
        print(f"      [↻] DDGS: reintento {attempt + 1}/3 en {delay:.2f}s...")
        if self.stop_event and self.stop_event.wait(delay):
          return urls
        time.sleep(0)

    return urls

  def fetch_urls_with_fallbacks(self, keyword: str, max_results: int) -> list:
    """Consulta los motores de búsqueda de forma robusta, depurando duplicados al vuelo."""
    engine_name = "DuckDuckGo (Librería)"
    print(f"  [*] Consultando motor: {engine_name} para: '{keyword}'...")

    all_urls = []
    seen = set()

    try:
      urls = self.search_engine_ddg_library(keyword, max_results)
      added_count = 0

      for u in urls:
        if u not in seen:
          seen.add(u)
          all_urls.append(u)
          added_count += 1

      print(
          f"      [+] {engine_name}: {len(urls)} resultados obtenidos,"
          f" {added_count} únicos añadidos."
      )
    except Exception as e:
      print(f"      [!] Fallo al procesar {engine_name}: {e}")

    print(f"  [+] Total de enlaces únicos acumulados: {len(all_urls)}")
    return all_urls
