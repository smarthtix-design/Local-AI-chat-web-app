"""Checks that everything this project needs is installed and working.

    python selfcheck.py              full check (includes a short model answer, slow on CPU)
    python selfcheck.py --no-chat    skip the model answer test

Options: --ollama URL  --server URL  --model NAME  --embed NAME
Exit code 0 = no FAIL, 1 = at least one FAIL. Uses only the standard library itself."""
import argparse, importlib, json, os, shutil, sys, time, urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--ollama", default=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
ap.add_argument("--server", default="http://127.0.0.1:8000")
ap.add_argument("--model", default="")
ap.add_argument("--embed", default=os.environ.get("RAG_EMBED_MODEL", "all-minilm"))
ap.add_argument("--no-chat", action="store_true")
a = ap.parse_args()
levels = []


def out(level, name, detail="", hint=""):
    levels.append(level)
    print(f"[{level:4}] {name}" + (f": {detail}" if detail else ""))
    if hint and level != "PASS":
        print(f"         fix: {hint}")


def http(url, body=None, timeout=10):
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(urllib.request.Request(url, data, {"Content-Type": "application/json"}), timeout=timeout) as r:
        return json.load(r)


def meminfo():
    try:
        kv = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo")}
        return kv.get("MemAvailable", 0) // 1024, kv.get("SwapTotal", 0) // 1024
    except OSError:
        return None, None


print(f"Project folder: {BASE}\n")
# 1. Python and packages
ok = sys.version_info >= (3, 10)
out("PASS" if ok else "FAIL", "Python version", sys.version.split()[0], "Python 3.10 or newer is required (the ddgs package needs it)")
if sys.prefix == sys.base_prefix:
    out("WARN", "Virtual environment", "not running inside a venv", "source venv/bin/activate   (then run this again)")
for mod, pipname in (("chromadb", "chromadb"), ("pypdf", "pypdf"), ("docx", "python-docx"), ("openpyxl", "openpyxl"), ("pptx", "python-pptx"), ("ddgs", "ddgs")):
    try:
        importlib.import_module(mod); out("PASS", f"Python package {pipname}")
    except ImportError:
        out("FAIL", f"Python package {pipname}", "not installed", "pip install -r requirements.txt   (inside the venv)")

# 2. Project files
for rel in ("server.py", "index.html", "admin.html", "webtools.py", "retrieval.py", "stats.py"):
    out("PASS" if (BASE / rel).exists() else "FAIL", f"File {rel}", "", f"{rel} must be in {BASE}")
ing = [p for p in (BASE / "rag" / "ingest.py", BASE / "ingest.py") if p.exists()]
out("PASS" if ing else "FAIL", "File ingest.py", str(ing[0].relative_to(BASE)) if ing else "missing", "keep ingest.py in rag/ (server.py imports it)")
docs = [p for p in (BASE / "documents").rglob("*") if p.is_file()] if (BASE / "documents").exists() else []
out("PASS" if docs else "WARN", "Shared documents folder", f"{len(docs)} files", "add files to documents/ then run: python rag/ingest.py")

# 3. Machine resources
mem, swap = meminfo()
if mem is not None:
    out("PASS" if mem >= 1500 else "WARN", "Free RAM", f"{mem} MB available, {swap} MB swap",
        "close other programs, or add swap (see SETUP.md troubleshooting); the chat model needs roughly 1 to 2 GB")
free = shutil.disk_usage(BASE).free // 2**30
out("PASS" if free >= 2 else "WARN", "Free disk space", f"{free} GB", "free some disk space")

# 4. Ollama and models
names = []
try:
    out("PASS", "Ollama is running", "version " + http(a.ollama + "/api/version", timeout=5).get("version", "?"))
    names = [m["name"] for m in http(a.ollama + "/api/tags", timeout=5).get("models", [])]
except Exception as e:
    out("FAIL", "Ollama is running", str(e)[:80], "sudo systemctl start ollama")
