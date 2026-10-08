"""Descarga y limpieza de páginas web (HTML y PDF) preservando bloques de código."""
import io
import re

from bs4 import BeautifulSoup, NavigableString

from .dataset import content_hash, quality_score
from .red import DomainRateLimiter, fetch_bounded, get_thread_session

HTML_LIMIT = 2_000_000
PDF_LIMIT = 15_000_000
TOTAL_TIMEOUT = 30.0

BLOCK_TAGS = [
    "address", "article", "aside", "blockquote", "caption", "details", "dd", "div", "dl", "dt",
    "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6",
    "header", "hr", "li", "main", "nav", "ol", "p", "section", "summary", "table", "tbody",
    "thead", "tfoot", "tr", "ul",
]
REMOVE_TAGS = [
    "script", "style", "footer", "iframe", "noscript", "menu",
    "svg", "template", "button", "select", "textarea",
]
PROTECTED_TAGS = {"html", "body", "main", "article"}

# Coincide con "ad", "ads", "cookie-banner", "sidebar", etc. como palabras de class/id,
# no como parte de otra (así "threads-list" no se confunde con "ads").
BOILERPLATE_RE = re.compile(
    r"(?:^|[\s_-])(?:cookies?|consent|advert(?:isement)?|ads?|adsbygoogle|banner|popup|modal|"
    r"sidebar|social-share|newsletter)(?:$|[\s_-])",
    re.I,
)
HIDDEN_STYLE_RE = re.compile(r"display\s*:\s*none", re.I)
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")

# Frases lo bastante específicas como para buscarlas en cualquier parte de la línea
NOISE_PHRASES = (
    "ir al contenido", "de wikipedia, la enciclopedia libre", "busca fuentes:",
    "control de autoridades", "proyectos wikimedia", "last updated on", "created using sphinx",
    "found a bug", "wikimedia commons alberga", "wikilibros alberga", "asociación de robótica",
    "instituto de ingenieros eléctricos", "foro de robótica", "multimedia: electronics",
)
# Palabras genéricas: solo son ruido si ocupan la línea ENTERA (menús, cabeceras de sección)
GENERIC_NOISE_RE = re.compile(
    r"^(?:navigation|index|modules|theme|table of contents|contenidos?|men[uú]|referencias|"
    r"enlaces externos|v[eé]ase tambi[eé]n|references|external links|see also)"
    r"\s*(?:\[[^\]]*\])?\s*:?\s*$",
    re.I,
)
COPYRIGHT_RE = re.compile(r"^\s*(?:copyright\b|©|\(c\)\s*\d)", re.I)
NUMERIC_REF_RE = re.compile(r"^\d+(?:[ \t]+\d+)+")
BIBLIO_RE = re.compile(r"^\[?\d+\]?\.?\s+[A-ZÁÉÍÓÚÑ][\w'’-]+,\s+[A-Z]\.")


