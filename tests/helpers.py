"""Servidor HTTP local para probar descargas sin red externa."""
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"


def article_text(seed: int = 0, n: int = 30) -> str:
    return "\n".join(
        f"<p>Sección {i}: el procesador {i * 7 + seed} ejecuta instrucciones distintas y coordina {i + 3 + seed} "
        f"unidades internas mientras la caché guarda datos recientes para acelerar el trabajo.</p>"
        for i in range(n)
    )


def page(seed: int = 0, title: str = "Artículo") -> bytes:
    html = (f"<html><head><title>{title}</title></head><body><nav>Inicio Blog Contacto</nav>"
            f"<article><h1>{title}</h1>{article_text(seed)}</article>"
            f"<footer>Copyright 2024 Acme</footer></body></html>")
    return html.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status, body=b"", ctype="text/html; charset=utf-8", length=True):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        if length:
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            try:
                self.wfile.write(body)
            except OSError:  # el cliente cortó la descarga (esperado en las pruebas de límite)
                pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/a", "/b", "/c"):
            self._send(200, page(seed={"/a": 0, "/b": 1000, "/c": 2000}[path], title=f"Página {path[1:]}"))
        elif path == "/dup":  # mismo contenido que /a
            self._send(200, page(0, "Página a"))
        elif path == "/junk":
            self._send(200, ("<html><body>" + "<p>Inicio Blog Tienda Contacto</p>" * 80 + "</body></html>").encode())
        elif path == "/big":  # Content-Length declarado enorme
            self._send(200, b"x" * 3_000_000)
        elif path == "/bigstream":  # sin Content-Length: hay que cortar en streaming
            self._send(200, b"", length=False)
            try:
                for _ in range(60):
                    self.wfile.write(b"y" * 65536)
            except OSError:
                pass
        elif path == "/slow":  # gotea datos: debe vencer el plazo total
            self._send(200, b"", length=False)
            try:
                for _ in range(50):
                    self.wfile.write(b"z" * 10)
                    self.wfile.flush()
                    time.sleep(0.2)
            except OSError:
                pass
        elif path == "/pdf":
            self._send(200, b"%PDF-1.4 fake", ctype="application/pdf")
        else:
            self._send(404, b"nope")


class LocalServer:
    def __enter__(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
