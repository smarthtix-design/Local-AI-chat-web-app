// Page tests with a tiny fake browser (no browser or internet needed).
// Run from the project folder:  node tests/test_ui.js
const fs = require("fs"), vm = require("vm"), path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];

class El {
  constructor(tag) { this.tag = tag; this.children = []; this._c = ""; this._cl = []; this._t = ""; this.style = {}; this.dataset = {}; this.value = ""; this.checked = true; this.hidden = false; }
  set className(v) { this._c = v; this._cl.push(v); } get className() { return this._c; }
  set textContent(v) { this._t = String(v); (this._tl ||= []).push(this._t); this.children = []; }
  get textContent() { return this._t + this.children.map(c => c.textContent ?? c.text ?? "").join(""); }
  set innerHTML(v) { this._html = v; this.children = []; }
  append(...a) { a.forEach(x => this.children.push(typeof x === "string" ? { text: x } : x)); }
  appendChild(x) { if (x.tag === "#frag") x.children.forEach(c => this.children.push(c)); else this.children.push(x); return x; }
  after() {} click() {} remove() {} focus() {} select() {} addEventListener() {} insertAdjacentElement() {}
}
const els = {}, store = {}, created = [], calls = [];
const doc = { getElementById: id => els[id] ??= new El(id), createElement: t => { const e = new El(t); created.push(e); return e; },
  createTextNode: t => ({ text: t }), createDocumentFragment: () => new El("#frag"), body: new El("body"), execCommand() {} };
let chatLines = [];
const enc = new TextEncoder();
const stream = lines => { let sent = false; return { getReader: () => ({ read: async () => sent ? { done: true } : (sent = true, { done: false, value: enc.encode(lines.map(l => JSON.stringify(l)).join("\n") + "\n") }) }) }; };
const ctx = { Blob, document: doc, localStorage: { getItem: k => store[k] ?? null, setItem: (k, v) => store[k] = v }, crypto, URL, TextDecoder, DOMException, AbortController, setTimeout, console, navigator: {},
  setInterval() {},
  fetch: async (url, opts = {}) => {
    const body = typeof opts.body === "string" ? JSON.parse(opts.body) : null;
    calls.push({ url, body });
    if (url === "/api/chat") return { ok: true, status: 200, body: stream(chatLines), json: async () => ({}) };
    if (url === "/api/addurl") return body.url.includes("bad") ? { ok: false, status: 400, json: async () => ({ error: "That address is not allowed." }) }
                                                              : { ok: true, status: 200, json: async () => ({ name: "web: example.com/x", chunks: 3 }) };
    return { ok: true, status: 200, json: async () => ({ models: ["tinyllama:latest", "qwen2.5:1.5b"], mine: [], shared: [], limits: { max_mb: 5 }, online: 3, questions: ["What does Autopilot cover?"] }) };
  } };
vm.createContext(ctx);
vm.runInContext(script + "\n;this.T = { ragTag, row, render, ask, retryWeb, md, vote, addUrl, get history() { return history; }, set history(v) { history = v; }, get cfg() { return cfg; }, get lastError() { return lastError; } };", ctx);
const T = ctx.T; let ok = 0, bad = 0;
const check = (n, c, x) => { c ? (ok++, console.log("PASS", n)) : (bad++, console.log("FAIL", n, x ?? "")); };
const flat = e => e.children.flatMap(c => c.children ? [c, ...flat(c)] : [c]);
const txt = e => e.textContent;
const done = { done: true, eval_count: 5, eval_duration: 1e9, load_duration: 0, total_duration: 2e9 };

