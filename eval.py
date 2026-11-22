"""Measures how well document search finds the right file. Needs Ollama running (for embeddings).

    python eval.py                 uses evalset.json
    python eval.py --file my.json  each entry: {"q": "question", "expect": "text that must be in the file name"}

Use it after changing MIN_SIMILARITY, the embedding model, or the documents."""
import argparse, importlib.util, json, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent


def run(items, retrieve):
    rows = []
    for it in items:
        try:
            _, sources, best = retrieve(it["q"], None)
        except Exception as e:
            rows.append({"q": it["q"], "ok": False, "best": None, "files": [], "error": str(e)[:80]})
            continue
        files = [s["file"] for s in sources]
        rows.append({"q": it["q"], "ok": any(it["expect"].lower() in f.lower() for f in files), "best": best, "files": files})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(BASE / "evalset.json"))
    a = ap.parse_args()
    spec = importlib.util.spec_from_file_location("srv", BASE / "server.py")
    srv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srv)
    items = json.loads(Path(a.file).read_text())
    rows = run(items, srv.retrieve)
    for r in rows:
        print(("PASS " if r["ok"] else "MISS ") + f"best={r['best']}  {r['q']}" + (f"   ({r['error']})" if r.get("error") else ""))
        if not r["ok"]:
            print("       found:", ", ".join(r["files"]) or "nothing above the threshold")
    hit = sum(r["ok"] for r in rows)
    print(f"\n{hit}/{len(rows)} questions found the expected file (MIN_SIMILARITY={srv.MIN_SIMILARITY}).")
    sys.exit(0 if hit == len(rows) else 1)


if __name__ == "__main__":
    main()
