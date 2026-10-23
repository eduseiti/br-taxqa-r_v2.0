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


_WORDS = {w: i for i, w in enumerate(
    "zero um dois três quatro cinco seis sete oito nove dez onze doze treze quatorze quinze dezesseis dezessete "
    "dezoito dezenove".split())}
_WORDS.update({"uma": 1, "duas": 2, "tres": 3, "catorze": 14, "cem": 100, "cento": 100,
               **{w: 10 * i for i, w in enumerate("vinte trinta quarenta cinquenta sessenta setenta oitenta "
                                                  "noventa".split(), 2)},
               **{w: 100 * i for i, w in enumerate("duzentos trezentos quatrocentos quinhentos seiscentos "
                                                   "setecentos oitocentos novecentos".split(), 2)}})
_W = "(?:" + "|".join(sorted(_WORDS, key=len, reverse=True)) + ")"
_WNUM = rf"{_W}(?:\s+e\s+{_W})*"
_SPELLED_PCT = re.compile(rf"\b({_WNUM})(?:\s+inteiros?(?:\s+e\s+({_WNUM})\s+(décimos?|centésimos?))?)?\s+por\s+cento\b",
                          re.I)


def _words_to_int(s: str) -> int:
    return sum(_WORDS[w] for w in re.split(r"\s+e\s+", s.lower().strip()))


def _pct_digits(m: re.Match) -> str:
    n = str(_words_to_int(m.group(1)))
    if m.group(2):
        frac = _words_to_int(m.group(2))
        n += "," + (f"{frac:01d}" if m.group(3).lower().startswith("d") else f"{frac:02d}")
    return f"{n}%"


def digits_for_words(text: str) -> str:
    """Percentages written in words ("quinze por cento", "vinte e sete inteiros e cinco décimos por cento") as
    digits, and the degree sign of ordinals ("1° de janeiro") as ``º``, so :func:`extract` finds them (phase 5
    value checks; the provisions write many values this way)."""
    return _SPELLED_PCT.sub(_pct_digits, text.replace("°", "º"))


def number_tokens(text: str) -> set[str]:
    """Digit sequences, normalized so ``30.639,90`` ≡ ``30639,90`` and a trailing separator is dropped."""
    return {t.replace(".", "") for t in _NUM.findall(text)}
