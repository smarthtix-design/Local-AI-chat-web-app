# Tiny Chat + RAG: Full Setup Guide

A local AI chat website that runs entirely on your own PC.

- **Chat model:** Qwen2.5 1.5B (recommended) or TinyLlama (lighter), served by Ollama
- **Document search (RAG):** `all-minilm` embeddings + ChromaDB
- **Internet search:** DuckDuckGo through the `ddgs` Python package (no API key). Only this step needs internet; everything else stays on your PC.
- **Website:** one `index.html` plus a Python server (`server.py`)
- **How an answer is made:** your documents first. If nothing matches, a question that needs live information (weather, news, prices, scores, "today", recent years) goes straight to the internet; any other question is answered by the model alone. If the model admits it is unsure, the page shows a message with a **Search the internet** button. Each answer is tagged **Documents** (file, page, match score), **Internet** or **Internet (live data)** (clickable links), or **Model only** (with the reason).
- **Search quality:** document search matches meaning *and* exact words/file names (hybrid). Answers carry numbered citations ([1], [2]) that link to the source. For internet answers the top result pages are read, not just the snippets.
- **Files and pages:** PDF, DOCX, XLSX, PPTX, CSV, HTML, TXT and MD, plus "add a web page by link". Visitors can upload their own files (private to their browser).
- **Owner tools:** an admin page that opens only on this PC (live visitors, answers by source, speed, errors, feedback, re-index, internet on/off, delete uploads, and a debug panel), thumbs up/down on every answer, automatic re-indexing when `documents/` changes, a health check with automatic restart, daily backups, and an evaluation script.
- **Chat extras:** live progress line, follow-up questions, greetings answered without searching, tables in answers, starter questions, export chat, voice input (Chrome/Edge), and a "Not satisfied? Search the internet" button.

Tested on Linux Mint (Ubuntu based), Intel i5, 4 GB RAM, no GPU.

---

## 0. Project layout

Everything below assumes this layout. `PROJECT` is the folder that contains `server.py`.

```
tiny-chat/
└── rag/                  <- PROJECT
    ├── server.py         web server, API, hybrid RAG, internet search, uploads, admin API
    ├── index.html        the chat page
    ├── admin.html        owner page (opens only on this PC)
    ├── webtools.py       safe web fetching and page-text extraction
    ├── retrieval.py      keyword search and fusion with meaning search
    ├── stats.py          usage counts and feedback (no question text), file stats.db
    ├── selfcheck.py      checks the whole setup
    ├── eval.py, evalset.json   measures document-search quality
    ├── requirements.txt  Python packages
    ├── tests/            automatic tests (run_all.py runs everything)
    ├── deploy/           healthcheck.sh, backup.sh, install-timers.sh
    ├── documents/        shared files that everyone can search
    ├── chroma_db/        vector database (created automatically)
    ├── backups/          daily backups (created by backup.sh)
    ├── venv/             Python virtual environment (created in step 3)
    └── rag/
        └── ingest.py     reads files and indexes the documents/ folder
```

`server.py` imports `ingest.py`, so keep it in `PROJECT/rag/`. `ingest.py` expects `documents/` and `chroma_db/` one level above its own folder, which is `PROJECT`.

Set this variable in every new terminal (change the path if yours differs):

```bash
export PROJECT="$HOME/Desktop/tiny-chat/rag"
```

---

## 1. System packages

```bash
sudo apt update
sudo apt install -y curl wget python3 python3-venv python3-pip
python3 --version        # 3.10 or newer
```

---

## 2. Ollama and the two models

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
systemctl is-active ollama          # should print: active

