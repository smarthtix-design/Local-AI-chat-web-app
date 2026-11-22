"""Server tests with a fake Ollama, fake vector store, fake internet. Nothing real is touched.
Run from the project folder:  python tests/test_backend.py"""
import http.server, importlib.util, io, json, os, sys, tempfile, threading, time, types, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp())
os.environ["STATS_DB"] = str(TMP / "stats.db")
spec = importlib.util.spec_from_file_location("srv", ROOT / "server.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
import stats, webtools
OLLAMA_PORT, APP_PORT = 18434, 18000          # test-only ports, so a running real server is not disturbed
m.OLLAMA = f"http://127.0.0.1:{OLLAMA_PORT}"
ok = fail = skip = 0
def check(name, cond, extra=""):
    global ok, fail
    if cond: ok += 1; print("PASS", name)
    else: fail += 1; print("FAIL", name, extra)

seen = {}; reply = {"t": "ok"}
class O(http.server.BaseHTTPRequestHandler):      # fake Ollama
    def log_message(self, *a): pass
    def do_GET(self):
        b = json.dumps({"version": "0.0"} if "version" in self.path else {"models": [{"name": "qwen2.5:1.5b"}]}).encode(); self.send_response(200); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        seen.clear(); seen.update(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        self.send_response(200); self.end_headers()
        self.wfile.write((json.dumps({"message": {"content": reply["t"]}, "done": False}) + "\n").encode())
        self.wfile.write(b'{"done":true,"eval_count":4,"eval_duration":1000000000,"total_duration":2000000000}\n')
m.H.log_message = lambda self, *a: None
for port, h in ((OLLAMA_PORT, O), (APP_PORT, m.H)):
    threading.Thread(target=http.server.ThreadingHTTPServer(("127.0.0.1", port), h).serve_forever, daemon=True).start()
time.sleep(0.5); m.MIN_GAP = 0; m.WEB_FETCH_PAGES = 0
V, V2 = "a1" * 16, "b2" * 16

# ---------- text helpers ----------
check("casual: greetings skip search", all(m.is_casual(x) for x in ["hi", "Hello!", "thanks", "Thank you.", "good morning", "ok"]))
check("casual: real questions do not", not any(m.is_casual(x) for x in ["hi, how do I enroll iOS in Intune?", "what is autopilot", "thanks for nothing, explain MDM"]))
check("follow-up: pronoun/connector questions use the previous question", "enroll Android" in m.search_query("what about iOS?", "How to enroll Android?") and "Why is that" in m.search_query("Why is that needed?", "What is MDM?"))
check("follow-up: standalone questions unchanged", m.search_query("How do I enroll iOS devices in Intune?", "What is MDM?") == "How do I enroll iOS devices in Intune?" and m.search_query("what about iOS?", "") == "what about iOS?")
check("live: weather/news/price/today detected", all(m.is_live(x) for x in ["what is the weather in Kolkata today?", "latest news on AI", "bitcoin price of", "who won the match", "AZ-305 changes in 2026"]))
check("live: normal questions not flagged", not any(m.is_live(x) for x in ["What is DNS?", "How do I enroll iOS devices in Intune?", "Explain live migration in Azure", "what is a kernel"]))
check("unsure: admissions detected, confident answers not", all(m.looks_unsure(x) for x in ["I'm sorry, but I can't provide real-time weather information.", "I don't have access to live data.", "", "I'm not certain about that."])
      and not any(m.looks_unsure(x) for x in ["DNS translates names to IP addresses.", "Use Autopilot to enroll devices."]))

# ---------- fake vector store ----------
class Col:
    def __init__(s, rows=()): s.rows = {f"c{i}": {"doc": r[0], "meta": r[1], "dist": r[2]} for i, r in enumerate(rows)}
    def count(s): return len(s.rows)
    def _ok(s, meta, w):
        if not w: return True
        if "$and" in w: return all(s._ok(meta, c) for c in w["$and"])
        for k, v in w.items():
            if isinstance(v, dict):
                op, val = next(iter(v.items()))
                if not (meta.get(k, 0) >= val if op == "$gte" else meta.get(k, 0) < val): return False
            elif meta.get(k) != v: return False
        return True
    def _sel(s, where): return [(i, r) for i, r in s.rows.items() if s._ok(r["meta"], where)]
    def get(s, where=None, limit=None, include=None):
        sel = s._sel(where)[:limit] if limit else s._sel(where)
        return {"ids": [i for i, _ in sel], "documents": [r["doc"] for _, r in sel], "metadatas": [r["meta"] for _, r in sel]}
    def query(s, query_embeddings, n_results, include, where=None):
        sel = sorted(s._sel(where), key=lambda x: x[1]["dist"])[:n_results]
        return {"ids": [[i for i, _ in sel]], "documents": [[r["doc"] for _, r in sel]], "metadatas": [[r["meta"] for _, r in sel]], "distances": [[r["dist"] for _, r in sel]]}
    def add(s, ids, documents, embeddings, metadatas): s.rows.update({i: {"doc": d, "meta": mt, "dist": 0.2} for i, d, mt in zip(ids, documents, metadatas)})
    def delete(s, ids=None, where=None):
        for i, _ in (s._sel(where) if where else [(i, 0) for i in ids]): s.rows.pop(i, None)
state = {m.SHARED: Col(), m.UPLOADS: Col()}
m.col = lambda name: state[name]
m.embed = lambda texts: [[0.0] for _ in texts]
real_retrieve = m.retrieve

# ---------- retrieve(): hybrid search ----------
def fresh(shared=(), mine=()): state[m.SHARED], state[m.UPLOADS] = Col(shared), Col(mine); m.kw_cache["shared"] = None
fresh(); ctx, src, best = m.retrieve("q", V); check("empty index -> best None", ctx == "" and best is None)
fresh([("good chunk", {"filename": "a.md", "page": 2}, 0.30), ("bad chunk", {"filename": "b.md", "page": 0}, 0.90)])
ctx, src, best = m.retrieve("q", V)
check("meaning match above threshold used, below ignored", "good chunk" in ctx and "bad chunk" not in ctx and best == 0.7 and src[0]["similarity"] == 0.7, (src, best))
check("context is numbered and asks for [1]-style citations", "[1] a.md, page 2" in ctx and "like [1]" in ctx)
fresh([("The Recommended settings for supervised iPads", {"filename": "Chapter-6/Recommended_iOS_Config.txt", "page": 0}, 0.90), ("printers and scanners", {"filename": "other.md"}, 0.95)])
ctx, src, best = m.retrieve("recommended iOS config", V)
check("keyword match finds a file by name although meaning score is low", "Recommended settings" in ctx and src[0]["kw"] is True and src[0]["similarity"] == 0.1 and best == 0.1, (src, best))
check("keyword search does not fire on weak overlap", m.retrieve("printers wifi password", V)[0] == "")
m.USE_KEYWORD = False; check("USE_KEYWORD False -> meaning search only", m.retrieve("recommended iOS config", V)[0] == ""); m.USE_KEYWORD = True
fresh([("good chunk about autopilot", {"filename": "a.md", "page": 0}, 0.30)]); src = m.retrieve("autopilot", V)[1]
check("found by meaning and keywords -> one source, both flags", len(src) == 1 and src[0]["kw"] and src[0]["similarity"] == 0.7, src)
fresh([("far", {"filename": "b.md", "page": 0}, 0.90)]); ctx, src, best = m.retrieve("q", V); check("below threshold -> empty + best score", ctx == "" and best == 0.1, best)
fresh([], [("my note", {"filename": "n.txt", "page": 0, "owner": V}, 0.2)])
check("own upload found; other visitors cannot see it", (m.retrieve("q", V)[1] or [{}])[0].get("scope") == "mine" and not m.retrieve("q", V2)[1])

# ---------- web_search(): parsing, page reading, backup engine ----------
calls = []; fake = types.ModuleType("ddgs")
class D:
    def text(self, q, max_results=10):
        calls.append(q); return [{"title": "T", "href": "https://www.example.com/x", "body": "b" * 600},
                                 {"title": "bad", "href": "javascript:alert(1)", "body": "x"}, {"title": "n", "body": "no href"}]
fake.DDGS = D; sys.modules["ddgs"] = fake
r1 = m.web_search("Hello World"); m.web_search("hello world ")
check("web: bad urls dropped, text trimmed, cached", len(r1) == 1 and len(r1[0]["text"]) == 400 and len(calls) == 1)
m.WEB_FETCH_PAGES = 2; orig_fetch = webtools.safe_fetch
webtools.safe_fetch = lambda url, **kw: (url, "<p>Kolkata weather today is sunny with a high of 31 degrees and light wind.</p><p>" + "Football " * 20 + "</p>", "text/html")
r = m.web_search("kolkata weather page test"); check("web: top result page is read and the relevant part kept", r[0].get("excerpt", "").startswith("Kolkata weather today"), r)
def failing(url, **kw): raise ValueError("down")
webtools.safe_fetch = failing; r = m.web_search("kolkata weather page fail")
check("web: unreadable page -> snippet still used", len(r) == 1 and r[0]["excerpt"] == "", r); webtools.safe_fetch = orig_fetch; m.WEB_FETCH_PAGES = 0
class Slow:
    def text(self, q, max_results=10): time.sleep(3); return []
fake.DDGS = Slow; m.WEB_TIMEOUT = 1; t0 = time.time()
try: m.web_search("slow query"); check("web: timeout raises", False)
except Exception: check("web: timeout raises quickly", time.time() - t0 < 2.5)
m.WEB_TIMEOUT = 8
class Err:
    def text(self, q, max_results=10): raise RuntimeError("rate limited")
fake.DDGS = Err
sx_srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), type("S", (http.server.BaseHTTPRequestHandler,), {"log_message": lambda *a: None,
        "do_GET": lambda s: (s.send_response(200), s.end_headers(), s.wfile.write(json.dumps({"results": [{"title": "SX", "url": "https://x.org/a", "content": "c"}]}).encode()))}))
