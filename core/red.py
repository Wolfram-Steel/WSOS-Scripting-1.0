import random
import socket
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Union
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter


class RateLimiter:
    """Limitador temporal cooperativo y seguro entre hilos.

    Cada llamada reserva un hueco de tiempo bajo el lock y espera FUERA de él, de modo
    que los hilos no se bloquean entre sí y siguen respetando el intervalo mínimo.
    """

    def __init__(self, min_interval: float = 0.20):
        self.min_interval = max(0.0, float(min_interval))
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def wait(self, stop_event=None) -> bool:
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._next_slot)
            self._next_slot = slot + self.min_interval
            delay = slot - now
        if delay > 0:
            if stop_event:
                if stop_event.wait(delay):
                    return False
            else:
                time.sleep(delay)
        return not (stop_event and stop_event.is_set())


class AdaptiveRateLimiter(RateLimiter):
    """Limitador compartido que aumenta el intervalo ante errores de límite y lo recupera lentamente."""

    def __init__(self, min_interval: float = 1.0, max_interval: float = 8.0):
        super().__init__(min_interval)
        self.base_interval = max(0.0, float(min_interval))
        self.max_interval = max(self.base_interval, float(max_interval))

    def penalize(self, factor: float = 2.0) -> None:
        with self._lock:
            self.min_interval = min(self.max_interval, max(self.base_interval, self.min_interval * factor))

    def recover(self, step: float = 0.10) -> None:
        with self._lock:
            self.min_interval = max(self.base_interval, self.min_interval - max(0.0, step))


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


def _retry_after(response) -> float:
    """Segundos indicados por la cabecera Retry-After (solo formato numérico, máx. 30 s)."""
    value = response.headers.get("Retry-After")
    try:
        return max(0.0, min(30.0, float(value))) if value else 0.0
    except ValueError:
        return 0.0


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
        retry_after = 0.0
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
            retry_after = _retry_after(response)
            response.close()
            last_error = RuntimeError(f"HTTP {response.status_code}")
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= attempts:
                break

        delay = max(backoff_delay(attempt), retry_after)
        print(f"      [↻] Reintento {attempt + 1}/{attempts} en {delay:.2f}s: {url}")
        if stop_event and stop_event.wait(delay):
            return None
        if not stop_event:
            time.sleep(delay)

    if last_error:
        raise last_error
    return None


def _abort_connection(response) -> bool:
    """Cierra el socket subyacente para desbloquear una lectura en curso (mejor esfuerzo)."""
    raw = getattr(response, "raw", None)
    candidates = [
        getattr(getattr(raw, "_connection", None), "sock", None),
        getattr(getattr(getattr(getattr(raw, "_fp", None), "fp", None), "raw", None), "_sock", None),
    ]
    for sock in candidates:
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
                return True
            except OSError:
                continue
    return False


@dataclass
class FetchResult:
    url: str
    status: int = 0
    content: bytes = b""
    headers: Any = field(default_factory=dict)
    reason: str = "ok"  # ok | stopped | timeout | too_large | pdf_skipped | http_<n> | error
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.reason == "ok"


def fetch_bounded(
    url: str,
    *,
    max_bytes: Union[int, Callable[[Any], int]],
    headers=None,
    timeout=(5, 10),
    total_timeout: float = 30.0,
    attempts: int = 3,
    rate_limiter=None,
    stop_event=None,
    session: Optional[requests.Session] = None,
    skip_if: Optional[Callable[[Any], Optional[str]]] = None,
) -> FetchResult:
    """Descarga en streaming con tope de bytes y plazo total.

    Corta la lectura al superar `max_bytes` (o el Content-Length declarado), al agotar
    `total_timeout` o al pedirse la parada; así una página enorme o un servidor que
    gotea datos no bloquea un worker. `skip_if(headers)` puede devolver un motivo para
    abortar antes de leer el cuerpo (p. ej. "pdf_skipped").
    """
    try:
        response = request_with_retry(
            "GET", url, session=session, headers=headers, timeout=timeout,
            attempts=attempts, rate_limiter=rate_limiter, stop_event=stop_event, stream=True,
        )
    except requests.RequestException as exc:
        return FetchResult(url, reason="error", error=str(exc))
    if response is None:
        return FetchResult(url, reason="stopped")

    try:
        status = response.status_code
        if status != 200:
            return FetchResult(url, status=status, headers=response.headers, reason=f"http_{status}")
        if skip_if:
            why = skip_if(response.headers)
            if why:
                return FetchResult(url, status=status, headers=response.headers, reason=why)

        limit = max_bytes(response.headers) if callable(max_bytes) else max_bytes
        declared = response.headers.get("Content-Length", "")
        if declared.isdigit() and int(declared) > limit:
            return FetchResult(url, status=status, headers=response.headers, reason="too_large")

        # Vigilante: una lectura bloqueada por un servidor que gotea datos no vuelve sola,
        # así que se corta la conexión al vencer el plazo o al pedirse la parada.
        deadline = time.monotonic() + total_timeout
        aborted = {"reason": None}
        finished = threading.Event()

        def watchdog():
            while not finished.wait(0.25):
                why = None
                if stop_event and stop_event.is_set():
                    why = "stopped"
                elif time.monotonic() > deadline:
                    why = "timeout"
                if why:
                    aborted["reason"] = why
                    _abort_connection(response)
                    return

        threading.Thread(target=watchdog, daemon=True).start()
        chunks, size = [], 0
        try:
            for chunk in response.iter_content(chunk_size=65536):
                if aborted["reason"]:
                    break
                if stop_event and stop_event.is_set():
                    return FetchResult(url, status=status, headers=response.headers, reason="stopped")
                if time.monotonic() > deadline:
                    return FetchResult(url, status=status, headers=response.headers, reason="timeout")
                if not chunk:
                    continue
                size += len(chunk)
                if size > limit:
                    return FetchResult(url, status=status, headers=response.headers, reason="too_large")
                chunks.append(chunk)
        except (requests.RequestException, OSError, ValueError) as exc:
            if aborted["reason"]:
                return FetchResult(url, status=status, headers=response.headers, reason=aborted["reason"])
            return FetchResult(url, status=status, reason="error", error=str(exc))
        finally:
            finished.set()
        if aborted["reason"]:
            return FetchResult(url, status=status, headers=response.headers, reason=aborted["reason"])
        return FetchResult(url, status=status, content=b"".join(chunks), headers=response.headers)
    except requests.RequestException as exc:
        return FetchResult(url, status=response.status_code, reason="error", error=str(exc))
    finally:
        response.close()
