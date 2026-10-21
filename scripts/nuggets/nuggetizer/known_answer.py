"""Known-answer tests (plan v2 §5.7): answers whose correct labels are known by construction.

Built from the gold answer and one nugget set, deterministically (seeded). Each test records the
nuggets it targets, the nuggets whose expected label is ambiguous (``excluded``) and, implicitly,
that every other nugget should still be ``support``. Rule-based types: G, V (± a plausible step),
VP (a real value of the corpus, phase 4), Y, N, D, C (clause delimited by punctuation; no LLM
rewrite), W and E.

Phase 4 fixes of the pilot's test artifacts (pilot note §7): D and C skip a deletion whose content
is restated in the rest of the answer, and W skips a substitute answer that restates a nugget (a
near-duplicate question). Both use ``restated`` (content-word bigram containment).
"""
from __future__ import annotations

import random
import re
from collections import Counter
from statistics import mean

from . import values
from .validate import ITEM, norm

EMPTY = "Não há informação suficiente nos dispositivos fornecidos."
TARGET_TYPES = ["V", "VP", "Y", "N", "D", "C"]
# a clause opened by a conditional marker after a comma, a semicolon or at the start of the span (not
# at a hard line wrap of the PDF); "caso" as a noun ("no caso dos ativos") is not a marker
CONDITION = re.compile(r"(?:,\s*|;\s*|^)(desde que|exceto|salvo|caso(?!\s+d[eoa]s?\b|\s+em\b)|a menos que|"
                       r"contanto que|somente se|se)\s[^,;.:]+", re.I)
STOP = set("a o as os de da do das dos e em no na nos nas um uma uns umas por pela pelo pelas pelos para com "
           "que se ao aos à às ou é são ser foi como mais sua seu suas seus este esta esse essa isso".split())
RESTATED = 0.5      # D / C: share of the removed fragment's bigrams still in the corrupted answer
W_RESTATED = 0.4    # W: share of a nugget's bigrams found in the substitute answer
_MONEY = re.compile(r"(?<![\d.,])\d{1,3}(?:\.\d{3})*,\d{2}(?![\d,])")
CITATION_TAIL = re.compile(r"n[º°o]\s*[\d.]+(?:/\d+)?,?\s*(?:de\s+\d{1,2}º?\s+de\s+\w+\s+)?de\s*$", re.I)


def find(span: str, text: str) -> tuple[int, int] | None:
    """Character range of ``span`` in the original ``text``, whitespace-insensitive; None if absent."""
    toks = ITEM.sub("", span).split()
    if not toks:
        return None
    m = re.search(r"\s+".join(re.escape(t) for t in toks), text)
    return (m.start(), m.end()) if m else None


def _bigrams(s: str) -> set[tuple[str, str]]:
    w = [t for t in re.findall(r"\w+", norm(s)) if t not in STOP]
    return set(zip(w, w[1:]))


def restated(fragment: str, text: str) -> float:
    """Share of the content-word bigrams of ``fragment`` that also occur in ``text``."""
    b = _bigrams(fragment)
    return len(b & _bigrams(text)) / len(b) if b else 0.0


class CorpusValues:
    """Real alternative amounts from the legal corpus (VP tests, plan v2 §5.7): for an amount of the answer,
    another R$ amount written within ``window`` characters of it in an article of the corpus, between 0.75×
    and 1.34× of it and at least 2 % away (often the same item in another year's table or amendment, not always). Amounts under
    R$ 10 are skipped."""

    def __init__(self, texts: list[str], window: int = 300):
        self.texts, self.window, self._memo = texts, window, {}

    def alternative(self, num: str) -> str | None:
        if num not in self._memo:
            pat = re.compile(rf"(?<![\d.,]){re.escape(num)}(?![\d,])")
            x0, best = values._num(num), Counter()
            if x0 < 10:
                self._memo[num] = None
                return None
            for t in self.texts:
                if num not in t:
                    continue
                for m in pat.finditer(t):
                    lo, hi = max(0, m.start() - self.window), m.end() + self.window
                    for o in _MONEY.finditer(t, lo, hi):
                        y = values._num(o.group(0))
                        # not a bracket edge one cent away (2.112,00 → 2.112,01): at least 2 % apart
                        if 0.75 * x0 <= y <= 1.34 * x0 and abs(y - x0) >= 0.02 * x0:
                            best[o.group(0)] += 1
            self._memo[num] = min(best, key=lambda k: (-best[k], k)) if best else None
        return self._memo[num]