threading.Thread(target=sx_srv.serve_forever, daemon=True).start()
try: m.web_search("only duck fails no backup"); check("web: DuckDuckGo error without backup raises", False)
except RuntimeError as e: check("web: DuckDuckGo error without backup raises", "rate limited" in str(e))
m.SEARXNG_URL = f"http://127.0.0.1:{sx_srv.server_port}"; r = m.web_search("duck fails use searx")
check("web: SearXNG backup used when DuckDuckGo fails", r and r[0]["title"] == "SX", r); m.SEARXNG_URL = ""
del sys.modules["ddgs"]
try: m.web_search("no module")
except RuntimeError as e: check("web: missing package message", "pip install ddgs" in str(e))

# ---------- chat flow over HTTP (streamed JSON lines) ----------
def chat(history=None, vid=V, **kw):
    msgs = [{"role": "system", "content": "sys"}] + (history or []) + [{"role": "user", "content": kw.pop("q", "question?")}]
    body = {"model": "qwen2.5:1.5b", "messages": msgs}; body.update(kw)
    req = urllib.request.Request(f"http://127.0.0.1:{APP_PORT}/api/chat", json.dumps(body).encode(), {"X-Visitor-Id": vid})
    with urllib.request.urlopen(req, timeout=15) as r:
        lines = [json.loads(x) for x in r.read().decode().splitlines() if x.strip()]
    return next((x["rag"] for x in lines if "rag" in x), None), [x["status"] for x in lines if "status" in x], lines
