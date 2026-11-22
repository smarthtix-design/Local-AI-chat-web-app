"""Keyword (BM25) search and fusion with vector search. Pure Python, no extra RAM worth mentioning."""
import math, re
from collections import Counter

STOP = set("""a an the and or but if of to in on at by for with from as is are was were be been being it its this that these those
what which who whom how why when where do does did can could should would will shall may might i you he she we they me my your
our their there here about into than then so not no yes please tell show give explain""".split())


def terms(text):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and (len(w) > 1 or w.isdigit())]


class KW:
    """items: dicts with id, text, file, page, scope. File names are searched too (so 'recommended iOS config' finds
    Recommended_iOS_Config.txt)."""
    def __init__(self, items):
        self.items = items
        self.tf = [Counter(terms(i.get("file", "") + " " + i["text"])) for i in items]
        self.len = [sum(c.values()) or 1 for c in self.tf]
        self.avg = (sum(self.len) / len(self.len)) if items else 1
        self.df = Counter(t for c in self.tf for t in c)

    def search(self, q, k=5, min_cover=0.6):
        qt = list(dict.fromkeys(terms(q)))
        if not qt or not self.items:
            return []
        n, out = len(self.items), []
        for it, c, ln in zip(self.items, self.tf, self.len):
            hit = [t for t in qt if t in c]
            if len(hit) / len(qt) < min_cover:     # most of the question's words must appear in the chunk
                continue
            s = sum(math.log(1 + (n - self.df[t] + .5) / (self.df[t] + .5)) * c[t] * 2.5 /
                    (c[t] + 1.5 * (.25 + .75 * ln / self.avg)) for t in hit)
            out.append((s, it))
        return [dict(it, kw=True, score=round(s, 3)) for s, it in sorted(out, key=lambda x: -x[0])[:k]]


def fuse(vec_hits, kw_hits, k):
    """Reciprocal rank fusion: chunks ranked well by meaning AND by keywords float to the top."""
    score, info = {}, {}
    for lst in (vec_hits, kw_hits):
        for rank, h in enumerate(lst):
            score[h["id"]] = score.get(h["id"], 0) + 1 / (60 + rank)
            info.setdefault(h["id"], dict(h))
            if h.get("kw"):
                info[h["id"]]["kw"] = True
    return [info[i] for i in sorted(score, key=lambda i: -score[i])[:k]]