def _br(x: float, cents: bool) -> str:
    s = f"{x:,.2f}" if cents else f"{x:,.0f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _bump(v: dict) -> str | None:
    """The number part of ``v['raw']`` moved by a plausible step."""
    raw = v["raw"]
    if v["kind"] == "brl":
        num = raw.replace("R$", "").strip()
        new = _br(round(v["normalized"] * 1.1, 2), "," in num)
        return raw.replace(num, new)
    if v["kind"] == "pct":
        p = v["normalized"] * 100
        q = p + 2.5 if p < 50 else p - 2.5
        s = (f"{q:.2f}".rstrip("0").rstrip(".")).replace(".", ",")
        return raw.replace(re.match(r"[\d,]+", raw).group(0), s)
    if v["kind"] == "date":
        m = re.match(r"(\d{1,2})", raw)
        d = int(m.group(1))
        return raw.replace(m.group(1), str(d + 5 if d <= 23 else d - 5), 1)
    return None


def _drop_spelled(text: str, start: int) -> str:
    """Remove an amount written out in words right after a value: ``R$ 40.000,00 (quarenta mil reais)``."""
    m = re.match(r"\s*\([^()\d]{3,}\)", text[start:])
    return text[:start] + text[start + m.end():] if m else text


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def _replace_all(ans: str, old: str, new: str) -> str:
    text, pos = ans, 0
    while (i := text.find(old, pos)) >= 0:
        text = text[:i] + new + text[i + len(old):]
        text = _drop_spelled(text, i + len(new))
        pos = i + len(new)
    return text