suggested = lambda lines: any("suggest_web" in x for x in lines)
LIVEQ = "what is the weather in Kolkata today?"
web_calls, rag_calls = [], []
def fake_web(q): web_calls.append(q); return [{"title": "Site", "url": "https://a.com/p", "text": "web text", "excerpt": "page excerpt text"}]
def rag_hit(q, vid): rag_calls.append(q); return "RAGCTX", [{"file": "a.md", "page": 0, "scope": "shared", "similarity": 0.7, "kw": False}], 0.7
def rag_miss(q, vid): rag_calls.append(q); return "", [], 0.2
m.web_search, m.retrieve = fake_web, rag_hit
h, st, lines = chat(); sp = seen["messages"][0]["content"]
check("1 docs hit -> docs mode, no web call", h["mode"] == "docs" and not web_calls and h["sources"][0]["file"] == "a.md", h)
check("1 context reached model, ctx>=2048", "RAGCTX" in sp and seen["options"]["num_ctx"] >= 2048)
check("1 progress lines in order", st[0] == "Searching your documents..." and st[-1] == "Writing the answer...", st)
check("1 model output still streamed", any(x.get("done") for x in lines) and any(x.get("message") for x in lines))
m.retrieve = rag_miss; web_calls.clear()
h, st, _ = chat(q=LIVEQ); sp = seen["messages"][0]["content"]
check("2 LIVE question goes to the internet directly (with live flag, numbered results, page excerpt)", h["mode"] == "web" and h["live"] is True and h["sources"][0]["url"] == "https://a.com/p"
      and "[1] Site - https://a.com/p" in sp and "Page excerpt: page excerpt text" in sp and "like [1]" in sp and "This needs live information. Searching the internet..." in st, (h, st))
