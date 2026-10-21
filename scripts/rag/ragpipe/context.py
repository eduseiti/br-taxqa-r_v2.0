"""Context selection: containment de-duplication and k / token-budget cutoffs (plan §6.1).

Used by the retrieval evaluation for the token-budget view (plan §4.3) and by stage C
(:mod:`ragpipe.contexts`), so the retrieval numbers describe exactly the contexts the generator will
see. Formatting of the selected chunks (plan §6.2): :class:`Template` and :func:`source_label`.

A ranked item is a text; ``intervals[i]`` lists the ``(file, Num_Inicio, Num_Final)`` of every chunk
of the strategy that has text ``i`` (representative and aliases).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

Interval = tuple[int, int, int]      # (file index, Num_Inicio, Num_Final)

DEDUP_MODES = ("none", "containment", "containment_merge")
OVERFLOW_MODES = ("skip", "stop")


@dataclass(frozen=True)
class Cutoff:
    """``k=<n>`` (number of texts) or ``budget=<tokens>`` (Qwen3 tokens)."""

    kind: str
    value: int

    @classmethod
    def parse(cls, spec: str) -> "Cutoff":
        m = re.fullmatch(r"\s*(k|budget)\s*=\s*(\d+)\s*", spec)
        if not m:
            raise ValueError(f"bad cutoff {spec!r}: use k=<n> or budget=<tokens>")
        return cls(m.group(1), int(m.group(2)))

    def __str__(self) -> str:
        return f"{self.kind}={self.value}"


def is_contained(item_intervals: Sequence[Interval], selected: dict[int, list[tuple[int, int]]]) -> bool:
    """True when some chunk of the item lies inside a selected chunk of the same file."""
    for f, s, e in item_intervals:
        for s2, e2 in selected.get(f, ()):
            if s2 <= s and e <= e2:
                return True
    return False


def select(ranked: Sequence[int], tokens: np.ndarray, intervals: Sequence[Sequence[Interval]], cutoff: Cutoff,
           dedup: str = "containment_merge", overflow: str = "skip") -> list[int]:
    """Indices (into ``ranked``) of the texts that make up the context, in context order.

    - ``ranked``: candidate positions, best first; ``tokens`` and ``intervals`` are indexed by them.
    - ``dedup="containment"``: drop a text whose chunk interval is inside the interval of an already
      selected chunk of the same file (a lower-ranked child of a selected parent). The reverse case
      (a parent after its child) is kept, since the parent adds text; the child's text is then in the
      context twice. The context order is the rank order.
    - ``dedup="containment_merge"``: as ``containment``, and a parent after its selected children
      **replaces** them (it takes the place of the first one; it needs only its tokens minus theirs),
      so no text is repeated (plan §6.1, "left for later"; Phase 2 note §4). **Default** since
      2026-10-21 (user decision): ``containment`` sends a child's text twice when its parent follows.
    - ``overflow``: for budgets, ``skip`` a text that does not fit and keep filling, or ``stop``.
    """
    if dedup not in DEDUP_MODES:
        raise ValueError(f"dedup must be one of {DEDUP_MODES}")
    if overflow not in OVERFLOW_MODES:
        raise ValueError(f"overflow must be one of {OVERFLOW_MODES}")
    ranked = np.asarray(ranked, dtype=np.int64)
    toks = tokens[ranked]
    budget = cutoff.value if cutoff.kind == "budget" else None
    k = cutoff.value if cutoff.kind == "k" else None
    merge = dedup == "containment_merge"
    use_dedup = dedup != "none"
    # suffix minimum of the token counts: once nothing further can fit, stop scanning (not with
    # merging, where a parent may fit by replacing its children)
    early_stop = budget is not None and len(toks) and not merge
    suffix_min = np.minimum.accumulate(toks[::-1])[::-1] if early_stop else toks
    out: list[int] = []
    selected: dict[int, list[tuple[int, int]]] = {}     # spans of the selected chunks, per file
    used = 0
    for i in range(len(ranked)):
        if k is not None and len(out) >= k:
            break
        if early_stop and suffix_min[i] > budget - used:
            break
        ivs = intervals[ranked[i]]
        if merge:
            if is_contained(ivs, selected):
                continue
            children = [j for j in out if is_contained(intervals[ranked[j]], _spans([ivs]))]
            need = int(toks[i]) - sum(int(toks[j]) for j in children)
        else:       # the order of the checks is that of the evaluation runs before the merge option
            children, need = [], int(toks[i])
        if budget is not None and need > budget - used:
            if overflow == "stop":
                break
            continue
        if not merge and use_dedup and is_contained(ivs, selected):
            continue
        if children:
            pos = out.index(children[0])
            out = [j for j in out[:pos] if j not in children] + [i] + [j for j in out[pos:] if j not in children]
            selected = _spans([intervals[ranked[j]] for j in out])
        else:
            out.append(i)
            if use_dedup:
                for f, s, e in ivs:
                    selected.setdefault(f, []).append((s, e))
        used += need
    return out


def _spans(ivs_list: Sequence[Sequence[Interval]]) -> dict[int, list[tuple[int, int]]]:
    spans: dict[int, list[tuple[int, int]]] = {}
    for ivs in ivs_list:
        for f, s, e in ivs:
            spans.setdefault(f, []).append((s, e))
    return spans


# ------------------------------------------------------------------------------------------------
# Formatting (plan §6.2)
# ------------------------------------------------------------------------------------------------

#: Issuing body named in the header when the document title does not name it (last ``;`` segment of
#: the URN authority). Titles of RFB acts read "INSTRUÇÃO NORMATIVA Nº 1.500, …", without the body.
AUTHORITY = {
    "secretaria.receita.federal": ("Receita Federal", ("SRF", "RFB", "Receita")),
    "secretaria.receita.federal.brasil": ("Receita Federal do Brasil", ("SRF", "RFB", "Receita")),
    "ministerio.fazenda": ("Ministério da Fazenda", ("MF", "Fazenda")),
    "procuradoria.geral.fazenda.nacional": ("Procuradoria-Geral da Fazenda Nacional", ("PGFN",)),
    "banco.central.brasil": ("Banco Central do Brasil", ("BCB", "Banco Central")),
    "ministerio.previdencia.social": ("Ministério da Previdência Social", ("MPS", "Previdência")),
    "comite.gestor.simples.nacional": ("Comitê Gestor do Simples Nacional", ("CGSN", "Simples")),
    "tribunal.superior.eleitoral": ("Tribunal Superior Eleitoral", ("TSE", "Eleitoral")),
    "conselho.administrativo.recursos.fiscais": ("Conselho Administrativo de Recursos Fiscais", ("CARF",)),
    "superior.tribunal.justica": ("Superior Tribunal de Justiça", ("STJ",)),
    "plenario": ("Supremo Tribunal Federal", ("STF",)),
    "advocacia.geral.uniao": ("Advocacia-Geral da União", ("AGU",)),
}
#: ``citacao`` values that are not a citation path (non-statutory text blocks).
NO_CITATION = {"", "texto"}


def authority_of(urn: str) -> str | None:
    """Issuing body of a LexML URN (``urn:lex:br:<authority>:<type>:…``); joint acts: the first body."""
    parts = (urn or "").split(":")
    if len(parts) < 4:
        return None
    return parts[3].split(",")[0].split(";")[-1]


def source_label(title: str, urn: str, annex: bool, citacao: str, parte: int, n_partes: int) -> str:
    """The ``{fonte}`` of a context block: title [— body] [— Anexo] [— citation] [(parte p de n)]."""
    out = [title]
    auth = AUTHORITY.get(authority_of(urn) or "")
    if auth and not any(a.lower() in title.lower() for a in auth[1]):
        out.append(auth[0])
    if annex:
        out.append("Anexo")
    if citacao.strip().lower() not in NO_CITATION:
        # the segmentation writes "Art. 71., § 1º" / "Parágrafo único., II": drop a period before a comma
        out.append(re.sub(r"\.(?=\s*,)", "", citacao.strip()).rstrip("."))
    label = " — ".join(out)
    return f"{label} (parte {parte} de {n_partes})" if n_partes > 1 else label


@dataclass(frozen=True)
class Template:
    """A versioned context template (``prompts/<name>.pt.md``): one block per text, joined by a blank
    line. The leading HTML comment documents the template and is not rendered."""

    name: str
    block: str
    sha256: str

    @classmethod
    def load(cls, prompts_dir: Path, name: str) -> "Template":
        path = Path(prompts_dir) / f"{name}.pt.md"
        if not path.exists():
            raise FileNotFoundError(f"context template {path} not found")
        raw = path.read_text(encoding="utf-8")
        block = re.sub(r"<!--.*?-->", "", raw, flags=re.S).strip("\n")
        for ph in ("{n}", "{fonte}", "{texto}"):
            if ph not in block:
                raise ValueError(f"{path}: placeholder {ph} missing")
        return cls(name, block, hashlib.sha256(raw.encode("utf-8")).hexdigest())

    def render(self, blocks: Sequence[tuple[str, str]]) -> str:
        """``blocks``: ``(fonte, texto)`` in context order → the context text (empty for no blocks)."""
        return "\n\n".join(self.block.replace("{n}", str(i)).replace("{fonte}", f).replace("{texto}", t)
                           for i, (f, t) in enumerate(blocks, 1))
