"""Mechanical validation of one question's nuggets (plan v2 §3.3 and §3.5.1). No LLM."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from . import values

# The P&R's own period: allowed in nuggets even when the question and answer do not state it (R8).
DOC_YEARS = {"2023", "2024"}
BACKREF = re.compile(r"\b(esse|essa|esses|essas|tal|tais|o referido|a referida|o mesmo|a mesma|"
                     r"neste caso|nesse caso|nessa hipótese|nesta hipótese)\b", re.I)
ITEM = re.compile(r"^\s*(\d{1,2}|[a-z]|[IVX]{1,4})\s*[-–)]\s+")
POINTER = re.compile(r"pergunta\s+(n[ºo°]\s*)?\d{3}", re.I)
NEG = re.compile(r"\b(não|nem|nenhum|nenhuma|vedad[oa]s?|nunca)\b", re.I)


def norm(s: str) -> str:
    s = s.replace("–", "-").replace("—", "-").replace("“", '"').replace("”", '"').replace("’", "'")
    return re.sub(r"\s+", " ", s).strip().lower()


def units(answer: str) -> list[str]:
    """Answer split into list items and sentences (lines of the PDF are hard-wrapped)."""
    out, cur = [], []
    for line in answer.splitlines():
        if not line.strip():
            continue
        if ITEM.match(line) or (cur and cur[-1].rstrip().endswith((".", ";", ":"))
                                and (line[:1].isupper() or cur[-1].rstrip().endswith(":"))):
            if cur:
                out.append(" ".join(cur))
            cur = [line.strip()]
        else:
            cur.append(line.strip())
    if cur:
        out.append(" ".join(cur))
    sents = []
    for u in out:
        sents += [s for s in re.split(r"(?<=\.)\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", u) if s.strip()]
    return sents


def locate(span: str, ans_n: str) -> tuple[str, list[tuple[int, int]]]:
    """``exact`` / ``fuzzy`` / ``missing`` and the covered character ranges of the normalized answer."""
    sp = norm(ITEM.sub("", span))
    if not sp:
        return "missing", []
    i = ans_n.find(sp)
    if i >= 0:
        return "exact", [(i, i + len(sp))]
    sm = SequenceMatcher(None, ans_n, sp, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size >= 12]
    got = sum(b.size for b in blocks)
    if got / len(sp) >= 0.85:
        return "fuzzy", [(b.a, b.a + b.size) for b in blocks]
    return "missing", [(b.a, b.a + b.size) for b in blocks]


def validate(q: dict, nuggets: list[dict]) -> dict:
    """Fill ``values``/``flags``/``issues`` on each nugget and return the question-level report."""
    answer, src = q["answer_cleaned"], q["question_text"] + "\n" + q["answer_cleaned"]
    ans_n = norm(answer)
    src_nums = values.number_tokens(src)
    src_years = set(values.YEAR.findall(src)) | DOC_YEARS
    covered = [False] * len(ans_n)
    errors, warnings = [], []
    seen = {}
    for nug in nuggets:
        nid, txt, iss = nug["nugget_id"], nug["text"], []
        nug["values"] = values.extract(txt)
        # numeric grounding (hard), out-of-answer years (hard)
        for y in set(values.YEAR.findall(txt)) - src_years:
            iss.append(("error", "year_not_in_source", y))
        missing = {t for t in values.number_tokens(txt) - src_nums if t not in values.YEAR.findall(txt)}
        for t in sorted(missing):
            iss.append(("error", "number_not_in_source", t))
        # span
        status, ranges = locate(nug["source_span"], ans_n)
        nug["span_match"] = status
        if status == "missing":
            iss.append(("error", "span_not_found", nug["source_span"][:80]))
        elif status == "fuzzy":
            iss.append(("warning", "span_fuzzy", ""))
        for a, b in ranges:
            for k in range(a, b):
                covered[k] = True
        # self-containment proxy, period anchor, duplicates
        m = BACKREF.search(txt)
        if m:
            iss.append(("warning", "backreference", m.group(0)))
        if nug["values"] and not values.PERIOD.search(txt):
            iss.append(("warning", "value_without_period", ""))
        key = norm(txt)
        if key in seen:
            iss.append(("error", "duplicate_of", seen[key]))
        seen.setdefault(key, nid)
        nug["issues"] = [{"severity": s, "code": c, "detail": d} for s, c, d in iss]
        for s, c, d in iss:
            (errors if s == "error" else warnings).append({"nugget_id": nid, "code": c, "detail": d})

    # answer-level checks
    if not any(n["importance"] == "vital" for n in nuggets):
        errors.append({"nugget_id": None, "code": "no_vital", "detail": ""})
    verdict = re.match(r"\s*(Sim|Não)\b", answer)
    direct = [n for n in nuggets if n["category"] == "resposta_direta"]
    if verdict and len(direct) != 1:
        errors.append({"nugget_id": None, "code": "verdict_count", "detail": f"{len(direct)} resposta_direta"})
    if verdict and verdict.group(1) == "Não" and direct and not NEG.search(direct[0]["text"]):
        warnings.append({"nugget_id": direct[0]["nugget_id"], "code": "verdict_polarity", "detail": "Não"})
    if len(nuggets) > 40:
        warnings.append({"nugget_id": None, "code": "many_nuggets", "detail": str(len(nuggets))})
    uncovered = []
    pos = 0
    for u in units(answer):
        un = norm(u)
        i = ans_n.find(un, pos)
        if i < 0:
            continue
        pos = i + len(un)
        cov = sum(covered[i:i + len(un)]) / max(len(un), 1)
        if cov < 0.5 and not u.rstrip().endswith(":"):   # lead-ins ("Atenção:", "às seguintes alíquotas:")
            is_item, is_ptr = bool(ITEM.match(u)), bool(POINTER.search(u))
            code = "enum_item_uncovered" if is_item and not is_ptr else "unit_uncovered"
            (errors if code == "enum_item_uncovered" else warnings).append(
                {"nugget_id": None, "code": code, "detail": u[:120]})
            uncovered.append(u)
    coverage = sum(covered) / max(len(covered), 1)
    return {"question_number": q["question_number"], "n_nuggets": len(nuggets),
            "n_vital": sum(n["importance"] == "vital" for n in nuggets),
            "char_coverage": round(coverage, 3), "errors": errors, "warnings": warnings,
            "uncovered_units": uncovered}
