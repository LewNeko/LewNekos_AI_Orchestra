import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

LOREM = "The platform was founded in 2014 by Ada Chen. " * 6


def page(title, body, extra=""):
    return f"<html lang='en'><head><title>{title}</title></head><body><nav><a href='/login'>Login</a></nav>{extra}<main>{body}</main><footer>(c) junk</footer></body></html>"


def make_pdf() -> bytes:
    from fpdf import FPDF
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, "Annual report. Revenue grew strongly in 2025."); return bytes(pdf.output())


ROUTES = {
    "/": lambda: page("Home", f"<h1>Home</h1><p>{LOREM}</p><a href='/docs/guide'>Guide</a> <a href='/random/x'>X</a> "
                              "<a href='/login'>Login</a> <a href='/cart'>Cart</a> <a href='/private/secret'>Secret</a> "
                              "<a href='/docs/guide?utm_source=tw'>Guide again</a> <a href='/img.png'>img</a>"),
    "/docs/guide": lambda: page("Guide", f"<h1 id='g'>Guide</h1><p>{LOREM}</p><h2>Pricing</h2><table><tr><th>Year</th><th>Revenue</th></tr><tr><td>2024</td><td>$4.2B</td></tr><tr><td>2025</td><td>$5.1B</td></tr></table>"),
    "/random/x": lambda: page("X", f"<h1>X</h1><p>{LOREM}</p>"),
    "/private/secret": lambda: page("Secret", f"<p>{LOREM}</p>"),
    "/spa": lambda: "<html><head><title>App</title></head><body><div id='root'></div><noscript>Enable JavaScript</noscript><script src='a.js'></script></body></html>",
    "/robots.txt": lambda: "User-agent: *\nDisallow: /private\n",
    "/sitemap.xml": lambda: "<urlset><url><loc>%(base)s/docs/guide</loc></url><url><loc>%(base)s/random/x</loc></url></urlset>",
}


class Handler(BaseHTTPRequestHandler):
    counts: dict = {}

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8", headers=None):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        base = f"http://127.0.0.1:{self.server.server_port}"
        Handler.counts[path] = Handler.counts.get(path, 0) + 1
        if path == "/flaky":
            return self._send(503, "busy") if Handler.counts[path] < 3 else self._send(200, page("Flaky", f"<p>{LOREM}</p>"))
        if path == "/ratelimited":
            return self._send(429, "slow down", headers={"Retry-After": "0"}) if Handler.counts[path] < 2 else self._send(200, page("RL", f"<p>{LOREM}</p>"))
        if path == "/blocked":
            return self._send(403, "forbidden")
        if path == "/missing":
            return self._send(404, "nope")
        if path == "/doc.pdf":
            return self._send(200, make_pdf(), "application/pdf")
        if path == "/data.json":
            return self._send(200, '{"a": 1}', "application/json")
        if path in ROUTES:
            body = ROUTES[path]()
            ctype = "text/plain" if path == "/robots.txt" else "application/xml" if path.endswith(".xml") else "text/html; charset=utf-8"
            return self._send(200, body % {"base": base} if "%(base)s" in body else body, ctype)
        self._send(404, "nope")


@pytest.fixture(scope="session")
def server():
    s = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{s.server_port}"
    s.shutdown()


SPA_HTML = b"""<html><head><title>SPA</title></head><body><div id=root></div><script>
setTimeout(()=>{document.getElementById('root').innerHTML='<main><h1>Client rendered</h1><p>'+'Hydrated by JavaScript. '.repeat(20)+'</p><button id=b onclick="this.textContent=\\'clicked\\'">go</button></main>'},100)
</script></body></html>"""


@pytest.fixture(scope="session")
def spa_server():
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            self.send_response(200); self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(SPA_HTML))); self.end_headers(); self.wfile.write(SPA_HTML)
    s = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}/"
    s.shutdown()
