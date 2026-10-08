"""Caput text variants of paragraph-family rows (caput plan C3, docs/20261005_184116_*).

Since decision D-A (2026-10-05) the XSL writes paragraph-family rows (PAR, and INC/ALI/ITE under a
``Paragrafo`` of an ``Artigo``) **without** the caput sentence: these are the ``base`` rows of
S1–S3. Decision D-B adds the old texts back as a second **variant** of the same unit, used by S4
(and the free filter S2c):

    base   Art. 8º § 2º O disposto na alínea a do inciso II: I – …
    caput  Art. 8º A base de cálculo … somas: § 2º O disposto na alínea a do inciso II: I – …

A variant row copies every column of its base twin except ``Texto``, ``texto_sha256``, the token
counts and ``chunk_id`` (``<stem>#c<seq>`` next to the base ``<stem>#<seq>``); ``variante`` is
``caput`` and ``contexto_ids`` holds the id of the caput whose text was added.

The variants are built in step 6 of ``segment_all.py`` from the element of each XSL row, so the
base text is checked on the way: it must equal ``prefix + caminho(e) + texto(e)`` with no caput
text, which is the XSL/Python parity of the ``caput_em_paragrafo='nao'`` path for every
paragraph-family row of the corpus.

Rows that get no variant: everything outside the paragraph family, split ART/DSP parts (their HEAD
keeps the caput sentence, caput plan §1, Q2), and paragraphs with no ``Caput`` sibling (orphan
structures: S4 then falls back to their ``base`` row). ``caput_completo`` (S5, full caput) is not
built yet (caput plan Q3).
"""

from __future__ import annotations

from common import L, caminho, child_elems, in_article_paragraph, norm, texto

VARIANTS = ("caput",)
FAMILY_TIPOS = ("PAR", "INC", "ALI", "ITE")


def article_of(e):
    """The Artigo whose Paragrafo holds e (e is, or is inside, that Paragrafo)."""
    for a in [e, *e.iterancestors()]:
        if L(a) == "Paragrafo" and L(a.getparent()) == "Artigo":
            return a.getparent()
    return None


def caput_variant(e, tipo: str, base_text: str) -> tuple[str, str] | None:
    """(variant text, caput id) for the XSL row of element e, or None if it gets no variant.

    Raises if ``base_text`` is not the caput-free text Python computes for e (parity)."""
    if tipo not in FAMILY_TIPOS or not in_article_paragraph(e):
        return None
    art = article_of(e)
    caputs = child_elems(art, "Caput") if art is not None else []
    if not caputs:
        return None
    body = norm(caminho(e, "nenhum") + " " + texto(e))
    if not base_text.endswith(body):
        raise ValueError(f"{e.get('id')}: base text differs from the caput-free Python text")
    prefix = base_text[: len(base_text) - len(body)]
    variant = prefix + norm(caminho(e, "frase") + " " + texto(e))
    if variant == base_text:  # caput without its own p: nothing to add
        return None
    return variant, caputs[0].get("id", "")
