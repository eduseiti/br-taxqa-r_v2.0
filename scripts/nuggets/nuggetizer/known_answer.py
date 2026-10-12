"""Known-answer tests (plan v2 §5.7): answers whose correct labels are known by construction.

Built from the gold answer and one nugget set, deterministically (seeded). Each test records the
nuggets it targets, the nuggets whose expected label is ambiguous (``excluded``) and, implicitly,
that every other nugget should still be ``support``. The pilot builds the rule-based types only:
G, V (± a plausible step; the "another period's value from the corpus" variant is left to phase 4),
Y, N, D, C (clause delimited by punctuation; no LLM rewrite), W and E.
"""
from __future__ import annotations

import random
import re
from statistics import mean

from . import values
from .validate import ITEM, norm

EMPTY = "Não há informação suficiente nos dispositivos fornecidos."
TARGET_TYPES = ["V", "Y", "N", "D", "C"]
# a clause opened by a conditional marker after a comma, a semicolon or at the start of the span (not
# at a hard line wrap of the PDF); "caso" as a noun ("no caso dos ativos") is not a marker
CONDITION = re.compile(r"(?:,\s*|;\s*|^)(desde que|exceto|salvo|caso(?!\s+d[eoa]s?\b|\s+em\b)|a menos que|"
                       r"contanto que|somente se|se)\s[^,;.:]+", re.I)
CITATION_TAIL = re.compile(r"n[º°o]\s*[\d.]+(?:/\d+)?,?\s*(?:de\s+\d{1,2}º?\s+de\s+\w+\s+)?de\s*$", re.I)


def find(span: str, text: str) -> tuple[int, int] | None:
    """Character range of ``span`` in the original ``text``, whitespace-insensitive; None if absent."""
    toks = ITEM.sub("", span).split()
    if not toks:
        return None
    m = re.search(r"\s+".join(re.escape(t) for t in toks), text)
    return (m.start(), m.end()) if m else None


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


def build(q: dict, nuggets: list[dict], all_qs: list[dict], seed: int = 13) -> list[dict]:
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
            text, pos = ans, 0
            while (i := text.find(v["raw"], pos)) >= 0:
                text = text[:i] + new + text[i + len(v["raw"]):]
                text = _drop_spelled(text, i + len(new))
                pos = i + len(new)
            targets = [n["nugget_id"] for n in nuggets
                       if any(w["kind"] == v["kind"] and w["normalized"] == v["normalized"] for w in n.get("values") or [])]
            add("V", text, targets, detail=f"{v['raw']} → {new}")

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
        add("N", ans[:m.start(1)] + flip + ans[m.end(1):], direct, detail=f"{m.group(1)} → {flip}")

    # D: the span of one vital nugget deleted
    dc = [n["nugget_id"] for n in nuggets if n["importance"] == "vital" and loc[n["nugget_id"]]
          and (loc[n["nugget_id"]][1] - loc[n["nugget_id"]][0]) < 0.8 * len(ans)]
    if dc:
        nid = rng.choice(dc)
        r = loc[nid]
        inside, partial = touched(r)
        text = re.sub(r"[ \t]{2,}", " ", ans[:r[0]] + ans[r[1]:]).strip()
        add("D", text, inside, excluded=partial, detail=f"span of {nid} deleted")

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
    if cc:
        nid, a, b = rng.choice(sorted(set(cc)))
        inside, partial = touched((a, b))
        others = [x for x, *_ in cc if x != nid and _overlap(loc[x], (a, b))]
        text = ans[:a] + ans[b:]
        add("C", text, [nid], excluded=inside + partial + others, detail=f"removed: «{ans[a:b].strip()}»")

    # W: the answer of the nearest question with another summary (same part of the P&R)
    num = int(qn)
    pool = sorted((x for x in all_qs if x["question_summary"] != q["question_summary"] and x["question_number"] != qn),
                  key=lambda x: (abs(int(x["question_number"]) - num), x["question_number"]))
    if pool:
        w = pool[0]
        add("W", w["answer_cleaned"].strip(), ids, detail=f"answer of Q{w['question_number']} ({w['question_summary']})")

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
                contra_target += nid in tset and t["type"] in ("V", "Y", "N")
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
