# Segmentation Strategies for the BR-TaxQA-R v2.0 RAG Experiments

**Generated:** 2026-09-23 19:38:52 (local time, from `date +%Y%m%d_%H%M%S`)
**Goal:** choose which segmentation strategies to compare when evaluating whether hierarchical
segmentation of the LexML-parsed legal documents gives better chunks for a RAG system that answers
the **prose** (not multiple-choice) questions of BR-TaxQA-R. System answers are compared against
the gold answers in `docs/P&R IRPF 2024 - v1.0 - 2024.05.03.pdf` using nuggets.

**Decision (summary):**

| ID | Strategy | Status |
|---|---|---|
| **S1** | Article (flat) + metadata | Baseline |
| **S2** | Article + sub-article units (caput, §, inciso, alínea, item), each with its **ancestor path** (no siblings) + metadata | Main hypothesis |
| S3 | S2 + grouping chunks (parte, livro, título, capítulo, seção, subseção) | Optional |

All three come from **one** embedding run per embedding model (S1 and S2 are filters over the S3
chunk set), which saves budget for sweeping context size, the generator LLM and the embedding model.

**Sources discussed:**

- Fernandes, Lima, de Martim, Oliveira, Lotufo, Pereira — *Structural Segmentation for Brazilian
  Legal Document Retrieval* (`../Artigo chunks legislação.pdf`), referred to below as **[F]**.
- Oliveira Lima, J.A. — *Unlocking Legal Knowledge with Multi-Layered Embedding-Based Retrieval*,
  arXiv:2411.07739 (2024), referred to below as **[L]**.
- `../lexml-parser-projeto-lei/scripts/GeraCSVporArtigoPorAgrupador.xsl` (applied in batch by
  `run_segmentation_csv.py`), referred to below as **the XSL**.

---

## 1. Strategies evaluated in [F]

[F] adopts the multi-layered segmentation of [L] (§3.2) with these levels:

| Level | Content |
|---|---|
| Document | Whole text (used only as the baseline, from the Juá benchmark) |
| Document component | Main normative text; non-normative components (tables, annexes, justification of bills) |
| Basic unit hierarchy | Each grouping of articles (subseção, seção, capítulo, título, livro, parte) |
| Basic unit | Each article, with all its subdivisions |
| Basic unit component | Each caput and each paragraph |
| Enumeration | Each inciso / alínea / item |

Each chunk can be enriched with context: **document title + summary (ementa)** ("metadata") and the
**titles of all enclosing groupings**.

The four representation strategies (Table 1 of [F]):

| Strategy | Chunks | Context |
|---|---|---|
| Hierarchical Chunks | All levels from document component to enumeration | Title + Summary + Hierarchy |
| Core Chunks + Full Context | Articles + non-normative document components | Title + Summary + Hierarchy |
| Core Chunks + Metadata | Same | Title + Summary |
| Core Chunks + No Context | Same | None |

Findings relevant here:

- Context-enriched segmentation beats whole-document indexing for dense retrievers; **No Context
  is consistently worse**.
- There is **no clear evidence that hierarchy titles help beyond title + summary**; [F] recommends
  Core Chunks + Metadata.
- Segmentation does not consistently help BM25.
- Retrieval uses max-score aggregation of chunk scores into document scores (an IR evaluation, not RAG).

## 2. What the XSL covers

The XSL writes one CSV row per structural unit (`Tipo, Rotulo, Num_Inicio, Num_Final, Texto, urn`).
`Texto` = `[ <context> ] <content>`. Content inside `Alteracao` (quoted amending text) gets no rows
of its own.

| [F] level | XSL `Tipo` | Context added |
|---|---|---|
| Document | — not produced | — |
| Document component (main text, annexes, tables, justification) | — **not produced** | — |
| Basic unit hierarchy | `PRT, LIV, TIT, SBT, CAP, SEC, SSC` | Ementa + `NomeAgrupador` of the unit and its ancestors |
| Basic unit | `ART` | Ementa + enclosing `NomeAgrupador`s |
| Basic unit component | `CPT`, `PAR` | Ementa + enclosing `NomeAgrupador`s |
| Enumeration | `INC, ALI, ITE` | Ementa + article label + text of the parent caput/§/inciso/alínea (no grouping names) |

Coverage of the [F] strategies:

- **Hierarchical Chunks — partial.** Four of the five evaluated levels are produced. Missing or
  different:
  - no document-component chunks;
  - the document **title (Epígrafe)** is not in the text (only the filename appears in `Rotulo`);
  - groupings contribute only their name (`NomeAgrupador`), not their label ("CAPÍTULO I");
  - enumeration chunks get the parent text instead of the grouping names.
