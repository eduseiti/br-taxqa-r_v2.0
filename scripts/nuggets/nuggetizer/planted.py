"""Planted nugget errors: an auditor sensitivity test (pilot addition to plan v2 §3.5.3).

One nugget per question is damaged by a rule with a known expected check, so the share of planted
errors each auditor flags is measured, as the known-answer tests (§5.7) do for the judge. The types
are tried in a fixed rotation and the first one that applies to the question is used:

- ``value``      (C1) a value in the nugget text moved by a plausible step;
- ``polarity``   (C1) the verdict nugget negated ("não" inserted or removed);
- ``condition``  (C1) a condition clause (", desde que …", ", exceto …") removed from the nugget;
- ``quantifier`` (C1) "somente" / "apenas" / "até" / "qualquer" / "todos" changed or removed;
- ``addition``   (C1) a scope clause the answer does not state appended;
- ``merge``      (C3) two independent nuggets of the question joined into one;
- ``importance`` (C4) a verdict, value or condition nugget relabelled `okay`.
"""
from __future__ import annotations

import random
import re

from . import values
from .known_answer import _bump

ORDER = ["value", "polarity", "condition", "quantifier", "addition", "merge", "importance"]
COND = re.compile(r",\s*(desde que|exceto|salvo|caso|a menos que|contanto que|somente se|se)\s[^,;.]+", re.I)
QUANT = [(r"\bsomente\b", ""), (r"\bapenas\b", ""), (r"\baté\b", "acima de"), (r"\bqualquer\b", "algum"),
         (r"\btodos os\b", "alguns"), (r"\btodas as\b", "algumas")]
ADDITION = ", inclusive quando o contribuinte for não residente no Brasil"
# the addition changes nothing when the nugget is already about non-residents (pilot Q703_N03)
IMPLIED = re.compile(r"n[ãa]o[- ]residente|residente no exterior|residente no brasil|residência", re.I)
EXPECTED = {"value": "c1_faithful", "polarity": "c1_faithful", "condition": "c1_faithful",
            "quantifier": "c1_faithful", "addition": "c1_faithful", "merge": "c3_one_unit",
            "importance": "c4_importance"}


def _try(kind: str, nugs: list[dict], rng: random.Random):
    """Return (index, new nugget, detail, removed index or None), or None if the type does not apply."""
    idx = list(range(len(nugs)))
    rng.shuffle(idx)
    for i in idx:
        n = dict(nugs[i])
        t = n["text"]
        if kind == "value":
            for v in values.extract(t):
                new = _bump(v)
                if new and new != v["raw"]:
                    n["text"] = t.replace(v["raw"], new, 1)
                    return i, n, f"{v['raw']} → {new}", None
        elif kind == "polarity" and n["category"] == "resposta_direta":
            if re.search(r"\bnão\b", t):
                n["text"] = re.sub(r"\bnão\s+", "", t, count=1)
                return i, n, "'não' removed", None
            m = re.search(r"\b(é|são|pode|podem|deve|devem|está|estão|incide|incidem|há)\b", t)
            if m:
                n["text"] = t[:m.start()] + "não " + t[m.start():]
                return i, n, f"'não' inserted before '{m.group(0)}'", None
        elif kind == "condition":
            m = COND.search(t)
            if m and len(m.group(0)) >= 15:
                n["text"] = t[:m.start()] + t[m.end():]
                return i, n, f"removed «{m.group(0).strip(', ')}»", None
        elif kind == "quantifier":
            for pat, rep in QUANT:
                if re.search(pat, t):
                    n["text"] = re.sub(r"\s{2,}", " ", re.sub(pat, rep, t, count=1))
                    return i, n, f"{pat} → '{rep}'", None
        elif kind == "addition" and t.rstrip().endswith(".") and not IMPLIED.search(t):
            n["text"] = t.rstrip()[:-1] + ADDITION + "."
            return i, n, "scope clause appended", None
        elif kind == "merge" and len(nugs) >= 3:
            j = i + 1 if i + 1 < len(nugs) else i - 1
            if nugs[j]["category"] != nugs[i]["category"] or nugs[i]["category"] in ("regra", "condicao"):
                a, b = sorted((i, j))
                n = dict(nugs[a])
                n["text"] = nugs[a]["text"].rstrip(".") + ". Além disso, " + nugs[b]["text"][0].lower() + nugs[b]["text"][1:]
                return a, n, f"merged with {nugs[b]['nugget_id']}", b
        elif kind == "importance" and n["importance"] == "vital" and n["category"] in (
                "resposta_direta", "valor_prazo", "condicao"):
            n["importance"] = "okay"
            return i, n, "vital → okay", None
    return None


def plant(qn: str, nugs: list[dict], k: int, seed: int = 13) -> tuple[list[dict], dict | None]:
    """Damage one nugget of question ``qn``; the type rotation starts at ``k`` (the question's position)."""
    rng = random.Random(f"{seed}:{qn}")
    for step in range(len(ORDER)):
        kind = ORDER[(k + step) % len(ORDER)]
        got = _try(kind, nugs, rng)
        if got:
            i, new, detail, drop = got
            out = [dict(x) for x in nugs]
            new["planted"] = {"type": kind, "expected_check": EXPECTED[kind], "detail": detail,
                              "original": nugs[i]["text"], "original_importance": nugs[i]["importance"]}
            out[i] = new
            if drop is not None:
                out.pop(drop)
            for o, x in enumerate(out, 1):
                x["ordinal"] = o
                x["nugget_id"] = f"Q{qn}_N{o:02d}"
            return out, {"question_number": qn, "nugget_id": new["nugget_id"], **new["planted"]}
    return nugs, None