web_calls.clear(); h, st, lines = chat()
check("3 ordinary question, no document match -> model answers alone", h["mode"] == "model" and not web_calls and h["why"] == "no matching document" and h["best"] == 0.2, (h, web_calls))
m.web_search = lambda q: (_ for _ in ()).throw(RuntimeError("x"))
h, _, _ = chat(q=LIVEQ); check("4 live + search fails -> model only, reasons listed", h["mode"] == "model" and "no matching document" in h["why"] and "internet search failed" in h["why"], h)
m.web_search = lambda q: []
h, _, _ = chat(q=LIVEQ); check("5 live + no results -> model only", h["mode"] == "model" and "no web results" in h["why"], h)
m.web_search = fake_web; rag_calls.clear()
h, _, _ = chat(force_web=True); check("6 force_web (button) skips documents and searches", h["mode"] == "web" and h["live"] is False and not rag_calls, h)
h, _, _ = chat(rag=False, web=False); check("7 documents off + internet off -> model only", h["mode"] == "model" and h["why"] == "documents off", h)
m.USE_INTERNET = False
h, _, _ = chat(q=LIVEQ); check("8 internet disabled -> says live data needs internet", h["mode"] == "model" and "needs live data, internet off" in h["why"], h); m.USE_INTERNET = True
m.ALWAYS_WEB_IF_NO_DOCS = True; web_calls.clear()
h, _, _ = chat(); check("9 ALWAYS_WEB_IF_NO_DOCS restores 'no document -> internet'", h["mode"] == "web" and web_calls, h); m.ALWAYS_WEB_IF_NO_DOCS = False
def rag_err(q, vid): raise RuntimeError("chroma down")
m.retrieve = rag_err
h, _, _ = chat(q=LIVEQ); check("10 documents error + live question -> still reaches the internet", h["mode"] == "web", h)
h, _, _ = chat(q=LIVEQ, web=False); check("10 documents error + internet off + live -> reasons", h["mode"] == "model" and h["why"] == "documents unavailable, needs live data, internet off", h)
m.retrieve = rag_hit; rag_calls.clear(); web_calls.clear()
h, st, _ = chat(q="thanks"); check("11 greeting skips documents and internet", h["mode"] == "model" and h["why"] == "casual message" and not rag_calls and not web_calls and st == ["Writing the answer..."], (h, st))
h, st, _ = chat(history=[{"role": "user", "content": "How to enroll Android?"}, {"role": "assistant", "content": "x"}], q="what about iOS?")
check("12 follow-up is searched with the previous question", rag_calls[-1].startswith("How to enroll Android?") and "iOS" in rag_calls[-1] and "enroll Android" in h["query"], (rag_calls, h))
m.retrieve = rag_miss
reply["t"] = "I'm sorry, but I can't provide real-time information."
h, _, lines = chat(q="tell me about the Kolkata metro extension"); check("13 unsure model-only answer -> suggest_web line", h["mode"] == "model" and suggested(lines), lines)
reply["t"] = "The Kolkata metro opened in 1984."
_, _, lines = chat(q="tell me about the Kolkata metro"); check("14 confident answer -> no suggestion", not suggested(lines))
reply["t"] = "I don't know."
_, _, lines = chat(q="thanks"); check("15 casual message never suggests", not suggested(lines))
_, _, lines = chat(q=LIVEQ, force_web=True); check("15 internet answers never suggest", not suggested(lines))
m.USE_INTERNET = False; _, _, lines = chat(q="tell me about metro"); check("15 no suggestion when the internet is disabled", not suggested(lines)); m.USE_INTERNET = True
reply["t"] = "ok"