- **Core Chunks + Full Context — covered** (`Tipo == "ART"`), with the same title/label limits and
  no non-normative components (for statutes that means annexes and tables).
- **Core Chunks + Metadata — not directly.** Needs an XSL variant that drops the `NomeAgrupador` loop
  in the `ART` block, or post-processing that keeps only the ementa part of the prefix.
- **Core Chunks + No Context — derivable** by stripping the `[ ... ] ` prefix (breaks if an ementa
  contains `]`).

To match [F]'s context exactly: add `//Epigrafe` next to `$escopo`, and join each ancestor's
`Rotulo` with its `NomeAgrupador`.

## 3. What [L] proposes

[L] does not compare several segmentation schemes. It proposes one and compares it against a flat
baseline in a qualitative RAG case study on the Brazilian Constitution (8 questions,
text-embedding-3-large at 256 dimensions, gpt-4-turbo-preview, chunk relevance graded
essential / complementary / unnecessary).

1. **Flat chunking by article** — "traditional method of uniform fragments"; 276 chunks for the
   Constitution.
2. **Multi-layered chunking** (§4.1) — the six levels listed in §1 above; 2,954 chunks for the
   Constitution.
3. **Semantic chunking** (semchunk-style recursive splitting) — mentioned and criticised for
   flattening the hierarchy; not evaluated. Footnote 2 also mentions averaging the embeddings of
   semantic chunks for texts longer than the model's token limit.

Details that matter here:

- **Context enrichment in [L] is limited to enumerations:** incisos, alíneas and itens are embedded
  with the text of their ancestors up to the caput or paragraph (footnote 7:
  "[A República Federativa … tem como fundamentos:] dignidade da pessoa humana"). Prepending title,
  ementa or grouping names is new in [F].
- **The XSL is most likely [L]'s implementation.** Its enumeration context matches footnote 7, and
  its `Rotulo` format matches the chunk labels in [L]'s appendix ("Art. 29., caput, Inciso X",
  "TÍTULO IV, CAPÍTULO II, Seção V, Subseção I"). The ementa + `NomeAgrupador` prefix looks like a
  later addition.
- The worked example in [L] §4.1 uses other level names and counts incisos under the
  article-component level, which is inconsistent with the layer list.
- No document-level or main-text chunk ever appears among the retrieved chunks, so the experiment
  apparently used the four levels the XSL produces.
- **Retrieval-side filtering (§4.2):** 2,500-token budget; drop chunks whose similarity is more than
  25% below the top hit; drop a chunk whose text is already covered by a higher-scored chunk (e.g.
  skip "Art. 5, § 1, I" if "Art. 5, § 1" was retrieved); keep at least 7 chunks.

## 4. Constraints of this experiment

- The article-level "uniform fragments" segmentation is the baseline.
- Gold-answer references in the QA document go down to the enumeration level, so any hierarchical
  strategy must reach inciso / alínea / item.
- The embedding budget is limited, and it must also cover sweeps over the number of chunks, the
  generator LLM and the embedding model, so the number of strategies should be minimal.

Corpus facts (from `lexml/`, excluding `Alteracao` content):

| | `articulados` (468 XML = 225 main + 243 annex files) | `nao_articulados` (235 XML) |
|---|---:|---:|
| Artigo | 19,393 (of which 2,231 in annex files) | 0 |
| Caput | 19,393 | 0 |
| Parágrafo | 21,620 | 0 |
| Inciso | 20,703 | 0 |
| Alínea | 5,349 | 0 |
| Item | 2,148 | 0 |
| Groupings (Parte … Subseção) | 5,278 | — |
| Agrupamento / Bloco / `p` | — | 2,675 / 1,306 / 23,284 |
| Text characters | ≈ 23.7 M | ≈ 4.5 M |

The 225 main documents all have a `ProjetoNorma` root. The parser writes each annex to a **separate
file** (`<stem>.anexoN.xml`, root `Anexo` → `DocumentoArticulado` or `DocumentoGenerico`); annexes
are not `<Anexo>` elements inside the main documents. By **content** they fall into three categories
(correction added 2026-09-24; see §6, item 3):

