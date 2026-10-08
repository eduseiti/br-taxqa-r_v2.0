# Reference Fixes (Q144, §2.3 (c)) and Investigation of the Label-Only Article Chunks (N3)

**Generated:** 2026-10-08 19:02:26 (local time, from `date +%Y%m%d_%H%M%S`)
**About:** follow-up to `docs/20261008_133726_corpus_rebuild_review_answers.md` (**the review note**).
The user has already applied, outside this note: the SC Cosit 194/2015 and 140/2015 `.docx` repairs,
the removal of `in_rfb_1911_20191011`, `lei_3071_19160101` and `lei_5869_19730111`, the RIR/2018
LIVRO and Lei 6.766 "III-A" parser fixes (`lexml-parser-projeto-lei` `c587f6b`) and the linker fix.
This note covers what the user asked next:

1. drop the wrong reference 144-05 (review note N1);
2. fix the 10 pairs of review note §2.3 (c) by **changing the mapping**;
3. investigate how to fix the 435 label-only article chunks (N3), either in the Scala statutory
   parser or with the Python non-statutory parser.

Nothing was re-parsed, re-segmented or re-embedded. The only file changed is
`scripts/dataset/reference_overrides.json`.

---

## 0. Summary

- **Reference fixes: done in `reference_overrides.json` and verified with a scratch build.** One
  `drop` entry (144-05) and 8 `citations` entries cover the 10 pairs. No code change was needed. The
  review note said the override format had to be extended, but that was wrong: the existing
  `citations` override already replaces a reference's provisions. In the scratch build, missing
  fragments fall from 25 to 15. Each of the 10 pairs becomes `matchable: true`, and nothing else
  changes apart from what is listed in §1.3.
- **`dataset/` was not regenerated.** The local `../br-taxqa-document-fetcher` checkout is at
  `d4b7323` (2026-07-31). It does not contain `c7f4b8f`, the commit with the 27 canonical-record
  corrections that the committed dataset was built from (`build_report.json → git.fetcher_commit`),
  and `git fetch` fails here (no SSH key). A build against the stale list stops with 19 unresolved
  file names. **Pull the fetcher, then run the build** (§1.4).
- **N3 is three parser defects, not one, and all three are in the Scala parser:**
  - **D1 (`Block.scala`).** A bare article label ("Artigo 34", "ARTIGO 4º") never receives the
    paragraphs that follow it. The parser attaches following text to agrupadores, but no rule
    does this for articles. This produces the 438 label-only `Artigo` elements in 16 files. In
    some of these, the orphan text then becomes the `TituloDispositivo` of the *next* article.
  - **D2 (`LexmlRenderer.renderAnexoArticulado`).** In annexes rendered as `DocumentoArticulado`,
    every non-`Dispositivo` block after the first article is **silently dropped**. Decreto 8.624
    annex 1 loses 79 source paragraphs and Decreto 9.358 loses 43, mostly the D1 article bodies.
    IN SRF 81 (16) and IN RFB 1.548 (5) lose form text. This loss was not visible in the review
    note's "loose `TXT` chunks" description.
  - **D3 (`LexmlRenderer.renderAnexoBlocks`).** In annexes rendered as `DocumentoGenerico`, all
    paragraphs and tables are emitted first and all dispositivos after them, so text order is lost.
    The Decreto 5.128 annex has 53 article bodies stacked on top, followed by 85 label-only
    articles and loose alíneas.
- **Recommendation: fix D1–D3 in the Scala parser** and re-parse the affected files. The Python
  non-statutory parser is not an option. Even with `--emitter norma` forced on
  `decreto_56435_19650608.docx`, its statutory emitter refuses the document and falls back to a
  flat `DocumentoGenerico` with **0 `Artigo` elements**. That would remove the article ids that
  today's gold matches (143-01/144-01 `art37_cpt_ite2/ite4`, 149-02, 151-01, 160-02…), and it would
  make S1 = S2 = S3 for these documents.

---

## 1. Reference fixes

### 1.1 Q144: drop 144-05

| Field | Value |
|---|---|
| Reference | 144-05, `embedded`, cited title "Convenção de Viena sobre o Direito dos Tratados", v1 file `Convenção de Viena sobre o Direito dos Tratados.txt` → `decreto_7030_20091214` |
| Why wrong | The "Convenção de Viena" in Q144 is the Convention on Diplomatic Relations (Decreto 56.435/1965), which is already reference 144-01 (art. 37, items 2 and 4) |
| Override | `drop` entry `{question_number: "144", file: "Convenção de Viena sobre o Direito dos Tratados.txt"}` |

