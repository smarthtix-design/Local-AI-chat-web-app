"""Safe web fetching and page-text extraction. Used to read search results and to 'add a web page'.
Safety: only http/https on ports 80/443, every address must be a public IP (checked before connecting, and the
connection is pinned to the checked IP), redirects are re-checked, size/time are capped."""
import http.client, ipaddress, json, re, socket, ssl, time, urllib.parse, urllib.request
from html.parser import HTMLParser


class BlockedURL(ValueError):
    pass


SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "iframe", "template"}
BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "td", "th", "pre", "div", "section", "article", "br", "blockquote"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [""], 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skip += 1
        elif tag in BLOCK:
            self.out.append("")

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK:
            self.out.append("")

    def handle_data(self, d):
        if not self.skip:
            self.out[-1] += d


def html_to_text(html):
    p = _Text()
    try:
        p.feed(html)
        p.close()
    except Exception:
        pass
    return "\n".join(x for x in (re.sub(r"\s+", " ", t).strip() for t in p.out) if len(x) > 1)


_W = re.compile(r"[a-z0-9]+")


def page_excerpt(text, query, limit=1200):
    """The paragraphs of a page that share the most words with the question, in page order."""
    qs = {w for w in _W.findall(query.lower()) if len(w) > 2}
    paras = [p for p in text.split("\n") if len(p) >= 40]
    ranked = sorted(((len(qs & set(_W.findall(p.lower()))), -i, p) for i, p in enumerate(paras)), reverse=True)
    if ranked and ranked[0][0] > 0:          # keep only paragraphs that share words with the question
        ranked = [r for r in ranked if r[0] > 0]
    keep, total = [], 0
    for _, ni, p in ranked:
        room = limit - total
        if room < 20:
            break
        keep.append((-ni, p[:room]))
        total += min(len(p), room) + 1       # +1 for the joining space
    return " ".join(p for _, p in sorted(keep))


def resolve_public(host, port):
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValueError("Could not find that website.")
    for info in infos:
        a = ipaddress.ip_address(info[4][0].split("%")[0])
        if a.version == 6 and a.ipv4_mapped:
            a = a.ipv4_mapped
        if not a.is_global or a.is_multicast:
            raise BlockedURL("That address is not allowed.")
    return infos[0][4][0]


class _HTTP(http.client.HTTPConnection):
    def __init__(self, host, port, ip, timeout):
        super().__init__(host, port, timeout=timeout)
        self._ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


class _HTTPS(http.client.HTTPSConnection):
    def __init__(self, host, port, ip, timeout):
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self._ip = ip

    def connect(self):
        self.sock = self._context.wrap_socket(socket.create_connection((self._ip, self.port), self.timeout),
                                              server_hostname=self.host)


def safe_fetch(url, timeout=6, max_bytes=500_000, allow_private=False):
    """Returns (final_url, text, content_type). Raises ValueError/BlockedURL with a readable message."""
    deadline = time.time() + timeout
    for _ in range(4):
        u = urllib.parse.urlsplit(url)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise ValueError("Only http and https links are allowed.")
        port = u.port or (443 if u.scheme == "https" else 80)
        if not allow_private and port not in (80, 443):
            raise BlockedURL("That address is not allowed.")
        ip = socket.getaddrinfo(u.hostname, port, type=socket.SOCK_STREAM)[0][4][0] if allow_private \
            else resolve_public(u.hostname, port)
        conn = (_HTTPS if u.scheme == "https" else _HTTP)(u.hostname, port, ip, timeout)
        try:
            conn.request("GET", urllib.parse.urlunsplit(("", "", u.path or "/", u.query, "")),
                         headers={"User-Agent": "Mozilla/5.0 (compatible; TinyChat/1.0)", "Accept": "text/html,text/plain",
                                  "Accept-Encoding": "identity"})
            r = conn.getresponse()
            loc = r.getheader("Location")
            if r.status in (301, 302, 303, 307, 308) and loc:
                url = urllib.parse.urljoin(url, loc)
                continue
            if r.status != 200:
                raise ValueError(f"The page answered with HTTP {r.status}.")
            ctype = (r.getheader("Content-Type") or "").lower()
            if not any(t in ctype for t in ("text/html", "text/plain", "xhtml")):
                raise ValueError("That link is not a web page or text file.")
            body = b""
            while len(body) < max_bytes and time.time() < deadline:
                chunk = r.read(min(16384, max_bytes - len(body)))
                if not chunk:
                    break
                body += chunk
            m = re.search(r"charset=([\w-]+)", ctype)
            try:
                text = body.decode(m.group(1) if m else "utf-8", "replace")
            except LookupError:
                text = body.decode("utf-8", "replace")
            return url, text, ctype
        finally:
            conn.close()
    raise ValueError("Too many redirects.")


def searx_search(base, q, n=4, timeout=8):
    """Backup search engine: your own SearXNG (JSON format must be enabled). Same result shape as ddgs."""
    url = base.rstrip("/") + "/search?" + urllib.parse.urlencode({"q": q, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "TinyChat"}), timeout=timeout) as r:
        data = json.load(r)
    return [{"title": x.get("title", ""), "href": x.get("url", ""), "body": x.get("content", "")} for x in data.get("results", [])[:n]]