# ---------- queue ----------
m.QUEUE_WAIT = 10; m.gen_lock.acquire(); out = {}
t = threading.Thread(target=lambda: out.update(zip(("h", "st", "lines"), chat()))); t.start()
time.sleep(3.2); m.gen_lock.release(); t.join(15)
check("16 queued visitor sees 'Waiting for your turn' then the answer", any(s.startswith("Waiting for your turn") for s in out.get("st", [])) and any(x.get("done") for x in out.get("lines", [])), out.get("st"))
m.QUEUE_WAIT = 1; m.gen_lock.acquire(); _, st, lines = chat(); m.gen_lock.release()
check("17 queue timeout -> busy error line; waiting counter back to zero", any("busy" in x.get("error", "") for x in lines) and m.qs["waiting"] == 0, lines)
m.QUEUE_WAIT = 90

# ---------- usage statistics ----------
sm = stats.summary(); modes = {x["mode"] for x in sm["by_mode"]}
check("18 every answer is counted by source (no question text stored)", sm["total"] >= 15 and {"docs", "web", "model", "casual"} <= modes and sm["errors"] >= 1, sm)

# ---------- http helpers ----------
def call(method, path, vid=V, body=None, headers=None, raw=False):
    h = {"X-Visitor-Id": vid} if vid else {}; h.update(headers or {})
    req = urllib.request.Request(f"http://127.0.0.1:{APP_PORT}{path}", body, h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r: d = r.read(); return r.status, (d.decode() if raw else json.loads(d))
    except urllib.error.HTTPError as e:
        d = e.read(); return e.code, (d.decode() if raw else json.loads(d))
jb = lambda o: json.dumps(o).encode()

# ---------- feedback, suggestions, health, ping ----------
c1, _ = call("POST", "/api/feedback", body=jb({"vote": 1, "mode": "docs", "best": .6, "model": "x"})); call("POST", "/api/feedback", body=jb({"vote": -1, "mode": "evil"}))
fb = stats.summary()["feedback"]
check("19 feedback stored by source; unknown source normalised; oversize rejected", c1 == 200 and {(f["mode"], f["vote"]) for f in fb} >= {("docs", 1), ("model", -1)} and call("POST", "/api/feedback", body=b"x" * 3000)[0] == 413, fb)
fresh([("t", {"filename": "Chapter-6/Recommended_iOS_Config.txt"}, .3), ("t", {"filename": "README.md"}, .3), ("t", {"filename": "PUT_DOCUMENTS_HERE.txt"}, .3)]); m.sug["t"] = 0
q = call("GET", "/api/suggestions")[1]["questions"]; check("20 starter questions come from file names (README skipped)", q == ["What does Recommended iOS Config cover?"], q)
check("21 /health reports server and Ollama", call("GET", "/health", vid=None)[1] == {"ok": True, "ollama": True})
check("22 live visitors counted per browser", call("POST", "/api/ping")[1]["online"] >= 1 and call("POST", "/api/ping", vid=V2)[1]["online"] >= 2)

# ---------- uploads (all file types) ----------
fresh(); up = lambda name, data, vid=V: call("POST", "/api/upload?name=" + urllib.request.quote(name), vid=vid, body=data)
check("23 upload csv and html", up("devices.csv", b"device,os\niPad,iOS 17\n") [1].get("chunks") == 1 and up("page.html", b"<p>HTML page about Conditional Access policies and rules for sign in.</p>")[1].get("chunks") == 1)
try:
    from openpyxl import Workbook; from pptx import Presentation; from docx import Document
    b = io.BytesIO(); wb = Workbook(); wb.active.append(["a", "b"]); wb.save(b); x = up("sheet.xlsx", b.getvalue(), V2)
    b = io.BytesIO(); pr = Presentation(); s = pr.slides.add_slide(pr.slide_layouts[1]); s.shapes.title.text = "Slide"; pr.save(b); p = up("deck.pptx", b.getvalue(), V2)
    b = io.BytesIO(); dd = Document(); dd.add_paragraph("Hello"); dd.save(b); w = up("doc.docx", b.getvalue(), V2)
    check("24 upload xlsx, pptx, docx", x[1].get("chunks") == 1 and p[1].get("chunks") == 1 and w[1].get("chunks") == 1, (x, p, w))
except ImportError: skip += 1; print("SKIP 24 (office libraries not installed here)")
check("25 same name replaces the old file; delete removes it", up("devices.csv", b"device,os\nPixel,Android\n")[1].get("chunks") == 1 and [f["name"] for f in call("GET", "/api/files")[1]["mine"]].count("devices.csv") == 1
      and call("DELETE", "/api/files?name=devices.csv")[0] == 200 and "devices.csv" not in [f["name"] for f in call("GET", "/api/files")[1]["mine"]])
check("26 bad type, empty file, corrupt Office file rejected", up("a.exe", b"x")[0] == 400 and up("e.txt", b"")[0] == 413 and up("broken.docx", b"not a zip")[0] == 400)
for i in range(m.MAX_FILES): up(f"f{i}.txt", b"some text %d" % i, "c3" * 16)
check("27 file limit per visitor", "limit" in up("one-too-many.txt", b"x y z", "c3" * 16)[1].get("error", "").lower())

# ---------- add a web page ----------
page = "<p>Autopilot lets you pre provision Windows devices for zero touch deployment in your organisation.</p>"
ps = http.server.ThreadingHTTPServer(("127.0.0.1", 0), type("P", (http.server.BaseHTTPRequestHandler,), {"log_message": lambda *a: None,
        "do_GET": lambda s: (s.send_response(200), s.send_header("Content-Type", "text/html"), s.end_headers(), s.wfile.write(page.encode()))}))
threading.Thread(target=ps.serve_forever, daemon=True).start(); purl = f"http://127.0.0.1:{ps.server_port}/guide"
addurl = lambda u, vid=V: call("POST", "/api/addurl", vid=vid, body=jb({"url": u}))
m.uploads_today.clear()
blocked = [addurl(x)[1].get("error", "") for x in (purl, "http://localhost/", "http://169.254.169.254/latest/meta-data/", "http://[::1]/", "http://10.0.0.1/", "ftp://example.com/x", "file:///etc/passwd")]
check("28 add-a-page refuses internal addresses and odd schemes (SSRF)", all(blocked) and blocked[0] == "That address is not allowed." and "http" in blocked[5].lower(), blocked)
m.ALLOW_PRIVATE_FETCH = True; r = addurl(purl, V2); m.ALLOW_PRIVATE_FETCH = False
check("29 web page added as a searchable file", r[0] == 200 and r[1]["name"] == f"web: 127.0.0.1/guide" and r[1]["chunks"] == 1, r)
check("30 added page is listed", "web: 127.0.0.1/guide" in [f["name"] for f in call("GET", "/api/files", vid=V2)[1]["mine"]])
m.UPLOADS_PER_DAY = 0; check("30 daily upload/add-page limit per IP", addurl(purl)[0] == 429 and up("late.txt", b"abc def")[0] == 429); m.UPLOADS_PER_DAY = 20

# ---------- owner tools: only on this PC ----------
code, html = call("GET", "/admin", vid=None, raw=True); check("31 admin page opens on this PC", code == 200 and "Tiny Chat admin" in html)
CF = {"CF-Connecting-IP": "1.2.3.4"}; EVIL = {"Host": "evil.trycloudflare.com"}; AD = {"X-Admin": "1"}
check("32 admin hidden behind the public link (tunnel headers or foreign Host header)", all(call("GET", p, vid=None, headers=h)[0] == 404 for p in ("/admin", "/api/admin/stats") for h in (CF, EVIL, {"X-Forwarded-For": "1.1.1.1"})))
check("33 admin actions need the X-Admin header and a local request", call("POST", "/api/admin/internet", vid=None, body=jb({"on": False}))[0] == 404 and call("POST", "/api/admin/internet", vid=None, body=jb({"on": False}), headers={**AD, **CF})[0] == 404 and m.USE_INTERNET is True)
s = call("GET", "/api/admin/stats", vid=None)[1]; check("34 admin stats", {"stats", "online", "internet", "reindex"} <= set(s) and s["stats"]["total"] > 0 and s["upload_chunks"] > 0, s)
check("35 admin can switch the internet off and on", call("POST", "/api/admin/internet", vid=None, body=jb({"on": False}), headers=AD)[1]["internet"] is False and m.USE_INTERNET is False
      and call("POST", "/api/admin/internet", vid=None, body=jb({"on": True}), headers=AD)[1]["internet"] is True)
m.index_folder = lambda col_, docs, log, **kw: {"indexed": 2, "unchanged": 5, "skipped": 0, "errors": 0, "removed": 0}; m.kw_cache["shared"] = object()
check("36 admin re-index runs and refreshes the keyword index", call("POST", "/api/admin/reindex", vid=None, headers=AD)[1]["started"] is True)
for _ in range(40):
    if not m.rs["running"] and "2 indexed" in m.rs["msg"]: break
    time.sleep(0.1)
check("36 re-index result recorded", "2 indexed" in m.rs["msg"] and m.kw_cache["shared"] is None, m.rs)
m.rs["running"] = True; check("36 second re-index refused while one is running", call("POST", "/api/admin/reindex", vid=None, headers=AD)[1]["started"] is False); m.rs["running"] = False
n = state[m.UPLOADS].count(); r = call("POST", "/api/admin/clear-uploads", vid=None, headers=AD)[1]
check("38 admin can delete all visitor uploads", r["removed_chunks"] == n and n > 0 and state[m.UPLOADS].count() == 0, (r, n))
m.retrieve = real_retrieve; fresh([("autopilot zero touch", {"filename": "a.md", "page": 0}, .3)])
d = call("POST", "/api/admin/debug", vid=None, body=jb({"question": "autopilot"}), headers=AD)[1]
check("37 debug panel shows route, scores and the text the model would get", d["route"] == "documents" and d["sources"][0]["similarity"] == 0.7 and "[1] a.md" in d["context"], d)
fresh()
check("37 debug routes: live -> internet, casual -> model", call("POST", "/api/admin/debug", vid=None, body=jb({"question": LIVEQ}), headers=AD)[1]["route"] == "internet (live data)"
      and call("POST", "/api/admin/debug", vid=None, body=jb({"question": "thanks"}), headers=AD)[1]["route"].startswith("model only"))
m.UPLOADS_PER_DAY = 1000; m.uploads_today.clear(); fresh()
codes = [up("rapid.txt", b"quick upload number %d" % i, "d4" * 16)[0] for i in range(40)]; m.UPLOADS_PER_DAY = 20
check("38b 40 back-to-back uploads are never answered 'busy' (lock released before replying)", codes == [200] * 40, set(codes))
check("39 only index.html and admin.html are served (no source leak)", call("GET", "/server.py", vid=None)[0] == 404 and call("GET", "/stats.db", vid=None)[0] == 404)
check("40 no access code anywhere", "X-Access-Code" not in (ROOT / "server.py").read_text() and "access_code" not in (ROOT / "server.py").read_text())
print(f"\n{ok} passed, {fail} failed" + (f", {skip} skipped" if skip else "")); sys.exit(1 if fail else 0)