The same v1 file name is also used by Q160, where an existing `reassign` override maps it to
`decreto_8624_20151229`. So the file name is still in use and the "dead override" guard does not fire.
After the drop, **`decreto_7030_20091214` is cited by no question** (`documents_not_cited`). The
review note (§2.1) recommends removing it from the corpus. That has not been done: it is the user's
decision, like the other removals.

### 1.2 Review note §2.3 (c): change the mapping

Each pair now has a `citations` override (question + origin + v1 file → hand-written citation,
parsed by the same `citations.py`). Every target id was checked in the LexML before the edit:

| Reference(s) | Cited | Override citation | New fragment(s) | Text of the target (LexML) |
|---|---|---|---|---|
| 018-01 | Lei 9.250 art. 10, **inciso X** | `art. 10, inciso IX` | `art10_cpt_inc9` | "IX – R$ 16.754,34 … a partir do ano-calendário de 2015" (the amount the answer quotes) |
| 093-02, 093-06 | Lei 6.015 art. 167, I, **itens 24 e 25** | `art. 167, inciso I, alíneas "x" e "y"` | `…_ali24`, `…_ali25` | "x) das sentenças que nos inventários…", "y) dos atos de entrega de legados…" |
| 209-01 | Lei 6.015 art. 167, I, **item 7** (+ art. 220, V) | `arts. 167, inciso I, alínea "g", e 220, inciso V` | `art167_cpt_inc1_ali7` (+ `art220_cpt_inc5` unchanged) | "g) do usufruto e do uso sobre imóveis…" |
| 460-03 | IN RFB 2.178 art. 11, **§ 2º, inciso II** | `art. 11, § 3º, inciso II` | `art11_par3_inc2` | "II – bens móveis e direitos cujo valor unitário … inferior a R$ 5.000,00" |
| 683-02 | Lei 12.350 art. 45, **§ 3º** | `art. 45` | `art45` | Art. 45 rewrites art. 8 of Lei 9.959; the § 3º is inside the quoted wording |
| 708-01 | Lei 11.033 art. 3º, incisos II a V, **e parágrafo único** | `art. 3º, incisos II a V, e § 1º` | `art3_cpt_inc2…inc5`, `art3_par1` | "§ 1º … (Parágrafo único acrescido pela Lei nº 11.196 … e transformado em § 1º pela Lei nº 14.754…)" |
| 708-11 | Lei 11.033 **parágrafo único do art. 3º** | `§ 1º do art. 3º` | `art3_par1` | same |

Every entry's `reason` starts with "user fix (2026-10-08, review answers note §2.3 (c))" and gives
the diagnosis. The `provisions_note` of each reference carries this reason. 018-01 maps to inciso IX
as the user decided. The review note's other option, checking Planalto for an inciso X that this
`.docx` lacks, was not taken.

### 1.3 Verification (scratch build)

`build_v2_dataset.py` reads `reference_overrides.json` next to itself, so the check ran on a copy
in the session scratchpad. The copy had 19 stand-in `files` entries for the unresolved names (each
pointing at the `document_id` the committed dataset gives that file name), and
`ROOT` pointed at this repository. Diff against the committed `dataset/references.jsonl`:

| Change | References |
|---|---|
| removed | 144-05 |
| provisions changed (all now `matchable: true`) | 018-01, 093-02, 093-06, 209-01, 460-03, 683-02, 708-01, 708-11 |
| `document_id` changed | 150-03, 280-08: **artifacts of the stale fetcher list** (these are two of the 27 `c7f4b8f` corrections), not of this change |

Counts: references 1,917 → 1,916; `fragment_ids_missing` 25 → **15** (the 13 treaty pairs of §2.3 (a)
plus the 2 N3 pairs 142-03 and 157-01); `documents_not_cited` gains `decreto_7030_20091214`. (It also
gains `ad_pgfn_3_20160330`, another stale-list artifact, and loses the three removed documents.)
`python3 -m pytest scripts/dataset/tests`: 36 passed.

### 1.4 To do before the rebuild

```bash
git -C ../br-taxqa-document-fetcher pull          # must contain c7f4b8f
python3 scripts/dataset/build_v2_dataset.py --questions ../br-taxqa-document-fetcher/questions_QA_2024_v1.1.json
```

The default `--questions` path (`../questions_QA_2024_v1.1_manual_fix.json`) does not exist in this
checkout. `../br-taxqa-document-fetcher/questions_QA_2024_v1.1.json` has the SHA-256 recorded in
`build_report.json` (`097abfc4…`), so it is the same input. Check after the build that
`git.fetcher_commit` is `c7f4b8f…` and that the diff matches §1.3 without the two stale-list rows.
The build should run **after** the re-parse (§2), because the 2 N3 pairs become matchable only then.

