import random
import threading
import time
from collections import defaultdict
from typing import Optional
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter


class RateLimiter:
    """Limitador temporal cooperativo y seguro entre hilos."""

    def __init__(self, min_interval: float = 0.20):
        self.min_interval = max(0.0, float(min_interval))
        self._lock = threading.Lock()
        self._last_request = 0.0

    def wait(self, stop_event=None) -> bool:
        with self._lock:
            now = time.monotonic()
            delay = max(0.0, self.min_interval - (now - self._last_request))
            if delay and stop_event and stop_event.wait(delay):
                return False
            if delay and not stop_event:
                time.sleep(delay)
            self._last_request = time.monotonic()
            return not (stop_event and stop_event.is_set())


class DomainRateLimiter:
    """Rate limiting independiente por host: paraleliza dominios sin saturar uno solo."""

    def __init__(self, min_interval: float = 0.10):
        self.min_interval = max(0.0, float(min_interval))
        self._limiters = defaultdict(lambda: RateLimiter(self.min_interval))
        self._lock = threading.Lock()

    def wait(self, url: str, stop_event=None) -> bool:
        try:
            host = urlsplit(url).hostname or "_unknown"
        except Exception:
            host = "_unknown"
        with self._lock:
            limiter = self._limiters[host]
        return limiter.wait(stop_event)


_thread_local = threading.local()


def get_thread_session(pool_size: int = 8) -> requests.Session:
    """Una Session persistente por worker, con pooling/keep-alive reutilizable."""
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size, max_retries=0)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        _thread_local.session = session
    return session


def backoff_delay(attempt: int, base: float = 0.5, maximum: float = 4.0) -> float:
    delay = min(maximum, base * (2 ** max(0, attempt - 1)))
    return delay + random.uniform(0.0, min(0.25, delay * 0.25))


def request_with_retry(
    method: str,
    url: str,
    *,
    session: Optional[requests.Session] = None,
    headers=None,
    timeout=10,
    attempts: int = 3,
    rate_limiter=None,
    stop_event=None,
    retry_statuses=(408, 429, 500, 502, 503, 504),
    stream: bool = False,
):
    """Petición HTTP con pooling, rate limit, reintentos y backoff interrumpible."""
    session = session or get_thread_session()
    last_error = None

    for attempt in range(1, attempts + 1):
        if stop_event and stop_event.is_set():
            return None
        if rate_limiter:
            try:
                allowed = rate_limiter.wait(url, stop_event)
            except TypeError:  # compatibilidad con RateLimiter clásico
                allowed = rate_limiter.wait(stop_event)
            if not allowed:
                return None
        try:
            response = session.request(
                method, url, headers=headers, timeout=timeout,
                allow_redirects=True, stream=stream
            )
            if response.status_code not in retry_statuses or attempt >= attempts:
                return response
            response.close()
            last_error = RuntimeError(f"HTTP {response.status_code}")
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= attempts:
                break

        delay = backoff_delay(attempt)
        print(f"      [↻] Reintento {attempt + 1}/{attempts} en {delay:.2f}s: {url}")
        if stop_event and stop_event.wait(delay):
            return None
        if not stop_event:
            time.sleep(delay)

    if last_error:
        raise last_error
    return None
