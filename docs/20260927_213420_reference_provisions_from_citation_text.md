# Reference Provisions Parsed from the Citation Text (fix of `references.jsonl`)

**Generated:** 2026-09-27 21:34:20 (local time, from `date +%Y%m%d_%H%M%S`)
**Status:** implemented and run. `dataset/references.jsonl` and `dataset/build_report.json` rebuilt.
**Corrects:** `docs/20260927_180401_dataset_v2_format_and_reference_fixes.md` §3.2 (the
`provisions` design) and its schema in `dataset/README.md`.

---

## 1. The error

The v2.0 `references` rows stored each cited article with **flat lists** of paragraphs, incisos,
alíneas and items, copied from v1.1's LLM-extracted `formatted_references`. The flat lists lose the
nesting, so two different citations got the same shape:

| Citation in the Q&A document | v2.0 (before) | Meaning |
|---|---|---|
| Q001: "Lei nº 11.482/2007, art. 1º, **inciso X e parágrafo único**" | `paragraphs: ["único"], incisos: ["X"]` | two sibling units: `art1_cpt_inc10` and `art1_par1u` |
| Q051: "IN RFB nº 2.178/2024, art. 12, **§ 1º, inciso II**" | `paragraphs: ["1º"], incisos: ["II"]` | one unit: `art12_par1_inc2` |

575 rows had such lists. Of the 140 (article, paragraph, inciso) combinations, the LexML alone
settles 95. In 38, both readings exist in the XML (for example `art12_cpt_inc2` and
`art12_par1_inc2`), and in 7 neither does.

**How it happened.** The dataset note (§3.2) said: *"v1.1 lost which inciso belongs to which
paragraph, and that cannot be recovered reliably"*, and deferred provision-level ids to
`lexml-linker`. Both parts were wrong:

- The nesting is in the **citation text itself**, which v1.1 keeps (`references`,
  `embedded_references`, carried into v2.0 as `references_text` / `embedded_references_text`).
  Word order gives it: "art. 12, § 1º, inciso II" is a path, "inciso X e parágrafo único" is a
  list of siblings, and "inciso II do § 1º do art. 162" is a path written in reverse.
- `lexml-linker` is unrelated to the gold references. It is for citations in *generated* answers,
  and it does not even recognise the Q&A style, where the act comes first
  ("Lei nº 11.482, de 31 de maio de 2007, art. 1º, …" gives no URN).

The builder simply never parsed the text. It also inherited two other v1.1 extraction errors, found
by the fix below: **ranges cut short** ("arts. 128 a 153" was stored as art. 128 only), which
together with a few treaty articles left 262 article ids missing from 33 rows, and **invented articles** for acts cited without any article (11
article ids in 5 rows).

## 2. The fix

### 2.1 Parser (`scripts/dataset/citations.py`)

A parser for the citation style of the Q&A document:

1. **Chains.** `find_chains` finds each run of provision tokens: `art.`/`arts.`/`artigo`, `§`/`§§`/
   `parágrafo`, `caput`, `inciso`, `alínea`/quoted letters, `item`/`itens`, `Anexo`, `Capítulo`/
   `Seção`/`Título`. The values can be ordinals, thousands (`1.042`), suffixes (`12-A` → `art12-1`),
   `único`, roman numerals, letters and decimals (`item 19.1`). The joins are `,`, `e`, `, e`, ranges
   (`a`/`ao`/`até`, expanded up to 300), and the genitive `do`/`da`/`de seu`.
2. **Reverse order.** A genitive link ("inciso II do § 1º do art. 162") is rewritten into a forward
   path (`art162_par1_inc2`).