def build(q: dict, nuggets: list[dict], all_qs: list[dict], seed: int = 13,
          corpus: CorpusValues | None = None) -> list[dict]:
    rng = random.Random(f"{seed}:{q['question_number']}")
    ans = q["answer_cleaned"].strip()
    qn = q["question_number"]
    ids = [n["nugget_id"] for n in nuggets]
    loc = {n["nugget_id"]: find(n["source_span"], ans) for n in nuggets}
    tests = []

    def add(kind, text, targets=(), excluded=(), detail=""):
        tests.append({"test_id": f"{qn}_{kind}", "question_number": qn, "type": kind, "answer": text,
                      "targets": list(targets), "excluded": [x for x in excluded if x not in targets],
                      "detail": detail})

    def touched(region):
        """Nuggets whose span overlaps ``region``: fully inside → affected, partly → ambiguous."""
        inside, partial = [], []
        for nid, r in loc.items():
            if r is None:
                continue
            ov = _overlap(r, region)
            if ov and ov >= 0.9 * (r[1] - r[0]):
                inside.append(nid)
            elif ov:
                partial.append(nid)
        return inside, partial

    add("G", ans)

    # V: one value changed everywhere it occurs in the answer
    cands = []
    for n in nuggets:
        for v in n.get("values") or []:
            if v["kind"] in ("brl", "pct", "date") and v["raw"] in ans:
                cands.append(v)
    uniq = {(v["kind"], str(v["normalized"])): v for v in cands}
    if uniq:
        v = uniq[rng.choice(sorted(uniq))]
        new = _bump(v)
        if new and new != v["raw"]:
            targets = [n["nugget_id"] for n in nuggets
                       if any(w["kind"] == v["kind"] and w["normalized"] == v["normalized"] for w in n.get("values") or [])]
            add("V", _replace_all(ans, v["raw"], new), targets, detail=f"{v['raw']} → {new}")

    # VP: one R$ amount replaced by a real neighbouring amount of the corpus (another period's value)
    if corpus is not None:
        alts = []
        for key in sorted(k for k in uniq if k[0] == "brl"):
            v = uniq[key]
            num = v["raw"].replace("R$", "").strip()
            alt = corpus.alternative(num) if "," in num else None
            if alt and alt not in ans:
                alts.append((v, num, alt))
        if alts:
            v, num, alt = alts[rng.randrange(len(alts))]
            targets = [n["nugget_id"] for n in nuggets
                       if any(w["kind"] == "brl" and w["normalized"] == v["normalized"] for w in n.get("values") or [])]
            add("VP", _replace_all(ans, v["raw"], v["raw"].replace(num, alt)), targets,
                detail=f"{v['raw']} → R$ {alt} (corpus)")

    # Y: a year inside a target nugget's span moved by one, citation years left alone
    ycands = []
    for n in nuggets:
        r = loc[n["nugget_id"]]
        if r is None:
            continue
        for y in sorted(set(values.YEAR.findall(n["text"]))):
            for m in re.finditer(rf"\b{y}\b", ans[r[0]:r[1]]):
                s = r[0] + m.start()
                if not CITATION_TAIL.search(ans[max(0, s - 60):s]):
                    ycands.append((n["nugget_id"], y, s))
    if ycands:
        nid, y, s = rng.choice(ycands)
        r = loc[nid]
        new_seg = re.sub(rf"\b{y}\b", lambda m: m.group(0) if CITATION_TAIL.search(
            ans[max(0, r[0] + m.start() - 60):r[0] + m.start()]) else str(int(y) + 1), ans[r[0]:r[1]])
        text = ans[:r[0]] + new_seg + ans[r[1]:]
        inside, partial = touched(r)
        targets = [x for x in inside + partial if y in next(n["text"] for n in nuggets if n["nugget_id"] == x)]
        add("Y", text, targets, excluded=[x for x in inside + partial if x not in targets],
            detail=f"{y} → {int(y) + 1} in the span of {nid}")

    # N: leading Sim ↔ Não
    m = re.match(r"\s*(Sim|Não)\b", ans)
    direct = [n["nugget_id"] for n in nuggets if n["category"] == "resposta_direta"]
    if m and direct:
        flip = "Não" if m.group(1) == "Sim" else "Sim"
        # a verdict nugget that restates the body ("Sim. O contribuinte deve apresentar somente uma…") is still
        # supported by the unchanged body: ambiguous, like a D deletion the rest of the answer implies
        body = ans[m.end(1):]
        amb = [x for x in direct if restated(next(n["text"] for n in nuggets if n["nugget_id"] == x), body) >= RESTATED]
        add("N", ans[:m.start(1)] + flip + ans[m.end(1):], [x for x in direct if x not in amb], excluded=amb,
            detail=f"{m.group(1)} → {flip}" + (f"; restated in the body: {', '.join(amb)}" if amb else ""))

    # D: the span of one vital nugget deleted
    # not the verdict: the rest of the answer usually implies it (pilot 503_D, 679_D); N tests verdicts
    dc = [n["nugget_id"] for n in nuggets if n["importance"] == "vital" and loc[n["nugget_id"]]
          and n["category"] != "resposta_direta"
          and (loc[n["nugget_id"]][1] - loc[n["nugget_id"]][0]) < 0.8 * len(ans)]
    rng.shuffle(dc)
    for nid in dc:      # the first deletion whose content is not restated in the rest of the answer
        r = loc[nid]
        text = re.sub(r"[ \t]{2,}", " ", ans[:r[0]] + ans[r[1]:]).strip()
        rs = restated(ans[r[0]:r[1]], text)
        if rs < RESTATED:
            inside, partial = touched(r)
            add("D", text, inside, excluded=partial, detail=f"span of {nid} deleted (restated {rs:.2f})")
            break

    # C: a delimited condition clause removed from one nugget's span
    cc = []
    for n in nuggets:
        r = loc[n["nugget_id"]]
        if r is None:
            continue
        for m in CONDITION.finditer(ans[r[0]:r[1]]):
            clause = m.group(0).strip(" ,;")
            # the clause must be a real part of this nugget: quoted in its text, or a condicao nugget
            if 15 <= len(clause) <= 0.7 * (r[1] - r[0]) and (norm(clause)[:40] in norm(n["text"])
                                                              or n["category"] == "condicao"):
                cc.append((n["nugget_id"], r[0] + m.start(), r[0] + m.end()))
    cc = sorted(set(cc))
    rng.shuffle(cc)
    for nid, a, b in cc:    # the first condition not restated elsewhere in the answer
        text = ans[:a] + ans[b:]
        rs = restated(ans[a:b], text)
        if rs < RESTATED:
            inside, partial = touched((a, b))
            others = [x for x, *_ in cc if x != nid and _overlap(loc[x], (a, b))]
            add("C", text, [nid], excluded=inside + partial + others,
                detail=f"removed: «{ans[a:b].strip()}» (restated {rs:.2f})")
            break

    # W: the answer of the nearest question with another summary (same part of the P&R)
    num = int(qn)
    pool = sorted((x for x in all_qs if x["question_summary"] != q["question_summary"] and x["question_number"] != qn),
                  key=lambda x: (abs(int(x["question_number"]) - num), x["question_number"]))
    skipped = []
    for w in pool:          # the nearest one that restates none of the nuggets (no near-duplicate)
        wa = w["answer_cleaned"].strip()
        rs = max((restated(n["text"], wa) for n in nuggets), default=0.0)
        rs = max(rs, max((restated(n["source_span"], wa) for n in nuggets), default=0.0))
        if rs < W_RESTATED:
            add("W", wa, ids, detail=f"answer of Q{w['question_number']} ({w['question_summary']})"
                + (f"; skipped near-duplicates {', '.join(skipped)}" if skipped else ""))
            break
        skipped.append(f"Q{w['question_number']} ({rs:.2f})")

    add("E", EMPTY, ids)
    return tests