---

## 2. N3: the label-only article chunks

### 2.1 What the XML looks like

A scan of `lexml/articulados/*.xml` for `Artigo` elements with no text outside their `Rotulo`
finds **438 in 16 files**: the review note's 14 files, plus `in_rfb_1505` (2, inside amendment
text, and the document is a removal candidate) and `mp_2189-49` (1, a revoked article inside
amendment text: correct). Classified by the article's next sibling:

| Next sibling | Count | Example | Source | What happened |
|---|---:|---|---|---|
| `p` (body text) | 286 | `decreto_56435` art34, `decreto_67542` art10 | `Artigo 34` / `O agente diplomático gozará…` / `a) …` | Body left as a sibling `p`, which also blocks the following alíneas from being absorbed |
| none (last child of its parent) | 69 | `decreto_50656` art1 (in `cap1`) | `CAPÍTULO I` / `Nome e objeto` / `ARTIGO 1` / two body paragraphs / `CAPÍTULO II` | The chapter absorbs the article but stops at the paragraphs, which end up *after* the chapter |
| `Artigo` | 51 | `decreto_50656` art43; `decreto_5128` annex art4–art7 | `Artigo 43` / body / `Artigo 44` / body | Body of art. 43 became the `TituloDispositivo` of art. 44 (step `identificaTitulos`); in the 5128 annex the bodies were moved to the top (D3) |
| `Item` / `Alinea` / `Inciso` | 24 | `decreto_9358` annex 1 art102 | `Artigo 102` / `Composição, funcionamento e reuniões … (Const. 17)` / `1. …` | The article title (after the label, treaty style) is a sibling `p`, so the numbered items are not absorbed; in the articulated annex the title is then dropped (D2) |
| `Capitulo` | 5 | `decreto_8624` annex 1 art15 | `Artigo 15` / `Transparência e Prestação de contas` / `O Banco assegurará…` / `Capítulo IV` | Title and body **dropped** (D2) |
| inside `Alteracao` | 3 | `in_rfb_1505`, `mp_2189-49` | n/a | Not a defect (amendment text, revoked article) |

### 2.2 Root causes in `../lexml-parser-projeto-lei`

The articulation pipeline is `ProjetoLei.parseArticulacao` (`ProjetoLei.scala:290-345`):
`reconheceDispositivos` → `reconheceOmissis` → **`identificaTextosAgregadores`** (6) →
**`identificaTitulos`** (7) → `limpaParagrafosVazios` → **`organizaDispositivos`** (8) → …

**D1: a bare article label gets no body** (`block/Block.scala`)

- Step 6 (`identificaTextosAgregadores`, `Block.scala:953`) appends the following non-empty paragraphs
  to an agrupador (`d.rotulo.isAgregador`) as its name. No equivalent exists for `RotuloArtigo`.
- Step 7 (`identificaTitulos`, `Block.scala:990`) takes a paragraph *before* any dispositivo as
  its title when it has no `.`, `;` or `:` (`podeSerTitulo`). This is the Brazilian style, where the
  epígrafe sits above "Art. N". With D1, the orphan body of article N that has no such punctuation becomes the
  title of article N+1 (`decreto_50656` art44).
- Step 8 (`organizaDispositivos.agrupa`, `Block.scala:658`) attaches a following paragraph to an
  *agrupador* with empty content (`Block.scala:697`). It also continues an article whose caput
  ends in `,` `;` `-` (`Block.scala:708`), but it does nothing for an article with **no** content.
  `spanNivel` then stops at that paragraph, so any alíneas or items after it stay siblings.
  Articles whose text starts with "1." work (Vienna art. 37 → `art37_cpt_ite2`). The numbered
  paragraphs are dispositivos, so `spanNivel` absorbs them.

**D2: articulated annexes drop loose paragraphs** (`output/LexmlRenderer.scala:458`,
`renderAnexoArticulado`)

```scala
val (leading, rest) = a.blocks.span(!_.isInstanceOf[Dispositivo])
val dispositivos = rest.collect { case d: Dispositivo => d }   // Paragraphs in `rest` are discarded
```

