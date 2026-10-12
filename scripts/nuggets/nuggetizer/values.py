"""pt-BR value extraction and normalization (plan v2 §3.3), reused later by scoring (§5.4)."""
from __future__ import annotations

import re

MONTHS = {m: i for i, m in enumerate(
    "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split(), 1)}
_BRL = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)")
_PCT = re.compile(r"(\d+(?:,\d+)?)\s*%")
_DATE = re.compile(r"\b(\d{1,2})º?\s+de\s+(" + "|".join(MONTHS) + r")(?:\s+de\s+(\d{4}))?", re.I)
_DMY = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_NUM = re.compile(r"\d+(?:[.,]\d+)*")
YEAR = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
PERIOD = re.compile(r"\b(19|20)\d{2}\b|ano-calend[áa]rio|exerc[íi]cio|\bano\b|\bmês\b|mensal", re.I)


def _num(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def extract(text: str) -> list[dict]:
    """Values in ``text`` as ``{raw, kind, normalized}`` (``reference_period`` is left to the caller)."""
    out = []
    for m in _BRL.finditer(text):
        out.append({"raw": m.group(0), "kind": "brl", "normalized": round(_num(m.group(1)), 2)})
    for m in _PCT.finditer(text):
        out.append({"raw": m.group(0), "kind": "pct", "normalized": round(_num(m.group(1)) / 100, 6)})
    for m in _DATE.finditer(text):
        d, mon, y = int(m.group(1)), MONTHS[m.group(2).lower()], m.group(3)
        out.append({"raw": m.group(0), "kind": "date",
                    "normalized": f"{y}-{mon:02d}-{d:02d}" if y else f"--{mon:02d}-{d:02d}"})
    for m in _DMY.finditer(text):
        out.append({"raw": m.group(0), "kind": "date",
                    "normalized": f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"})
    return out


def number_tokens(text: str) -> set[str]:
    """Digit sequences, normalized so ``30.639,90`` ≡ ``30639,90`` and a trailing separator is dropped."""
    return {t.replace(".", "") for t in _NUM.findall(text)}
