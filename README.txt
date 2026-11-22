FOLDER-BASED OLLAMA RAG WEB CHAT
================================

This project extends your supplied index.html and server.py. It keeps:
- Access-code gate and access_code.txt / ACCESS_CODE environment variable
- Ollama model selector
- Existing temperature, context, max reply, history and system prompt settings
- Streaming chat, Stop, Clear chat, retry on HTTP 503
- Existing per-IP rate limit and one-generation lock

NEW:
- Put .pdf, .docx, .txt and .md files in documents/
- Manually index with: python rag/ingest.py
- Toggle "Search my documents (RAG)" in the web UI
- ChromaDB persistent vectors are stored in chroma_db/
- Ollama embedding model default: all-minilm
- Retrieved sources are shown after the answer

INSTALL (Linux Mint):
1. Ensure Ollama is running:
   sudo systemctl start ollama
2. Pull the embedding model:
   ollama pull all-minilm
3. Create and activate a virtual environment:
   python3 -m venv venv
   source venv/bin/activate
4. Install packages:
   pip install -r requirements.txt
5. Copy documents into documents/
6. Build/update the index:
   python rag/ingest.py
7. Start the web server:
   python server.py
8. Open http://127.0.0.1:8000 and enter access_code.txt's code.

WHEN DOCUMENTS CHANGE:
Run `python rag/ingest.py` again. It skips unchanged files, replaces changed
files' chunks, and removes chunks for files deleted from documents/.

SECURITY:
- documents/ and chroma_db/ are not web-served.
- RAG context is retrieved on the server; browser cannot submit its own context.
- Do not expose Ollama port 11434 or ChromaDB to the network.
- Treat documents as untrusted. The system prompt tells the model to ignore
  instructions embedded in retrieved document text, but prompt injection
  resistance is not perfect.
- A Cloudflare tunnel makes the web chat internet-accessible while active.
  Share the access code only with intended users.
- Only use documents you have permission to index.

NOTES:
- PDF extraction uses text extraction; scanned/image-only PDFs need OCR first.
- DOCX parser reads paragraphs and tables; embedded images are not OCR'd.
- Initial chunking is character-based (600 chars, 100 overlap), a practical
  starting point for this small local project.
- Retrieval is top 4 chunks; the backend caps inserted context at 6500 chars.
- Existing chat model context is still capped by num_ctx in server.py.
- If you use a different embedding model, set RAG_EMBED_MODEL to the same
  model before indexing and when running server.py.