| Category | Root | Files | Articles | Examples |
|---|---|---:|---:|---|
| **A – has `Artigo`** | `DocumentoArticulado` | 8 | 1,111 | `decreto_lei_5452_19430501.anexo1` (CLT, 922 arts.), `decreto_9358_20180430.anexo1` |
| | `DocumentoGenerico` | 4 | 1,120 | **`decreto_9580_20181122.anexo1` (RIR/2018)**, `decreto_5128_20040706.anexo1`, `mp_2228-1_20010906.anexo1` |
| **B – dispositivos, no `Artigo`** | `DocumentoArticulado` | 18 | 0 | `decreto_9358_20180430.anexo2`, `decreto_8289_20140725.anexo1`, `in_rfb_1548_20150213.anexo11` |
| | `DocumentoGenerico` | 32 | 0 | `in_rfb_1500_20141029.anexo8`, `in_rfb_1717_20170717.anexo1` |
| **C – plain text / tables** | `DocumentoGenerico` | 181 | 0 | `ade_rfb_3_20240402.anexo1..3`, `in_rfb_1500_20141029.anexo1` |

The root element is therefore **not** a reliable signal: four `DocumentoGenerico` annexes (including
the RIR/2018, likely the most-cited source in the IRPF Q&A) contain articles nested in
`PartePrincipal` → `Livro`/`Capitulo`/`Secao`/`Artigo`, while 18 `DocumentoArticulado` annexes contain
only orphan `Item`/`Alinea`/`Inciso`/`Paragrafo` elements directly under `Articulacao` (often with a
`TituloDispositivo`). Orphan dispositivos also occur directly under `PartePrincipal` in
`DocumentoGenerico` annexes.

## 5. Recommended strategies

| ID | Chunks indexed | Approx. statutory chunks | Question answered |
|---|---|---:|---|
| **S1 – Article** | `ART` | ≈ 19.4 k | Baseline |
| **S2 – Article + ancestor-path sub-units** | `ART` + `CPT`/`PAR` + `INC`/`ALI`/`ITE` | ≈ 88 k | Does going down to the enumeration level help? (S1 vs S2) |
| S3 – Full multi-layer (optional) | S2 + `PRT`/`LIV`/`TIT`/`SBT`/`CAP`/`SEC`/`SSC` | ≈ 94 k | Do grouping chunks add anything? (S2 vs S3) |

If only two strategies fit the budget, keep **S1 vs S2**. Grouping chunks are the ones most likely
to exceed embedding input limits (up to ~3.8 k tokens in [L]'s tables) and to crowd the RAG context.

Not included:

- **Document and document-component levels:** whole documents exceed embedding limits and are
  useless as RAG context; [L] did not evaluate them either.
- **"Leaves only"** (sub-article units without the article chunks): free to build from the S3
  embeddings, but every extra strategy multiplies the generation and nugget-evaluation grid.
  It would test whether whole-article vectors are needed next to the fine ones — a secondary question.
- **Context-free chunks:** [F] already shows they hurt dense retrieval.

### 5.1 How S1 and S2 differ

S1 and S2 cover **the same text**: an `ART` chunk already holds the whole article down to every
item. What differs is the **unit the retriever can match and return**. Each chunk has one vector
and is retrieved as a whole:

| | S1 | S2 |
|---|---|---|
| What a vector represents | A whole article | An article, **or** one caput / § / inciso / alínea / item |
| What reaches the LLM on a hit | Always the full article | The smallest unit that matched |
| Specific questions | Diluted match; context full of unrelated provisions | Precise match; small context |
| Broad questions | Good match | Still covered, since article chunks are kept |

So S2 is not more text, but more entry points into the same text. If a gold answer depends on one
inciso, S1 can reach it only through the whole-article vector and delivers it mixed with everything
else; S2 can find and deliver exactly that inciso. Nugget evaluation should show this as better
recall of specific nuggets, or the same recall with less context.

### 5.2 Composition of a sub-article chunk (no isolated items)

A sub-article unit is **never embedded alone**. Every caput / § / inciso / alínea / item chunk is:

> **own text + own descendants + the opening text of each ancestor (without their other children) + metadata**

Example — Lei 9.250/1995, Art. 8 (`lexml/articulados/lei_9250_19951226.xml`), chunk
`art8_cpt_inc2_ali2_ite10` (education-deduction limit):

```
[ <Epígrafe> | <Ementa> ]
Art. 8º A base de cálculo do imposto devido no ano-calendário será a diferença entre as somas:
II – das deduções relativas:
b) a pagamentos de despesas com instrução do contribuinte e de seus dependentes, ... até o limite anual individual de:
10. R$ 3.561,50 (...), a partir do ano-calendário de 2015
```

- **Included:** caput opening sentence, inciso II text, alínea b text, item 10.
- **Excluded:** items 1–9 of alínea b, alíneas a and c–j, inciso I, §§ 1–4.
- The chunk for alínea b itself contains its items 1–10 (its own descendants), but not alíneas a or c.

This is [L]'s footnote-7 rule, and the XSL already applies it to incisos, alíneas and itens.

## 6. Implementation changes before running

1. **One context template for every chunk type, so embeddings are computed once.** If an article
   chunk has the same text in S1, S2 and S3, embed the S3 set once per model and build S1/S2 by
   filtering on `Tipo`.
   - Metadata = **Epígrafe + Ementa** (the XSL currently adds only the ementa; add `//Epigrafe`).
   - **Drop `NomeAgrupador`** from the prefix ([F] found no clear gain, and it removes a dimension).
   - **Keep the ancestor-path context** on enumerations (§5.2).
   - Put the metadata in **every** strategy, including the baseline, so the comparison measures
     segmentation rather than the presence of context.
2. **Add the caput to paragraph-level chunks.** For `PAR` chunks and incisos/alíneas/itens inside
   paragraphs, the XSL context is only `Art. Nº` + the paragraph text. In LexML the caput is a
   sibling of the paragraph, not its ancestor, but paragraphs often depend on it — e.g. Art. 8, § 2
   ("O disposto na alínea a do inciso II:"). Add the caput's opening sentence (its own `p` only,
   not its incisos). Cross-references such as "alínea a do inciso II" remain unresolved inside the
   chunk; [L] lists inter-article relationships as future work.