ollama pull qwen2.5:1.5b            # recommended chat model, about 1 GB
ollama pull tinyllama               # lighter chat model, about 640 MB (optional)
ollama pull all-minilm              # embedding model for document search, about 45 MB
ollama list                         # all should be listed
```

Test both:

```bash
ollama run qwen2.5:1.5b "hello"     # type /bye to exit
curl -s http://localhost:11434/api/embed -d '{"model":"all-minilm","input":"hello"}' | head -c 120
```

The second command must print `{"model":"all-minilm",...`. If it returns 404, update Ollama by re-running the install command above.

---

## 3. Python environment

```bash
cd "$PROJECT"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

If `requirements.txt` is missing or incomplete:

```bash
pip install chromadb pypdf python-docx openpyxl python-pptx ddgs
```

Verify:

```bash
python -c "import chromadb, pypdf, docx, openpyxl, pptx, ddgs; print('ok')"
```

Always use the venv Python (`python`, not `python3`) to run the project. Activate it in each new terminal with `source "$PROJECT/venv/bin/activate"`.

---

## 4. Shared documents and indexing

Put files you want everyone to be able to search into `documents/`. Supported types: PDF, DOCX, XLSX, PPTX, CSV, HTML, TXT, MD. Subfolders are fine.

```bash
cd "$PROJECT"
source venv/bin/activate
mkdir -p documents
cp /path/to/your/files/* documents/
python rag/ingest.py
```

Output lines:

| Line | Meaning |
|---|---|
| `INDEXED: file (N chunks)` | New or changed file was embedded |
| `UNCHANGED: file` | Skipped (fast) |
| `SKIP (no extractable text)` | Often a scanned PDF; OCR is not supported |
| `Removed N chunks...` | A file was deleted from `documents/` |

**You normally do nothing:** while the server runs it checks `documents/` every 60 seconds (`REINDEX_EVERY`) and re-indexes new, edited or deleted files by itself. You can also press **Re-index** on the admin page, or run `python rag/ingest.py` by hand (then restart the server). Visitor uploads are indexed when uploaded.

If you ever change the embedding model, wipe and rebuild, because vectors from different models cannot be compared:

```bash
rm -rf "$PROJECT/chroma_db" && python rag/ingest.py
```

---

## 5. Run the server

```bash
cd "$PROJECT"
source venv/bin/activate
python server.py
```

It prints `Tiny Chat + RAG on http://127.0.0.1:8000`. Leave the terminal open. Open `http://localhost:8000` in a browser and try:

1. Ask something that is in your documents. The tag should say **Documents** with the file name and a score such as `(0.62)`.
2. Ask a live question, for example `weather in Kolkata today`. The status line says "This needs live information. Searching the internet...", and the tag says **Internet (live data)** with clickable links.
3. Ask a general question that is not in your files, for example `What is DNS?`. The tag says **Model only (no matching document)** and no internet is used. If the model says it is unsure, a message appears with a **Search the internet** button.
4. Untick "Use internet" and ask the weather question again. The tag should say **Model only (...)** with the reason.
5. Open "My documents", upload a small file, then ask about it. The tag should say **Documents: your file ...**.

On any answer that was not from the internet, "Not satisfied? Search the internet" asks the same question again with web results.

The server listens on `127.0.0.1` only, so nothing is reachable from your network until you add a tunnel (step 7).

---

### Check everything, and run the tests

```bash
cd "$PROJECT" && source venv/bin/activate
python selfcheck.py              # add --no-chat to skip the model answer test (slow on CPU)
python tests/run_all.py          # everything below in one go
python tests/test_backend.py     # server logic, with fake Ollama, fake vector store and fake internet
python tests/test_features.py    # file readers, indexer, safe web fetching, keyword search, stats, deploy scripts
node tests/test_ui.js            # the web page, with a fake browser (needs nodejs: sudo apt install -y nodejs)
```

`selfcheck.py` prints PASS, WARN or FAIL for each item (Python and packages, project files, RAM and disk, Ollama and models, embeddings, a short model answer with its speed, the vector database, DuckDuckGo, and the running web server) with the fix next to anything that is not PASS. Run it first whenever something breaks. The two test files use ports 18000 and 18434 and never touch your real documents, so they are safe to run while the site is live. Re-run them after every code change.

---

## 6. Run automatically after a reboot (systemd)

Run these in a terminal (not inside VS Code). The variables expand to your user name and project path.

```bash
export PROJECT="$HOME/Desktop/tiny-chat/rag"

sudo tee /etc/systemd/system/tinychat.service > /dev/null << EOF
[Unit]
Description=Tiny Chat web and RAG server
After=network-online.target ollama.service
Wants=ollama.service

[Service]
User=$USER
WorkingDirectory=$PROJECT
ExecStart=$PROJECT/venv/bin/python $PROJECT/server.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now tinychat
systemctl status tinychat --no-pager | head -5
```

Stop any manually started server first (`fuser -k 8000/tcp`), because the service needs port 8000.

---

## 7. Public access with a Cloudflare quick tunnel (optional, free, no account)

```bash
cd /tmp
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
cloudflared --version
```

Quick test (leave it running; Ctrl+C stops it):

```bash
cloudflared tunnel --url http://localhost:8000
```

It prints `https://<random-words>.trycloudflare.com`. Open it from a phone on mobile data to confirm.

Keep the tunnel running across reboots:

```bash
sudo tee /etc/systemd/system/tinychat-tunnel.service > /dev/null << EOF
[Unit]
Description=Cloudflare quick tunnel for Tiny Chat
After=network-online.target tinychat.service
Wants=network-online.target

[Service]
User=$USER
ExecStart=/usr/bin/cloudflared tunnel --no-autoupdate --url http://localhost:8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now tinychat-tunnel
sleep 10
journalctl -u tinychat-tunnel --no-pager | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1
```

Quick tunnels get a **new URL every restart and reboot**; the last command shows the current one. A fixed URL needs a named tunnel and a domain on Cloudflare.

---

## 8. Settings you can change (top of `server.py`)

Restart the server after editing.

| Setting | Default | Meaning |
|---|---|---|
| `USE_KEYWORD` | `True` | Also match exact words and file names, not only meaning (hybrid search) |
| `AUTO_REINDEX`, `REINDEX_EVERY` | `True`, `60` | Re-index `documents/` by itself when files change, checked every N seconds |
| `WEB_FETCH_PAGES` | `2` | Read the top N result pages (not just snippets). `0` = snippets only. |
| `SEARXNG_URL` (env var) | empty | Backup search engine used when DuckDuckGo fails (see below) |
| `USE_SHARED_DOCS` | `True` | `True`: every visitor can search your `documents/` folder. Set `False` if it holds anything private. |
| `MIN_SIMILARITY` | `0.40` | Document match strictness (0 to 1, higher = stricter). The best chunk must reach this score, otherwise the internet is tried. Watch the scores shown under answers: if relevant questions miss, lower it; if unrelated questions match your files, raise it. |
| `USE_INTERNET` | `True` | `False`: the server never contacts the internet |
| `ALWAYS_WEB_IF_NO_DOCS` | `False` | `False`: the model answers alone unless the question needs live data. `True`: search the web whenever no document matches. |
| `WEB_RESULTS`, `WEB_TIMEOUT` | `4`, `8` | Search results used per question, and seconds to wait for them |
| `WEB_CACHE_SECS` | `600` | Repeated questions reuse earlier search results for this long |
| `RAG_TOP_K` | `4` | Excerpts fed to the model per question |
| `MAX_USER` | `500` | Max characters per question |
| `MIN_GAP`, `DAILY_CAP` | `2` s, `150` | Seconds between requests, and chats per IP per day |
| `QUEUE_WAIT` | `90` | Maximum seconds a visitor waits in line (one answer at a time). They see "Waiting for your turn (N in line)" while waiting. |
| `MAX_UPLOAD_MB`, `MAX_FILES` | `5`, `5` | Upload size and files per visitor |
| `UPLOADS_PER_DAY`, `DOC_TTL_DAYS` | `20`, `7` | Uploads per IP per day; days before uploads are auto-deleted |
| `RAG_EMBED_MODEL` (env var) | `all-minilm` | Embedding model name. `ingest.py` has its own `EMBED_MODEL`, so keep them identical. |

---

### Owner page, evaluation, backups, health check

**Admin page:** open `http://localhost:8000/admin` **on this PC**. It shows live visitors, answers by source (documents, internet, live data, model only), speed, errors, thumbs up/down, and has buttons to re-index, turn the internet on or off (until the next restart), and delete all visitor uploads. The **debug box** shows, for any question, which route it would take, the match scores and the exact document text the model would receive. It refuses requests that arrive through the tunnel (they carry tunnel headers or a different `Host`). After setting up the tunnel, check that `https://<your-public-url>/admin` shows "Not found".

**Measure search quality:** edit `evalset.json` (a question and part of the file name that should answer it), then `python eval.py`. It reports which questions found their file. Re-run it after changing `MIN_SIMILARITY`, the documents or the embedding model.

**Health check and backups (optional):**
```bash
cd "$PROJECT" && sudo bash deploy/install-timers.sh
systemctl list-timers | grep tinychat
```
This installs a check every minute (restarts `tinychat` or `ollama` after 3 failed checks in a row), a daily backup of `chroma_db`, `stats.db` and `documents/` into `backups/` (newest 7 kept), and a 200 MB limit for system logs. Run `bash deploy/backup.sh` for a backup now.

**Backup search engine (optional):** if DuckDuckGo rate-limits you, run your own SearXNG and give its address to the server. SearXNG must have the JSON format enabled (`search: formats: [html, json]` in its `settings.yml`).
```bash
docker run -d --name searxng -p 127.0.0.1:8888:8080 -v "$HOME/searxng:/etc/searxng" searxng/searxng
# edit $HOME/searxng/settings.yml: add "json" to search.formats, then: docker restart searxng
```
Then add `Environment="SEARXNG_URL=http://127.0.0.1:8888"` under `[Service]` in `/etc/systemd/system/tinychat.service` and restart the service (or `export SEARXNG_URL=...` before `python server.py`).

**Fixed public address (optional, needs a domain on Cloudflare):** `cloudflared tunnel login`, `cloudflared tunnel create tinychat`, `cloudflared tunnel route dns tinychat chat.yourdomain.com`, then run `cloudflared tunnel run --url http://localhost:8000 tinychat` (or install it as a service with a config file). The same URL then survives reboots. With a domain you can also put **Cloudflare Access** (free, email login) or a WAF **rate-limiting rule** in front of the site for bot protection. These need your Cloudflare account, so they are not built into the project.

## 9. Security notes (there is no login)

- Anyone with the link can use your PC's CPU. Share it only with people you trust, and stop the tunnel when not needed: `sudo systemctl stop tinychat-tunnel`.
- Visitor uploads are tied to a random ID stored in that browser. They are private to that browser, and clearing browser data loses access to them.
- Uploaded PDFs and DOCX files are parsed on your PC. Size and chunk limits reduce the risk, but only expose the site to people you trust.
- With "Use internet" on, the visitor's question text is sent to DuckDuckGo. The page says so. Set `USE_INTERNET = False` if that is not acceptable. Search results are fed to the model as untrusted reference text (titles, snippets and links only; no pages are downloaded).
- Reading result pages and "add a web page" fetch addresses on behalf of visitors, so `webtools.py` only allows http/https on ports 80/443, only public IP addresses (never this PC, your network or cloud-metadata addresses; checked before connecting, and after every redirect), a size and time limit, and text or HTML only.
- Thumbs up/down and the statistics store only counts, source types and scores, never question or answer text.
- Never expose Ollama's port (11434) directly. The tunnel points only at port 8000.

---

## 10. Daily commands

| Task | Command |
|---|---|
| Admin page (on this PC) | `http://localhost:8000/admin` |
| Backup now | `bash deploy/backup.sh` |
| Measure search quality | `python eval.py` |
| Check the whole setup | `python selfcheck.py` (from the project folder, venv active) |
| Run all tests | `python tests/run_all.py` |
| Server status | `systemctl status tinychat --no-pager` |
| Live web log | `journalctl -u tinychat -f` |
| Restart after editing code or re-indexing | `sudo systemctl restart tinychat` |
| Current public URL | `journalctl -u tinychat-tunnel --no-pager \| grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' \| tail -1` |
| Take the site offline | `sudo systemctl stop tinychat tinychat-tunnel` |
| Watch Ollama | `journalctl -u ollama -f` |
| Is a model loaded in RAM? | `ollama ps` (empty when idle is normal) |
| Unload the model | `ollama stop tinyllama` |
| Check RAM | `free -h` |
| Who owns port 8000? | `sudo lsof -i :8000` |
| Free port 8000 | `sudo fuser -k 8000/tcp` |

---

## 11. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `ModuleNotFoundError: No module named 'ingest'` | `server.py` is not in `PROJECT`, or `ingest.py` is not in `PROJECT/rag/`. Run from `PROJECT`. |
| "RAG dependencies missing" | Server was started with system `python3`. Use `venv/bin/python`, or `pip install -r requirements.txt` inside the venv. |
| "Embedding model missing. Run: ollama pull all-minilm" | `ollama pull all-minilm`; if it persists, update Ollama (step 2). |
| `Address already in use` (port 8000) | An old server is running: `sudo fuser -k 8000/tcp`, then start again. |
| Tag says "Model only (documents unavailable)" | Retrieval failed. Look for `RAG error:` in `journalctl -u tinychat` (or the server terminal). |
| Tag says "Model only (no matching document)" | Normal for general questions. The model answered alone. If you expected your files to be used, check the score shown next to the tag and lower `MIN_SIMILARITY`. |
| Tag says "Model only (needs live data, internet off)" | The question needs live information but the internet is off (the "Use internet" box, or `USE_INTERNET = False`). |
| Weather or news question was not sent to the internet | Live questions are recognised by keywords (`LIVE` in `server.py`). Rephrase with a word like "today" or "latest", or use the **Search the internet** button. |
| Tag says "Model only (internet search failed)" | `ddgs` is missing (`pip install ddgs` in the venv), the PC has no internet, or DuckDuckGo is rate-limiting you. Check `journalctl -u tinychat` for `Web search error:`. Wait a few minutes and try again. |
| Tag says "Model only (no web results)" | The search ran but returned nothing usable. Try rewording the question. |
| Shared files list is empty or stale | Run `python rag/ingest.py`, then restart the server. |
| "Ollama is not answering" | `sudo systemctl start ollama` |
| Page says "Waiting for your turn (N in line)" | Another visitor is being answered (one at a time). After `QUEUE_WAIT` seconds it says the server is busy; try again. |
| Tag says "Model only (casual message)" | Greetings and thanks skip all searching on purpose. |
| `429 Slow down` / daily limit | Rate limits in step 8 |
| Tunnel error 1033 or page not found | The quick-tunnel URL changed; get the current one (step 10). |
| Very slow or out-of-memory | Close heavy browser tabs. TinyLlama needs roughly 1 to 2 GB. Add swap: `sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile` |
| `/admin` says "Not found" | It only opens on this PC at `http://localhost:8000/admin` (not the tunnel address, not the PC's LAN address). |
| "Add page" says "That address is not allowed" | By design: private/internal addresses, other ports and non-web links are blocked. Use a public http(s) page. |
| Search misses a file you know exists | Check it is listed under "Shared files" and re-index (admin page). Exact names and codes are matched by the keyword search; for meaning search, `python eval.py` shows scores. |
| Internet answers have no page excerpts | Some sites block automated readers; the search snippets are used instead. `WEB_FETCH_PAGES = 0` turns page reading off. |

---

## 12. Quick start (everything in order)

```bash
# 1. system packages
sudo apt update && sudo apt install -y curl wget python3 python3-venv python3-pip

# 2. Ollama and models
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
ollama pull qwen2.5:1.5b
ollama pull all-minilm

# 3. Python environment
export PROJECT="$HOME/Desktop/tiny-chat/rag"
cd "$PROJECT"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. index the shared documents
mkdir -p documents          # then copy your files in
python rag/ingest.py

# 5. run
python server.py            # open http://localhost:8000
```

Then continue with step 6 (auto-start) and step 7 (public link) if you want them.

---

## 13. Reset and uninstall

```bash
# wipe all indexed documents and visitor uploads (re-run ingest afterwards)
rm -rf "$PROJECT/chroma_db"

# remove the services
sudo systemctl disable --now tinychat tinychat-tunnel
sudo rm /etc/systemd/system/tinychat.service /etc/systemd/system/tinychat-tunnel.service
sudo systemctl daemon-reload

# remove models
ollama rm tinyllama
ollama rm all-minilm
```