Leading paragraphs go to the `Preambulo`. Every `Paragraph` after the first `Dispositivo` is lost
without a warning. `isArticulatedAnexo` (line 425) chooses this path whenever the annex has only
`Dispositivo`s and `Paragraph`s. A text-coverage scan (each source paragraph of ≥ 40 characters, label
stripped, searched in the normalized text of the document's XML files) over the 17 documents with
`DocumentoArticulado` annexes:

| Document | Source paragraphs lost | What they are |
|---|---:|---|
| `decreto_8624_20151229` (NDB agreement, cited by Q160) | 79 | article titles and bodies of the label-only articles |
| `decreto_9358_20180430` (UPU convention, Q150) | 43 | article titles ("Composição, funcionamento…"), dash items |
| `in_srf_81_20011011` (cited by 20+ questions) | 16 | annex form fields (the cited articles are in the main file and complete) |
| `in_rfb_1548_20150213` (Q058, Q059) | 5 | annex model-form lines |
| `decreto_lei_5452_19430501` (CLT) | 3 | odd labels ("­­­I -" with soft hyphens, "§ lº", "§ 10º"), a different cause, not D2 |
| `in_srf_698`, `in_rfb_2060`, `in_srf_256` | 1–2 | table/header noise |

**D3: generic annexes reorder text** (`output/LexmlRenderer.scala:395`, `renderAnexoBlocks`)

```scala
val (dispositivos, simples) = a.blocks.partition { case _: Dispositivo => true; case _ => false }
...
NodeSeq.fromSeq(simplesNodes) ++ dispNodes          // all p/table first, all dispositivos after
```

`decreto_5128_20040706.anexo1.xml` (OEI seat agreement, Q157) went this way because it holds a
non-paragraph block. Its `PartePrincipal` has 53 `p` (the preamble *and* every article body) and
then 85 dispositivos (label-only articles and loose alíneas). No text is lost, but the chunks are
meaningless: alínea "d" of art. 21 (cited by 157-01) is a loose `ALI` chunk far from its caput. Other
generic annexes with this shape (`lei_12249` annexes 2–9, `lei_comp_123` annexes 1–5…) have a few
header paragraphs and one table-like dispositivo, so the reordering is harmless there. Check them
when re-parsing anyway.

### 2.3 Why not the Python non-statutory parser

`lexml_parser_non_statutory` has a statutory emitter (`render/norma.py`, `render_norma_checked`).
It is built to *refuse* articulation it cannot prove ("statutory detection's main job is refusing
false positives"). Run on the Vienna convention:

```bash
PYTHONPATH=src python3 -m lexml_nonstat parse --emitter norma \
    --urn 'urn:lex:br:federal:decreto:1965-06-08;56435' --summary -o <scratch> \
    ../br-taxqa-r_v2.0/original/articulados/decreto_56435_19650608.docx
# route: generico (0.75), emitter: generico, hierarchy: flat (0.00)
```

The output is a flat `DocumentoGenerico` with 219 `p` and **0 `Artigo` elements**, and "Artigo 34" is
a plain `<p>`. Moving the 14 files to the non-statutory route would therefore:

- remove every article id from these documents. The article and provision gold that matches today
  would become unreachable: 143-01 and 144-01 `art37_cpt_ite2/ite4`, 149-02/150-13 `art6`, 151-01
  `art47`, 151-02 `art15`, 153-02 `art141`, 160-02 `art34_cpt_ali2`. The gold matcher does not
  support article ids in a `DocumentoGenerico` (review note §2.3 (a));
- make every chunk a `TXT`, so S1 = S2 = S3 = S2c = S4 for these documents, which removes them from
  the segmentation comparison;
- still not fix D2/D3 for the statutory documents that are not treaties (IN SRF 81, IN RFB 1.548).

The Scala parser already recognizes "Artigo N" / "ARTIGO N" labels and builds the right ids. Only the
attachment and rendering steps are wrong, so the fix belongs there.

### 2.4 Proposed fix (Scala, `../lexml-parser-projeto-lei`)

**F1: attach the text after a bare article label (D1).** Add a new pass between step 6 and step 7.
It must run before `identificaTitulos`, which would otherwise take the orphan body as the next
article's title. For a `Dispositivo` with `RotuloArtigo`, empty content (`None` or a blank
`Paragraph`), no sub-dispositivos, and outside `Alteracao`, followed (after empty paragraphs) by
non-empty paragraphs:

1. **Title (treaty style).** The first paragraph becomes `titulo` (`TituloDispositivo`) when it is
   short (≤ 150 characters), does not end in `.`, `;`, `:` or `,`, and is followed by another
   non-empty paragraph or by a sub-article dispositivo (`§`, inciso, alínea, item). Examples:
   "Composição, funcionamento e reuniões do Conselho de Administração (Const. 17)", "Transparência e
   Prestação de contas", "Utilização de recursos". Short sentences that end in a period stay caput
   text ("O Banco assegurará…", "O presente Tratado terá duração ilimitada.").
2. **Caput.** The following non-empty paragraphs up to the next `Dispositivo` become the caput. The
   model holds one `Paragraph` per dispositivo, so join them with a space, as step 6 does for
   agrupadores. (The rigid schema allows several `p` in a dispositivo, so a later renderer change
   could keep them separate.) Stop at closing formulas so the treaty's final clause is not swallowed
   into the last article: `^(EM FÉ DO QUE|EM TESTEMUNHO|FEITO EM|Feito em|Assinado|Pel[oa] Governo)`.
3. Nothing else changes. Step 8's `spanNivel` then absorbs the alíneas, items and incisos that follow
   (as it already does for Vienna art. 37), which gives `art34_cpt_ali4` and `art21_cpt_ali4`.

**F2: never drop text in articulated annexes (D2).** In `isArticulatedAnexo`, also require that
no non-empty `Paragraph` follows the first `Dispositivo`. Otherwise fall back to
`renderAnexoGenerico`, as the method already does for tables. After F1 the treaty annexes no
longer have such paragraphs and stay articulated. Form annexes (IN SRF 81, IN RFB 1.548) fall back
and keep their text. Also log the fallback to the `.err.log`, so a future loss is visible.

**F3: keep the order in generic annexes (D3).** `renderAnexoBlocks` should walk `a.blocks` in
order and emit each maximal run of `Dispositivo`s through `renderBlocks` at its own position. The
table ids keep their running index.

**Tests.** Add unit tests next to `RotuloParserTest` with small block lists: (a) a bare label + body + alíneas;
(b) a bare label + title + numbered items; (c) a bare label + body at the end of a chapter;
(d) Brazilian-style title above "Art. N" (must be unchanged); (e) the last article + "EM FÉ DO QUE";
(f) inside `Alteracao` (must be unchanged). Add one renderer test each for F2 and F3.

**Expected effect on the corpus.**

| Measure | Now | After F1–F3 |
|---|---:|---|
| label-only `Artigo` outside `Alteracao` | 435 (14 files) | ≈ 0 (left-overs listed and reviewed) |
| cited article items on an empty `ART` chunk | 5 (142-03, 151-01, 151-02, 153-02, 157-01) | 0 |
| `fragment_ids_missing` | 15 (after §1) | 13: 142-03 `art34_cpt_ali4` and 157-01 `art21_cpt_ali4` become matchable |
| source paragraphs lost in articulated annexes | 143 (8624, 9358, IN SRF 81, IN RFB 1.548) | 0 |
| loose `TXT`/`ALI`/`DSP` chunks in these 14 files | many | only the real preamble and closing text |

**Verification after the re-parse.** Re-parse all statutory files, not only the 14, and diff the
XML against the current `lexml/articulados/`. Only the 14 treaty files, the 5 documents with D2
losses and generic annexes with interleaved dispositivos should change. Every other change is a
regression of F1's title rule. Then re-run `scripts/lexml/audit_article_coverage.py`, the
label-only scan and the text-coverage scan from this note.

### 2.5 Related, not fixed here

- `decreto_lei_5452` (CLT): 3 paragraphs lost to unusual labels ("­­­I -" with soft hyphens, "§ lº"
  with a lowercase L, "§ 10º"). This is a different cause and needs its own look.
- The treaty decrees of review note §2.3 (a) (O1) have no treaty text, or have labels the parser
  does not read ("Artigo I…XXV" in some annexes, `decreto_57942` without markers). F1 does not
  change them.

---

## 3. Corpus state to settle before the re-parse

- The LexML files of the removed documents are still in `lexml/articulados/`:
  `in_rfb_1911_20191011` (61 files), `lei_3071_19160101`, `lei_5869_19730111`. Delete them with
  their `.err.log` files, or make sure the re-parse and `segment_all.py` start from an empty
  output folder. Otherwise their chunks come back.
- Still pending from the review note, these are the user's decisions:
  - remove `in_rfb_1505_20141031` and `decreto_7030_20091214` (both cited by no question after this
    note);
  - add the Q029 service-page references and re-extract Q576's references (N2);
  - O5 and O7: the test snapshot and the referee cache.
- Suggested order: (1) pull the fetcher; (2) F1–F3 + tests in `../lexml-parser-projeto-lei`;
  (3) re-parse statutory documents (all) and non-statutory documents (SC 140/194); (4) dataset build
  (§1.4); (5) segmentation, embedding of the new texts, retrieval and evaluation.
