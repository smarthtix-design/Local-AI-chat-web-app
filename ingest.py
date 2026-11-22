"""Folder indexer for PDF, DOCX, XLSX, PPTX, CSV, HTML, TXT and Markdown files.
Run:  python rag/ingest.py       (the server also runs it automatically when documents/ changes)"""
import csv, hashlib, json, os, sys
from pathlib import Path
import urllib.request

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
from webtools import html_to_text   # noqa: E402

DOCS = BASE / "documents"
DB = BASE / "chroma_db"
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
EMBED_MODEL = os.environ.get("RAG_EMBED_MODEL", "all-minilm")
SUPPORTED = {".pdf", ".docx", ".xlsx", ".pptx", ".csv", ".html", ".htm", ".txt", ".md"}
CHUNK_SIZE, OVERLAP = 600, 100


def extract(path):
    """Returns [(page_or_None, text)]."""
    s = path.suffix.lower()
    if s == ".pdf":
        from pypdf import PdfReader
        return [(i + 1, p.extract_text() or "") for i, p in enumerate(PdfReader(str(path)).pages)]
    if s == ".docx":
        from docx import Document
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        for t in doc.tables:
            text += "\n" + "\n".join(" | ".join(c.text for c in r.cells) for r in t.rows)
        return [(None, text)]
    if s == ".xlsx":
        from openpyxl import load_workbook
        wb = load_workbook(str(path), read_only=True, data_only=True)
        return [(None, f"Sheet: {ws.title}\n" + "\n".join(r for r in (" | ".join(str(c) for c in row if c is not None)
                for row in ws.iter_rows(values_only=True)) if r.strip())) for ws in wb.worksheets]
    if s == ".pptx":
        from pptx import Presentation
        out = []
        for n, slide in enumerate(Presentation(str(path)).slides, 1):
            parts = []
            for sh in slide.shapes:
                if sh.has_text_frame:
                    parts.append(sh.text_frame.text)
                if getattr(sh, "has_table", False) and sh.has_table:
                    parts += [" | ".join(c.text for c in r.cells) for r in sh.table.rows]
            out.append((n, "\n".join(parts)))
        return out
    if s == ".csv":
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            return [(None, "\n".join(" | ".join(r) for _, r in zip(range(5000), csv.reader(f))))]
    text = path.read_text(encoding="utf-8", errors="replace")
    return [(None, html_to_text(text) if s in (".html", ".htm") else text)]


def chunks(text):
    text = " ".join(text.split())
    if not text:
        return []
    out, start = [], 0
    while start < len(text):
        end = min(len(text), start + CHUNK_SIZE)
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        if end >= len(text):
            break
        start = max(start + 1, end - OVERLAP)
    return out


def embed(texts):
    body = json.dumps({"model": EMBED_MODEL, "input": texts}).encode()
    req = urllib.request.Request(OLLAMA + "/api/embed", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        vectors = json.load(r).get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise RuntimeError("Unexpected Ollama embedding response.")
    return vectors


def folder_signature(docs=DOCS):
    """Changes whenever a file in documents/ is added, edited or removed."""
    if not docs.exists():
        return ()
    return tuple(sorted((str(p.relative_to(docs)), p.stat().st_size, p.stat().st_mtime_ns)
                        for p in docs.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED))


def index_folder(col, docs=DOCS, log=print, embed_fn=None):
    """Brings the collection in line with the folder. Unchanged files are skipped (by hash). Returns counts."""
    embed_fn = embed_fn or embed
    docs.mkdir(exist_ok=True)
    files = sorted(p for p in docs.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED)
    rels = {str(p.relative_to(docs)) for p in files}
    n = {"indexed": 0, "unchanged": 0, "skipped": 0, "errors": 0, "removed": 0}
    log(f"Scanning {docs} ({len(files)} supported files)")
    for path in files:
        rel = str(path.relative_to(docs))
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            existing = col.get(where={"filename": rel}, include=["metadatas"])
            old = existing.get("metadatas") or []
            if old and all(m.get("file_hash") == digest for m in old):
                n["unchanged"] += 1
                log(f"UNCHANGED: {rel}")
                continue
            fid = hashlib.sha256(rel.encode()).hexdigest()[:16]
            ids, texts, metas = [], [], []
            for page, text in extract(path):
                for i, piece in enumerate(chunks(text)):
                    ids.append(f"{fid}-{page or 0}-{i}")
                    texts.append(piece)
                    metas.append({"filename": rel, "page": page or 0, "chunk": i, "file_hash": digest})
            if not ids:
                n["skipped"] += 1
                log(f"SKIP (no extractable text): {rel}")
                continue
            if existing.get("ids"):
                col.delete(ids=existing["ids"])
            vecs = []
            for i in range(0, len(texts), 32):
                vecs.extend(embed_fn(texts[i:i + 32]))
            col.add(ids=ids, documents=texts, metadatas=metas, embeddings=vecs)
            n["indexed"] += 1
            log(f"INDEXED: {rel} ({len(ids)} chunks)")
        except Exception as e:
            n["errors"] += 1
            log(f"ERROR: {rel}: {e}")
    allm = col.get(include=["metadatas"])
    stale = [i for i, m in zip(allm.get("ids") or [], allm.get("metadatas") or []) if m.get("filename") not in rels]
    if stale:
        col.delete(ids=stale)
        n["removed"] = len(stale)
        log(f"Removed {len(stale)} chunks from files no longer in documents/")
    return n


def main():
    try:
        import chromadb
    except ImportError:
        sys.exit("Install dependencies first: pip install -r requirements.txt")
    col = chromadb.PersistentClient(path=str(DB)).get_or_create_collection("local_documents", metadata={"hnsw:space": "cosine"})
    index_folder(col)
    print(f"Done. Vector database now contains {col.count()} chunks.")


if __name__ == "__main__":
    main()