3. **Nesting.** A stack puts each unit under the nearest open unit of a higher level. An
   inciso, alínea or item with no paragraph above it belongs to the caput (`_cpt_`). A unit is
   cited when nothing is attached under it, or when a child follows it with "e" ("art. 26 e
   parágrafo único" cites both).
4. **Values without a keyword.** A roman numeral is an inciso and a letter is an alínea. A bare
   arabic number continues the last open plural list ("arts. 2º, inciso IV, 4º e 6º" → articles). A
   list closed by "e" takes no more values ("§§ 1º e 4º, e 7º" → art. 7º). A number followed by
   `caput`/`§` is an article ("§§ 2º a 4º, 16, caput" → art. 16).
5. **Attribution to the cited acts** (`attribute`):
   - Each v1.1 reference is found in the text by its number (`nº 9.250`); the RIR/2018 by its name;
     unnumbered acts (Constituição, conventions) by the head of the title.
   - A chain followed by "do/da <act>" goes to the next act mention. Any other chain goes to the
     closest mention before it. In the explicit block, "…; e art. 6º" continues the previous act.
   - Mentions that are not the cited act are skipped: "aprovado pelo Decreto nº 9.580",
     "alterada pela Lei nº …".
   - Mentions of acts that no v1.1 reference claims become anonymous anchors, so their provisions
     are not given to a neighbour. The build **fails** if any chain is left without a reference.

### 2.2 New `references` fields

`provisions` is now **one row per cited unit**, with the nesting in the LexML id (the same scheme
as the chunks' `unidade_id` / `cobre_ids`):

```json
"citation_text": ["Lei nº 11.482, de 31 de maio de 2007, art. 1º, inciso X e parágrafo único"],
"article_ids": ["art1"],
"provisions": [
  {"label": "art. 1º, inciso X", "article_id": "art1", "fragment_id": "art1_cpt_inc10",
   "annex": null, "lexml_file": "lexml/articulados/lei_11482_20070531.xml"},
  {"label": "art. 1º, parágrafo único", "article_id": "art1", "fragment_id": "art1_par1u",
   "annex": null, "lexml_file": "lexml/articulados/lei_11482_20070531.xml"}],
"provisions_note": null
```

| Field | Content |
|---|---|
| `citation_text` | the source text the provisions were parsed from (the `;`-pieces of the reference block, or the embedded citation strings), so the gold can always be checked against the source |
| `article_ids` | distinct cited articles (row level; replaces `provisions[].article_ids`) |
| `provisions[].label` | canonical citation path ("art. 736, parágrafo único, inciso II") |
| `provisions[].fragment_id` | LexML id with the full path; `null` when the unit has no id form (annex items, chapters, numbered items of pareceres, "inciso 1.8") |
| `provisions[].annex` | "Anexo II" etc., when the unit is in an annex |
| `provisions[].lexml_file` | the LexML file holding `fragment_id`: the main file or an annex file (for the RIR/2018 and "do Anexo" citations the annex files are searched first); `null` when not found |
| `provisions_note` | the reason, when the provisions come from a hand override (§2.3) |

Removed: `provisions[].article`, `.article_ids`, `.paragraphs`, `.incisos`, `.alineas`, `.items`.
`annexes` stays (v1.1 annex labels plus annex-only units from the text).

### 2.3 Hand overrides (`reference_overrides.json → citations`)

For 5 references the text can't be parsed as written. Each entry gives the source wording, the
citation parsed in its place, and the reason:

| Ref | Source | Parsed as | Why |
|---|---|---|---|
| Q143, Q144 Convenção de Viena | "art. 37, 2" / "art. 37, 2 e 4" | "art. 37, caput, item(s) 2 (e 4)" | treaty numbering; the LexML holds the numbered paragraphs as `art37_cpt_ite2` |
| Q154 Decreto 86.084 | "art. IX, 2" | "art. IX, item 2" | same treaty numbering |
| Q511 IN SRF 83 | "art. 5º; § 2º, inciso III" | "art. 5º e § 2º, inciso III" | `;` typo for `,`; both readings kept |
| Q517 Lei 11.524 (embedded) | "o artigo 3º da referida lei … o inciso III do § 1º do mesmo artigo" | "art. 3º; inciso III do § 1º do art. 3º" | the law is named elsewhere in the answer |

## 3. Cross-check against v1.1

Per reference, the articles found in the text were compared with v1.1's article lists before the
lists were dropped:

| Result | References |
|---|---:|
| Same articles | 1,326 with articles + 520 citing the whole act |
| Text has more articles (262 article ids, almost all from ranges v1.1 cut short) | 33 |
| v1.1 has articles the text does not (`build_report.json → validation.v1_article_ids_not_in_citation_text`) | 5 |

The 5 v1.1-only cases were checked against the whole answer text. None of those articles appears
anywhere, so they are LLM inventions and are dropped:

- Q150 UPU (art. 1 and art. 10): the source cites only "UPU".
- Q239 FGTS (7 articles): the source is "Lei do Fundo de Garantia do Tempo de Serviço (FGTS)".
- Q652 Lei 9.615 (art. 1): the act is cited without articles.
- Q611 IN SRF 107 (art. 1): the source cites "inciso 1.8". The unit is kept with its label and no
  id.

## 4. Results

`python3 scripts/dataset/build_v2_dataset.py`:

| | Count |
|---|---:|
| References (unchanged) | 1,919 |
| References with provisions | 1,349 (2,319 units) |
| Units by depth: article / § or caput / inciso / alínea / item | 1,445 / 392 / 375 / 65 / 6 |
| References with sub-article units | 567, in 366 questions |
| Cited article ids | 2,052 (was 1,801) |
| Units found in the main LexML file / in an annex file | 1,626 / 615 |
| Units without an id form | 36 |
| Units whose `fragment_id` is not in the LexML | 41 (`validation.fragment_ids_missing`) |

The 41 missing fragments are XML or source issues, not parser errors:

- **Known gaps** (dataset note §7.1–7.2): the treaty decrees with an empty `<Articulacao>` (Q149–159),
  MP 2.158-35 art. 24, Lei 13.043 art. 16, Lei 11.941 art. 56, Lei 6.404 art. 252 and
  Decreto 59.566 art. 3.
- **New, seen at provision level:**
  - Lei 9.250 art. 10: the XML has incisos I–IX only, but Q018 cites inciso X.
  - Lei 6.015 art. 167, I: the numbered items were parsed as alíneas (`ali24`); Q093 and Q209 cite
    items.
  - IN RFB 2.178 art. 11, § 2º: the XML has no incisos (Q460).
  - Lei 11.033 art. 3º: the XML (current text) has §§ 1º–4º, but Q708 cites a "parágrafo único".
  - Lei 12.350 art. 45, § 3º: the § 3º is inside an amendment block
    (`art45_cpt_alt1_art8_par3`).

Tests: `scripts/dataset/tests/test_citations.py` (36 cases taken from the Q&A document), run with
`python3 -m pytest scripts/dataset/tests`.

## 5. Consequences

- **Provision-level retrieval gold is available now.** A retrieved chunk hits a gold unit when some
  id in its `cobre_ids` equals the `fragment_id` or is its ancestor (prefix up to a `_`), within
  the same `lexml_file`. The RAG plan (`docs/20260927_204356_rag_pipeline_implementation_plan.md`
  §4.1) no longer defers this level.
- The legal-provision score of the answers (nugget plan §4.5) gets nested gold fragment ids, and
  the matcher can use the same file-level match.
