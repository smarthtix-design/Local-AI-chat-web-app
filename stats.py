"""Usage statistics and answer feedback in a small SQLite file. Never stores question or answer text."""
import contextlib, os, sqlite3, threading, time
from datetime import date
from pathlib import Path

PATH = Path(os.environ.get("STATS_DB") or Path(__file__).resolve().parent / "stats.db")
_lock = threading.Lock()


def _run(sql, args=(), fetch=False):
    with _lock, contextlib.closing(sqlite3.connect(PATH, timeout=5)) as c:
        c.execute("CREATE TABLE IF NOT EXISTS events (ts INTEGER, day TEXT, mode TEXT, live INTEGER, model TEXT, tok_s REAL, secs REAL, best REAL, error INTEGER, suggest INTEGER, vh TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS feedback (ts INTEGER, day TEXT, vote INTEGER, mode TEXT, best REAL, model TEXT)")
        rows = c.execute(sql, args).fetchall() if fetch else c.execute(sql, args) and None
        c.commit()
        return rows


def log_event(mode, live=False, model="", tok_s=None, secs=None, best=None, error=False, suggest=False, vh=""):
    try:
        _run("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?)", (int(time.time()), date.today().isoformat(), mode, int(bool(live)),
             model, tok_s, secs, best, int(error), int(suggest), vh))
    except Exception:
        pass


def log_feedback(vote, mode, best=None, model=""):
    try:
        _run("INSERT INTO feedback VALUES (?,?,?,?,?,?)", (int(time.time()), date.today().isoformat(), vote, mode, best, model))
    except Exception:
        pass


def summary():
    today = date.today().isoformat()
    try:
        one = lambda sql, a=(): _run(sql, a, True)[0][0]
        by = [{"mode": m, "live": bool(l), "count": n, "avg_tok_s": round(t or 0, 1), "avg_secs": round(s or 0, 1)}
              for m, l, n, t, s in _run("SELECT mode, live, COUNT(*), AVG(tok_s), AVG(secs) FROM events GROUP BY mode, live ORDER BY COUNT(*) DESC", (), True)]
        fb = [{"mode": m, "vote": v, "count": n} for m, v, n in _run("SELECT mode, vote, COUNT(*) FROM feedback GROUP BY mode, vote", (), True)]
        return {"total": one("SELECT COUNT(*) FROM events"), "today": one("SELECT COUNT(*) FROM events WHERE day=?", (today,)),
                "visitors_today": one("SELECT COUNT(DISTINCT vh) FROM events WHERE day=?", (today,)),
                "errors": one("SELECT COUNT(*) FROM events WHERE error=1"), "unsure": one("SELECT COUNT(*) FROM events WHERE suggest=1"),
                "avg_tok_s": round(one("SELECT AVG(tok_s) FROM events WHERE tok_s IS NOT NULL") or 0, 1),
                "by_mode": by, "feedback": fb}
    except Exception as e:
        return {"error": str(e), "total": 0, "today": 0, "visitors_today": 0, "errors": 0, "unsure": 0, "avg_tok_s": 0, "by_mode": [], "feedback": []}