3. **Segment annex files by content, not by root element** (categories in §4). The XSL processes
   annex files, but they carry no `Ementa`/`Epigrafe`, so `$escopo` is empty; category B yields
   `INC`/`ALI`/`ITE` rows with an empty article label and drops orphan `Paragrafo`s (paragraphs are only
   reached through `Caput`); category C yields no rows at all. Rules:
   1. **Category A → statutory**, identical to the main documents in S1/S2/S3. Metadata = the
      **parent** document's Epígrafe + Ementa + the annex label.
   2. **Category B → top-level dispositivo as the basic unit.** Each top-level `Item` / `Alinea` /
      `Inciso` / `Paragrafo` (with its `TituloDispositivo` and subtree) plays the role of an article:
      S1 indexes these units; S2 adds their descendants with the ancestor path (§5.2). Same metadata
      as rule 1.
   3. **Category C → the non-statutory treatment** of item 4, fixed across strategies. Same metadata
      as rule 1.
4. **Treat non-statutory documents identically in all strategies.** The `nao_articulados` files and
   category-C annexes have no `Artigo`, only `Agrupamento` / `Bloco` / `p` / `table`, so the article
   baseline does not apply. Use one fixed treatment — e.g. `Agrupamento`-level chunks with metadata,
   split by `p` above a token cap; one chunk per table, split by rows with the header repeated when
   too large — unchanged across S1–S3, so the comparison stays about statutory segmentation.
5. **Implementation split** (recommended):
   - **Statutory (main documents, annex categories A and B): an amended copy of the XSL** in this
     repo's `scripts/`, leaving the original in `lexml-parser-projeto-lei` untouched. It keeps the
     link to [L]'s implementation. Parent-document metadata can be passed in without restructuring:
     `$sigla` and `$escopo` are already `xsl:param`s, and `run_segmentation_csv.py` already groups
     `.anexoN` files by family stem (it just passes no parameters yet).
   - **Non-statutory (`nao_articulados` and category-C annexes): separate Python code (lxml).**
     Token caps need the embedding model's tokenizer, which XSLT cannot count; splitting tables by
     rows with repeated headers is simple in Python and painful in XSLT; and `Agrupamento`/`Bloco`
     share no templates with the article logic.
   - **Both emit the same CSV schema** (`Tipo, Rotulo, Num_Inicio, Num_Final, Texto, urn`), including
     the XSL's nested interval numbering (`calculaPos`: a parent's interval encloses its
     descendants'), so containment de-duplication works uniformly: X covers Y when
     `Num_Inicio_X ≤ Num_Inicio_Y` and `Num_Final_Y ≤ Num_Final_X`.

## 7. Retrieval and evaluation notes

- **Raw k is not comparable across strategies.** Chunk sizes range from a ~40-token inciso to a
  ~3.8 k-token título, so "top-10" gives very different context sizes in S1 and S2/S3. Sweep a
  **token budget** instead of (or alongside) k.
- **Apply containment de-duplication** ([L] §4.2): drop a chunk whose text is already covered by a
  higher-scored retrieved chunk. Otherwise S2/S3 top-k will often contain both `Art. X` and
  `Art. X, caput, Inciso Y`.
- Without these two controls, part of any measured difference will come from context length and
  redundancy rather than from segmentation.