class WebProcessor:
    """Descarga páginas web, elimina el contenido basura y conserva el código."""

    def __init__(self, stop_event=None, rate_limiter=None, *, retries: int = 3,
                 max_chars: int = 2_000_000):
        self.stop_event = stop_event
        self.rate_limiter = rate_limiter or DomainRateLimiter(0.20)
        self.retries = max(1, int(retries))
        self.max_chars = max(1_000, int(max_chars))
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
                " like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }

    # ------------------------------------------------------------------ filtrado de texto
    def is_noise_line(self, line: str) -> bool:
        stripped = line.strip()
        low = stripped.lower()
        if low.startswith("```"):
            return False
        body = stripped.lstrip("#- ").strip()
        # No descartamos líneas cortas por longitud: al llegar aquí ya hemos filtrado
        # el DOM. Esto conserva fórmulas, identificadores, estados HTTP y títulos breves.
        if len(stripped) < 2:
            return True
        if any(phrase in low for phrase in NOISE_PHRASES):
            return True
        if GENERIC_NOISE_RE.match(body) or COPYRIGHT_RE.match(low):
            return True
        return bool(NUMERIC_REF_RE.match(stripped) or BIBLIO_RE.match(stripped))

    def clean_text_preserving_code(self, text: str) -> str:
        if not text:
            return ""
        text = ZERO_WIDTH_RE.sub("", text)
        out, inside_code = [], False
        for line in text.splitlines():
            fences = line.count("```")
            if fences:
                if fences % 2:
                    inside_code = not inside_code
                out.append(line.rstrip())
                continue
            if inside_code:
                out.append(line.rstrip())
                continue
            clean = re.sub(r"[ \t]+", " ", line).strip()
            if not clean:
                continue
            if not self.is_noise_line(clean):
                out.append(clean)
        return "\n".join(out).strip()

    # ------------------------------------------------------------------ HTML -> texto
    @staticmethod
    def _gone(element) -> bool:
        return getattr(element, "decomposed", False)

    @staticmethod
    def _link_density(element) -> float:
        text = element.get_text(" ", strip=True)
        if not text:
            return 0.0
        links = element.find_all("a")
        link_text = " ".join(a.get_text(" ", strip=True) for a in links)
        return min(1.0, len(link_text) / max(1, len(text)))

    def _remove_structural_noise(self, soup) -> None:
        """Filtra navegación/boilerplate usando estructura DOM antes de aplanar el texto."""
        for tag in soup.find_all(["nav", "aside", "form"]):
            density = self._link_density(tag)
            text_len = len(tag.get_text(" ", strip=True))
            # Un bloque claramente navegacional se elimina; un form con texto útil
            # (p. ej. documentación WebForms) se conserva.
            if tag.name == "nav" and (density >= 0.15 or (text_len < 200 and not tag.find(["p", "article", "main", "section"]))):
                tag.decompose()
            elif tag.name == "aside" and density >= 0.45:
                tag.decompose()
            elif tag.name == "form" and density >= 0.60 and not tag.find(["p", "article", "main", "section"]):
                tag.decompose()

        headings = soup.find_all([f"h{i}" for i in range(1, 7)])
        for heading in headings:
            text = heading.get_text(" ", strip=True).lower()
            if not re.match(r"^(?:referencias|enlaces externos|véase también|notas(?: y referencias)?|bibliografía|references|external links|see also|further reading|notes|footnotes)$", text):
                continue
            section_nodes = []
            level = int(heading.name[1])
            for sibling in heading.next_siblings:
                if getattr(sibling, "name", "") and re.fullmatch(r"h[1-6]", sibling.name):
                    if int(sibling.name[1]) <= level:
                        break
                section_nodes.append(sibling)
            text_len = sum(len(getattr(n, "get_text", lambda *a, **k: str(n))(" ", strip=True)) for n in section_nodes)
            link_len = sum(len(a.get_text(" ", strip=True)) for n in section_nodes if hasattr(n, "find_all") for a in n.find_all("a"))
            if text_len >= 120 and link_len / max(1, text_len) >= 0.45:
                for node in section_nodes:
                    if getattr(node, "decompose", None):
                        node.decompose()
                heading.decompose()

    def html_to_text(self, soup):
        """Devuelve (título, texto) respetando párrafos, títulos, listas, tablas y código."""
        title = ""
        if soup.title and soup.title.string:
            title = " ".join(soup.title.string.split())

        self._remove_structural_noise(soup)
        for element in soup(REMOVE_TAGS):
            if not self._gone(element):
                element.decompose()
        hidden = soup.find_all(attrs={"hidden": True}) + soup.find_all(attrs={"aria-hidden": "true"})
        hidden += soup.find_all(style=HIDDEN_STYLE_RE)
        for element in hidden:
            if not self._gone(element) and element.name not in PROTECTED_TAGS:
                element.decompose()
        for header in soup.find_all("header"):  # una cabecera con título es contenido
            if not self._gone(header) and not header.find(["h1", "h2"]):
                header.decompose()

        victims = []
        for element in soup.find_all(True):
            if element.name in PROTECTED_TAGS or not element.attrs:
                continue
            classes = element.attrs.get("class") or ""
            class_text = " ".join(classes) if isinstance(classes, list) else str(classes)
            if BOILERPLATE_RE.search(class_text) or BOILERPLATE_RE.search(str(element.attrs.get("id") or "")):
                victims.append(element)
        for element in victims:
            if not self._gone(element):
                element.decompose()

        # Código: <pre> -> bloque con marcador; <code> en línea -> `texto`
        codes = []
        for pre in soup.find_all("pre"):
            if self._gone(pre):
                continue
            token = f"\x00CODE{len(codes)}\x00"
            codes.append(pre.get_text().strip("\n"))
            pre.replace_with(NavigableString(f"\n{token}\n"))
        for code in soup.find_all("code"):
            text = " ".join(code.get_text().split())
            code.replace_with(NavigableString(f"`{text}`" if text else ""))

        # Estructura tipo Markdown
        for level in range(1, 7):
            for heading in soup.find_all(f"h{level}"):
                heading.insert(0, NavigableString("#" * level + " "))
        for item in soup.find_all("li"):
            item.insert(0, NavigableString("- "))
        for cell in soup.find_all(["td", "th"]):
            cell.append(NavigableString(" | "))

        # Espacios en blanco del código fuente HTML -> un solo espacio
        for string in soup.find_all(string=True):
            if type(string) is NavigableString:
                string.replace_with(NavigableString(re.sub(r"\s+", " ", str(string))))

        for br in soup.find_all("br"):
            br.replace_with(NavigableString("\n"))
        for block in soup.find_all(BLOCK_TAGS):
            block.insert_before(NavigableString("\n"))
            block.insert_after(NavigableString("\n"))

        raw = soup.get_text()
        raw = re.sub(r"[ \t]*\|[ \t]*(?=\n|$)", "", raw)  # barra final de las filas de tabla
        for index, code in enumerate(codes):
            raw = raw.replace(f"\x00CODE{index}\x00", f"\n```\n{code}\n```\n")
        return title, raw

    # ------------------------------------------------------------------ descarga
    @staticmethod
    def _is_pdf(url: str, content_type: str) -> bool:
        return "application/pdf" in content_type or url.lower().split("?")[0].endswith(".pdf")

    def scrape_url(self, url: str, stop_event=None, allow_pdf: bool = False) -> str:
        return self.scrape_url_details(url, stop_event=stop_event, allow_pdf=allow_pdf)["content"]

    def _result(self, url, content="", reason="ok", **extra):
        truncated = False
        if len(content) > self.max_chars:
            cut = content.rfind("\n", 0, self.max_chars)
            content = content[: cut if cut > self.max_chars * 0.5 else self.max_chars].rstrip()
            truncated = True
        return {
            "url": url, "content": content, "reason": reason, "truncated": truncated,
            "quality": quality_score(content) if content else 0,
            "sha256": content_hash(content) if content else "",
            **extra,
        }

    def scrape_url_details(self, url: str, stop_event=None, allow_pdf: bool = False) -> dict:
        active_stop = stop_event or self.stop_event
        if active_stop and active_stop.is_set():
            return self._result(url, reason="stopped")
        print(f"  [*] Analizando fuente: {url}")

        def skip_if(headers):
            ctype = (headers.get("Content-Type") or "").lower()
            return "pdf_skipped" if self._is_pdf(url, ctype) and not allow_pdf else None

        def limit_for(headers):
            ctype = (headers.get("Content-Type") or "").lower()
            return PDF_LIMIT if self._is_pdf(url, ctype) else HTML_LIMIT

        fetched = fetch_bounded(
            url, max_bytes=limit_for, headers=self.headers, attempts=self.retries,
            total_timeout=TOTAL_TIMEOUT, rate_limiter=self.rate_limiter,
            stop_event=active_stop, session=get_thread_session(), skip_if=skip_if,
        )
        if not fetched.ok:
            if fetched.reason.startswith("http_"):
                print(f"      [!] Error de acceso (Status: {fetched.status})")
            elif fetched.reason == "too_large":
                print("      [!] Contenido demasiado grande, omitido.")
            elif fetched.reason in ("timeout", "error"):
                print(f"      [!] No se pudo descargar ({fetched.error or fetched.reason}).")
            return self._result(url, reason=fetched.reason, status=fetched.status)

        ctype = (fetched.headers.get("Content-Type") or "").lower()
        try:
            if self._is_pdf(url, ctype):
                return self._process_pdf(url, fetched)
            return self._process_html(url, fetched, ctype)
        except Exception as exc:  # noqa: BLE001
            print(f"      [!] Error procesando contenido: {exc}")
            return self._result(url, reason="error", status=fetched.status)

    def _process_html(self, url, fetched, content_type):
        match = re.search(r"charset=([\w.-]+)", content_type)
        encoding = match.group(1) if match else None
        try:
            soup = BeautifulSoup(fetched.content, "lxml", from_encoding=encoding)
        except Exception:  # lxml ausente o fallo de parseo
            soup = BeautifulSoup(fetched.content, "html.parser", from_encoding=encoding)
        title, raw = self.html_to_text(soup)
        return self._result(url, self.clean_text_preserving_code(raw), title=title, status=fetched.status, bytes=len(fetched.content))

    def _process_pdf(self, url, fetched):
        try:
            from pypdf import PdfReader
        except ImportError:
            print("      [!] Falta 'pypdf' para leer PDFs.")
            return self._result(url, reason="error", status=fetched.status)
        reader = PdfReader(io.BytesIO(fetched.content))
        pages = []
        for page in reader.pages:
            if self.stop_event and self.stop_event.is_set():
                return self._result(url, reason="stopped")
            pages.append(page.extract_text() or "")
        return self._result(url, self.clean_text_preserving_code("\n".join(pages)),
                            status=fetched.status, bytes=len(fetched.content))