def metrics(tests: list[dict], labels: dict[str, dict[str, str]], nuggets: dict[str, dict]) -> dict:
    """``labels[test_id][nugget_id]`` → label. Returns per-type and pooled metrics."""
    by = {}
    pooled = {"tp": 0, "pos": 0, "tn": 0, "neg": 0}
    contra_all, contra_target = 0, 0
    for t in tests:
        lab = labels.get(t["test_id"])
        if lab is None:
            continue
        d = by.setdefault(t["type"], {"tests": 0, "targets": 0, "detected": 0, "contradicts": 0,
                                      "nontargets": 0, "support": 0, "vstrict": []})
        d["tests"] += 1
        tset, excl = set(t["targets"]), set(t["excluded"])
        for nid, l in lab.items():
            if l == "contradicts":
                contra_all += 1
                contra_target += nid in tset and t["type"] in ("V", "VP", "Y", "N")
            if nid in excl:
                continue
            if nid in tset:
                d["targets"] += 1
                d["detected"] += l != "support"
                d["contradicts"] += l == "contradicts"
                pooled["pos"] += 1
                pooled["tp"] += l != "support"
            else:
                d["nontargets"] += 1
                d["support"] += l == "support"
                pooled["neg"] += 1
                pooled["tn"] += l == "support"
        vit = [nid for nid in lab if nuggets[nid]["importance"] == "vital"]
        if vit:
            d["vstrict"].append(sum(lab[x] == "support" for x in vit) / len(vit))
    out = {}
    for k, d in by.items():
        out[k] = {"tests": d["tests"], "targets": d["targets"],
                  "sensitivity": d["detected"] / d["targets"] if d["targets"] else None,
                  "contradicts_rate": d["contradicts"] / d["targets"] if d["targets"] else None,
                  "nontargets": d["nontargets"],
                  "specificity": d["support"] / d["nontargets"] if d["nontargets"] else None,
                  "v_strict": mean(d["vstrict"]) if d["vstrict"] else None}
    sens = pooled["tp"] / pooled["pos"] if pooled["pos"] else None
    spec = pooled["tn"] / pooled["neg"] if pooled["neg"] else None
    out["_pooled"] = {"sensitivity": sens, "specificity": spec,
                      "balanced_accuracy": (sens + spec) / 2 if sens is not None and spec is not None else None,
                      "contradicts_precision": contra_target / contra_all if contra_all else None,
                      "contradicts_labels": contra_all}
    return out