if names:
    out("PASS", "Models installed", ", ".join(names))
    chat = a.model or next((m for m in ("qwen2.5:1.5b", "tinyllama:latest", "tinyllama") if m in names), "")
    if not chat:
        out("FAIL", "Chat model", "none found", "ollama pull qwen2.5:1.5b   (or: ollama pull tinyllama)")
    else:
        out("PASS", "Chat model", chat)
        if "qwen2.5:1.5b" not in names:
            out("WARN", "Recommended chat model", "qwen2.5:1.5b not installed (follows documents and web results better)", "ollama pull qwen2.5:1.5b")
    if not any(n.split(":")[0] == a.embed.split(":")[0] for n in names):
        out("FAIL", "Embedding model", f"{a.embed} not installed", f"ollama pull {a.embed}")
    else:
        try:
            vec = http(a.ollama + "/api/embed", {"model": a.embed, "input": "hello"}, 60)["embeddings"][0]
            out("PASS", "Embedding works", f"{len(vec)} numbers per text")
        except Exception as e:
            out("FAIL", "Embedding works", str(e)[:80], "update Ollama: curl -fsSL https://ollama.com/install.sh | sh")
    if chat and not a.no_chat:
        try:
            t0 = time.time()
            r = http(a.ollama + "/api/chat", {"model": chat, "stream": False, "keep_alive": "10m",
                     "messages": [{"role": "user", "content": "Reply with the single word OK."}], "options": {"num_predict": 16}}, 240)
            tps = r["eval_count"] / (r["eval_duration"] / 1e9) if r.get("eval_duration") else 0
            out("PASS" if tps >= 2 else "WARN", "Model answers", f"{time.time() - t0:.1f}s total, {tps:.1f} tokens/s",
                "very slow: use a smaller model or free RAM")
        except Exception as e:
            out("FAIL", "Model answers", str(e)[:80], f"ollama run {chat} \"hi\"   to see the error")

# 5. Vector database
try:
    import chromadb
    if (BASE / "chroma_db").exists():
        client = chromadb.PersistentClient(path=str(BASE / "chroma_db"))
        names = [c if isinstance(c, str) else c.name for c in client.list_collections()]   # differs between Chroma versions
        have = {n: client.get_collection(n).count() for n in names}
        shared, uploads = have.get("local_documents", 0), have.get("visitor_uploads", 0)
        out("PASS" if shared else "WARN", "Vector database", f"{shared} shared chunks, {uploads} visitor chunks", "run: python rag/ingest.py")
    else:
        out("WARN", "Vector database", "chroma_db/ does not exist yet", "run: python rag/ingest.py")
except ImportError:
    pass
except Exception as e:
    out("FAIL", "Vector database", str(e)[:80], "if the server is running, stop it and retry; else delete chroma_db/ and re-run ingest.py")

# 6. Internet search
try:
    from ddgs import DDGS
    res = list(DDGS().text("python programming", max_results=2))
    out("PASS" if res else "WARN", "Internet search (DuckDuckGo)", f"{len(res)} results", "no results: DuckDuckGo may be rate-limiting; try again later")
except ImportError:
    pass
except Exception as e:
    out("WARN", "Internet search (DuckDuckGo)", str(e)[:80], "check the PC's internet connection; set USE_INTERNET = False in server.py if you do not need it")

# 7. Web server
try:
    j = http(a.server + "/api/models", timeout=5)
    out("PASS", "Web server", f"answering at {a.server}, models: {', '.join(j.get('models', []))}")
except Exception as e:
    out("WARN", "Web server", f"not reachable at {a.server}", "start it: python server.py   (or: sudo systemctl status tinychat)")

print(f"\n{levels.count('PASS')} passed, {levels.count('WARN')} warnings, {levels.count('FAIL')} failed")
sys.exit(1 if "FAIL" in levels else 0)