(async () => {
  await new Promise(r => setTimeout(r, 30));
  check("best installed model is preferred by default (qwen2.5:1.5b)", T.cfg.model === "qwen2.5:1.5b", T.cfg.model);
  check("live visitor badge updates", txt(els.online).includes("3 online"), txt(els.online));

  // --- source tags ---
  let f = T.ragTag({ mode: "docs", sources: [{ file: "a.md", page: 2, scope: "shared", similarity: 0.71 }] });
  check("docs tag shows file, page, score", txt(f).includes("Documents") && txt(f).includes("shared a.md p.2 (0.71)"), txt(f));
  f = T.ragTag({ mode: "web", sources: [{ title: "<img onerror=x>", url: "https://www.example.com/a?b=1" }, { title: "evil", url: "javascript:alert(1)" }] });
  const links = flat(f).filter(c => c.tag === "a");
  check("web tag: one safe clickable link, host shown", links.length === 1 && links[0].href === "https://www.example.com/a?b=1" && links[0].textContent === "example.com");
  check("web link opens safely; javascript: url dropped", links[0].rel === "noopener noreferrer" && links[0].target === "_blank" && !txt(f).includes("javascript"));
  f = T.ragTag({ mode: "model", why: "no matching document, internet off", best: 0.31, min: 0.4, query: "A B" });
  check("model tag shows reason, best score and the searched text", txt(f).includes("Model only (no matching document, internet off)") && txt(f).includes("0.31 (needs 0.4)") && txt(f).includes("searched: A B"), txt(f));
  check("older saved messages still readable", txt(T.ragTag({ mode: "none", sources: [] })).includes("Model only (no matching document)") && txt(T.ragTag(null)) === "");

  // --- streamed answer: status -> rag -> tokens ---
  els.q.value = "what about iOS?";
  chatLines = [{ status: "Searching your documents..." }, { status: "Searching the internet..." },
    { rag: { mode: "web", sources: [{ title: "T", url: "https://a.com/p" }], query: "x what about iOS?" } },
    { status: "Writing the answer..." }, { message: { content: "Hello " }, done: false }, { message: { content: "there" }, done: false }, done];
  await T.ask();
  const last = T.history[T.history.length - 1];
  check("answer text assembled from stream", last.role === "assistant" && last.content === "Hello there", last);
  check("answer keeps its source info and speed stats", last.rag.mode === "web" && last.rag.sources[0].url === "https://a.com/p" && /5 tokens, 5\.0 tok\/s/.test(last.stat), last);
  check("progress text was shown while waiting", created.some(e => e._cl.includes("msg bot wait")) && created.some(e => (e._tl || []).includes("Searching the internet...")));
  const sent = calls.filter(c => c.url === "/api/chat").pop().body;
  check("request carries internet/documents flags", sent.web === true && sent.rag === true && sent.force_web === false && sent.model === "qwen2.5:1.5b", sent);

  // --- 'Not satisfied? Search the internet' ---
  T.history = [{ role: "user", content: "q" }, { role: "assistant", content: "a", rag: { mode: "model", why: "documents off" } }];
  check("retry button only on the last non-web answer",
        flat(T.row(T.history[1], true)).some(c => c.textContent && c.textContent.includes("Search the internet")) &&
        !flat(T.row(T.history[1], false)).some(c => c.textContent && c.textContent.includes("Search the internet")) &&
        !flat(T.row({ role: "assistant", content: "x", rag: { mode: "web", sources: [] } }, true)).some(c => c.textContent && c.textContent.includes("Search the internet")));
  chatLines = [{ rag: { mode: "web", sources: [] } }, { message: { content: "better" }, done: false }, done];
  await T.retryWeb();
  check("retry re-asks with force_web and replaces the answer", calls.filter(c => c.url === "/api/chat").pop().body.force_web === true
        && T.history.length === 2 && T.history[1].content === "better", T.history);

  // --- model unsure -> message + button; live-data tag ---
  chatLines = [{ rag: { mode: "model", why: "no matching document", sources: [], best: 0.2, min: 0.4 } }, { message: { content: "I can't provide real-time info." }, done: false }, done, { suggest_web: "The model may not be able to answer this reliably." }];
  els.q.value = "something recent"; await T.ask();
  const u = T.history[T.history.length - 1], uRow = flat(T.row(u, true));
  check("unsure answer remembers the suggestion", !!u.suggest, u);
  check("unsure answer shows a message with a Search-the-internet button", uRow.some(c => c.className === "hint") && uRow.some(c => c.tag === "button" && c.textContent === "Search the internet"));
  check("small 'Not satisfied?' link is not duplicated", !uRow.some(c => c.textContent && c.textContent.includes("Not satisfied?")));
  check("no message when the model was confident", !flat(T.row({ role: "assistant", content: "x", rag: { mode: "model" } }, true)).some(c => c.className === "hint"));
  check("live answers are labelled", txt(T.ragTag({ mode: "web", live: true, sources: [] })).includes("Internet (live data)") && !txt(T.ragTag({ mode: "web", sources: [] })).includes("live"));
  // --- starter questions, citations, tables, keyword tag, feedback, add page, export ---
  T.history = []; T.render();
  check("starter question chips appear on an empty chat", flat(els.chat).some(c => c.tag === "button" && c.textContent === "What does Autopilot cover?"));
  let h = T.md("Use Intune [1], see [2], also [9] and [3].", [{ url: "https://a.com/p" }, { file: "x.md" }, { url: "javascript:alert(1)", file: "evil" }]);
  check("[1] links to a web source, [2] marks a document, unknown [9] untouched", h.includes('<a class="cite" href="https://a.com/p" target="_blank" rel="noopener noreferrer">[1]</a>') && h.includes('<span class="cite" title="x.md">[2]</span>') && h.includes("[9]"), h);
  check("javascript: source is never turned into a link", !h.includes("javascript:") || !h.includes('href="javascript'), h);
  h = T.md("see [1]", [{ url: 'https://a.com/"><img src=x onerror=alert(1)>' }]);
  check("source URLs cannot break out of the link", !h.includes('"><img') && !h.includes("<img"), h);
  h = T.md("Intro\n\n| Setting | Value |\n|---|---|\n| Mode | **Supervised** |\n\nAfter");
  check("markdown tables render (header, cells, text around them)", h.includes("<table>") && h.includes("<th>Setting</th>") && h.includes("<td><b>Supervised</b></td>") && h.includes("Intro") && h.includes("After"), h);
  check("a pipe in normal text is not a table", !T.md("use a | b in the shell").includes("<table>"));
  check("keyword matches are labelled; sources are numbered", txt(T.ragTag({ mode: "docs", sources: [{ file: "a.md", page: 0, scope: "shared", similarity: null, kw: true }] })).includes("[1] shared a.md +keyword")
        && txt(T.ragTag({ mode: "web", sources: [{ title: "t", url: "https://www.example.com/x" }] })).includes("[1] example.com"));
  T.history = [{ role: "user", content: "secret question" }, { role: "assistant", content: "secret answer", rag: { mode: "docs", best: 0.6, sources: [] } }];
  check("answers offer Helpful / Not helpful", flat(T.row(T.history[1], true)).filter(c => c.tag === "button" && (c.textContent === "Helpful" || c.textContent === "Not helpful")).length === 2);
  await T.vote(T.history[1], 1); const fb = calls.filter(c => c.url === "/api/feedback").pop().body;
  check("feedback sends only vote, source type, score and model (never the text)", JSON.stringify(Object.keys(fb).sort()) === '["best","mode","model","vote"]' && fb.vote === 1 && fb.mode === "docs" && !JSON.stringify(fb).includes("secret"), fb);
  check("after voting: thanks message, buttons gone", txt(T.row(T.history[1], true)).includes("Thanks for the feedback") && !flat(T.row(T.history[1], true)).some(c => c.textContent === "Helpful"));
  doc.getElementById("url").value = "https://example.com/x"; await T.addUrl();
  check("add a web page: request sent, result shown", calls.filter(c => c.url === "/api/addurl").pop().body.url === "https://example.com/x" && txt(els.upMsg).includes("Indexed web: example.com/x (3 chunks)"), txt(els.upMsg));
  doc.getElementById("url").value = "http://bad.local/"; await T.addUrl();
  check("add a web page: server refusal shown to the visitor", txt(els.upMsg).includes("not allowed"), txt(els.upMsg));
  els.export.onclick(); check("export chat creates chat.txt", created.some(e => e.download === "chat.txt"));

  // --- server error line (for example: queue timeout) ---
  chatLines = [{ error: "The server is busy. Please try again in a minute." }];
  els.q.value = "another question"; await T.ask();
  check("server error line shown to the visitor", T.lastError.includes("busy"), T.lastError);
  T.render(); check("render() runs without errors", true);
  console.log(`\n${ok} passed, ${bad} failed`); process.exit(bad ? 1 : 0);
})();
