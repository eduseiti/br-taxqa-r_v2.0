# Corpus Rebuild Results: Answers to the Review Questions (levels, budgets, open points, metric handling, chunk samples)

**Generated:** 2026-10-08 13:37:26 (local time, from `date +%Y%m%d_%H%M%S`)
**About:** `docs/20261008_010441_corpus_rebuild_results.md` (**the results note**). This note answers the
user's questions on its §4.1 and §6 and on the evaluation, and holds 20 chunk samples for review.
Nothing in the corpus, the dataset or the runs was changed while writing it.
**Sources:** `dataset/*.jsonl` and `build_report.json`; `segmented/chunks_all.csv.gz` (SHA-256 `d1b9cf7e…`);
`runs/retrieval/jua-4b-mixed/irpf/eval/v2c_either_containment_skip/{metrics,reachability}.csv`;
`scripts/rag/ragpipe/{relevance,context,evaluation}.py`; `scripts/lexml/audit_article_coverage.py` (re-run);
the `lexml/` XML and the `original/` `.docx` files; the test suite of `../lexml_parser_non_statutory` (re-run).

---

## 0. Summary

**Answers in brief**

- **Levels (§1.1).** *Document* = any chunk of the cited act. *Article* = any chunk of the cited
  article. *Provision* = the exact unit cited in the gold, e.g. `art1_cpt_inc10` for "art. 1º, inciso X".
  It is not "up to the article". A chunk scores a full hit when it holds the whole unit: the unit
  itself, an ancestor (the article chunk included), a grouping chunk that contains it, or every part
  of a split article.
- **1k–16k (§1.2)** are **context sizes in Qwen3 tokens**. They are not a number of chunks and do
  not come from sampling. For every question, the ranked texts are added to the context in rank order
  until the budget is full. Recall@B is the share of the question's gold items hit by that context.
  All questions with gold count (596 / 553 / 558 per level).
- **Missing fragments (§3.1)** stay in the denominator of the headline numbers (`gold=all`) and are
  left out of `gold=reachable`. They are the same items for every strategy. The provision-level ceiling is 0.965,
  and the gap between the two numbers is 0.3–2 points. The S1/S2/S3/S2c/S4 comparisons do not change
  direction.

**New findings (not in the results note)**

| # | Finding | Effect | Section |
|---|---|---|---|
| N1 | Reference **144-05** is wrong. "Convenção de Viena" in Q144 is the **diplomatic-relations** convention (Decreto 56.435, already 144-01), not the law-of-treaties convention (Decreto 7.030) | One false document-level gold item; once dropped, `decreto_7030` is uncited | §2.1 |
| N2 | Most of the O2 "uncited" documents **are cited in the answer texts**. The 5 service pages are named in Q029, and Parecer Cosit 26/2000 and SC Cosit 153/2014 are in Q576's citation block. The v1 references missed them | Missing gold, so these documents should get references rather than be removed | §2.1 |
| N3 | **435 article chunks hold only their label** ("Art. 34."), in 14 treaty-type files. The article body was parsed outside the `Artigo` element and became loose `TXT`/`DSP` chunks. **5 cited articles** fall on such empty chunks | Those 5 article items count as "reachable", but their article chunk has no content | §2.3, §3.1 |
| N4 | The **RIR/2018 annex has broken groupings**. The parser read the headings "Livro diário" and "Livro de Apuração do Lucro Real" as LIVROs, so 404 Livro II articles sit under two fake LIVROs. LIVRO III holds 1 article, and its other ≈ 210 articles hang outside any LIVRO. The ids `liv3` and `liv4` are duplicated | Only S3/S4 grouping chunks and the `agrupadores_*` metadata. Article and sub-article chunk texts are correct | §3.2 (A9) |
| N5 | 10 of the 25 missing fragments are **fixable**: wrong numbering in the source, renumbering by a later law, a citation into amendment text, and citation errors | They would become reachable | §2.3 |
| N6 | `decreto_7030_20091214` (the treaty convention) has **3 chunks / 411 tokens**: the convention's 85 articles are not in the chunks at all | Only matters if it stays in the corpus | §2.2 |
| N7 | Isolated parse and source defects seen in the samples: Lei 6.766 art. 4 "III-A" merged into inciso III; SC Cosit 194/2015 has words glued together in the `.docx` itself; SC Cosit 140/2015 has a layout table that comes out as fragments | Local to those chunks | §3.2 |

---

## 1. Item 4.1 of the results note

### 1.1 Document, article and provision levels

The gold comes from `dataset/references.jsonl`. Each resolved reference gives a document, its
`article_ids` and its `provisions[]`. The provisions are parsed from the citation text
(`docs/20260927_213420_reference_provisions_from_citation_text.md`). Example, reference 001-03, "Lei nº 11.482, de 31 de maio de
2007, art. 1º, inciso X e parágrafo único":

| Level | Gold items of 001-03 | Items in the whole dataset (questions) |
|---|---|---:|
| document | `lei_11482_20070531` | 1,725 (596) |
| article | `(lei_11482_20070531, art1)` | 1,958 (553) |
| provision | `(…, art1_cpt_inc10)` and `(…, art1_par1u)` | 2,230 (558) |

When a citation names only the article ("art. 25"), the provision is the whole article
(`fragment_id = art25`). The results note's slices "whole-article gold" (429 questions) and
"sub-article gold" (366) split on this.

**Hit rules** (`ragpipe/relevance.py`, G1–G5):

| Level | A retrieved chunk hits the item when… | Example for gold `art1_cpt_inc10` |
|---|---|---|
| document | it belongs to the document's main file or to one of its annexes | any chunk of Lei 11.482 |
| article | it belongs to article N (the `ART` chunk, any part of a split article, the caput, any §, inciso or alínea), or it is a grouping chunk (`CAP`, `SEC`…) whose interval contains the article. Annex rule `either`: article N of the main file or of an annex | the `INC` chunk of inciso V also hits `art1` |
| provision, **full** | its `cobre_ids` holds the unit **or an ancestor of it**, or it is a grouping chunk that contains the unit, or **all** parts of a split article that hold the unit are in the context | `art1_cpt_inc10` (INC), `art1_cpt` (CPT), `art1` (ART), the chapter, but not `art1_cpt_inc9` |
| provision, partial | it holds only part of the unit (a descendant) | gold `art1`, retrieved `art1_par1u` |

**Is the provision level "the match up to the article component, as described in the gold"?** No.
The article level is the match up to the article. The provision level matches the exact component
the gold cites: caput, §, inciso, alínea or item. Recall counts only **full** hits. Partial hits are
reported separately as `partial_recall`. Two consequences explain the slices in the results note:

- **Sub-article gold:** an S1 `ART` chunk that contains inciso X is a full hit, but it costs the
  whole article's tokens. S2 can fill the budget with the inciso alone. Result at 4k: S2 0.424 vs
  S1 0.313.
- **Whole-article gold:** S2's paragraph and inciso chunks are only partial hits. Only the `ART`
  chunk, all of a split article's parts, or a grouping chunk counts as full. Result at 4k: S1 **0.337**
  vs S2 0.266.

### 1.2 What the 1k–16k columns are

They are **token budgets for the retrieved context** (`--budgets 1000,2000,4000,8000,16000`). Tokens
are counted with the Qwen3 tokenizer on the full chunk text, metadata prefix included
(`n_tokens_qwen3`). For each question and strategy (`ragpipe/context.select`):

1. dense retrieval ranks the strategy's texts by cosine similarity, and the top 1,000 are stored;
2. the context is filled in rank order. A text whose chunk lies inside an already selected chunk of
   the same file is skipped (containment de-duplication: a child after its parent adds nothing). A text
   that does not fit in the remaining budget is skipped and filling continues (`overflow=skip`).
   Filling stops when no remaining text fits;
3. recall@B = gold items hit by the selected texts / gold items of the question, averaged over the
   questions.

**There is no sampling.** Every question with gold at the level is used (596 document / 553 article /
558 provision), with every text of its ranking. The budget view replaces "top-k" because chunk sizes
differ a lot by type. Median Qwen3 tokens are ART 194, PAR 150, INC 169, CAP 822 and TIT 1,556, so
top-10 would mean very different context sizes in S1 and S3. A budget is also what the generator
will receive (Phase 2 uses the same `select`).

Average number of texts per context (document level, `gold=all`):

| Budget | S1 | S2 | S3 | S2c | S4 |
|---|---:|---:|---:|---:|---:|
| 1k | 3.8 | 4.5 | 4.4 | 4.3 | 4.2 |
| 2k | 6.3 | 7.8 | 7.4 | 7.4 | 7.1 |
| 4k | 11.0 | 13.6 | 12.6 | 13.1 | 12.1 |
| 8k | 20.9 | 25.9 | 22.4 | 24.7 | 21.7 |
| 16k | 41.0 | 50.4 | 40.6 | 48.0 | 39.3 |

The average context fills the budget to within about 17 tokens: 3,983 of 4,000 at 4k for every strategy.

---

## 2. Item 6 of the results note: open points

### 2.1 O2: uncited documents. Can they simply be removed?

"Uncited" means that no resolved reference points at the document (`build_report.json →
documents_not_cited`). A search of the 715 answers and citation lists shows three different situations:

| Document | What it is | Chunks / tokens | Where the dataset mentions it | Recommendation |
|---|---|---:|---|---|
| `in_rfb_1911_20191011` | IN RFB 1.911/2019 (PIS/Pasep and Cofins regulation, 60 annexes) | **4,528 / 1.93 M** | Nowhere. It was v1's wrong match for IN RFB 1.997/2019, and that reference (Q025) is now dropped | **Remove.** It is the largest distractor in the corpus (≈ 5 % of the S3 rows) and was never cited |
| `in_rfb_1505_20141031` | IN RFB 1.505/2014 (amends IN RFB 971/2009, social-security contributions) | 11 / 5,244 | Only in Q081's dropped embedded reference ("IN RFB 1.505, de 05 de agosto de 2014"). Q081's answer cites nothing | **Remove** |
| 5 service pages: `declaracao_benficios_fiscais_DBF`, `…_DIMOB`, `…_DMED`, `…_DOI`, `sistema_…_CARNE_LEAO` | Receita portal pages about the DBF, Dimob, Dmed and DOI returns and the Carnê-Leão | 21 + 6 + 7 + 6 + 5 | **Q029's answer** lists them as sources of the pre-filled return (items II–VII), and they are in its `embedded_references_text`. The v1.1 references of Q029 have only IN 2.178 and IN 1.888. (The DIRF page in the same list is in the corpus and cited by Q207.) | **Keep and add references:** 5 embedded references for Q029, document level only. Their overrides already exist in `reference_overrides.json` and are the "override for a file name no question cites" warnings |
| `par_cosit_26_20000629`, `sc_cosit_153_20140611` | Parecer Cosit 26/2000 and SC Cosit 153/2014, both on the assignment of court-ordered payments (*precatórios*) | 33 / 9,447 and 13 / 9,514 | **Q576's citation block**: "…; Parecer Cosit nº 26, de 29 de junho de 2000; Solução de Consulta Cosit nº 153, de 11 de junho de 2014; e Solução de Consulta Cosit nº 674, de 27 de dezembro de 2017)". Q576 has `references_text = []`. All 8 of its references are `embedded`, and the list misses these two and SC 674 | **Keep and add references:** re-extract Q576's explicit references from its citation block (9 acts, including SC 674, which Q252 already cites) |
| `lei_3071_19160101` | Código Civil de 1916 | 3,083 / 565 k | Nowhere. It came from the fetcher's `fetched_documents` and was already flagged as "harmless extra" in `docs/20260913_143905_*`. Its XML has 25 duplicate article ids | **Remove**, or keep as a distractor and fix the duplicate ids |
| `lei_5869_19730111` | CPC de 1973 | 3,735 / 766 k | Nowhere in the dataset (the answers cite the CPC of 2015, Lei 13.105). Lei 9.250 art. 8 § 3 mentions it in its text | **Remove**, or keep as a distractor |
| `decreto_7030_20091214` (new, N1) | Convention on the Law of Treaties | 3 / 411 | Only through the wrong reference 144-05 | **Drop 144-05**, then remove the document |

Removing documents changes only the chunk set (`segment_all.py` without them). Every remaining text
already has a vector, so no new embedding is needed. Rankings and metrics must be regenerated, and the
corpus counts in the notes change.

### 2.2 O3: "uncited documents with parse gaps"

The results note calls these documents uncited. That is not right: **each is cited at the document
level by one question**. What no question cites are their articles, so the gaps cannot affect article
or provision gold. They can affect document-level retrieval when the missing text is the relevant part.

| Document (citing reference) | Audit result | Detail |
|---|---|---|
| `decreto_7030_20091214` (144-05, wrong, see N1) | 85 articles in the `.docx`, 3 in the XML | The convention numbers its articles "Artigo N", which the statutory parser does not read, and its text does not reach the chunks (3 chunks, 411 tokens) |
| `mp_2228-1_20010906` (442-07) | arts. 13, 31, 51, 73 absent; `art33` duplicated in annex 1 | All wordings of these 4 articles are struck through on Planalto, so the parser dropped them (rebuild results note, R3a: superseded text, left alone) |
| `decreto_70951_19720809` (302-01) | 35 article labels in the `.docx`, 77 ids in the XML; `art15`, `art21`, `art23`, `art32`, `art35`, `art40`, `art48`, `art79` duplicated | More ids than labels: quoted or annexed articles were parsed as top-level articles |
| `decreto_71733_19730118` (163-02) | `art22-15` absent; `art22`, `art23`, `art27` duplicated | Article-label variants mis-parsed |
| `lei_12715_20120917` (442-13) | `art69`…`art78` duplicated | Articles of quoted amendment text read as top level (unclosed quote, cause 2c) |
| `decreto_lei_58_19371210` (256-04) | `art1`…`art4` duplicated | Same pattern |
| `decreto_lei_1535_19770413` (177-11), `lei_7290_19841219` (191-01) | `art1-15` / `art2-1` absent | One "Art. N-A" label each, not recognized |

Duplicate ids lead to `id_ambiguo = 1` chunks. The evaluation flags matches that exist only through
such chunks (G4), and there are **0** for the current gold (`reachability.csv`).

### 2.3 O4: the 25 cited provision fragments missing from the XML

`build_report.json → validation.fragment_ids_missing` lists 25 (reference, fragment) pairs. They
are marked `matchable: false` and their `lexml_file` is empty. They fall into three groups.

**(a) Treaty articles absent from the XML: 13 pairs, 11 articles of 9 decrees** (O1;
`scripts/lexml/unmatchable_articles.tsv`)

| Reference | Document | Cited | Why absent |
|---|---|---|---|
| 149-01, 150-12 | `decreto_27784_19500216` | art. V | Non-statutory treaty decree; the treaty text is not in the `.docx` |
| 149-03, 150-05 | `decreto_59308_19660923` | art. V | Non-statutory treaty decree |
| 152-01 | `decreto_57942_19660310` | art. 10 "b" | The treaty text has no article markers the parser reads (0 labels in the `.docx`) |
| 153-01 | `decreto_57942_19660310` | art. 1º | Same |
| 153-04 | `decreto_361_19911210` | art. 13 | The `.docx` holds only the 2-article promulgating decree |
| 154-01 | `decreto_86084_19810608` | art. IX, item 2 | Non-statutory treaty decree |
| 155-01 | `decreto_87563_19820913` | art. XV "b" | The treaty numbers its articles "ARTIGO I…XXV" |
| 157-02 | `decreto_8289_20140725` | art. XIII, item 2 | Annex 1 numbers its articles "Artigo I…XIV" |
| 158-02 (×2) | `decreto_85801_19810310` | arts. XII and VI | Non-statutory treaty decree; the treaty text is absent |
| 159-01 | `decreto_93153_19860822` | art. VII | Same |

Fix (O1): fetch the treaty texts and map their "ARTIGO N" blocks by label. The non-statutory ones
would need article-level ids in a `DocumentoGenerico`, which the current gold matcher does not support.

**(b) The article exists but is empty: 2 pairs** (new, N3)

| Reference | Document | Cited | What the XML has |
|---|---|---|---|
| 142-03 | `decreto_56435_19650608` (Vienna Convention on Diplomatic Relations) | art. 34 "d" | `<Artigo id="art34">` with an empty `Caput`. The text "O agente diplomático gozará de isenção…" and alíneas a)–f) come **after** `</Artigo>` and became chunk `#188` (TXT) plus loose `ALI`/`DSP` chunks without `artigo_id` |
| 157-01 | `decreto_5128_20040706.anexo1` (OEI seat agreement) | art. 21 "d" | Same: an empty `art21`, and alíneas `ali1…` as siblings after it |

Cause: the source has "Artigo 34" (or "ARTIGO 21") on its own line, followed by unnumbered text. The
parser opens an `Artigo` from the heading line but does not attach the following paragraphs to it.
Articles whose text starts with "1." work, because they become numbered items (e.g. art. 37, cited by
Q144, is complete). Corpus-wide there are **435 label-only `ART` chunks** in 14 files:
`decreto_67542_19701112` (149), `decreto_50656_19610524` (64), `decreto_61078_19670726` (39),
`decreto_5128…anexo1` (35), `decreto_56435` (28), `decreto_57784_19660211` (26), `decreto_75102_19741220` (25),
`decreto_9358_20180430.anexo1` (24), `decreto_8624_20151229.anexo1` (21), `decreto_85306_19801030` (9),
`decreto_legislativo_92_19751105.anexo1` (9), `decreto_9358….anexo3` (4), `decreto_52288_19630724` (1),
`lei_12431_20110624` (1). **Five cited article items** point at an empty `ART` chunk: 142-03
(56435 art34), 151-01 (50656 art47), 151-02 (57784 art15), 153-02 (67542 art141), 157-01 (5128
annex art21). Fix: a statutory-parser rule that attaches the paragraphs after a bare "Artigo N"
heading to that article, then re-parse these 14 files.

**(c) Statutory citations with a cause that can be fixed: 10 pairs**

| Reference | Cited | What the source says | Diagnosis | Fix |
|---|---|---|---|---|
| 018-01 | Lei 9.250, art. 10, **inciso X** | Art. 10 ends at inciso IX, "R$ 16.754,34 … a partir do ano-calendário de 2015". The answer quotes this amount ("limitado a R$ 16.754,34") | Citation error in the P&R (IX), unless a later law added an inciso X that this `.docx` lacks. Check Planalto before deciding | Map to `art10_cpt_inc9` (override) or refresh the `.docx` |
| 093-02, 093-06 | Lei 6.015, art. 167, I, **items 24 and 25** | The `.docx` (Câmara compilation) letters the items a)…; the official text numbers them 1)…. The parse has `art167_cpt_inc1_ali24` = "x) das sentenças que nos inventários, arrolamentos e partilhas, adjudicarem bens de raiz…" and `ali25` = "y) dos atos de entrega de legados de imóveis, dos formais de partilha…" | Only the numbering differs; the content matches Q093 (inheritance) | Map `ite24`→`ali24` and `ite25`→`ali25` |
| 209-01 | Lei 6.015, art. 167, I, **item 7** | `ali7` = "g) do usufruto e do uso sobre imóveis…" | Same (Q209 is about usufruct) | Map `ite7`→`ali7` |
| 460-03 | IN RFB 2.178, art. 11, **§ 2º, inciso II** | § 2º (trusts) has no incisos. § 3º II = "bens móveis e direitos cujo valor unitário de aquisição seja inferior a R$ 5.000,00" | Citation error in the P&R: the answer's threshold for crypto-assets ("igual ou superior a R$ 5.000,00") is § 3º II | Map to `art11_par3_inc2` |
| 683-02 | Lei 12.350, art. 45, **§ 3º** | Art. 45 rewrites art. 8 of Lei 9.959; the § 3º is inside the quoted new wording (`art45_cpt_alt1`). The same question also cites Lei 9.959 art. 8 § 3º directly (683-01, matchable) | The citation points into amendment text, which has no § id of its own | Map to `art45` (whole article) |
| 708-01, 708-11 | Lei 11.033, art. 3º, **parágrafo único** | Lei 14.754/2023 turned the parágrafo único into § 1º from 2024-01-01. The `.docx` has the new numbering: `art3_par1` "(Parágrafo único acrescido pela Lei nº 11.196… e transformado em § 1º pela Lei nº 14.754…)" | Renumbering; the P&R uses the 2023 numbering | Map to `art3_par1` |

All 10 can be fixed with a provision-level override in `reference_overrides.json`. The `build_v2_dataset.py`
override format supports files and drops today, not provisions, so a small extension is needed.

### 2.4 O5: the 11 failing tests of `lexml_parser_non_statutory`

Re-run on `e8c3d1e` (`PYTHONPATH=src python3 -m pytest -q`): **11 failed, 6,196 passed, 4 skipped**.
All 11 are `requires_corpus` tests. They read `../br-taxqa-r_v2.0/original/nao_articulados/` and the
referee cache, and assert numbers measured on the September corpus (233 `.docx`):

| Test | Expected | Measured | What changed |
|---|---:|---:|---|
| `test_flatness_causes::test_the_corpus_flat_count` | 233 | 232 | Number of `.docx` documents (the folder now has 232 `.docx` + 12 PDFs) |
| `…::test_the_corpus_cause_partition` | partition incl. `body_span: 11` | `…sections: 8` | Flatness causes of the new document set |
| `…::test_truncation_is_visible_in_span_coverage` | 82 | 89 | Same |
| `…::test_ad_pgfn_is_flat_but_proposes_nothing` | 15 | 16 | Same |
| `test_profile_solucao_consulta::test_the_genre_selects_its_own_profile` | 127 | 114 | Fewer SC `.docx` files (12 SCs are now PDFs) |
| `…::test_sc_cosit_flatness_falls` | 109 | 97 | Same |
| `test_referee_economics::test_the_cache_answers_almost_every_question` | 681 | 554 | `/tmp/lexml_referee_cache` lost answers (results note §5.5) |
| `…::test_the_misses_are_all_abstentions_that_change_nothing` | 10 | 14 | Same |
| `…::test_the_overrides_reproduce_the_plans_table` | plan's table | 31 `own` headings | Same |
| `…::test_the_referee_now_moves_flatness_86_to_83` | 86 | 94 | Rules-only baseline on the new set |
| `…::test_the_heading_overrides_are_not_rule_learnable` | ≥ 30 | 26 | Cache contents |

None of them is a parser regression: they pin a corpus snapshot. Options: (a) freeze the 233-document
set and the 681-answer cache as test data outside `/tmp` (this also fixes O7); (b) re-measure and
update the constants. (a) is better, because these tests document a past measurement.

### 2.5 O6: the linker defect

For "art. 19, caput, da Lei nº 9.096…" `/usr/local/bin/linkertool` (built 2025-10-31) returns
`urn:lex:br:federal:lei:1995-09-19;9096!cpt`. The article is lost (`!art19_cpt` expected).
Reproduce with:

```bash
echo 'O art. 19, caput, da Lei nº 9.096, de 19 de setembro de 1995 - Lei dos Partidos' \
    | LC_ALL=C.UTF-8 linkertool --contexto=federal
```

The new statutory corpus has 234 such `…!cpt…` links (227 before). Four unchanged `.docx` files had
better links in the committed XML, probably from a linker built elsewhere. **Effect on this
experiment: none.** The links are `Remissao` attributes in the XML. Chunk texts, the gold and the
matcher do not use them. They matter only for a future citation-graph use or for the quality of the
released XML. The fix belongs in `../lexml-linker` (the "caput" token after "art. N," must keep the
article), followed by a re-parse. The text would be byte-identical.

---

## 3. General questions

### 3.1 How do the IR metrics handle missing fragments?

Every gold item is kept, and an item no chunk can hit is marked **unreachable**
(`ragpipe/evaluation.py`: `reachable = False` with a reason). Every metric is then reported twice:

- `gold=all` (**the headline**): unreachable items stay in the denominator and count as misses for
  every strategy;
- `gold=reachable`: unreachable items are left out, and so are questions with no reachable gold.

Unreachable items (`reachability.csv`, identical for all five strategies):

| Level | Gold items | Unreachable | Reason | Questions (all / with reachable gold) | Oracle recall (`gold=all`) |
|---|---:|---:|---|---|---:|
| document | 1,725 | 0 | — | 596 / 596 | 1.000 |
| article | 1,958 | 13 | `article_not_in_lexml`: the treaty articles of §2.3 (a) | 553 / 549 | 0.989 |
| provision | 2,230 | 57 | `no_lexml_id`: 22 missing fragments (the 25 of §2.3 minus 3 duplicates within a question) + 35 units with no LexML id (non-statutory "item 19", "Anexo II", "Capítulo III", treaty "Seção 18"…) | 558 / 548 | 0.965 |

Effect on the reported recall (4k; the other budgets behave alike):

| Level | | S1 | S2 | S3 | S2c | S4 |
|---|---|---:|---:|---:|---:|---:|
| article | all / reachable | 0.379 / 0.382 | 0.473 / 0.477 | 0.464 / 0.469 | 0.428 / 0.431 | 0.426 / 0.429 |
| provision | all / reachable | 0.347 / 0.357 | 0.361 / 0.372 | 0.361 / 0.372 | 0.321 / 0.329 | 0.334 / 0.342 |
| provision @16k | all / reachable | 0.532 / 0.551 | 0.565 / 0.585 | 0.581 / 0.601 | 0.538 / 0.558 | 0.555 / 0.574 |

So the missing fragments **lower the absolute numbers** by 0.3–2 points but **do not affect the
comparisons**. The unreachable items are the same for every strategy, so they add 0 to both sides of
every per-question difference. The 10 provision questions with only unreachable gold give a
difference of 0 and dilute the mean difference by 10/558 ≈ 2 %. No sign or significance in §4.2 of
the results note depends on them.

**Caveat (N3).** The 5 cited treaty articles whose `ART` chunk is label-only count as *reachable*. A
hit on them is a hit on "[decree prefix] Art. 34.". That is 5 of 1,958 article items (≤ 0.26 % of
article recall in the worst case, and their provision items are unreachable anyway). The per-item
table that would show whether any of them is ever retrieved could not be regenerated here: the
rankings and the corpus vectors (`embeddings/jua-4b-mixed/corpus/texts.csv`) are not on disk.
Fixing N3 removes the caveat.

### 3.2 Twenty segmentation samples (10 statutory, 10 non-statutory)

**How they were drawn.** Stratified at random (seed `20261008`) from documents cited by at least one
question, one sample per document, using the frozen chunk set and the pipeline's own
`ragpipe.strategies.member_mask` for the ✓ columns, which are exactly what retrieval indexes:

- statutory (10): 4 articles with paragraphs, 2 with incisos and no paragraph, 1 without sub-units,
  1 article split into parts, 1 article of a category-A annex (RIR/2018), and 1 orphan dispositivo
  (`DSP`) of a category-B annex. Articles with 2–10 sub-unit chunks were preferred so the samples stay
  readable;
- non-statutory (10): 2 SCs, 1 Parecer Normativo, 1 Ato Declaratório, 1 SCI, 1 PGFN parecer, 1 treaty
  decree, 1 service page, 1 court document (STJ súmula), 1 category-C annex table.

**What to check in each sample.** The LexML parse is shown as an outline: each element `id
[element]: Rotulo + its own text`, with quoted amendment text in «…». The next table shows every chunk
of the unit with its `cobre_ids`, source interval and Qwen3 tokens, plus the strategies that index it.
The full chunk texts follow. Grouping chunks are shortened in the middle, with the omitted length
given.

**What the strategies should look like (design: `docs/20260923_193852_*`, `docs/20261005_184116_*`):**

| | Indexed rows | Text of a paragraph-family chunk |
|---|---|---|
| S1 | `ART` (or its parts), `DSP`, `TXT`, `TAB` | — |
| S2 | S1 + `CPT`, `PAR`, `INC`, `ALI`, `ITE` (`base`) | `[prefix] Art. N. § k …`: article label plus the ancestor path, **without the caput** |
| S3 | S2 + grouping chunks ≤ 8,192 tokens (larger ones are not emitted: `groupings_over_limit.csv`) | as S2 |
| S2c / S4 | as S2 / S3, with the `caput` twin (`#c<seq>`) replacing the `base` row | `[prefix] Art. N. <caput sentence> § k …` |

Rules visible in the samples:

- a `CPT` chunk is emitted only when the article has paragraphs (A5, A6: articles with only a caput
  and incisos have no `CPT`);
- caput incisos (`art_cpt_incN`) have no caput variant, because their ancestor path already holds the
  caput. Incisos of a paragraph do get one (A3: `#c4189`);
- non-statutory units are `TXT`/`TAB` only, so **S1 = S2 = S3 = S2c = S4** for every non-statutory
  chunk. The non-statutory samples check the parse → chunk step only;
- the metadata prefix is `[ epígrafe | ementa (≤ 128 tokens, "…" when cut) | annex label ]`. The
  grouping path is **not** in the prefix of article chunks; it appears only as the heading inside
  grouping chunks and, for non-statutory units, as the `heading > heading` path at the start of the
  text;
- split units (A8, B6) carry `parte/n_partes`. A split `ART` part repeats the caput sentence in its
  head (caput plan Q2). Split non-statutory parts have an empty `cobre_ids` and the unit in
  `parcial_ids`.

**Defects found in the samples:**

| Sample | Observation | Scope |
|---|---|---|
| A8 (Lei 6.766 art. 4) | Inciso "III-A. –" is not recognized and is merged into inciso III (`art4_cpt_inc3`); "III-B" is correctly `inc3-2` | A corpus-wide pattern search finds only this case |
| A9 (RIR/2018 art. 483) | The grouping path reads "LIVRO DE – Apuração do Lucro Real". The section name ends with "… Determinação do custo", an unnumbered sub-heading glued onto "Seção X" | **N4**: 404 articles under the fake LIVROs "LIVRO DIARIO" (4 articles) and "LIVRO DE" (400); LIVRO III contains 1 article; ≈ 210 articles of Livro III are outside any LIVRO; `liv3`/`liv4` are duplicated. Article texts are correct; S3/S4 grouping chunks and `agrupadores_*` are wrong for these articles |
| B1 (SC Cosit 140/2015) | `pp1_tab1` is a layout table holding body-text fragments ("natalista, a qual \| afirma que o nascituro…"), and comes out as a broken `TAB` chunk | That document |
| B2 (SC Cosit 194/2015) | Words are glued together: "setembrode", "Decretonº", "ouexigir". The `.docx` itself has them (converted from `.odt`, rebuild plan §1) | This document is the clear outlier in a glued-word scan of all non-statutory sources (10 per 1,000 words; the next is 2.5) |
| B6 (Parecer PGFN/CAT 1.503/2010) | The quoted case-law ementa has one `<p>` per printed line (hard line breaks in the source). The chunk text joins them correctly | Text is fine; only the XML is noisy |
| B7 (Decreto 59.309) | The `nota` unit starts with the signatures "H. Castello Branco M. Pio Corrêa" before the agreement text | Cosmetic |

Everything else in the 20 samples matches the design: the base and caput texts, the strategy
membership, the containment intervals of the grouping chunks, the split-part coverage and the
category-A/B/C annex treatment.

---

## 4. Suggested next steps

1. **Dataset fixes:** drop 144-05; add Q029's 5 service-page references and Q576's explicit
   references; add provision overrides for the 10 fixable fragments of §2.3 (c). This needs the
   provision-level override format.
2. **Corpus:** remove `in_rfb_1911_20191011`, `in_rfb_1505_20141031`, `decreto_7030_20091214` and,
   unless they are kept as distractors, `lei_3071_19160101` and `lei_5869_19730111`.
3. **Statutory parser:** attach the text after a bare "Artigo N" heading to its article (N3, 14 files);
   read "Livro diário"/"Livro de Apuração…" as text, not as a LIVRO, inside an article context (N4,
   RIR/2018); accept "III-A." labels. Then re-parse, re-segment and evaluate.
4. Then the tests and cache (O5/O7) and the linker (O6), which do not affect retrieval numbers.

---

## Appendix: the samples

### A. Statutory samples

#### A1. `lei_6015_19731231.xml` — `art264` (article with paragraphs (main document))

- Document: `lei_6015_19731231` — LEI Nº 6.015, DE 31 DE DEZEMBRO DE 1973; cited by 3 question(s); this article is not cited.
- Groupings (`agrupadores_rotulos`): TÍTULO V – DO REGISTRO DE IMÓVEIS ; CAPÍTULO IX – DO BEM DE FAMÍLIA; source interval Num 2739–2748.

**LexML parse** (`id [element]: Rotulo + own text`; «…» = quoted amendment text):

```text
art264 [Artigo]: Art. 264.
  art264_cpt [Caput]: Se for apresentada reclamação, dela fornecerá o oficial ao instituidor, cópia autêntica e lhe restituirá a escritura, com a declaração de haver sido suspenso o registro, cancelando a prenotação.
  art264_par1 [Paragrafo]: § 1º O instituidor poderá requerer ao juiz que ordene o registro, sem embargo da reclamação.
  art264_par2 [Paragrafo]: § 2º Se o juiz determinar que proceda ao registro, ressalvará ao reclamante o direito de recorrer à ação competente para anular a instituição ou de fazer execução sobre o prédio instituído, na hipótese de tratar-se de dívida anterior e cuja solução se tornou inexeqüível em virtude do ato da instituição.
  art264_par3 [Paragrafo]: § 3º O despacho do juiz será irrecorrível e, se deferir o pedido será transcrito integralmente, juntamente com o instrumento.
```

**Chunks and strategy membership** (✓ = indexed by the strategy):

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `lei_6015_19731231#114` | CPT | base | `art264_cpt` | 2740–2741 | 109 |  | ✓ | ✓ | ✓ | ✓ |
| `lei_6015_19731231#470` | PAR | base | `art264_par1` | 2742–2743 | 77 |  | ✓ | ✓ |  |  |
| `lei_6015_19731231#c470` | PAR | caput | `art264_par1` | 2742–2743 | 136 |  |  |  | ✓ | ✓ |
| `lei_6015_19731231#471` | PAR | base | `art264_par2` | 2744–2745 | 141 |  | ✓ | ✓ |  |  |
| `lei_6015_19731231#c471` | PAR | caput | `art264_par2` | 2744–2745 | 200 |  |  |  | ✓ | ✓ |
| `lei_6015_19731231#472` | PAR | base | `art264_par3` | 2746–2747 | 86 |  | ✓ | ✓ |  |  |
| `lei_6015_19731231#c472` | PAR | caput | `art264_par3` | 2746–2747 | 145 |  |  |  | ✓ | ✓ |
| `lei_6015_19731231#796` | ART | base | `art264` | 2739–2748 | 263 | ✓ | ✓ | ✓ | ✓ | ✓ |

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `lei_6015_19731231#877` | CAP | base | `tit5_cap9` | 2718–2753 | 730 |  |  | ✓ |  | ✓ |

**Chunk texts** (in `chunk_id` order; grouping chunks shortened):

`lei_6015_19731231#114` (CPT, base):
```text
[ LEI Nº 6.015, DE 31 DE DEZEMBRO DE 1973 | Dispõe sobre os registros públicos e dá outras providências. ] Art. 264. Se for apresentada reclamação, dela fornecerá o oficial ao instituidor, cópia autêntica e lhe restituirá a escritura, com a declaração de haver sido suspenso o registro, cancelando a prenotação.
```
`lei_6015_19731231#470` (PAR, base):
```text
[ LEI Nº 6.015, DE 31 DE DEZEMBRO DE 1973 | Dispõe sobre os registros públicos e dá outras providências. ] Art. 264. § 1º O instituidor poderá requerer ao juiz que ordene o registro, sem embargo da reclamação.
```
`lei_6015_19731231#c470` (PAR, caput):
```text
[ LEI Nº 6.015, DE 31 DE DEZEMBRO DE 1973 | Dispõe sobre os registros públicos e dá outras providências. ] Art. 264. Se for apresentada reclamação, dela fornecerá o oficial ao instituidor, cópia autêntica e lhe restituirá a escritura, com a declaração de haver sido suspenso o registro, cancelando a prenotação. § 1º O instituidor poderá requerer ao juiz que ordene o registro, sem embargo da reclamação.
```
`lei_6015_19731231#471` (PAR, base):
```text
[ LEI Nº 6.015, DE 31 DE DEZEMBRO DE 1973 | Dispõe sobre os registros públicos e dá outras providências. ] Art. 264. § 2º Se o juiz determinar que proceda ao registro, ressalvará ao reclamante o direito de recorrer à ação competente para anular a instituição ou de fazer execução sobre o prédio instituído, na hipótese de tratar-se de dívida anterior e cuja solução se tornou inexeqüível em virtude do ato da instituição.
```
`lei_6015_19731231#c471` (PAR, caput):
```text
[ LEI Nº 6.015, DE 31 DE DEZEMBRO DE 1973 | Dispõe sobre os registros públicos e dá outras providências. ] Art. 264. Se for apresentada reclamação, dela fornecerá o oficial ao instituidor, cópia autêntica e lhe restituirá a escritura, com a declaração de haver sido suspenso o registro, cancelando a prenotação. § 2º Se o juiz determinar que proceda ao registro, ressalvará ao reclamante o direito de recorrer à ação competente para anular a instituição ou de fazer execução sobre o prédio instituído, na hipótese de tratar-se de dívida anterior e cuja solução se tornou inexeqüível em virtude do ato da instituição.
```
`lei_6015_19731231#472` (PAR, base):
```text
[ LEI Nº 6.015, DE 31 DE DEZEMBRO DE 1973 | Dispõe sobre os registros públicos e dá outras providências. ] Art. 264. § 3º O despacho do juiz será irrecorrível e, se deferir o pedido será transcrito integralmente, juntamente com o instrumento.
```
`lei_6015_19731231#c472` (PAR, caput):
```text
[ LEI Nº 6.015, DE 31 DE DEZEMBRO DE 1973 | Dispõe sobre os registros públicos e dá outras providências. ] Art. 264. Se for apresentada reclamação, dela fornecerá o oficial ao instituidor, cópia autêntica e lhe restituirá a escritura, com a declaração de haver sido suspenso o registro, cancelando a prenotação. § 3º O despacho do juiz será irrecorrível e, se deferir o pedido será transcrito integralmente, juntamente com o instrumento.
```
`lei_6015_19731231#796` (ART, base):
```text
[ LEI Nº 6.015, DE 31 DE DEZEMBRO DE 1973 | Dispõe sobre os registros públicos e dá outras providências. ] Art. 264. Se for apresentada reclamação, dela fornecerá o oficial ao instituidor, cópia autêntica e lhe restituirá a escritura, com a declaração de haver sido suspenso o registro, cancelando a prenotação. § 1º O instituidor poderá requerer ao juiz que ordene o registro, sem embargo da reclamação. § 2º Se o juiz determinar que proceda ao registro, ressalvará ao reclamante o direito de recorrer à ação competente para anular a instituição ou de fazer execução sobre o prédio instituído, na hipótese de tratar-se de dívida anterior e cuja solução se tornou inexeqüível em virtude do ato da instituição. § 3º O despacho do juiz será irrecorrível e, se deferir o pedido será transcrito integralmente, juntamente com o instrumento.
```
`lei_6015_19731231#877` (CAP, 730 tokens, shortened):
```text
[ LEI Nº 6.015, DE 31 DE DEZEMBRO DE 1973 | Dispõe sobre os registros públicos e dá outras providências. ] CAPÍTULO IX DO BEM DE FAMÍLIA Art. 260. A instituição do bem de família far-se-á por escritura pública, declarando o instituidor que determinado prédio se destina a domicílio de sua família e ficará isento de execução por dívida. Art. 261. Para a inscrição do bem de família, o instituidor apresentará ao oficial do registro a escritura pública de instituição, para que mande publicá-la na imp … [1,598 chars omitted] …  Quando o bem de família for instituído juntamente com a transmissão da propriedade (Decreto-Lei nº 3.200, de 14 de abril de 1941, artigo 8º, § 5º), a inscrição far-se-á imediatamente após o registro da transmissão ou, se for o caso, com a matrícula.
```

#### A2. `lei_4504_19641130.xml` — `art126` (article with paragraphs (main document))

- Document: `lei_4504_19641130` — LEI Nº 4.504, DE 30 DE NOVEMBRO DE 1964; cited by 3 question(s); this article is not cited.
- Groupings (`agrupadores_rotulos`): TÍTULO IV – DAS DISPOSIÇÕES GERAIS E TRANSITÓRIAS; source interval Num 1656–1663.

**LexML parse** (`id [element]: Rotulo + own text`; «…» = quoted amendment text):

```text
art126 [Artigo]: Art. 126.
  art126_cpt [Caput]: A Carteira de Colonização do Banco do Brasil, sem prejuízo de suas atribuições legais, atuará como entidade financiadora nas operações de venda de lotes rurais ...VETADO.
  art126_par1 [Paragrafo]: § 1º As Letras Hipotecárias que o Banco do Brasil está autorizado a emitir, em provimento de recursos e em empréstimos da sua Carteira de Colonização, poderão conter cláusula de garantia contra eventual desvalorização de moeda, de acordo com índices que forem sugeridos pelo Conselho Nacional de Economia, assegurando ao mesmo Banco o ressarcimento de prejuízos já previstos no artigo 4º da Lei nº 2.237, de 19 de junho de 1954.
  art126_par2 [Paragrafo]: § 2º Caberá à Diretoria do Banco do Brasil fixar o limite do valor dos empréstimos que o Banco fica autorizado a realizar no País ou no estrangeiro para aplicação, pela sua Carteira de Colonização, revogado, portanto o limite estabelecido no parágrafo único do art. 8º da Lei número 2.237, de 19 de junho de 1964, e as disposições em contrário.
```

**Chunks and strategy membership** (✓ = indexed by the strategy):

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `lei_4504_19641130#65` | CPT | base | `art126_cpt` | 1657–1658 | 103 |  | ✓ | ✓ | ✓ | ✓ |
| `lei_4504_19641130#259` | PAR | base | `art126_par1` | 1659–1660 | 185 |  | ✓ | ✓ |  |  |
| `lei_4504_19641130#c259` | PAR | caput | `art126_par1` | 1659–1660 | 235 |  |  |  | ✓ | ✓ |
| `lei_4504_19641130#260` | PAR | base | `art126_par2` | 1661–1662 | 164 |  | ✓ | ✓ |  |  |
| `lei_4504_19641130#c260` | PAR | caput | `art126_par2` | 1661–1662 | 214 |  |  |  | ✓ | ✓ |
| `lei_4504_19641130#394` | ART | base | `art126` | 1656–1663 | 346 | ✓ | ✓ | ✓ | ✓ | ✓ |

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `lei_4504_19641130#400` | TIT | base | `tit4` | 1443–1672 | 5309 |  |  | ✓ |  | ✓ |

**Chunk texts** (in `chunk_id` order; grouping chunks shortened):

`lei_4504_19641130#65` (CPT, base):
```text
[ LEI Nº 4.504, DE 30 DE NOVEMBRO DE 1964 | Dispõe sobre o Estatuto da Terra, e dá outras providências. ] Art. 126. A Carteira de Colonização do Banco do Brasil, sem prejuízo de suas atribuições legais, atuará como entidade financiadora nas operações de venda de lotes rurais ...VETADO.
```
`lei_4504_19641130#259` (PAR, base):
```text
[ LEI Nº 4.504, DE 30 DE NOVEMBRO DE 1964 | Dispõe sobre o Estatuto da Terra, e dá outras providências. ] Art. 126. § 1º As Letras Hipotecárias que o Banco do Brasil está autorizado a emitir, em provimento de recursos e em empréstimos da sua Carteira de Colonização, poderão conter cláusula de garantia contra eventual desvalorização de moeda, de acordo com índices que forem sugeridos pelo Conselho Nacional de Economia, assegurando ao mesmo Banco o ressarcimento de prejuízos já previstos no artigo 4º da Lei nº 2.237, de 19 de junho de 1954.
```
`lei_4504_19641130#c259` (PAR, caput):
```text
[ LEI Nº 4.504, DE 30 DE NOVEMBRO DE 1964 | Dispõe sobre o Estatuto da Terra, e dá outras providências. ] Art. 126. A Carteira de Colonização do Banco do Brasil, sem prejuízo de suas atribuições legais, atuará como entidade financiadora nas operações de venda de lotes rurais ...VETADO. § 1º As Letras Hipotecárias que o Banco do Brasil está autorizado a emitir, em provimento de recursos e em empréstimos da sua Carteira de Colonização, poderão conter cláusula de garantia contra eventual desvalorização de moeda, de acordo com índices que forem sugeridos pelo Conselho Nacional de Economia, assegurando ao mesmo Banco o ressarcimento de prejuízos já previstos no artigo 4º da Lei nº 2.237, de 19 de junho de 1954.
```
`lei_4504_19641130#260` (PAR, base):
```text
[ LEI Nº 4.504, DE 30 DE NOVEMBRO DE 1964 | Dispõe sobre o Estatuto da Terra, e dá outras providências. ] Art. 126. § 2º Caberá à Diretoria do Banco do Brasil fixar o limite do valor dos empréstimos que o Banco fica autorizado a realizar no País ou no estrangeiro para aplicação, pela sua Carteira de Colonização, revogado, portanto o limite estabelecido no parágrafo único do art. 8º da Lei número 2.237, de 19 de junho de 1964, e as disposições em contrário.
```
`lei_4504_19641130#c260` (PAR, caput):
```text
[ LEI Nº 4.504, DE 30 DE NOVEMBRO DE 1964 | Dispõe sobre o Estatuto da Terra, e dá outras providências. ] Art. 126. A Carteira de Colonização do Banco do Brasil, sem prejuízo de suas atribuições legais, atuará como entidade financiadora nas operações de venda de lotes rurais ...VETADO. § 2º Caberá à Diretoria do Banco do Brasil fixar o limite do valor dos empréstimos que o Banco fica autorizado a realizar no País ou no estrangeiro para aplicação, pela sua Carteira de Colonização, revogado, portanto o limite estabelecido no parágrafo único do art. 8º da Lei número 2.237, de 19 de junho de 1964, e as disposições em contrário.
```
`lei_4504_19641130#394` (ART, base):
```text
[ LEI Nº 4.504, DE 30 DE NOVEMBRO DE 1964 | Dispõe sobre o Estatuto da Terra, e dá outras providências. ] Art. 126. A Carteira de Colonização do Banco do Brasil, sem prejuízo de suas atribuições legais, atuará como entidade financiadora nas operações de venda de lotes rurais ...VETADO. § 1º As Letras Hipotecárias que o Banco do Brasil está autorizado a emitir, em provimento de recursos e em empréstimos da sua Carteira de Colonização, poderão conter cláusula de garantia contra eventual desvalorização de moeda, de acordo com índices que forem sugeridos pelo Conselho Nacional de Economia, assegurando ao mesmo Banco o ressarcimento de prejuízos já previstos no artigo 4º da Lei nº 2.237, de 19 de junho de 1954. § 2º Caberá à Diretoria do Banco do Brasil fixar o limite do valor dos empréstimos que o Banco fica autorizado a realizar no País ou no estrangeiro para aplicação, pela sua Carteira de Colonização, revogado, portanto o limite estabelecido no parágrafo único do art. 8º da Lei número 2.237, de 19 de junho de 1964, e as disposições em contrário.
```
`lei_4504_19641130#400` (TIT, 5309 tokens, shortened):
```text
[ LEI Nº 4.504, DE 30 DE NOVEMBRO DE 1964 | Dispõe sobre o Estatuto da Terra, e dá outras providências. ] TÍTULO IV DAS DISPOSIÇÕES GERAIS E TRANSITÓRIAS Art. 103. A aplicação da presente Lei deverá objetivar, antes e acima de tudo, a perfeita ordenação do sistema agrário do País, de acordo com os princípios da justiça social, conciliando a liberdade de iniciativa com a valorização do trabalho humano. § 1º Para a plena execução do disposto neste artigo, o Poder Executivo, através dos órgãos da s … [17,709 chars omitted] … to o limite estabelecido no parágrafo único do art. 8º da Lei número 2.237, de 19 de junho de 1964, e as disposições em contrário. Art. 127. VETADO. Art. 128. Esta Lei entrará em vigor na data de sua publicação, revogadas as disposições em contrário.
```

#### A3. `lei_13105_20150316.xml` — `art657` (article with paragraphs (main document))

- Document: `lei_13105_20150316` — LEI Nº 13.105, DE 16 DE MARÇO DE 2015; cited by 11 question(s); this article is not cited.
- Groupings (`agrupadores_rotulos`): PARTE ESPECIAL ; LIVRO I – DO PROCESSO DE CONHECIMENTO E DO CUMPRIMENTO DE SENTENÇA ; TÍTULO III – DOS PROCEDIMENTOS ESPECIAIS ; CAPÍTULO VI – DO INVENTÁRIO E DA PARTILHA ; Seção VIII – Da Partilha; source interval Num 6234–6245.

**LexML parse** (`id [element]: Rotulo + own text`; «…» = quoted amendment text):

```text
art657 [Artigo]: Art. 657.
  art657_cpt [Caput]: A partilha amigável, lavrada em instrumento público, reduzida a termo nos autos do inventário ou constante de escrito particular homologado pelo juiz, pode ser anulada por dolo, coação, erro essencial ou intervenção de incapaz, observado o disposto no § 4º do art. 966.
  art657_par1u [Paragrafo]: Parágrafo único. O direito à anulação de partilha amigável extingue-se em 1 (um) ano, contado esse prazo:
    art657_par1u_inc1 [Inciso]: I – no caso de coação, do dia em que ela cessou;
    art657_par1u_inc2 [Inciso]: II – no caso de erro ou dolo, do dia em que se realizou o ato;
    art657_par1u_inc3 [Inciso]: III – quanto ao incapaz, do dia em que cessar a incapacidade.
```

**Chunks and strategy membership** (✓ = indexed by the strategy):

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `lei_13105_20150316#344` | CPT | base | `art657_cpt` | 6235–6236 | 122 |  | ✓ | ✓ | ✓ | ✓ |
| `lei_13105_20150316#1437` | PAR | base | `art657_par1u` | 6237–6244 | 131 |  | ✓ | ✓ |  |  |
| `lei_13105_20150316#c1437` | PAR | caput | `art657_par1u` | 6237–6244 | 212 |  |  |  | ✓ | ✓ |
| `lei_13105_20150316#2754` | ART | base | `art657` | 6234–6245 | 212 | ✓ | ✓ | ✓ | ✓ | ✓ |
| `lei_13105_20150316#4189` | INC | base | `art657_par1u_inc1` | 6238–6239 | 93 |  | ✓ | ✓ |  |  |
| `lei_13105_20150316#c4189` | INC | caput | `art657_par1u_inc1` | 6238–6239 | 174 |  |  |  | ✓ | ✓ |
| `lei_13105_20150316#4190` | INC | base | `art657_par1u_inc2` | 6240–6241 | 98 |  | ✓ | ✓ |  |  |
| `lei_13105_20150316#c4190` | INC | caput | `art657_par1u_inc2` | 6240–6241 | 179 |  |  |  | ✓ | ✓ |
| `lei_13105_20150316#4191` | INC | base | `art657_par1u_inc3` | 6242–6243 | 94 |  | ✓ | ✓ |  |  |
| `lei_13105_20150316#c4191` | INC | caput | `art657_par1u_inc3` | 6242–6243 | 175 |  |  |  | ✓ | ✓ |

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `lei_13105_20150316#3376` | SEC | base | `prt2_liv1_tit3_cap6_sec8` | 6151–6256 | 1428 |  |  | ✓ |  | ✓ |

**Chunk texts** (in `chunk_id` order; grouping chunks shortened):

`lei_13105_20150316#344` (CPT, base):
```text
[ LEI Nº 13.105, DE 16 DE MARÇO DE 2015 | Código de Processo Civil. ] Art. 657. A partilha amigável, lavrada em instrumento público, reduzida a termo nos autos do inventário ou constante de escrito particular homologado pelo juiz, pode ser anulada por dolo, coação, erro essencial ou intervenção de incapaz, observado o disposto no § 4º do art. 966.
```
`lei_13105_20150316#1437` (PAR, base):
```text
[ LEI Nº 13.105, DE 16 DE MARÇO DE 2015 | Código de Processo Civil. ] Art. 657. Parágrafo único. O direito à anulação de partilha amigável extingue-se em 1 (um) ano, contado esse prazo: I – no caso de coação, do dia em que ela cessou; II – no caso de erro ou dolo, do dia em que se realizou o ato; III – quanto ao incapaz, do dia em que cessar a incapacidade.
```
`lei_13105_20150316#c1437` (PAR, caput):
```text
[ LEI Nº 13.105, DE 16 DE MARÇO DE 2015 | Código de Processo Civil. ] Art. 657. A partilha amigável, lavrada em instrumento público, reduzida a termo nos autos do inventário ou constante de escrito particular homologado pelo juiz, pode ser anulada por dolo, coação, erro essencial ou intervenção de incapaz, observado o disposto no § 4º do art. 966. Parágrafo único. O direito à anulação de partilha amigável extingue-se em 1 (um) ano, contado esse prazo: I – no caso de coação, do dia em que ela cessou; II – no caso de erro ou dolo, do dia em que se realizou o ato; III – quanto ao incapaz, do dia em que cessar a incapacidade.
```
`lei_13105_20150316#2754` (ART, base):
```text
[ LEI Nº 13.105, DE 16 DE MARÇO DE 2015 | Código de Processo Civil. ] Art. 657. A partilha amigável, lavrada em instrumento público, reduzida a termo nos autos do inventário ou constante de escrito particular homologado pelo juiz, pode ser anulada por dolo, coação, erro essencial ou intervenção de incapaz, observado o disposto no § 4º do art. 966. Parágrafo único. O direito à anulação de partilha amigável extingue-se em 1 (um) ano, contado esse prazo: I – no caso de coação, do dia em que ela cessou; II – no caso de erro ou dolo, do dia em que se realizou o ato; III – quanto ao incapaz, do dia em que cessar a incapacidade.
```
`lei_13105_20150316#4189` (INC, base):
```text
[ LEI Nº 13.105, DE 16 DE MARÇO DE 2015 | Código de Processo Civil. ] Art. 657. Parágrafo único. O direito à anulação de partilha amigável extingue-se em 1 (um) ano, contado esse prazo: I – no caso de coação, do dia em que ela cessou;
```
`lei_13105_20150316#c4189` (INC, caput):
```text
[ LEI Nº 13.105, DE 16 DE MARÇO DE 2015 | Código de Processo Civil. ] Art. 657. A partilha amigável, lavrada em instrumento público, reduzida a termo nos autos do inventário ou constante de escrito particular homologado pelo juiz, pode ser anulada por dolo, coação, erro essencial ou intervenção de incapaz, observado o disposto no § 4º do art. 966. Parágrafo único. O direito à anulação de partilha amigável extingue-se em 1 (um) ano, contado esse prazo: I – no caso de coação, do dia em que ela cessou;
```
`lei_13105_20150316#4190` (INC, base):
```text
[ LEI Nº 13.105, DE 16 DE MARÇO DE 2015 | Código de Processo Civil. ] Art. 657. Parágrafo único. O direito à anulação de partilha amigável extingue-se em 1 (um) ano, contado esse prazo: II – no caso de erro ou dolo, do dia em que se realizou o ato;
```
`lei_13105_20150316#c4190` (INC, caput):
```text
[ LEI Nº 13.105, DE 16 DE MARÇO DE 2015 | Código de Processo Civil. ] Art. 657. A partilha amigável, lavrada em instrumento público, reduzida a termo nos autos do inventário ou constante de escrito particular homologado pelo juiz, pode ser anulada por dolo, coação, erro essencial ou intervenção de incapaz, observado o disposto no § 4º do art. 966. Parágrafo único. O direito à anulação de partilha amigável extingue-se em 1 (um) ano, contado esse prazo: II – no caso de erro ou dolo, do dia em que se realizou o ato;
```
`lei_13105_20150316#4191` (INC, base):
```text
[ LEI Nº 13.105, DE 16 DE MARÇO DE 2015 | Código de Processo Civil. ] Art. 657. Parágrafo único. O direito à anulação de partilha amigável extingue-se em 1 (um) ano, contado esse prazo: III – quanto ao incapaz, do dia em que cessar a incapacidade.
```
`lei_13105_20150316#c4191` (INC, caput):
```text
[ LEI Nº 13.105, DE 16 DE MARÇO DE 2015 | Código de Processo Civil. ] Art. 657. A partilha amigável, lavrada em instrumento público, reduzida a termo nos autos do inventário ou constante de escrito particular homologado pelo juiz, pode ser anulada por dolo, coação, erro essencial ou intervenção de incapaz, observado o disposto no § 4º do art. 966. Parágrafo único. O direito à anulação de partilha amigável extingue-se em 1 (um) ano, contado esse prazo: III – quanto ao incapaz, do dia em que cessar a incapacidade.
```
`lei_13105_20150316#3376` (SEC, 1428 tokens, shortened):
```text
[ LEI Nº 13.105, DE 16 DE MARÇO DE 2015 | Código de Processo Civil. ] Seção VIII Da Partilha Art. 647. Cumprido o disposto no art. 642, § 3º, o juiz facultará às partes que, no prazo comum de 15 (quinze) dias, formulem o pedido de quinhão e, em seguida, proferirá a decisão de deliberação da partilha, resolvendo os pedidos das partes e designando os bens que devam constituir quinhão de cada herdeiro e legatário. Parágrafo único. O juiz poderá, em decisão fundamentada, deferir antecipadamente a qu … [3,838 chars omitted] …  incapaz, do dia em que cessar a incapacidade. Art. 658. É rescindível a partilha julgada por sentença: I – nos casos mencionados no art. 657; II – se feita com preterição de formalidades legais; III – se preteriu herdeiro ou incluiu quem não o seja.
```

#### A4. `lei_10406_20020110.xml` — `art1341` (article with paragraphs (main document))

- Document: `lei_10406_20020110` — LEI Nº 10.406, DE 10 DE JANEIRO DE 2002; cited by 24 question(s); this article is not cited.
- Groupings (`agrupadores_rotulos`): PARTE ESPECIAL ; LIVRO III – Do Direito das Coisas ; TÍTULO III – Da Propriedade ; CAPÍTULO VII – Do Condomínio Edilício ; Seção I – Disposições Gerais; source interval Num 7936–7951.

**LexML parse** (`id [element]: Rotulo + own text`; «…» = quoted amendment text):

```text
art1341 [Artigo]: Art. 1.341.
  art1341_cpt [Caput]: A realização de obras no condomínio depende:
    art1341_cpt_inc1 [Inciso]: I – se voluptuárias, de voto de dois terços dos condôminos;
    art1341_cpt_inc2 [Inciso]: II – se úteis, de voto da maioria dos condôminos.
  art1341_par1 [Paragrafo]: § 1º As obras ou reparações necessárias podem ser realizadas, independentemente de autorização, pelo síndico, ou, em caso de omissão ou impedimento deste, por qualquer condômino.
  art1341_par2 [Paragrafo]: § 2º Se as obras ou reparos necessários forem urgentes e importarem em despesas excessivas, determinada sua realização, o síndico ou o condômino que tomou a iniciativa delas dará ciência à assembléia, que deverá ser convocada imediatamente.
  art1341_par3 [Paragrafo]: § 3º Não sendo urgentes, as obras ou reparos necessários, que importarem em despesas excessivas, somente poderão ser efetuadas após autorização da assembléia, especialmente convocada pelo síndico, ou, em caso de omissão ou impedimento deste, por qualquer dos condôminos.
  art1341_par4 [Paragrafo]: § 4º O condômino que realizar obras ou reparos necessários será reembolsado das despesas que efetuar, não tendo direito à restituição das que fizer com obras ou reparos de outra natureza, embora de interesse comum.
```

**Chunks and strategy membership** (✓ = indexed by the strategy):

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `lei_10406_20020110#381` | CPT | base | `art1341_cpt` | 7937–7942 | 95 |  | ✓ | ✓ | ✓ | ✓ |
| `lei_10406_20020110#1178` | PAR | base | `art1341_par1` | 7943–7944 | 90 |  | ✓ | ✓ |  |  |
| `lei_10406_20020110#c1178` | PAR | caput | `art1341_par1` | 7943–7944 | 102 |  |  |  | ✓ | ✓ |
| `lei_10406_20020110#1179` | PAR | base | `art1341_par2` | 7945–7946 | 114 |  | ✓ | ✓ |  |  |
| `lei_10406_20020110#c1179` | PAR | caput | `art1341_par2` | 7945–7946 | 126 |  |  |  | ✓ | ✓ |
| `lei_10406_20020110#1180` | PAR | base | `art1341_par3` | 7947–7948 | 116 |  | ✓ | ✓ |  |  |
| `lei_10406_20020110#c1180` | PAR | caput | `art1341_par3` | 7947–7948 | 128 |  |  |  | ✓ | ✓ |
| `lei_10406_20020110#1181` | PAR | base | `art1341_par4` | 7949–7950 | 103 |  | ✓ | ✓ |  |  |
| `lei_10406_20020110#c1181` | PAR | caput | `art1341_par4` | 7949–7950 | 115 |  |  |  | ✓ | ✓ |
| `lei_10406_20020110#2901` | ART | base | `art1341` | 7936–7951 | 346 | ✓ | ✓ | ✓ | ✓ | ✓ |
| `lei_10406_20020110#4481` | INC | base | `art1341_cpt_inc1` | 7938–7939 | 76 |  | ✓ | ✓ | ✓ | ✓ |
| `lei_10406_20020110#4482` | INC | base | `art1341_cpt_inc2` | 7940–7941 | 74 |  | ✓ | ✓ | ✓ | ✓ |

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `lei_10406_20020110#3813` | CAP | base | `prt2_liv3_tit3_cap7` | 7838–8107 | 5667 |  |  | ✓ |  | ✓ |
| `lei_10406_20020110#3989` | SEC | base | `prt2_liv3_tit3_cap7_sec1` | 7839–7972 | 2555 |  |  | ✓ |  | ✓ |

**Chunk texts** (in `chunk_id` order; grouping chunks shortened):

`lei_10406_20020110#381` (CPT, base):
```text
[ LEI Nº 10.406, DE 10 DE JANEIRO DE 2002 | Institui o Código Civil. ] Art. 1.341. A realização de obras no condomínio depende: I – se voluptuárias, de voto de dois terços dos condôminos; II – se úteis, de voto da maioria dos condôminos.
```
`lei_10406_20020110#1178` (PAR, base):
```text
[ LEI Nº 10.406, DE 10 DE JANEIRO DE 2002 | Institui o Código Civil. ] Art. 1.341. § 1º As obras ou reparações necessárias podem ser realizadas, independentemente de autorização, pelo síndico, ou, em caso de omissão ou impedimento deste, por qualquer condômino.
```
`lei_10406_20020110#c1178` (PAR, caput):
```text
[ LEI Nº 10.406, DE 10 DE JANEIRO DE 2002 | Institui o Código Civil. ] Art. 1.341. A realização de obras no condomínio depende: § 1º As obras ou reparações necessárias podem ser realizadas, independentemente de autorização, pelo síndico, ou, em caso de omissão ou impedimento deste, por qualquer condômino.
```
`lei_10406_20020110#1179` (PAR, base):
```text
[ LEI Nº 10.406, DE 10 DE JANEIRO DE 2002 | Institui o Código Civil. ] Art. 1.341. § 2º Se as obras ou reparos necessários forem urgentes e importarem em despesas excessivas, determinada sua realização, o síndico ou o condômino que tomou a iniciativa delas dará ciência à assembléia, que deverá ser convocada imediatamente.
```
`lei_10406_20020110#c1179` (PAR, caput):
```text
[ LEI Nº 10.406, DE 10 DE JANEIRO DE 2002 | Institui o Código Civil. ] Art. 1.341. A realização de obras no condomínio depende: § 2º Se as obras ou reparos necessários forem urgentes e importarem em despesas excessivas, determinada sua realização, o síndico ou o condômino que tomou a iniciativa delas dará ciência à assembléia, que deverá ser convocada imediatamente.
```
`lei_10406_20020110#1180` (PAR, base):
```text
[ LEI Nº 10.406, DE 10 DE JANEIRO DE 2002 | Institui o Código Civil. ] Art. 1.341. § 3º Não sendo urgentes, as obras ou reparos necessários, que importarem em despesas excessivas, somente poderão ser efetuadas após autorização da assembléia, especialmente convocada pelo síndico, ou, em caso de omissão ou impedimento deste, por qualquer dos condôminos.
```
`lei_10406_20020110#c1180` (PAR, caput):
```text
[ LEI Nº 10.406, DE 10 DE JANEIRO DE 2002 | Institui o Código Civil. ] Art. 1.341. A realização de obras no condomínio depende: § 3º Não sendo urgentes, as obras ou reparos necessários, que importarem em despesas excessivas, somente poderão ser efetuadas após autorização da assembléia, especialmente convocada pelo síndico, ou, em caso de omissão ou impedimento deste, por qualquer dos condôminos.
```
`lei_10406_20020110#1181` (PAR, base):
```text
[ LEI Nº 10.406, DE 10 DE JANEIRO DE 2002 | Institui o Código Civil. ] Art. 1.341. § 4º O condômino que realizar obras ou reparos necessários será reembolsado das despesas que efetuar, não tendo direito à restituição das que fizer com obras ou reparos de outra natureza, embora de interesse comum.
```
`lei_10406_20020110#c1181` (PAR, caput):
```text
[ LEI Nº 10.406, DE 10 DE JANEIRO DE 2002 | Institui o Código Civil. ] Art. 1.341. A realização de obras no condomínio depende: § 4º O condômino que realizar obras ou reparos necessários será reembolsado das despesas que efetuar, não tendo direito à restituição das que fizer com obras ou reparos de outra natureza, embora de interesse comum.
```
`lei_10406_20020110#2901` (ART, base):
```text
[ LEI Nº 10.406, DE 10 DE JANEIRO DE 2002 | Institui o Código Civil. ] Art. 1.341. A realização de obras no condomínio depende: I – se voluptuárias, de voto de dois terços dos condôminos; II – se úteis, de voto da maioria dos condôminos. § 1º As obras ou reparações necessárias podem ser realizadas, independentemente de autorização, pelo síndico, ou, em caso de omissão ou impedimento deste, por qualquer condômino. § 2º Se as obras ou reparos necessários forem urgentes e importarem em despesas excessivas, determinada sua realização, o síndico ou o condômino que tomou a iniciativa delas dará ciência à assembléia, que deverá ser convocada imediatamente. § 3º Não sendo urgentes, as obras ou reparos necessários, que importarem em despesas excessivas, somente poderão ser efetuadas após autorização da assembléia, especialmente convocada pelo síndico, ou, em caso de omissão ou impedimento deste, por qualquer dos condôminos. § 4º O condômino que realizar obras ou reparos necessários será reembolsado das despesas que efetuar, não tendo direito à restituição das que fizer com obras ou reparos de outra natureza, embora de interesse comum.
```
`lei_10406_20020110#4481` (INC, base):
```text
[ LEI Nº 10.406, DE 10 DE JANEIRO DE 2002 | Institui o Código Civil. ] Art. 1.341. A realização de obras no condomínio depende: I – se voluptuárias, de voto de dois terços dos condôminos;
```
`lei_10406_20020110#4482` (INC, base):
```text
[ LEI Nº 10.406, DE 10 DE JANEIRO DE 2002 | Institui o Código Civil. ] Art. 1.341. A realização de obras no condomínio depende: II – se úteis, de voto da maioria dos condôminos.
```
`lei_10406_20020110#3813` (CAP, 5667 tokens, shortened):
```text
[ LEI Nº 10.406, DE 10 DE JANEIRO DE 2002 | Institui o Código Civil. ] CAPÍTULO VII Do Condomínio Edilício Seção I Disposições Gerais Art. 1.331. Pode haver, em edificações, partes que são propriedade exclusiva, e partes que são propriedade comum dos condôminos. § 1º As partes suscetíveis de utilização independente, tais como apartamentos, escritórios, salas, lojas e sobrelojas, com as respectivas frações ideais no solo e nas outras partes comuns, sujeitam-se a propriedade exclusiva, podendo ser … [16,964 chars omitted] … porador quanto aos aspectos civis e registrários. (Incluído por Lei nº 14.382 de 27.06.2022) § 3º Para fins de incorporação imobiliária, a implantação de toda a infraestrutura ficará a cargo do empreendedor. (Incluído por Lei nº 13.465 de 11.07.2017)
```
`lei_10406_20020110#3989` (SEC, 2555 tokens, shortened):
```text
[ LEI Nº 10.406, DE 10 DE JANEIRO DE 2002 | Institui o Código Civil. ] Seção I Disposições Gerais Art. 1.331. Pode haver, em edificações, partes que são propriedade exclusiva, e partes que são propriedade comum dos condôminos. § 1º As partes suscetíveis de utilização independente, tais como apartamentos, escritórios, salas, lojas e sobrelojas, com as respectivas frações ideais no solo e nas outras partes comuns, sujeitam-se a propriedade exclusiva, podendo ser alienadas e gravadas livremente por … [7,715 chars omitted] … rt. 1.345. O adquirente de unidade responde pelos débitos do alienante, em relação ao condomínio, inclusive multas e juros moratórios. Art. 1.346. É obrigatório o seguro de toda a edificação contra o risco de incêndio ou destruição, total ou parcial.
```

#### A5. `lei_8134_19901227.xml` — `art26` (article with incisos/alíneas, no paragraph (main document))

- Document: `lei_8134_19901227` — LEI Nº 8.134, DE 27 DE DEZEMBRO DE 1990; cited by 9 question(s); this article is not cited.
- Groupings (`agrupadores_rotulos`): —; source interval Num 237–244.

**LexML parse** (`id [element]: Rotulo + own text`; «…» = quoted amendment text):

```text
art26 [Artigo]: Art. 26.
  art26_cpt [Caput]: O disposto no artigo anterior não se aplica:
    art26_cpt_inc1 [Inciso]: I – aos resgates de quotas dos fundos de renda fixa, que continuam tributados na forma do art. 47 da Lei n° 7.799, de 1989;
    art26_cpt_inc2 [Inciso]: II – aos resgates de quotas dos fundos de aplicação de curto prazo, que continuam tributados na forma do art. 48 da Lei n° 7.799, de 1989, com as alterações do art. 1° da Lei n° 7.856, de 24 de outubro de 1989.
```

**Chunks and strategy membership** (✓ = indexed by the strategy):

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `lei_8134_19901227#72` | ART | base | `art26` | 237–244 | 203 | ✓ | ✓ | ✓ | ✓ | ✓ |
| `lei_8134_19901227#112` | INC | base | `art26_cpt_inc1` | 239–240 | 115 |  | ✓ | ✓ | ✓ | ✓ |
| `lei_8134_19901227#113` | INC | base | `art26_cpt_inc2` | 241–242 | 154 |  | ✓ | ✓ | ✓ | ✓ |

**Chunk texts** (in `chunk_id` order; grouping chunks shortened):

`lei_8134_19901227#72` (ART, base):
```text
[ LEI Nº 8.134, DE 27 DE DEZEMBRO DE 1990 | Altera a legislação do Imposto de Renda e dá outras providências. ] Art. 26. O disposto no artigo anterior não se aplica: I – aos resgates de quotas dos fundos de renda fixa, que continuam tributados na forma do art. 47 da Lei n° 7.799, de 1989; II – aos resgates de quotas dos fundos de aplicação de curto prazo, que continuam tributados na forma do art. 48 da Lei n° 7.799, de 1989, com as alterações do art. 1° da Lei n° 7.856, de 24 de outubro de 1989.
```
`lei_8134_19901227#112` (INC, base):
```text
[ LEI Nº 8.134, DE 27 DE DEZEMBRO DE 1990 | Altera a legislação do Imposto de Renda e dá outras providências. ] Art. 26. O disposto no artigo anterior não se aplica: I – aos resgates de quotas dos fundos de renda fixa, que continuam tributados na forma do art. 47 da Lei n° 7.799, de 1989;
```
`lei_8134_19901227#113` (INC, base):
```text
[ LEI Nº 8.134, DE 27 DE DEZEMBRO DE 1990 | Altera a legislação do Imposto de Renda e dá outras providências. ] Art. 26. O disposto no artigo anterior não se aplica: II – aos resgates de quotas dos fundos de aplicação de curto prazo, que continuam tributados na forma do art. 48 da Lei n° 7.799, de 1989, com as alterações do art. 1° da Lei n° 7.856, de 24 de outubro de 1989.
```

#### A6. `decreto_3000_19990326.xml` — `art721` (article with incisos/alíneas, no paragraph (main document))

- Document: `decreto_3000_19990326` — DECRETO Nº 3.000, DE 26 DE MARÇO DE 1999; cited by 1 question(s); this article is not cited.
- Groupings (`agrupadores_rotulos`): LIVRO IIITRIBUTACAO – NA FONTE E SOBRE OPERAÇÕES FINANCEIRAS ; TÍTULO I – TRIBUTAÇÃO NA FONTE ; CAPÍTULO VI – RETENÇÃO E RECOLHIMENTO ; Seção I – Retenção do Imposto Responsabilidade da Fonte; source interval Num 8203–8210.

**LexML parse** (`id [element]: Rotulo + own text`; «…» = quoted amendment text):

```text
art721 [Artigo]: Art. 721.
  art721_cpt [Caput]: Compete ao procurador a retenção (Decreto-Lei nº 5.844, de 1943, art. 100, parágrafo único):
    art721_cpt_inc1 [Inciso]: I – quando se tratar de aluguéis de imóveis pertencentes a residentes no exterior;
    art721_cpt_inc2 [Inciso]: II – quando o procurador não der conhecimento à fonte de que o proprietário do rendimento reside ou é domiciliado no exterior.
```

**Chunks and strategy membership** (✓ = indexed by the strategy):

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `decreto_3000_19990326#2738` | ART | base | `art721` | 8203–8210 | 183 | ✓ | ✓ | ✓ | ✓ | ✓ |
| `decreto_3000_19990326#4598` | INC | base | `art721_cpt_inc1` | 8205–8206 | 153 |  | ✓ | ✓ | ✓ | ✓ |
| `decreto_3000_19990326#4599` | INC | base | `art721_cpt_inc2` | 8207–8208 | 160 |  | ✓ | ✓ | ✓ | ✓ |

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `decreto_3000_19990326#3164` | CAP | base | `liv6_tit1_cap6` | 8171–8242 | 1778 |  |  | ✓ |  | ✓ |
| `decreto_3000_19990326#3377` | SEC | base | `liv6_tit1_cap6_sec1` | 8172–8235 | 1696 |  |  | ✓ |  | ✓ |

**Chunk texts** (in `chunk_id` order; grouping chunks shortened):

`decreto_3000_19990326#2738` (ART, base):
```text
[ DECRETO Nº 3.000, DE 26 DE MARÇO DE 1999 | Regulamenta a tributação, fiscalização, arrecadação e administração do Imposto sobre a Renda e Proventos de Qualquer Natureza. ] Responsabilidade do Procurador de Residente ou Domiciliado no Exterior Art. 721. Compete ao procurador a retenção (Decreto-Lei nº 5.844, de 1943, art. 100, parágrafo único): I – quando se tratar de aluguéis de imóveis pertencentes a residentes no exterior; II – quando o procurador não der conhecimento à fonte de que o proprietário do rendimento reside ou é domiciliado no exterior.
```
`decreto_3000_19990326#4598` (INC, base):
```text
[ DECRETO Nº 3.000, DE 26 DE MARÇO DE 1999 | Regulamenta a tributação, fiscalização, arrecadação e administração do Imposto sobre a Renda e Proventos de Qualquer Natureza. ] Responsabilidade do Procurador de Residente ou Domiciliado no Exterior Art. 721. Compete ao procurador a retenção (Decreto-Lei nº 5.844, de 1943, art. 100, parágrafo único): I – quando se tratar de aluguéis de imóveis pertencentes a residentes no exterior;
```
`decreto_3000_19990326#4599` (INC, base):
```text
[ DECRETO Nº 3.000, DE 26 DE MARÇO DE 1999 | Regulamenta a tributação, fiscalização, arrecadação e administração do Imposto sobre a Renda e Proventos de Qualquer Natureza. ] Responsabilidade do Procurador de Residente ou Domiciliado no Exterior Art. 721. Compete ao procurador a retenção (Decreto-Lei nº 5.844, de 1943, art. 100, parágrafo único): II – quando o procurador não der conhecimento à fonte de que o proprietário do rendimento reside ou é domiciliado no exterior.
```
`decreto_3000_19990326#3164` (CAP, 1778 tokens, shortened):
```text
[ DECRETO Nº 3.000, DE 26 DE MARÇO DE 1999 | Regulamenta a tributação, fiscalização, arrecadação e administração do Imposto sobre a Renda e Proventos de Qualquer Natureza. ] CAPÍTULO VI RETENÇÃO E RECOLHIMENTO Seção I Retenção do Imposto Responsabilidade da Fonte Art. 717. Compete à fonte reter o imposto de que trata este Título, salvo disposição em contrário (Decreto-Lei nº 5.844, de 1943, arts. 99 e 100, e Lei nº 7.713, de 1988, art. 7º, § 1º). Responsabilidade no Caso de Decisão Judicial Art. … [4,741 chars omitted] …  de 1962, art. 5º, e Lei nº 8.981, de 1995, art. 63, § 2º). Seção II Prazos de Recolhimento Art. 726. Ressalvados os prazos específicos previstos neste Decreto, o imposto de renda retido na fonte deverá ser recolhido nos prazos referidos no art. 865.
```
`decreto_3000_19990326#3377` (SEC, 1696 tokens, shortened):
```text
[ DECRETO Nº 3.000, DE 26 DE MARÇO DE 1999 | Regulamenta a tributação, fiscalização, arrecadação e administração do Imposto sobre a Renda e Proventos de Qualquer Natureza. ] Seção I Retenção do Imposto Responsabilidade da Fonte Art. 717. Compete à fonte reter o imposto de que trata este Título, salvo disposição em contrário (Decreto-Lei nº 5.844, de 1943, arts. 99 e 100, e Lei nº 7.713, de 1988, art. 7º, § 1º). Responsabilidade no Caso de Decisão Judicial Art. 718. O imposto incidente sobre os r … [4,514 chars omitted] … a líquida, cabendo o reajustamento do respectivo rendimento bruto, sobre o qual recairá o imposto, ressalvadas as hipóteses a que se referem os arts. 677 e 703, parágrafo único (Lei nº 4.154, de 1962, art. 5º, e Lei nº 8.981, de 1995, art. 63, § 2º).
```

#### A7. `lei_10833_20031229.xml` — `art20` (article without sub-units (main document))

- Document: `lei_10833_20031229` — LEI Nº 10.833, DE 29 DE DEZEMBRO DE 2003; cited by 5 question(s); this article is not cited.
- Groupings (`agrupadores_rotulos`): CAPÍTULO II – DAS OUTRAS DISPOSIÇÕES RELATIVAS À LEGISLAÇÃO TRIBUTÁRIA; source interval Num 482–485.

**LexML parse** (`id [element]: Rotulo + own text`; «…» = quoted amendment text):

```text
art20 [Artigo]: Art. 20.
  art20_cpt [Caput]: O art. 11 da Lei nº 8.248, de 23 de outubro de 1991, passa a vigorar com a seguinte redação: «Art. 11. Para fazer jus aos benefícios previstos no art. 4º desta Lei, as empresas de desenvolvimento ou produção de bens e serviços de informática e automação deverão investir, anualmente, em atividades de pesquisa e desenvolvimento em tecnologia da informação a serem realizadas no País, no mínimo 5% (cinco por cento) do seu faturamento bruto no mercado interno, decorrente da comercialização de bens e serviços de informática, deduzidos os tributos correspondentes a tais comercializações, bem como o valor das aquisições de produtos incentivados na forma desta Lei e da nº 8.387, de 30 de dezembro de 1991, conforme projeto elaborado pelas próprias empresas, a partir da apresentação da proposta de projeto de que trata o § 1ºC do art. 4º desta Lei.»
```

**Chunks and strategy membership** (✓ = indexed by the strategy):

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `lei_10833_20031229#309` | ART | base | `art20` | 482–485 | 301 | ✓ | ✓ | ✓ | ✓ | ✓ |

**Chunk texts** (in `chunk_id` order; grouping chunks shortened):

`lei_10833_20031229#309` (ART, base):
```text
[ LEI Nº 10.833, DE 29 DE DEZEMBRO DE 2003 | Altera a Legislação Tributária Federal e dá outras providências. ] Art. 20. O art. 11 da Lei nº 8.248, de 23 de outubro de 1991, passa a vigorar com a seguinte redação: Art. 11. Para fazer jus aos benefícios previstos no art. 4º desta Lei, as empresas de desenvolvimento ou produção de bens e serviços de informática e automação deverão investir, anualmente, em atividades de pesquisa e desenvolvimento em tecnologia da informação a serem realizadas no País, no mínimo 5% (cinco por cento) do seu faturamento bruto no mercado interno, decorrente da comercialização de bens e serviços de informática, deduzidos os tributos correspondentes a tais comercializações, bem como o valor das aquisições de produtos incentivados na forma desta Lei e da nº 8.387, de 30 de dezembro de 1991, conforme projeto elaborado pelas próprias empresas, a partir da apresentação da proposta de projeto de que trata o § 1ºC do art. 4º desta Lei.
```

#### A8. `lei_6766_19791219.xml` — `art4` (long article split into parts (main document))

- Document: `lei_6766_19791219` — LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979; cited by 4 question(s); this article is not cited.
- Groupings (`agrupadores_rotulos`): CAPÍTULO II – DOS REQUISITOS URBANÍSTICOS PARA LOTEAMENTO; source interval Num 69–94.

**LexML parse** (`id [element]: Rotulo + own text`; «…» = quoted amendment text):

```text
art4 [Artigo]: Art. 4º
  art4_cpt [Caput]: Os loteamentos deverão atender, pelo menos, aos seguintes requisitos:
    art4_cpt_inc1 [Inciso]: I – as áreas destinadas a sistemas de circulação, a implantação de equipamento urbano e comunitário, bem como a espaços livres de uso público, serão proporcionais à densidade de ocupação prevista pelo plano diretor ou aprovada por lei municipal para a zona em que se situem. (Inciso com redação dada pela Lei nº 9.785, de 29.1.1999)
    art4_cpt_inc2 [Inciso]: II – os lotes terão área mínima de 125 m2 (cento e vinte e cinco metros quadrados) e frente mínima de 5 (cinco) metros, salvo quando a legislação estadual ou municipal determinar maiores exigências, ou quando o loteamento se destinar a urbanização específica ou edificação de conjuntos habitacionais de interesse social, previamente aprovados pelos órgãos públicos competentes;
    art4_cpt_inc3 [Inciso]: III – ao longo das faixas de domínio público das rodovias, a reserva de faixa não edificável de, no mínimo, 15 (quinze) metros de cada lado poderá ser reduzida por lei municipal ou distrital que aprovar o instrumento do planejamento territorial, até o limite mínimo de 5 (cinco) metros de cada lado. (Inciso com redação dada pela Lei nº 13.913, de 25.11.2019, republicada na Edição Extra do DOU de 26.11.2019) III-A. - ao longo da faixa de domínio das ferrovias, será obrigatória a reserva de uma faixa não edificável de, no mínimo, 15 (quinze) metros de cada lado; (Inciso acrescido pela Lei nº 13.913, de 25.11.2019, republicada na Edição Extra do DOU de 26.11.2019, com redação dada pela Lei nº 14.285, de 29.12.2021)
    art4_cpt_inc3-2 [Inciso]: III-B – ao longo das águas correntes e dormentes, as áreas de faixas não edificáveis deverão respeitar a lei municipal ou distrital que aprovar o instrumento de planejamento territorial e que definir e regulamentar a largura das faixas marginais de cursos d´água naturais em área urbana consolidada, nos termos da Lei nº 12.651, de 25 de maio de 2012, com obrigatoriedade de reserva de uma faixa não edificável para cada trecho de margem, indicada em diagnóstico socioambiental elaborado pelo Município; (Inciso acrescido pela Lei nº 14.285, de 29.12.2021)
    art4_cpt_inc4 [Inciso]: IV – as vias de loteamento deverão articular-se com as vias adjacentes oficiais, existentes ou projetadas, e harmonizar-se com a topografia local.
  art4_par1 [Paragrafo]: § 1º A legislação municipal definirá, para cada zona em que se divida o território do Município, os usos permitidos e os índices urbanísticos de parcelamento e ocupação do solo, que incluirão, obrigatoriamente, as áreas mínimas e máximas de lotes e os coeficientes máximos de aproveitamento. (Parágrafo com redação dada pela Lei nº 9.785, de 29.1.1999)
  art4_par2 [Paragrafo]: § 2º Consideram-se comunitários os equipamentos públicos de educação, cultura, saúde, lazer e similares.
  art4_par3 [Paragrafo]: § 3º Se necessária, a reserva de faixa não-edificável vinculada a dutovias será exigida no âmbito do respectivo licenciamento ambiental, observados critérios e parâmetros que garantam a segurança da população e a proteção do meio ambiente, conforme estabelecido nas normas técnicas pertinentes. (Parágrafo acrescido com redação dada pela Lei nº 10.932, de 3.8.2004)
  art4_par4 [Paragrafo]: § 4º No caso de lotes integrantes de condomínio de lotes, poderão ser instituídas limitações administrativas e direitos reais sobre coisa alheia em benefício do poder público, da população em geral e da proteção da paisagem urbana, tais como servidões de passagem, usufrutos e restrições à construção de muros. (Parágrafo acrescido pela Lei nº 13.465, de 11.7.2017)
  art4_par5 [Paragrafo]: § 5º As edificações localizadas nas áreas contíguas às faixas de domínio público dos trechos de rodovia que atravessem perímetros urbanos ou áreas urbanizadas passíveis de serem incluídas em perímetro urbano, desde que construídas até a data de promulgação deste parágrafo, ficam dispensadas da observância da exigência prevista no inciso III do caput deste artigo, salvo por ato devidamente fundamentado do poder público municipal ou distrital. (Parágrafo acrescido pela Lei nº 13.913, de 25.11.2019, republicada na Edição Extra do DOU de 26.11.2019)
  art4_par6 [Paragrafo]: § 6º (VETADO na Lei nº 14.285, de 29.12.2021)
  art4_par7 [Paragrafo]: § 7º (VETADO na Lei nº 14.285, de 29.12.2021)
```

**Chunks and strategy membership** (✓ = indexed by the strategy):

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `lei_6766_19791219#4` | CPT | base | `art4_cpt` | 69–80 | 755 |  | ✓ | ✓ | ✓ | ✓ |
| `lei_6766_19791219#48` | PAR | base | `art4_par1` | 81–82 | 166 |  | ✓ | ✓ |  |  |
| `lei_6766_19791219#c48` | PAR | caput | `art4_par1` | 81–82 | 184 |  |  |  | ✓ | ✓ |
| `lei_6766_19791219#49` | PAR | base | `art4_par2` | 83–84 | 79 |  | ✓ | ✓ |  |  |
| `lei_6766_19791219#c49` | PAR | caput | `art4_par2` | 83–84 | 97 |  |  |  | ✓ | ✓ |
| `lei_6766_19791219#50` | PAR | base | `art4_par3` | 85–86 | 162 |  | ✓ | ✓ |  |  |
| `lei_6766_19791219#c50` | PAR | caput | `art4_par3` | 85–86 | 180 |  |  |  | ✓ | ✓ |
| `lei_6766_19791219#51` | PAR | base | `art4_par4` | 87–88 | 164 |  | ✓ | ✓ |  |  |
| `lei_6766_19791219#c51` | PAR | caput | `art4_par4` | 87–88 | 182 |  |  |  | ✓ | ✓ |
| `lei_6766_19791219#52` | PAR | base | `art4_par5` | 89–90 | 225 |  | ✓ | ✓ |  |  |
| `lei_6766_19791219#c52` | PAR | caput | `art4_par5` | 89–90 | 243 |  |  |  | ✓ | ✓ |
| `lei_6766_19791219#53` | PAR | base | `art4_par6` | 91–92 | 83 |  | ✓ | ✓ |  |  |
| `lei_6766_19791219#c53` | PAR | caput | `art4_par6` | 91–92 | 101 |  |  |  | ✓ | ✓ |
| `lei_6766_19791219#54` | PAR | base | `art4_par7` | 93–94 | 83 |  | ✓ | ✓ |  |  |
| `lei_6766_19791219#c54` | PAR | caput | `art4_par7` | 93–94 | 101 |  |  |  | ✓ | ✓ |
| `lei_6766_19791219#148` | ART | base | `art4_cpt;art4_par1;art4_par2;art4_par3` | 69–86 | 1009 | ✓ | ✓ | ✓ | ✓ | ✓ |
| `lei_6766_19791219#149` | ART | base | `art4_par4;art4_par5;art4_par6;art4_par7` | 87–94 | 420 | ✓ | ✓ | ✓ | ✓ | ✓ |
| `lei_6766_19791219#232` | INC | base | `art4_cpt_inc1` | 70–71 | 167 |  | ✓ | ✓ | ✓ | ✓ |
| `lei_6766_19791219#233` | INC | base | `art4_cpt_inc2` | 72–73 | 170 |  | ✓ | ✓ | ✓ | ✓ |
| `lei_6766_19791219#234` | INC | base | `art4_cpt_inc3` | 74–75 | 337 |  | ✓ | ✓ | ✓ | ✓ |
| `lei_6766_19791219#235` | INC | base | `art4_cpt_inc3-2` | 76–77 | 248 |  | ✓ | ✓ | ✓ | ✓ |
| `lei_6766_19791219#236` | INC | base | `art4_cpt_inc4` | 78–79 | 109 |  | ✓ | ✓ | ✓ | ✓ |

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `lei_6766_19791219#214` | CAP | base | `cap2` | 67–102 | 1481 |  |  | ✓ |  | ✓ |

**Chunk texts** (in `chunk_id` order; grouping chunks shortened):

`lei_6766_19791219#4` (CPT, base):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º Os loteamentos deverão atender, pelo menos, aos seguintes requisitos: I – as áreas destinadas a sistemas de circulação, a implantação de equipamento urbano e comunitário, bem como a espaços livres de uso público, serão proporcionais à densidade de ocupação prevista pelo plano diretor ou aprovada por lei municipal para a zona em que se situem. (Inciso com redação dada pela Lei nº 9.785, de 29.1.1999) II – os lotes terão área mínima de 125 m2 (cento e vinte e cinco metros quadrados) e frente mínima de 5 (cinco) metros, salvo quando a legislação estadual ou municipal determinar maiores exigências, ou quando o loteamento se destinar a urbanização específica ou edificação de conjuntos habitacionais de interesse social, previamente aprovados pelos órgãos públicos competentes; III – ao longo das faixas de domínio público das rodovias, a reserva de faixa não edificável de, no mínimo, 15 (quinze) metros de cada lado poderá ser reduzida por lei municipal ou distrital que aprovar o instrumento do planejamento territorial, até o limite mínimo de 5 (cinco) metros de cada lado. (Inciso com redação dada pela Lei nº 13.913, de 25.11.2019, republicada na Edição Extra do DOU de 26.11.2019) III-A. - ao longo da faixa de domínio das ferrovias, será obrigatória a reserva de uma faixa não edificável de, no mínimo, 15 (quinze) metros de cada lado; (Inciso acrescido pela Lei nº 13.913, de 25.11.2019, republicada na Edição Extra do DOU de 26.11.2019, com redação dada pela Lei nº 14.285, de 29.12.2021) III-B – ao longo das águas correntes e dormentes, as áreas de faixas não edificáveis deverão respeitar a lei municipal ou distrital que aprovar o instrumento de planejamento territorial e que definir e regulamentar a largura das faixas marginais de cursos d´água naturais em área urbana consolidada, nos termos da Lei nº 12.651, de 25 de maio de 2012, com obrigatoriedade de reserva de uma faixa não edificável para cada trecho de margem, indicada em diagnóstico socioambiental elaborado pelo Município; (Inciso acrescido pela Lei nº 14.285, de 29.12.2021) IV – as vias de loteamento deverão articular-se com as vias adjacentes oficiais, existentes ou projetadas, e harmonizar-se com a topografia local.
```
`lei_6766_19791219#48` (PAR, base):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º § 1º A legislação municipal definirá, para cada zona em que se divida o território do Município, os usos permitidos e os índices urbanísticos de parcelamento e ocupação do solo, que incluirão, obrigatoriamente, as áreas mínimas e máximas de lotes e os coeficientes máximos de aproveitamento. (Parágrafo com redação dada pela Lei nº 9.785, de 29.1.1999)
```
`lei_6766_19791219#c48` (PAR, caput):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º Os loteamentos deverão atender, pelo menos, aos seguintes requisitos: § 1º A legislação municipal definirá, para cada zona em que se divida o território do Município, os usos permitidos e os índices urbanísticos de parcelamento e ocupação do solo, que incluirão, obrigatoriamente, as áreas mínimas e máximas de lotes e os coeficientes máximos de aproveitamento. (Parágrafo com redação dada pela Lei nº 9.785, de 29.1.1999)
```
`lei_6766_19791219#49` (PAR, base):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º § 2º Consideram-se comunitários os equipamentos públicos de educação, cultura, saúde, lazer e similares.
```
`lei_6766_19791219#c49` (PAR, caput):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º Os loteamentos deverão atender, pelo menos, aos seguintes requisitos: § 2º Consideram-se comunitários os equipamentos públicos de educação, cultura, saúde, lazer e similares.
```
`lei_6766_19791219#50` (PAR, base):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º § 3º Se necessária, a reserva de faixa não-edificável vinculada a dutovias será exigida no âmbito do respectivo licenciamento ambiental, observados critérios e parâmetros que garantam a segurança da população e a proteção do meio ambiente, conforme estabelecido nas normas técnicas pertinentes. (Parágrafo acrescido com redação dada pela Lei nº 10.932, de 3.8.2004)
```
`lei_6766_19791219#c50` (PAR, caput):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º Os loteamentos deverão atender, pelo menos, aos seguintes requisitos: § 3º Se necessária, a reserva de faixa não-edificável vinculada a dutovias será exigida no âmbito do respectivo licenciamento ambiental, observados critérios e parâmetros que garantam a segurança da população e a proteção do meio ambiente, conforme estabelecido nas normas técnicas pertinentes. (Parágrafo acrescido com redação dada pela Lei nº 10.932, de 3.8.2004)
```
`lei_6766_19791219#51` (PAR, base):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º § 4º No caso de lotes integrantes de condomínio de lotes, poderão ser instituídas limitações administrativas e direitos reais sobre coisa alheia em benefício do poder público, da população em geral e da proteção da paisagem urbana, tais como servidões de passagem, usufrutos e restrições à construção de muros. (Parágrafo acrescido pela Lei nº 13.465, de 11.7.2017)
```
`lei_6766_19791219#c51` (PAR, caput):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º Os loteamentos deverão atender, pelo menos, aos seguintes requisitos: § 4º No caso de lotes integrantes de condomínio de lotes, poderão ser instituídas limitações administrativas e direitos reais sobre coisa alheia em benefício do poder público, da população em geral e da proteção da paisagem urbana, tais como servidões de passagem, usufrutos e restrições à construção de muros. (Parágrafo acrescido pela Lei nº 13.465, de 11.7.2017)
```
`lei_6766_19791219#52` (PAR, base):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º § 5º As edificações localizadas nas áreas contíguas às faixas de domínio público dos trechos de rodovia que atravessem perímetros urbanos ou áreas urbanizadas passíveis de serem incluídas em perímetro urbano, desde que construídas até a data de promulgação deste parágrafo, ficam dispensadas da observância da exigência prevista no inciso III do caput deste artigo, salvo por ato devidamente fundamentado do poder público municipal ou distrital. (Parágrafo acrescido pela Lei nº 13.913, de 25.11.2019, republicada na Edição Extra do DOU de 26.11.2019)
```
`lei_6766_19791219#c52` (PAR, caput):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º Os loteamentos deverão atender, pelo menos, aos seguintes requisitos: § 5º As edificações localizadas nas áreas contíguas às faixas de domínio público dos trechos de rodovia que atravessem perímetros urbanos ou áreas urbanizadas passíveis de serem incluídas em perímetro urbano, desde que construídas até a data de promulgação deste parágrafo, ficam dispensadas da observância da exigência prevista no inciso III do caput deste artigo, salvo por ato devidamente fundamentado do poder público municipal ou distrital. (Parágrafo acrescido pela Lei nº 13.913, de 25.11.2019, republicada na Edição Extra do DOU de 26.11.2019)
```
`lei_6766_19791219#53` (PAR, base):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º § 6º (VETADO na Lei nº 14.285, de 29.12.2021)
```
`lei_6766_19791219#c53` (PAR, caput):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º Os loteamentos deverão atender, pelo menos, aos seguintes requisitos: § 6º (VETADO na Lei nº 14.285, de 29.12.2021)
```
`lei_6766_19791219#54` (PAR, base):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º § 7º (VETADO na Lei nº 14.285, de 29.12.2021)
```
`lei_6766_19791219#c54` (PAR, caput):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º Os loteamentos deverão atender, pelo menos, aos seguintes requisitos: § 7º (VETADO na Lei nº 14.285, de 29.12.2021)
```
`lei_6766_19791219#148` (ART, base, part 1/2):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º Os loteamentos deverão atender, pelo menos, aos seguintes requisitos: I – as áreas destinadas a sistemas de circulação, a implantação de equipamento urbano e comunitário, bem como a espaços livres de uso público, serão proporcionais à densidade de ocupação prevista pelo plano diretor ou aprovada por lei municipal para a zona em que se situem. (Inciso com redação dada pela Lei nº 9.785, de 29.1.1999) II – os lotes terão área mínima de 125 m2 (cento e vinte e cinco metros quadrados) e frente mínima de 5 (cinco) metros, salvo quando a legislação estadual ou municipal determinar maiores exigências, ou quando o loteamento se destinar a urbanização específica ou edificação de conjuntos habitacionais de interesse social, previamente aprovados pelos órgãos públicos competentes; III – ao longo das faixas de domínio público das rodovias, a reserva de faixa não edificável de, no mínimo, 15 (quinze) metros de cada lado poderá ser reduzida por lei municipal ou distrital que aprovar o instrumento do planejamento territorial, até o limite mínimo de 5 (cinco) metros de cada lado. (Inciso com redação dada pela Lei nº 13.913, de 25.11.2019, republicada na Edição Extra do DOU de 26.11.2019) III-A. - ao longo da faixa de domínio das ferrovias, será obrigatória a reserva de uma faixa não edificável de, no mínimo, 15 (quinze) metros de cada lado; (Inciso acrescido pela Lei nº 13.913, de 25.11.2019, republicada na Edição Extra do DOU de 26.11.2019, com redação dada pela Lei nº 14.285, de 29.12.2021) III-B – ao longo das águas correntes e dormentes, as áreas de faixas não edificáveis deverão respeitar a lei municipal ou distrital que aprovar o instrumento de planejamento territorial e que definir e regulamentar a largura das faixas marginais de cursos d´água naturais em área urbana consolidada, nos termos da Lei nº 12.651, de 25 de maio de 2012, com obrigatoriedade de reserva de uma faixa não edificável para cada trecho de margem, indicada em diagnóstico socioambiental elaborado pelo Município; (Inciso acrescido pela Lei nº 14.285, de 29.12.2021) IV – as vias de loteamento deverão articular-se com as vias adjacentes oficiais, existentes ou projetadas, e harmonizar-se com a topografia local. § 1º A legislação municipal definirá, para cada zona em que se divida o território do Município, os usos permitidos e os índices urbanísticos de parcelamento e ocupação do solo, que incluirão, obrigatoriamente, as áreas mínimas e máximas de lotes e os coeficientes máximos de aproveitamento. (Parágrafo com redação dada pela Lei nº 9.785, de 29.1.1999) § 2º Consideram-se comunitários os equipamentos públicos de educação, cultura, saúde, lazer e similares. § 3º Se necessária, a reserva de faixa não-edificável vinculada a dutovias será exigida no âmbito do respectivo licenciamento ambiental, observados critérios e parâmetros que garantam a segurança da população e a proteção do meio ambiente, conforme estabelecido nas normas técnicas pertinentes. (Parágrafo acrescido com redação dada pela Lei nº 10.932, de 3.8.2004)
```
`lei_6766_19791219#149` (ART, base, part 2/2):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º Os loteamentos deverão atender, pelo menos, aos seguintes requisitos: § 4º No caso de lotes integrantes de condomínio de lotes, poderão ser instituídas limitações administrativas e direitos reais sobre coisa alheia em benefício do poder público, da população em geral e da proteção da paisagem urbana, tais como servidões de passagem, usufrutos e restrições à construção de muros. (Parágrafo acrescido pela Lei nº 13.465, de 11.7.2017) § 5º As edificações localizadas nas áreas contíguas às faixas de domínio público dos trechos de rodovia que atravessem perímetros urbanos ou áreas urbanizadas passíveis de serem incluídas em perímetro urbano, desde que construídas até a data de promulgação deste parágrafo, ficam dispensadas da observância da exigência prevista no inciso III do caput deste artigo, salvo por ato devidamente fundamentado do poder público municipal ou distrital. (Parágrafo acrescido pela Lei nº 13.913, de 25.11.2019, republicada na Edição Extra do DOU de 26.11.2019) § 6º (VETADO na Lei nº 14.285, de 29.12.2021) § 7º (VETADO na Lei nº 14.285, de 29.12.2021)
```
`lei_6766_19791219#232` (INC, base):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º Os loteamentos deverão atender, pelo menos, aos seguintes requisitos: I – as áreas destinadas a sistemas de circulação, a implantação de equipamento urbano e comunitário, bem como a espaços livres de uso público, serão proporcionais à densidade de ocupação prevista pelo plano diretor ou aprovada por lei municipal para a zona em que se situem. (Inciso com redação dada pela Lei nº 9.785, de 29.1.1999)
```
`lei_6766_19791219#233` (INC, base):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º Os loteamentos deverão atender, pelo menos, aos seguintes requisitos: II – os lotes terão área mínima de 125 m2 (cento e vinte e cinco metros quadrados) e frente mínima de 5 (cinco) metros, salvo quando a legislação estadual ou municipal determinar maiores exigências, ou quando o loteamento se destinar a urbanização específica ou edificação de conjuntos habitacionais de interesse social, previamente aprovados pelos órgãos públicos competentes;
```
`lei_6766_19791219#234` (INC, base):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º Os loteamentos deverão atender, pelo menos, aos seguintes requisitos: III – ao longo das faixas de domínio público das rodovias, a reserva de faixa não edificável de, no mínimo, 15 (quinze) metros de cada lado poderá ser reduzida por lei municipal ou distrital que aprovar o instrumento do planejamento territorial, até o limite mínimo de 5 (cinco) metros de cada lado. (Inciso com redação dada pela Lei nº 13.913, de 25.11.2019, republicada na Edição Extra do DOU de 26.11.2019) III-A. - ao longo da faixa de domínio das ferrovias, será obrigatória a reserva de uma faixa não edificável de, no mínimo, 15 (quinze) metros de cada lado; (Inciso acrescido pela Lei nº 13.913, de 25.11.2019, republicada na Edição Extra do DOU de 26.11.2019, com redação dada pela Lei nº 14.285, de 29.12.2021)
```
`lei_6766_19791219#235` (INC, base):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º Os loteamentos deverão atender, pelo menos, aos seguintes requisitos: III-B – ao longo das águas correntes e dormentes, as áreas de faixas não edificáveis deverão respeitar a lei municipal ou distrital que aprovar o instrumento de planejamento territorial e que definir e regulamentar a largura das faixas marginais de cursos d´água naturais em área urbana consolidada, nos termos da Lei nº 12.651, de 25 de maio de 2012, com obrigatoriedade de reserva de uma faixa não edificável para cada trecho de margem, indicada em diagnóstico socioambiental elaborado pelo Município; (Inciso acrescido pela Lei nº 14.285, de 29.12.2021)
```
`lei_6766_19791219#236` (INC, base):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] Art. 4º Os loteamentos deverão atender, pelo menos, aos seguintes requisitos: IV – as vias de loteamento deverão articular-se com as vias adjacentes oficiais, existentes ou projetadas, e harmonizar-se com a topografia local.
```
`lei_6766_19791219#214` (CAP, 1481 tokens, shortened):
```text
[ LEI Nº 6.766, DE 19 DE DEZEMBRO DE 1979 | Dispõe sobre o parcelamento do solo urbano e dá outras providências. ] CAPÍTULO II DOS REQUISITOS URBANÍSTICOS PARA LOTEAMENTO Art. 4º Os loteamentos deverão atender, pelo menos, aos seguintes requisitos: I – as áreas destinadas a sistemas de circulação, a implantação de equipamento urbano e comunitário, bem como a espaços livres de uso público, serão proporcionais à densidade de ocupação prevista pelo plano diretor ou aprovada por lei municipal para a … [3,815 chars omitted] … a de faixa non aedificandi destinada a equipamentos urbanos. Parágrafo único. Consideram-se urbanos os equipamentos públicos de abastecimento de água, serviços de esgotos, energia elétrica, coletas de águas pluviais, rede telefônica e gás canalizado.
```

#### A9. `decreto_9580_20181122.anexo1.xml` — `art483` (article of a category-A annex (articulated annex, e.g. RIR/2018))

- Document: `decreto_9580_20181122` — DECRETO Nº 9.580, DE 22 DE NOVEMBRO DE 2018; cited by 260 question(s); this article is not cited.
- Groupings (`agrupadores_rotulos`): LIVRO DE – Apuração do Lucro Real ; CAPÍTULO VI – DISPOSIÇÕES ESPECIAIS SOBRE ATIVIDADES DAS PESSOAS JURÍDICAS ; Seção X – Da compra e da venda, do loteamento, da incorporação, da construção e da reforma de imóveis Determinação do custo; source interval Num 6704–6713.

**LexML parse** (`id [element]: Rotulo + own text`; «…» = quoted amendment text):

```text
art483 [Artigo]: Art. 483.
  art483_cpt [Caput]: Se a venda for contratada antes de completado o empreendimento, o contribuinte poderá computar no custo do imóvel vendido, além dos custos pagos, incorridos ou contratados, os orçados para a conclusão das obras ou dos melhoramentos a que estiver contratualmente obrigado a realizar ( Decreto-Lei nº 1.598, de 1977, art. 28, caput ).
  art483_par1 [Paragrafo]: § 1º O custo orçado será baseado nos custos usuais no tipo de empreendimento imobiliário ( Decreto-Lei nº 1.598, de 1977, art. 28, § 1º ).
  art483_par2 [Paragrafo]: § 2º Se a execução das obras ou dos melhoramentos a que se obrigou o contribuinte se estender além do período de apuração da venda e o custo efetivamente realizado for inferior, em mais de quinze por cento, ao custo orçado computado na determinação do lucro bruto, o contribuinte ficará obrigado a pagar juros de mora sobre o valor do imposto postergado pela dedução de custo orçado excedente ao realizado ( Decreto-Lei nº 1.598, de 1977, art. 28, § 2º ).
  art483_par3 [Paragrafo]: § 3º Os juros de mora de que trata o § 2º deverão ser pagos juntamente ao imposto sobre a renda incidente no período de apuração em que tiver terminado a execução das obras ou dos melhoramentos ( Decreto-Lei nº 1.598, de 1977, art. 28, § 3º ).
```

**Chunks and strategy membership** (✓ = indexed by the strategy):

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `decreto_9580_20181122.anexo1#320` | CPT | base | `art483_cpt` | 6705–6706 | 195 |  | ✓ | ✓ | ✓ | ✓ |
| `decreto_9580_20181122.anexo1#1578` | PAR | base | `art483_par1` | 6707–6708 | 153 |  | ✓ | ✓ |  |  |
| `decreto_9580_20181122.anexo1#c1578` | PAR | caput | `art483_par1` | 6707–6708 | 253 |  |  |  | ✓ | ✓ |
| `decreto_9580_20181122.anexo1#1579` | PAR | base | `art483_par2` | 6709–6710 | 237 |  | ✓ | ✓ |  |  |
| `decreto_9580_20181122.anexo1#c1579` | PAR | caput | `art483_par2` | 6709–6710 | 337 |  |  |  | ✓ | ✓ |
| `decreto_9580_20181122.anexo1#1580` | PAR | base | `art483_par3` | 6711–6712 | 182 |  | ✓ | ✓ |  |  |
| `decreto_9580_20181122.anexo1#c1580` | PAR | caput | `art483_par3` | 6711–6712 | 282 |  |  |  | ✓ | ✓ |
| `decreto_9580_20181122.anexo1#3042` | ART | base | `art483` | 6704–6713 | 482 | ✓ | ✓ | ✓ | ✓ | ✓ |

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `decreto_9580_20181122.anexo1#3926` | SEC | base | `liv4_cap6_sec10` | 6687–6862 | 5498 |  |  | ✓ |  | ✓ |

**Chunk texts** (in `chunk_id` order; grouping chunks shortened):

`decreto_9580_20181122.anexo1#320` (CPT, base):
```text
[ DECRETO Nº 9.580, DE 22 DE NOVEMBRO DE 2018 | Regulamenta a tributação, a fiscalização, a arrecadação e a administração do Imposto sobre a Renda e Proventos de Qualquer Natureza. | Anexo 1 – ANEXO ] Venda anterior ao término do empreendimento Art. 483. Se a venda for contratada antes de completado o empreendimento, o contribuinte poderá computar no custo do imóvel vendido, além dos custos pagos, incorridos ou contratados, os orçados para a conclusão das obras ou dos melhoramentos a que estiver contratualmente obrigado a realizar ( Decreto-Lei nº 1.598, de 1977, art. 28, caput ).
```
`decreto_9580_20181122.anexo1#1578` (PAR, base):
```text
[ DECRETO Nº 9.580, DE 22 DE NOVEMBRO DE 2018 | Regulamenta a tributação, a fiscalização, a arrecadação e a administração do Imposto sobre a Renda e Proventos de Qualquer Natureza. | Anexo 1 – ANEXO ] Venda anterior ao término do empreendimento Art. 483. § 1º O custo orçado será baseado nos custos usuais no tipo de empreendimento imobiliário ( Decreto-Lei nº 1.598, de 1977, art. 28, § 1º ).
```
`decreto_9580_20181122.anexo1#c1578` (PAR, caput):
```text
[ DECRETO Nº 9.580, DE 22 DE NOVEMBRO DE 2018 | Regulamenta a tributação, a fiscalização, a arrecadação e a administração do Imposto sobre a Renda e Proventos de Qualquer Natureza. | Anexo 1 – ANEXO ] Venda anterior ao término do empreendimento Art. 483. Se a venda for contratada antes de completado o empreendimento, o contribuinte poderá computar no custo do imóvel vendido, além dos custos pagos, incorridos ou contratados, os orçados para a conclusão das obras ou dos melhoramentos a que estiver contratualmente obrigado a realizar ( Decreto-Lei nº 1.598, de 1977, art. 28, caput ). § 1º O custo orçado será baseado nos custos usuais no tipo de empreendimento imobiliário ( Decreto-Lei nº 1.598, de 1977, art. 28, § 1º ).
```
`decreto_9580_20181122.anexo1#1579` (PAR, base):
```text
[ DECRETO Nº 9.580, DE 22 DE NOVEMBRO DE 2018 | Regulamenta a tributação, a fiscalização, a arrecadação e a administração do Imposto sobre a Renda e Proventos de Qualquer Natureza. | Anexo 1 – ANEXO ] Venda anterior ao término do empreendimento Art. 483. § 2º Se a execução das obras ou dos melhoramentos a que se obrigou o contribuinte se estender além do período de apuração da venda e o custo efetivamente realizado for inferior, em mais de quinze por cento, ao custo orçado computado na determinação do lucro bruto, o contribuinte ficará obrigado a pagar juros de mora sobre o valor do imposto postergado pela dedução de custo orçado excedente ao realizado ( Decreto-Lei nº 1.598, de 1977, art. 28, § 2º ).
```
`decreto_9580_20181122.anexo1#c1579` (PAR, caput):
```text
[ DECRETO Nº 9.580, DE 22 DE NOVEMBRO DE 2018 | Regulamenta a tributação, a fiscalização, a arrecadação e a administração do Imposto sobre a Renda e Proventos de Qualquer Natureza. | Anexo 1 – ANEXO ] Venda anterior ao término do empreendimento Art. 483. Se a venda for contratada antes de completado o empreendimento, o contribuinte poderá computar no custo do imóvel vendido, além dos custos pagos, incorridos ou contratados, os orçados para a conclusão das obras ou dos melhoramentos a que estiver contratualmente obrigado a realizar ( Decreto-Lei nº 1.598, de 1977, art. 28, caput ). § 2º Se a execução das obras ou dos melhoramentos a que se obrigou o contribuinte se estender além do período de apuração da venda e o custo efetivamente realizado for inferior, em mais de quinze por cento, ao custo orçado computado na determinação do lucro bruto, o contribuinte ficará obrigado a pagar juros de mora sobre o valor do imposto postergado pela dedução de custo orçado excedente ao realizado ( Decreto-Lei nº 1.598, de 1977, art. 28, § 2º ).
```
`decreto_9580_20181122.anexo1#1580` (PAR, base):
```text
[ DECRETO Nº 9.580, DE 22 DE NOVEMBRO DE 2018 | Regulamenta a tributação, a fiscalização, a arrecadação e a administração do Imposto sobre a Renda e Proventos de Qualquer Natureza. | Anexo 1 – ANEXO ] Venda anterior ao término do empreendimento Art. 483. § 3º Os juros de mora de que trata o § 2º deverão ser pagos juntamente ao imposto sobre a renda incidente no período de apuração em que tiver terminado a execução das obras ou dos melhoramentos ( Decreto-Lei nº 1.598, de 1977, art. 28, § 3º ).
```
`decreto_9580_20181122.anexo1#c1580` (PAR, caput):
```text
[ DECRETO Nº 9.580, DE 22 DE NOVEMBRO DE 2018 | Regulamenta a tributação, a fiscalização, a arrecadação e a administração do Imposto sobre a Renda e Proventos de Qualquer Natureza. | Anexo 1 – ANEXO ] Venda anterior ao término do empreendimento Art. 483. Se a venda for contratada antes de completado o empreendimento, o contribuinte poderá computar no custo do imóvel vendido, além dos custos pagos, incorridos ou contratados, os orçados para a conclusão das obras ou dos melhoramentos a que estiver contratualmente obrigado a realizar ( Decreto-Lei nº 1.598, de 1977, art. 28, caput ). § 3º Os juros de mora de que trata o § 2º deverão ser pagos juntamente ao imposto sobre a renda incidente no período de apuração em que tiver terminado a execução das obras ou dos melhoramentos ( Decreto-Lei nº 1.598, de 1977, art. 28, § 3º ).
```
`decreto_9580_20181122.anexo1#3042` (ART, base):
```text
[ DECRETO Nº 9.580, DE 22 DE NOVEMBRO DE 2018 | Regulamenta a tributação, a fiscalização, a arrecadação e a administração do Imposto sobre a Renda e Proventos de Qualquer Natureza. | Anexo 1 – ANEXO ] Venda anterior ao término do empreendimento Art. 483. Se a venda for contratada antes de completado o empreendimento, o contribuinte poderá computar no custo do imóvel vendido, além dos custos pagos, incorridos ou contratados, os orçados para a conclusão das obras ou dos melhoramentos a que estiver contratualmente obrigado a realizar ( Decreto-Lei nº 1.598, de 1977, art. 28, caput ). § 1º O custo orçado será baseado nos custos usuais no tipo de empreendimento imobiliário ( Decreto-Lei nº 1.598, de 1977, art. 28, § 1º ). § 2º Se a execução das obras ou dos melhoramentos a que se obrigou o contribuinte se estender além do período de apuração da venda e o custo efetivamente realizado for inferior, em mais de quinze por cento, ao custo orçado computado na determinação do lucro bruto, o contribuinte ficará obrigado a pagar juros de mora sobre o valor do imposto postergado pela dedução de custo orçado excedente ao realizado ( Decreto-Lei nº 1.598, de 1977, art. 28, § 2º ). § 3º Os juros de mora de que trata o § 2º deverão ser pagos juntamente ao imposto sobre a renda incidente no período de apuração em que tiver terminado a execução das obras ou dos melhoramentos ( Decreto-Lei nº 1.598, de 1977, art. 28, § 3º ).
```
`decreto_9580_20181122.anexo1#3926` (SEC, 5498 tokens, shortened):
```text
[ DECRETO Nº 9.580, DE 22 DE NOVEMBRO DE 2018 | Regulamenta a tributação, a fiscalização, a arrecadação e a administração do Imposto sobre a Renda e Proventos de Qualquer Natureza. | Anexo 1 – ANEXO ] Seção X Da compra e da venda, do loteamento, da incorporação, da construção e da reforma de imóveis Determinação do custo Art. 481. O contribuinte que comprar imóvel para venda ou promover empreendimento de desmembramento ou loteamento de terrenos, incorporação imobiliária ou construção de prédio d … [15,731 chars omitted] … mpresa construa unidades habitacionais para vendê-las prontas, o pagamento unificado dos tributos a que se refere o caput será equivalente a um por cento da receita mensal auferida pelo contrato de alienação ( Lei nº 12.024, de 2009, art. 2º, § 7º ).
```

#### A10. `lei_9504_19970930.anexo1.xml` — `ite6-1` (orphan dispositivo of a category-B annex (DSP))

- Document: `lei_9504_19970930` — LEI Nº 9.504, DE 30 DE SETEMBRO DE 1997; cited by 1 question(s); this article is not cited.
- Groupings (`agrupadores_rotulos`): —; source interval Num 121–122.

**LexML parse** (the orphan dispositivo, not inside an `Artigo`):

```text
ite6-1 [Item]: 6. DATA DA EMISSÃO - informar a data em que o cheque foi emitido pelo doador, no formato dia, mês e ano;
```

**Chunks and strategy membership** (✓ = indexed by the strategy):

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `lei_9504_19970930.anexo1#34` | DSP | base | `ite6-1` | 121–122 | 82 | ✓ | ✓ | ✓ | ✓ | ✓ |

**Chunk texts** (in `chunk_id` order; grouping chunks shortened):

`lei_9504_19970930.anexo1#34` (DSP, base):
```text
[ LEI Nº 9.504, DE 30 DE SETEMBRO DE 1997 | Estabelece normas para as eleições. | Anexo 1 – ANEXO ] 6. DATA DA EMISSÃO - informar a data em que o cheque foi emitido pelo doador, no formato dia, mês e ano;
```

### B. Non-statutory samples

#### B1. `sc_cosit_140_20150605` — unit `pp1_tab1` (ministerio.fazenda_secretaria.receita.federal_solucao.consulta)

- File: `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2015-06-05_140.xml`; cited by 1 question(s); the document has 16 chunks; unit heading path: —.

**LexML parse of the unit:**

```text
pp1_tab1 [table ]:
  | natalista, a qual | afirma que o nascituro possui mera expectativa de direito, só fazendo jus à |  |
  | personalidade após o nascimento com vida, conforme se depreende da leitura d |  | o art. 2º da Lei |
```

**Chunks and strategy membership:**

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2015-06-05_140#13` | TAB | base | `pp1_tab1` | 27–28 | 215 | ✓ | ✓ | ✓ | ✓ | ✓ |

**Chunk texts:**

`urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2015-06-05_140#13` (TAB):
```text
[ Solução de Consulta Cosit nº 140, de 5 de junho de 2015 | IMPOSTO SOBRE A RENDA DE PESSOA FÍSICA – IRPF EMENTA: DESPESAS MÉDICAS. FERTILIZAÇÃO IN VITRO. DEDUTIBILIDADE. DECLARAÇÃO DE QUALQUER DOS CÔNJUGES. Os pagamentos efetuados a médicos e a hospitais, assim como as despesas com exames laboratoriais, realizados no âmbito de procedimento de reprodução assistida por fertilização in vitro, devidamente comprovados, são dedutíveis … ] Tabela: natalista, a qual | afirma que o nascituro possui mera expectativa de direito, só fazendo jus à | ; personalidade após o nascimento com vida, conforme se depreende da leitura d | | o art. 2º da Lei
```

#### B2. `sc_cosit_194_20150805` — unit `pp1_agr4` (ministerio.fazenda_secretaria.receita.federal_solucao.consulta)

- File: `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2015-08-05_194.xml`; cited by 3 question(s); the document has 3 chunks; unit heading path: —.

**LexML parse of the unit:**

```text
pp1_agr4 [Agrupamento texto]:
  <p> DISPOSITIVOS LEGAIS: Decreto nº 59.308, de 23 de setembrode 1966; Decreto nº 52.288, de 24 de junho de 1963; Decretonº 27.784, de 16 de fevereiro de 1950; Nota PGFN/CRJ nº 1.549, de3 de dezembro de 2012; REsp nº 1.306.393/DF; Solução de ConsultaCosit nº 64, de 7 de março de 2014.
```

**Chunks and strategy membership:**

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2015-08-05_194#2` | TXT | base | `pp1_agr4` | 3–4 | 305 | ✓ | ✓ | ✓ | ✓ | ✓ |

**Chunk texts:**

`urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2015-08-05_194#2` (TXT):
```text
[ SOLUÇÃO DE CONSULTA Nº 194,DE 5 DE AGOSTO DE 2015 | EMENTA: PERITOS DE ASSISTÊNCIA TÉCNICA.AGÊNCIA ESPECIALIZADA DA ONU. A Receita Federal do Brasil está impedida de constituir ouexigir créditos tributários relativos à incidência do IRPF sobre osrendimentos do trabalho recebidos por peritos de assistência técnicacontratados no Brasil para atuarem como consultores da ONU ou desuas Agências Especializadas, nem inscrevê-los em Dívida Ativa daUnião, devendo, ainda, rever de … ] DISPOSITIVOS LEGAIS: Decreto nº 59.308, de 23 de setembrode 1966; Decreto nº 52.288, de 24 de junho de 1963; Decretonº 27.784, de 16 de fevereiro de 1950; Nota PGFN/CRJ nº 1.549, de3 de dezembro de 2012; REsp nº 1.306.393/DF; Solução de ConsultaCosit nº 64, de 7 de março de 2014.
```

#### B3. `pn_cst_1_19850204` — unit `pp1_agh2_agh2_txt1` (ministerio.fazenda_secretaria.receita.federal_parecer)

- File: `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_parecer_1985-02-04_1.xml`; cited by 1 question(s); the document has 9 chunks; unit heading path: 3. ; 3.2..

**LexML parse of the unit:**

```text
pp1_agh2_agh2_txt1 [Agrupamento texto]:
  <p> Diversamente, porém, ocorre com a "Nota Promissória Rural", disciplinada nos artigos 42 e 43 do Decreto-lei nº 167. de 14.02.67. Eis que, tratando-se de promessa de pagamento, está vinculada à operação de venda que lhe deu origem, tanto que os produtos objeto da venda são nela indicados (art. 43, VI DL 167/67). Assim, quando estiver corretamente preenchida e não apresentar contradição com a correspondente "nota fiscal de produtor rural", a "Nota Promissória Rural" comprova o caráter creditício da operação e, por aplicação de regime financeiro, a receita será apropriada ao resultado do período-base em que efetivamente o vendedor vier a receber o pagamento prometido, o qual poderá ocorrer no desconto antecipado, no vencimento ou posteriormente como nas hipóteses de atraso de pagamento ou até de cobrança judicial.
  <p> À consideração superior.
```

**Chunks and strategy membership:**

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_parecer_1985-02-04_1#7` | TXT | base | `pp1_agh2_agh2_txt1` | 13–14 | 318 | ✓ | ✓ | ✓ | ✓ | ✓ |

**Chunk texts:**

`urn_lex_br_ministerio.fazenda_secretaria.receita.federal_parecer_1985-02-04_1#7` (TXT):
```text
[ Parecer Normativo CST nº 1, de 4 de fevereiro de 1985 | A receita correspondente à "Nota Promissória Rural" será apropriada ao resultado do ano-base em que efetivamente o vendedor vier a receber o pagamento garantido pelo título. ] 3. > 3.2. Diversamente, porém, ocorre com a "Nota Promissória Rural", disciplinada nos artigos 42 e 43 do Decreto-lei nº 167. de 14.02.67. Eis que, tratando-se de promessa de pagamento, está vinculada à operação de venda que lhe deu origem, tanto que os produtos objeto da venda são nela indicados (art. 43, VI DL 167/67). Assim, quando estiver corretamente preenchida e não apresentar contradição com a correspondente "nota fiscal de produtor rural", a "Nota Promissória Rural" comprova o caráter creditício da operação e, por aplicação de regime financeiro, a receita será apropriada ao resultado do período-base em que efetivamente o vendedor vier a receber o pagamento prometido, o qual poderá ocorrer no desconto antecipado, no vencimento ou posteriormente como nas hipóteses de atraso de pagamento ou até de cobrança judicial. À consideração superior.
```

#### B4. `adn_cosit_9_19990401` — unit `pp1_agh3_txt1` (ministerio.fazenda_secretaria.receita.federal_ato.declaratorio)

- File: `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_ato.declaratorio_1999-04-01_9.xml`; cited by 3 question(s); the document has 4 chunks; unit heading path: III -.

**LexML parse of the unit:**

```text
pp1_agh3_txt1 [Agrupamento texto]:
  <p> fica revogado o Ato Declaratório Normativo Cosit nº 06, de 12 de março de 1999, publicado no Diário Oficial da União de 15 de março de 1999.
```

**Chunks and strategy membership:**

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_ato.declaratorio_1999-04-01_9#4` | TXT | base | `pp1_agh3_txt1` | 7–8 | 107 | ✓ | ✓ | ✓ | ✓ | ✓ |

**Chunk texts:**

`urn_lex_br_ministerio.fazenda_secretaria.receita.federal_ato.declaratorio_1999-04-01_9#4` (TXT):
```text
[ Ato Declaratório Normativo Cosit nº 9, de 1º de abril de 1999 | Dispõe sobre a dedutibilidade das contribuições às entidades de previdência privada. ] III - fica revogado o Ato Declaratório Normativo Cosit nº 06, de 12 de março de 1999, publicado no Diário Oficial da União de 15 de março de 1999.
```

#### B5. `sci_cosit_5_20130215` — unit `pp1_tab1` (ministerio.fazenda_secretaria.receita.federal_solucao.consulta.interna)

- File: `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta.interna_2013-02-15_5.xml`; cited by 4 question(s); the document has 21 chunks; unit heading path: Fundamentos ; b) ; c).

**LexML parse of the unit:**

```text
pp1_tab1 [table ]:
  | DATA | COTAÇÃO DE COMPRA | COTAÇÃO DE VENDA |
  | 02/06/20XX | 2,42 | 2,50 |
  | 29/06/20XX | 2,80 | 2,88 |
  | 13/10/20XX | 2,00 | 2,03 |
  | 20/12/20XX | 2,10 | 2,18 |
  | 28/12/20XX | 2,30 | 2,38 |
```

**Chunks and strategy membership:**

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta.interna_2013-02-15_5#7` | TAB | base | `pp1_tab1` | 15–16 | 296 | ✓ | ✓ | ✓ | ✓ | ✓ |

**Chunk texts:**

`urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta.interna_2013-02-15_5#7` (TAB):
```text
[ Solução de Consulta Interna Cosit nº 5, de 15 de fevereiro de 2013 | Ementa: Aplicação em moeda estrangeira no exterior. Rendimentos auferidos originariamente em Reais. Tributação do Ganho de Capital. Liquidação. Resgate. Crédito de rendimentos. A tributação da variação cambial só ocorre no momento da liquidação ou resgate (parcial ou total) da aplicação financeira, ou seja, no momento em que qualquer montante do capital investido tenha sido movimentado pelo beneficiário. ] Fundamentos > b) > c) Cotações do dólar dos Estados Unidos da América (EUA): Tabela: DATA | COTAÇÃO DE COMPRA | COTAÇÃO DE VENDA ; 02/06/20XX | 2,42 | 2,50 ; 29/06/20XX | 2,80 | 2,88 ; 13/10/20XX | 2,00 | 2,03 ; 20/12/20XX | 2,10 | 2,18 ; 28/12/20XX | 2,30 | 2,38
```

#### B6. `parecer_pgfncat_1503_2010` — unit `pp1_agrf4` (procuradoria.geral.fazenda.nacional_parecer)

- File: `urn_lex_br_procuradoria.geral.fazenda.nacional_parecer_2010_1503.xml`; cited by 2 question(s); the document has 24 chunks; unit heading path: —.

**LexML parse of the unit:**

```text
pp1_agrf4 [Agrupamento nota]:
  <p> POR MORTE. RECONHECIMENTO DE UNIÃO ESTÁVEL. RELACIONAMENTO HOMOAFETIVO. POSSIBILIDADE.
  <p> PROVA TESTEMUNHAL ROBUSTA. DEPENDÊNCIA ECONÔMICA PRESUMIDA. CONCESSÃO DO BENEFÍCIO.
  <p> JUROS DE MORA. CORREÇÃO MONETÁRIA. HONORÁRIOS ADVOCATÍCIOS. 1. Remessa oficial, tida por
  <p> interposta, de sentença proferida na vigência da Lei nº 9.469, de 10 de julho de
  <p> 1997. Não incide, na hipótese, os artigos 475, § 2º, do Código de Processo Civil ou
  <p> 13 da Lei nº 10.259/01, em virtude de não ter sido demonstrado que o conteúdo
  <p> econômico do pleito é de valor inferior a 60 salários mínimos. 2. "A lei, só por si,
  <p> não extingue comportamentos racistas, preconceituosos, discriminatórios ou
  <p> mesmo criminosos, necessitando, antes, de uma conscientização da coletividade
  <p> sobre serem odiosas as condutas assim tipificadas. Não é a falta de uma lei
  <p> específica sobre o reconhecimento das uniões homoafetivas que vai alijar o
  <p> requerente do seu direito de obter, comprovados os requisitos objetivos da união
  <p> (convivência, relação amorosa, dependência econômica e publicidade da condição),
  <p> o reconhecimento da existência de uma união estável propiciadora da pensão por
  <p> morte requestada" (AC 2002.38.00.043831-2/MG, Rel. Desembargadora Federal
  <p> Neuza Maria Alves da Silva, Segunda Turma, DJ p.25 de 19/01/2007) 3. A
  <p> declaração particular colacionada aos autos, equiparável à prova testemunhal,
  <p> bem como as testemunhas ouvidas em juízo, as fotos do casal, cartões,
  <p> correspondências e títulos bancários com endereço comum, são uníssonos em
  <p> confirmar a relação duradoura de companheirismo entre o autor e seu falecido
  <p> companheiro. 4. A Lei nº. 8.213/91 somente exige início de prova material para fins
  <p> de comprovação de tempo de serviço, não ocorrendo tal exigência para fins de
  <p> comprovação de união estável. No mais, a teor do art. 16, §4º, da Lei 8.213/91, a
  <p> dependência mútua entre companheiros é presumida. 5. Atendidos os requisitos
  <p> indispensáveis à concessão do benefício previdenciário (arts. 74, da Lei 8.213/91), é
  <p> devida a pensão por morte, desde a data do requerimento administrativo. Sentença
  <p> mantida. 6. Os juros de mora de 1% ao mês devem ser contados da citação, no
  <p> tocante às prestações a ela anteriores e, da data do vencimento, para as posteriores.
  <p> Orientação da Primeira Seção e do STJ. 7. A correção monetária incide sobre o
  <p> débito previdenciário, a partir do vencimento de cada prestação, nos termos da Lei
  <p> nº. 6.899, de 8 de abril de 1981, conforme Manual de Orientação de Procedimentos
  <p> para os Cálculos na Justiça Federal. 8. Os honorários de advogado devem ser
  <p> reduzidos para 10% sobre o valor da condenação, correspondente às parcelas
  <p> vencidas até o momento da prolação da sentença, de acordo com a Súmula nº. 111
  <p> do Superior Tribunal de Justiça e artigo 20, § 3º, do CPC. 9. Apelação e remessa
  <p> oficial, tida por interposta, parcialmente providas, na forma dos itens 6 a 8. AC -
  <p> APELAÇÃO CIVEL – 200535000067997 TRF1 e-DJF1 DATA:05/03/2009
  <p> PAGINA:174
  <p> ADMINISTRATIVO E PROCESSUAL CIVIL – MILITAR – PENSÃO POR
  <p> MORTE. COMPANHEIRO - UNIÃO ESTÁVEL HOMOAFETIVA - INTELIGÊNCIA DO ARTIGO 226, CF;
  <p> ART.1723, CC/02 – PRINCÍPIOS
  <p> FUNDAMENTAIS DA DIGNIDADE DA PESSOA HUMANA, DA LIBERDADE,
  <p> DA IGUALDADE, DA NÃO DISCRIMINAÇÃO - INSTRUÇÃO NORMATIVA
  <p> 25/00/INSS – APLICAÇÃO – ISONOMIA - COMPROVAÇÃO – PASEP –
  <p> LEVANTAMENTO DE VALORES – IMPOSSIBILIDADE – INCOMPETÊNCIA
  <p> ABSOLUTA DO JUÍZO - HONORÁRIOS ADVOCATÍCIOS - ART.20, §4º, CPC
  <p> - APRECIAÇÃO EQÜITATIVA DO JUIZ - PRECEDENTES. -Objetivando a
  <p> parte autora, o reconhecimento da união estável que manteve com militar falecido
  <p> -Sr.Luiz Carlos Pinto de Freitas-, e o levantamento dos valores existentes na conta
  <p> do PASEP, ajuizou o presente feito. -Restou o mesmo julgado parcialmente
  <p> procedente, "para RECONHECER, exclusivamente para fins previdenciários
  <p> junto à Marinha do Brasil, a existência de sociedade de fato entre o Autor e o
  <p> Sr.Luiz Carlos Pinto de Freitas, bem como para CONDENAR a UNIÃO
  <p> FEDERAL a conceder a pensão por morte pleiteada e pagar as parcelas devidas, a
  <p> contar da data do óbito, cujos valores deverão ser corrigidos monetariamente e
  <p> acrescidos de juros de mora no percentual de 0,5% (meio por cento) ao mês (STF,
  <p> Plenário, RE453740/RJ, Rel.Min.Gilmar Mendes, DJ de 24.08.07), estes a partir da
  <p> data da citação, e, em conseqüência, DELARO a nulidade do ato administrativo
  <p> que reconheceu direito à mesma pensão ao segundo réu, Sr.ALARCON
  <p> BARBOSA DE FREITAS, isentando-o de devolução das quantias recebidas até a
  <p> definitiva suspensão dos pagamentos mensais. Faculto à União Federal promover a
  <p> imediata suspensão dos pagamentos mensais referentes à pensão que vem sendo
  <p> paga ao segundo Réu, independentemente do trânsito em julgado da
  <p> sentença.".Condenada a União Federal na verba honorária de 5% sobre o
  <p> montante devido, e o Alarcon Barbosa de Freitas, em 5% do valor da causa,
  <p> monetariamente atualizado, com custas ex lege. -No que concerne à liberação dos
  <p> valores creditados, em nome do de cujus, na conta do PASEP, nos termos do
  <p> verbete nº 161, da Súmula da jurisprudência do STJ, a competência para autorizar
  <p> levantamento dos valores relativos ao PIS/PASEP e FGTS, em decorrência do
  <p> falecimento do titular da conta, é da Justiça Estadual, pelo que, absoluta
  <p> incompetência do Juízo, como decidido. -"Há que se aplicar o direito à luz de
  <p> diversos preceitos constitucionais e não apenas atendo-se à interpretação literal do
  <p> art. 226, §3º da Constituição Federal, que não diz respeito ao âmbito
  <p> previdenciário, inserindo-se no capítulo 'Da Família', sendo certo que não houve
  <p> de parte do constituinte, exclusão dos relacionamentos homoafetivos, com vista à
  <p> produção de efeitos no campo do direito previdenciário, configurando-se mera
  <p> lacuna, que deverá ser preenchida a partir de outras fontes do direito" (STJ, RESP
  <p> 395904, Rel. Min. Hélio Quaglia Barbosa, DJ de 06/02/2006). -Conforme registrado
  <p> pelo STF no julgamento da ADI 3300 MC/DF, o magistério da doutrina, apoiando-
  <p> se em valiosa hermenêutica construtiva, utilizando-se da analogia e invocando
  <p> princípios fundamentais (como os da dignidade da pessoa humana, da liberdade,
  <p> da autodeterminação, da igualdade, do pluralismo, da intimidade, da não-
  <p> discriminação e da busca da felicidade), tem revelado admirável percepção do alto
  <p> significado de que se revestem tanto o reconhecimento do direito personalíssimo à
  <p> orientação sexual, de um lado, quanto a proclamação da legitimidade ético-jurídica
  <p> da união homoafetiva como entidade familiar, de outro, em ordem a permitir que
  <p> se extraiam, em favor de parceiros homossexuais, relevantes conseqüências no
  <p> plano do Direito e na esfera das relações sociais. -"Uma vez reconhecida, numa
  <p> interpretação dos princípios norteadores da Constituição pátria, a união entre
  <p> homossexuais como possível de ser abarcada dentro do conceito de entidade
  <p> familiar e afastados quaisquer impedimentos de natureza atuarial, deve a relação
  <p> da Previdência para com os casais de mesmo sexo dar-se nos mesmos moldes das
  <p> uniões estáveis entre heterossexuais, devendo ser exigido dos primeiros o mesmo
  <p> que se exige dos segundos para fins de comprovação do vínculo afetivo e
  <p> dependência econômica presumida entre os casais (...), quando do processamento
  <p> dos pedidos de pensão por morte e auxílio-reclusão." (Revista do TRF/4ª Região,
  <p> vol. 57/309-348, 310, Rel. Des. Federal João Batista Pinto Silveira - grifei) in STF,
  <p> ADI 3300 MC/DF. -"(...) O reconhecimento do direito à pensão previdenciária
  <p> para companheiro(a) de homossexual, no RGPS, consubstanciado na Instrução
  <p> Normativa nº 25, de 7 de junho de 2000, editada pelo INSS, pode ser utilizada, por
  <p> analogia, para a concessão de tal benefício aos servidores públicos federais, em
  <p> homenagem ao princípio da isonomia (...)"(TRF 5ª R. - AC 238.842 - RN - 1ª T. -
  <p> Relª Desª Fed. Margarida Cantarelli - DJU 13.03.2002). -Inexistindo situação
  <p> destoante, in casu, do apreciado, em epígrafe por este Colegiado, o inconformismo
  <p> não tem como prosperar. -Destarte, comungo do mesmo sentir da decisão de piso,
  <p> na medida em que, a meu juízo, o acervo probatório, conforme ali declinado, cuja
  <p> fundamentação, ora se incorpora, bem delineou a sociedade de fato constituída, em
  <p> especial o seguro de vida instituído pelo de cujus em favor do companheiro, ora
  <p> apelado, o que conduz à manutenção do decisum, sob esta vertente. -Quanto ao
  <p> termo inicial para o pagamento da pensão em comento, não há que se falar em
  <p> habilitação tardia, face ao que se extrai dos documentos acostados aos autos
  <p> (fls.59; 72), e como bem explicitado na sentença objurgada, no sentido de que, "O
  <p> direito do autor retroage à data do óbito, pois requereu administrativamente a
  <p> pensão apenas doze dias após (fl.59), e muito antes do deferimento da pensão em
  <p> favor do segundo Réu, em 02.05.2001 (fl.72). (...).", pelo que, de rigor a sua
  <p> manutenção, também sob este flanco. -Por derradeiro, por força da remessa
  <p> necessária, no que pertine à verba honorária fixada em desfavor do ente
  <p> federativo, a teor do §4º, do artigo 20, do CPC, sopesados os critérios estabelecidos
  <p> nas alíneas "a", "b" e "c" do parágrafo 3º do citado artigo, e ante a ausência de
  <p> complexidade da vexata quaestio, a reforma, neste aspecto deve ser efetivada, de
  <p> molde a se preservar a regra, arbitrando-se em R$ 1.500,00 (um mil e quinhentos
  <p> reais). -Recurso desprovido, remessa necessária, parcialmente provida. APELRE -
  <p> APELAÇÃO/REEXAME NECESSÁRIO – 464994 TRF2 E-DJF2R -
  <p> Data::05/05/2010 - Página::187/188"
  <p> 74.
  <p> Fácil antever o resultado provável de eventual judicialização do assunto mercê de
  <p> deferimento administrativo, mormente quando a própria AGU, na condição de representante judicial da
  <p> União e em sede de controle abstrato de constitucionalidade, reconhece direito análogo ao ora
  <p> vindicado. A previsibilidade do desfecho de potencial contencioso jurisdicional permite prevenir os
  <p> ônus que a sucumbência acarretaria em detrimento do princípio da economicidade administrativa.
  <p> V
  <p> 75.
  <p> Sem embargo do acima, mister salientar, por derradeiro, que o art. 226, §3º, da CF/88
  <p> não proíbe o reconhecimento de direitos civis à união de pessoas do mesmo sexo. Limita-se a conferir
  <p> proteção à união estável entre o homem e a mulher como entidade familiar, para efeito de a lei facilitar
  <p> sua conversão em casamento, no que foi seguida pela legislação ordinária.
  <p> 76.
  <p> A tutela do modelo tradicional de família prevista na Lei Maior longe está de constituir
  <p> a chamada "norma de clausura", segundo a qual tudo o que não for juridicamente permitido encontra-
  <p> se automaticamente proibido. Isso levaria a compreender que o silêncio equivale a proibição, com
  <p> negação de outras formas de organização familiar, sem atentar para preceptivos de igual ou superior
  <p> valor principiológico espraiados no texto constitucional.
  <p> 77.
  <p> A interpretação isolada do artigo 226, §3º da CF/88 deve ser substituída por uma
  <p> interpretação sistemática, que não pressupõe incompatibilidade entre a união estável entre pessoas do
  <p> mesmo sexo e a união estável entre pessoas de sexos diferentes. Sustenta Luís Roberto Barroso em
  <p> Parecer sobre o tema:
  <p> "O não reconhecimento jurídico das uniões homoafetivas não beneficia, em
  <p> nenhuma medida, as uniões convencionais e tampouco promove qualquer valor
  <p> constitucionalmente protegido. (...) a referência a homem e mulher não traduz uma
  <p> vedação da extensão do mesmo regime às relações homoafetivas. Extrair desse
  <p> preceito tal conseqüência seria desvirtuar a sua natureza: a de uma norma de
  <p> inclusão. (...) Não se deve interpretar uma regra constitucional contrariando os
  <p> princípios constitucionais e os fins que a justificaram." (5 in DIFERENTES, MAS IGUAIS:
  <p> O RECONHECIMENTO JURÍDICO DAS RELAÇÕES HOMOAFETIVAS NO BRASIL, Trabalho desenvolvido com a colaboração de Cláudio Pereira de Souza
  <p> Neto, Eduardo Mendonça e Nelson Nascimento Diz, que participaram da pesquisa e da discussão de idéias e
  <p> de teses.)
  <p> 78.
  <p> A par do art. 226, §3º, "a Constituição Federal proclama o direito à vida, à
  <p> liberdade, à igualdade e à intimidade (art. 5º, caput) e prevê como objetivo fundamental, a
  <p> promoção do bem de todos, 'sem preconceitos de origem, raça, sexo, cor, idade e quaisquer
  <p> outras formas de discriminação' (art. 3º, IV). Dispõe, ainda, que 'a lei punirá qualquer
  <p> discriminação atentatória dos direitos e liberdades fundamentais' (art. 5º, XLI). Portanto, sua
  <p> intenção é a promoção do bem dos cidadãos, que são livres para ser, rechaçando qualquer forma
  <p> de exclusão social ou tratamento desigual" (6 TJ/RS, j. 17 nov. 2004, AC 70009550070, Rel. Des. Maria Berenice Dias, apud Luís Roberto Barroso).
  <p> 79.
  <p> O princípio constitucional da dignidade da pessoa humana e da expressa vedação de
  <p> qualquer forma de discriminação sexual constitui impediente jurídico à proscrição do reconhecimento
  <p> de união estável entre pessoas do mesmo sexo, com os efeitos fiscais que lhe são imanentes. As uniões
  <p> homoafetivas são fatos lícitos e relativos à vida privada de cada indivíduo, fugindo à atuação estatal
  <p> intervir na orientação sexual para marginalizar ou excluir do seu manto as relações homoafetivas.
  <p> 80.
  <p> O centro da tutela constitucional não se põe na exclusividade do casamento. Antes
  <p> abarca a pluralidade dos modelos familiares que, fundados ou não no vínculo conjugal, contenham os
  <p> pressupostos para a tutela da dignidade da pessoa humana. Far-se-á ilegítima qualquer interpretação
  <p> restritiva dos núcleos familiares calcada na orientação sexual dos conviventes em desapreço aos
  <p> princípios constitucionais acima aludidos.
  <p> 81.
  <p> Não se entenda, com isso, que ao intérprete se outorga qualquer liberdade nesse mister.
  <p> A revés, encontra-se ele condicionado por todo o contexto constitucional, pelas exigências dos
  <p> princípios fundamentais e pela exegese sistemática e axiológica, suficientemente vigorosas a orientá-lo
  <p> com segurança.
  <p> 82.
  <p> Malgrado se reconheça que determinadas situações estão fora da zona de certeza de um
  <p> termo preciso, o art. 246 da CF há de ser interpretado em consonância com princípios constitucionais
  <p> outros, como o da dignidade da pessoa humana, posto inviável segregar-lhe o núcleo conceitual.
  <p> 84.
  <p> E a Administração tributária, por óbvio, também se subordina aos direitos fundamentais.
  <p> A vinculação da administração fazendária às normas de direitos fundamentais torna nulos os atos
  <p> praticados com ofensa ao sistema desses direitos.
  <p> 85.
  <p> Não se trata, in specie, de exercer juízo de inconstitucionalidade de uma lei e recusar-lhe
  <p> aplicação por entendê-la discordante de um direito fundamental. Mas compreender a lei conforme a
  <p> Constituição, dando-lhe sentido compatível com a norma fundamental.
  <p> VI
  <p> 86.
  <p> Por todo o exposto, conclui-se:
  <p> (i) a expressão companheiro ou companheira não encontra definição na legislação tributária, sendo
  <p> desimportante a sexualidade dos companheiros para aplicação dos arts. 4º, III e 8º, II, "b" e "c"
  <p> da Lei nº 9.250/95, e 77 do Decreto nº 3.000/99 (RIR/99);
  <p> (ii) as uniões homoafetivas estão compreendidas na polissemia dos arts. 35, II da Lei nº 9.250/95 e
  <p> 77, § 1º, inciso II do Decreto nº 3.000/99, razão pela qual vedado ao intérprete limitar o que a
  <p> lei expressamente não limita;
  <p> (iii) a paridade de tratamento tributário é direito constitucional que interdita qualquer
  <p> exegese fundada na discriminação de gênero. Embora certo que na perspectiva biológica,
  <p> sociológica ou antropológica constituam realidades distintas a união duradoura entre pessoas do
  <p> mesmo sexo e a de duas pessoas de sexo diverso, no domínio tributário a equiparação de
  <p> tratamento é fundamento material de incidência;
  <p> (iv) não se colhe do art. 226, §3º, da CF/88 "norma de clausura", a tornar proibido tudo o
  <p> que não estiver literalmente previsto. Além da sua interpretação sistemática com outros
  <p> preceptivos de igual ou superior hierarquia axiológica, o elemento fundamental do art. 246 da
  <p> CF é a família, não o sexo dos parceiros, cujo objetivo foi alargar a cobertura constitucional dos
  <p> direitos fundamentais, não o de restringir ou limitar, implícita ou explicitamente, à união
  <p> heterossexual;
  <p> (v) as relações homoafetivas, à míngua de previsão explícita na legislação tributária, não podem ser
  <p> tratadas como união de vida de 2ª categoria para efeitos fiscais. Não implica isso extravagância
  <p> ou juízo de inconstitucionalidade, mas compreensão da lei tributária conforme a Constituição,
  <p> dando-lhe sentido compatível com a norma fundamental;
  <p> VII
  <p> 87.
  <p> Posto isto, uma vez demonstrado, quantum satis, a viabilidade e procedência do
  <p> requerimento administrativo objeto da Nota Técnica nº 47/2010/COGES/DENOP/SRH/MP, opina-
  <p> se pela juridicidade da inclusão cadastral de companheira homoafetiva como dependente de
  <p> servidora pública federal para efeito de dedução do Imposto de Renda, desde que preenchidos os
  <p> demais requisitos exigíveis à comprovação da união estável disciplinada nos arts. 4º, III e 8º, II, "b"
  <p> e "c" da Lei nº 9.250/95, e no art. 77 do Decreto nº 3.000/99 (RIR/99).
  <p> É o Parecer jurídico. À consideração superior.
```

**Chunks and strategy membership:**

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `urn_lex_br_procuradoria.geral.fazenda.nacional_parecer_2010_1503#14` | TXT | base | `` | 32–33 | 780 | ✓ | ✓ | ✓ | ✓ | ✓ |
| `urn_lex_br_procuradoria.geral.fazenda.nacional_parecer_2010_1503#15` | TXT | base | `` | 34–35 | 344 | ✓ | ✓ | ✓ | ✓ | ✓ |
| `urn_lex_br_procuradoria.geral.fazenda.nacional_parecer_2010_1503#16` | TXT | base | `` | 36–37 | 1010 | ✓ | ✓ | ✓ | ✓ | ✓ |
| `urn_lex_br_procuradoria.geral.fazenda.nacional_parecer_2010_1503#17` | TXT | base | `` | 38–39 | 1022 | ✓ | ✓ | ✓ | ✓ | ✓ |
| `urn_lex_br_procuradoria.geral.fazenda.nacional_parecer_2010_1503#18` | TXT | base | `` | 40–41 | 785 | ✓ | ✓ | ✓ | ✓ | ✓ |
| `urn_lex_br_procuradoria.geral.fazenda.nacional_parecer_2010_1503#19` | TXT | base | `` | 42–43 | 943 | ✓ | ✓ | ✓ | ✓ | ✓ |
| `urn_lex_br_procuradoria.geral.fazenda.nacional_parecer_2010_1503#20` | TXT | base | `` | 44–45 | 666 | ✓ | ✓ | ✓ | ✓ | ✓ |

**Chunk texts:**

`urn_lex_br_procuradoria.geral.fazenda.nacional_parecer_2010_1503#14` (TXT, part 1/7):
```text
[ PARECER PGFN/CAT/Nº 1503//2010 | Requerimento administrativo de servidora federal ] POR MORTE. RECONHECIMENTO DE UNIÃO ESTÁVEL. RELACIONAMENTO HOMOAFETIVO. POSSIBILIDADE. PROVA TESTEMUNHAL ROBUSTA. DEPENDÊNCIA ECONÔMICA PRESUMIDA. CONCESSÃO DO BENEFÍCIO. JUROS DE MORA. CORREÇÃO MONETÁRIA. HONORÁRIOS ADVOCATÍCIOS. 1. Remessa oficial, tida por interposta, de sentença proferida na vigência da Lei nº 9.469, de 10 de julho de 1997. Não incide, na hipótese, os artigos 475, § 2º, do Código de Processo Civil ou 13 da Lei nº 10.259/01, em virtude de não ter sido demonstrado que o conteúdo econômico do pleito é de valor inferior a 60 salários mínimos. 2. "A lei, só por si, não extingue comportamentos racistas, preconceituosos, discriminatórios ou mesmo criminosos, necessitando, antes, de uma conscientização da coletividade sobre serem odiosas as condutas assim tipificadas. Não é a falta de uma lei específica sobre o reconhecimento das uniões homoafetivas que vai alijar o requerente do seu direito de obter, comprovados os requisitos objetivos da união (convivência, relação amorosa, dependência econômica e publicidade da condição), o reconhecimento da existência de uma união estável propiciadora da pensão por morte requestada" (AC 2002.38.00.043831-2/MG, Rel. Desembargadora Federal Neuza Maria Alves da Silva, Segunda Turma, DJ p.25 de 19/01/2007) 3. A declaração particular colacionada aos autos, equiparável à prova testemunhal, bem como as testemunhas ouvidas em juízo, as fotos do casal, cartões, correspondências e títulos bancários com endereço comum, são uníssonos em confirmar a relação duradoura de companheirismo entre o autor e seu falecido companheiro. 4. A Lei nº. 8.213/91 somente exige início de prova material para fins de comprovação de tempo de serviço, não ocorrendo tal exigência para fins de comprovação de união estável. No mais, a teor do art. 16, §4º, da Lei 8.213/91, a dependência mútua entre companheiros é presumida. 5. Atendidos os requisitos indispensáveis à concessão do benefício previdenciário (arts. 74, da Lei 8.213/91), é devida a pensão por morte, desde a data do requerimento administrativo. Sentença mantida. 6. Os juros de mora de 1% ao mês devem ser contados da citação, no tocante às prestações a ela anteriores e, da data do vencimento, para as posteriores.
```
`urn_lex_br_procuradoria.geral.fazenda.nacional_parecer_2010_1503#15` (TXT, part 2/7):
```text
[ PARECER PGFN/CAT/Nº 1503//2010 | Requerimento administrativo de servidora federal ] Orientação da Primeira Seção e do STJ. 7. A correção monetária incide sobre o débito previdenciário, a partir do vencimento de cada prestação, nos termos da Lei nº. 6.899, de 8 de abril de 1981, conforme Manual de Orientação de Procedimentos para os Cálculos na Justiça Federal. 8. Os honorários de advogado devem ser reduzidos para 10% sobre o valor da condenação, correspondente às parcelas vencidas até o momento da prolação da sentença, de acordo com a Súmula nº. 111 do Superior Tribunal de Justiça e artigo 20, § 3º, do CPC. 9. Apelação e remessa oficial, tida por interposta, parcialmente providas, na forma dos itens 6 a 8. AC - APELAÇÃO CIVEL – 200535000067997 TRF1 e-DJF1 DATA:05/03/2009 PAGINA:174 ADMINISTRATIVO E PROCESSUAL CIVIL – MILITAR – PENSÃO POR MORTE. COMPANHEIRO - UNIÃO ESTÁVEL HOMOAFETIVA - INTELIGÊNCIA DO ARTIGO 226, CF;
```
`urn_lex_br_procuradoria.geral.fazenda.nacional_parecer_2010_1503#16` (TXT, part 3/7):
```text
[ PARECER PGFN/CAT/Nº 1503//2010 | Requerimento administrativo de servidora federal ] ART.1723, CC/02 – PRINCÍPIOS FUNDAMENTAIS DA DIGNIDADE DA PESSOA HUMANA, DA LIBERDADE, DA IGUALDADE, DA NÃO DISCRIMINAÇÃO - INSTRUÇÃO NORMATIVA 25/00/INSS – APLICAÇÃO – ISONOMIA - COMPROVAÇÃO – PASEP – LEVANTAMENTO DE VALORES – IMPOSSIBILIDADE – INCOMPETÊNCIA ABSOLUTA DO JUÍZO - HONORÁRIOS ADVOCATÍCIOS - ART.20, §4º, CPC - APRECIAÇÃO EQÜITATIVA DO JUIZ - PRECEDENTES. -Objetivando a parte autora, o reconhecimento da união estável que manteve com militar falecido -Sr.Luiz Carlos Pinto de Freitas-, e o levantamento dos valores existentes na conta do PASEP, ajuizou o presente feito. -Restou o mesmo julgado parcialmente procedente, "para RECONHECER, exclusivamente para fins previdenciários junto à Marinha do Brasil, a existência de sociedade de fato entre o Autor e o Sr.Luiz Carlos Pinto de Freitas, bem como para CONDENAR a UNIÃO FEDERAL a conceder a pensão por morte pleiteada e pagar as parcelas devidas, a contar da data do óbito, cujos valores deverão ser corrigidos monetariamente e acrescidos de juros de mora no percentual de 0,5% (meio por cento) ao mês (STF, Plenário, RE453740/RJ, Rel.Min.Gilmar Mendes, DJ de 24.08.07), estes a partir da data da citação, e, em conseqüência, DELARO a nulidade do ato administrativo que reconheceu direito à mesma pensão ao segundo réu, Sr.ALARCON BARBOSA DE FREITAS, isentando-o de devolução das quantias recebidas até a definitiva suspensão dos pagamentos mensais. Faculto à União Federal promover a imediata suspensão dos pagamentos mensais referentes à pensão que vem sendo paga ao segundo Réu, independentemente do trânsito em julgado da sentença.".Condenada a União Federal na verba honorária de 5% sobre o montante devido, e o Alarcon Barbosa de Freitas, em 5% do valor da causa, monetariamente atualizado, com custas ex lege. -No que concerne à liberação dos valores creditados, em nome do de cujus, na conta do PASEP, nos termos do verbete nº 161, da Súmula da jurisprudência do STJ, a competência para autorizar levantamento dos valores relativos ao PIS/PASEP e FGTS, em decorrência do falecimento do titular da conta, é da Justiça Estadual, pelo que, absoluta incompetência do Juízo, como decidido. -"Há que se aplicar o direito à luz de diversos preceitos constitucionais e não apenas atendo-se à interpretação literal do art. 226, §3º da Constituição Federal, que não diz respeito ao âmbito previdenciário, inserindo-se no capítulo 'Da Família', sendo certo que não houve de parte do constituinte, exclusão dos relacionamentos homoafetivos, com vista à produção de efeitos no campo do direito previdenciário, configurando-se mera lacuna, que deverá ser preenchida a partir de outras fontes do direito" (STJ, RESP 395904, Rel. Min. Hélio Quaglia Barbosa, DJ de 06/02/2006). -Conforme registrado pelo STF no julgamento da ADI 3300 MC/DF, o magistério da doutrina, apoiando- se em valiosa hermenêutica construtiva, utilizando-se da analogia e invocando princípios fundamentais (como os da dignidade da pessoa humana, da liberdade,
```
`urn_lex_br_procuradoria.geral.fazenda.nacional_parecer_2010_1503#17` (TXT, part 4/7):
```text
[ PARECER PGFN/CAT/Nº 1503//2010 | Requerimento administrativo de servidora federal ] da autodeterminação, da igualdade, do pluralismo, da intimidade, da não- discriminação e da busca da felicidade), tem revelado admirável percepção do alto significado de que se revestem tanto o reconhecimento do direito personalíssimo à orientação sexual, de um lado, quanto a proclamação da legitimidade ético-jurídica da união homoafetiva como entidade familiar, de outro, em ordem a permitir que se extraiam, em favor de parceiros homossexuais, relevantes conseqüências no plano do Direito e na esfera das relações sociais. -"Uma vez reconhecida, numa interpretação dos princípios norteadores da Constituição pátria, a união entre homossexuais como possível de ser abarcada dentro do conceito de entidade familiar e afastados quaisquer impedimentos de natureza atuarial, deve a relação da Previdência para com os casais de mesmo sexo dar-se nos mesmos moldes das uniões estáveis entre heterossexuais, devendo ser exigido dos primeiros o mesmo que se exige dos segundos para fins de comprovação do vínculo afetivo e dependência econômica presumida entre os casais (...), quando do processamento dos pedidos de pensão por morte e auxílio-reclusão." (Revista do TRF/4ª Região, vol. 57/309-348, 310, Rel. Des. Federal João Batista Pinto Silveira - grifei) in STF, ADI 3300 MC/DF. -"(...) O reconhecimento do direito à pensão previdenciária para companheiro(a) de homossexual, no RGPS, consubstanciado na Instrução Normativa nº 25, de 7 de junho de 2000, editada pelo INSS, pode ser utilizada, por analogia, para a concessão de tal benefício aos servidores públicos federais, em homenagem ao princípio da isonomia (...)"(TRF 5ª R. - AC 238.842 - RN - 1ª T. - Relª Desª Fed. Margarida Cantarelli - DJU 13.03.2002). -Inexistindo situação destoante, in casu, do apreciado, em epígrafe por este Colegiado, o inconformismo não tem como prosperar. -Destarte, comungo do mesmo sentir da decisão de piso, na medida em que, a meu juízo, o acervo probatório, conforme ali declinado, cuja fundamentação, ora se incorpora, bem delineou a sociedade de fato constituída, em especial o seguro de vida instituído pelo de cujus em favor do companheiro, ora apelado, o que conduz à manutenção do decisum, sob esta vertente. -Quanto ao termo inicial para o pagamento da pensão em comento, não há que se falar em habilitação tardia, face ao que se extrai dos documentos acostados aos autos (fls.59; 72), e como bem explicitado na sentença objurgada, no sentido de que, "O direito do autor retroage à data do óbito, pois requereu administrativamente a pensão apenas doze dias após (fl.59), e muito antes do deferimento da pensão em favor do segundo Réu, em 02.05.2001 (fl.72). (...).", pelo que, de rigor a sua manutenção, também sob este flanco. -Por derradeiro, por força da remessa necessária, no que pertine à verba honorária fixada em desfavor do ente federativo, a teor do §4º, do artigo 20, do CPC, sopesados os critérios estabelecidos nas alíneas "a", "b" e "c" do parágrafo 3º do citado artigo, e ante a ausência de complexidade da vexata quaestio, a reforma, neste aspecto deve ser efetivada, de molde a se preservar a regra, arbitrando-se em R$ 1.500,00 (um mil e quinhentos
```
`urn_lex_br_procuradoria.geral.fazenda.nacional_parecer_2010_1503#18` (TXT, part 5/7):
```text
[ PARECER PGFN/CAT/Nº 1503//2010 | Requerimento administrativo de servidora federal ] reais). -Recurso desprovido, remessa necessária, parcialmente provida. APELRE - APELAÇÃO/REEXAME NECESSÁRIO – 464994 TRF2 E-DJF2R - Data::05/05/2010 - Página::187/188" 74. Fácil antever o resultado provável de eventual judicialização do assunto mercê de deferimento administrativo, mormente quando a própria AGU, na condição de representante judicial da União e em sede de controle abstrato de constitucionalidade, reconhece direito análogo ao ora vindicado. A previsibilidade do desfecho de potencial contencioso jurisdicional permite prevenir os ônus que a sucumbência acarretaria em detrimento do princípio da economicidade administrativa. V 75. Sem embargo do acima, mister salientar, por derradeiro, que o art. 226, §3º, da CF/88 não proíbe o reconhecimento de direitos civis à união de pessoas do mesmo sexo. Limita-se a conferir proteção à união estável entre o homem e a mulher como entidade familiar, para efeito de a lei facilitar sua conversão em casamento, no que foi seguida pela legislação ordinária. 76. A tutela do modelo tradicional de família prevista na Lei Maior longe está de constituir a chamada "norma de clausura", segundo a qual tudo o que não for juridicamente permitido encontra- se automaticamente proibido. Isso levaria a compreender que o silêncio equivale a proibição, com negação de outras formas de organização familiar, sem atentar para preceptivos de igual ou superior valor principiológico espraiados no texto constitucional. 77. A interpretação isolada do artigo 226, §3º da CF/88 deve ser substituída por uma interpretação sistemática, que não pressupõe incompatibilidade entre a união estável entre pessoas do mesmo sexo e a união estável entre pessoas de sexos diferentes. Sustenta Luís Roberto Barroso em Parecer sobre o tema: "O não reconhecimento jurídico das uniões homoafetivas não beneficia, em nenhuma medida, as uniões convencionais e tampouco promove qualquer valor constitucionalmente protegido. (...) a referência a homem e mulher não traduz uma vedação da extensão do mesmo regime às relações homoafetivas. Extrair desse preceito tal conseqüência seria desvirtuar a sua natureza: a de uma norma de inclusão. (...) Não se deve interpretar uma regra constitucional contrariando os princípios constitucionais e os fins que a justificaram." (5 in DIFERENTES, MAS IGUAIS: O RECONHECIMENTO JURÍDICO DAS RELAÇÕES HOMOAFETIVAS NO BRASIL, Trabalho desenvolvido com a colaboração de Cláudio Pereira de Souza Neto, Eduardo Mendonça e Nelson Nascimento Diz, que participaram da pesquisa e da discussão de idéias e de teses.)
```
`urn_lex_br_procuradoria.geral.fazenda.nacional_parecer_2010_1503#19` (TXT, part 6/7):
```text
[ PARECER PGFN/CAT/Nº 1503//2010 | Requerimento administrativo de servidora federal ] 78. A par do art. 226, §3º, "a Constituição Federal proclama o direito à vida, à liberdade, à igualdade e à intimidade (art. 5º, caput) e prevê como objetivo fundamental, a promoção do bem de todos, 'sem preconceitos de origem, raça, sexo, cor, idade e quaisquer outras formas de discriminação' (art. 3º, IV). Dispõe, ainda, que 'a lei punirá qualquer discriminação atentatória dos direitos e liberdades fundamentais' (art. 5º, XLI). Portanto, sua intenção é a promoção do bem dos cidadãos, que são livres para ser, rechaçando qualquer forma de exclusão social ou tratamento desigual" (6 TJ/RS, j. 17 nov. 2004, AC 70009550070, Rel. Des. Maria Berenice Dias, apud Luís Roberto Barroso). 79. O princípio constitucional da dignidade da pessoa humana e da expressa vedação de qualquer forma de discriminação sexual constitui impediente jurídico à proscrição do reconhecimento de união estável entre pessoas do mesmo sexo, com os efeitos fiscais que lhe são imanentes. As uniões homoafetivas são fatos lícitos e relativos à vida privada de cada indivíduo, fugindo à atuação estatal intervir na orientação sexual para marginalizar ou excluir do seu manto as relações homoafetivas. 80. O centro da tutela constitucional não se põe na exclusividade do casamento. Antes abarca a pluralidade dos modelos familiares que, fundados ou não no vínculo conjugal, contenham os pressupostos para a tutela da dignidade da pessoa humana. Far-se-á ilegítima qualquer interpretação restritiva dos núcleos familiares calcada na orientação sexual dos conviventes em desapreço aos princípios constitucionais acima aludidos. 81. Não se entenda, com isso, que ao intérprete se outorga qualquer liberdade nesse mister. A revés, encontra-se ele condicionado por todo o contexto constitucional, pelas exigências dos princípios fundamentais e pela exegese sistemática e axiológica, suficientemente vigorosas a orientá-lo com segurança. 82. Malgrado se reconheça que determinadas situações estão fora da zona de certeza de um termo preciso, o art. 246 da CF há de ser interpretado em consonância com princípios constitucionais outros, como o da dignidade da pessoa humana, posto inviável segregar-lhe o núcleo conceitual. 84. E a Administração tributária, por óbvio, também se subordina aos direitos fundamentais. A vinculação da administração fazendária às normas de direitos fundamentais torna nulos os atos praticados com ofensa ao sistema desses direitos. 85. Não se trata, in specie, de exercer juízo de inconstitucionalidade de uma lei e recusar-lhe aplicação por entendê-la discordante de um direito fundamental. Mas compreender a lei conforme a Constituição, dando-lhe sentido compatível com a norma fundamental. VI 86. Por todo o exposto, conclui-se: (i) a expressão companheiro ou companheira não encontra definição na legislação tributária, sendo desimportante a sexualidade dos companheiros para aplicação dos arts. 4º, III e 8º, II, "b" e "c" da Lei nº 9.250/95, e 77 do Decreto nº 3.000/99 (RIR/99);
```
`urn_lex_br_procuradoria.geral.fazenda.nacional_parecer_2010_1503#20` (TXT, part 7/7):
```text
[ PARECER PGFN/CAT/Nº 1503//2010 | Requerimento administrativo de servidora federal ] (ii) as uniões homoafetivas estão compreendidas na polissemia dos arts. 35, II da Lei nº 9.250/95 e 77, § 1º, inciso II do Decreto nº 3.000/99, razão pela qual vedado ao intérprete limitar o que a lei expressamente não limita; (iii) a paridade de tratamento tributário é direito constitucional que interdita qualquer exegese fundada na discriminação de gênero. Embora certo que na perspectiva biológica, sociológica ou antropológica constituam realidades distintas a união duradoura entre pessoas do mesmo sexo e a de duas pessoas de sexo diverso, no domínio tributário a equiparação de tratamento é fundamento material de incidência; (iv) não se colhe do art. 226, §3º, da CF/88 "norma de clausura", a tornar proibido tudo o que não estiver literalmente previsto. Além da sua interpretação sistemática com outros preceptivos de igual ou superior hierarquia axiológica, o elemento fundamental do art. 246 da CF é a família, não o sexo dos parceiros, cujo objetivo foi alargar a cobertura constitucional dos direitos fundamentais, não o de restringir ou limitar, implícita ou explicitamente, à união heterossexual; (v) as relações homoafetivas, à míngua de previsão explícita na legislação tributária, não podem ser tratadas como união de vida de 2ª categoria para efeitos fiscais. Não implica isso extravagância ou juízo de inconstitucionalidade, mas compreensão da lei tributária conforme a Constituição, dando-lhe sentido compatível com a norma fundamental; VII 87. Posto isto, uma vez demonstrado, quantum satis, a viabilidade e procedência do requerimento administrativo objeto da Nota Técnica nº 47/2010/COGES/DENOP/SRH/MP, opina- se pela juridicidade da inclusão cadastral de companheira homoafetiva como dependente de servidora pública federal para efeito de dedução do Imposto de Renda, desde que preenchidos os demais requisitos exigíveis à comprovação da união estável disciplinada nos arts. 4º, III e 8º, II, "b" e "c" da Lei nº 9.250/95, e no art. 77 do Decreto nº 3.000/99 (RIR/99). É o Parecer jurídico. À consideração superior.
```

#### B7. `decreto_59309_19660923` — unit `pp1_agrf2` (federal_decreto)

- File: `urn_lex_br_federal_decreto_1966-09-23_59309.xml`; cited by 1 question(s); the document has 16 chunks; unit heading path: —.

**LexML parse of the unit:**

```text
pp1_agrf2 [Agrupamento nota]:
  <p> H. Castello Branco
  <p> M. Pio Corrêa
  <p> ACÔRDO SÔBRE PRIVILÉGIOS E IMUNIDADES DA AGÊNCIA INTERNACIONAL DE ENERGIA ATÔMICA.
  <p> CONSIDERANDO que o parágrafo C do Artigo XV do Estatuto da Agência Internacional de Energia Atômica dispõe que a capacidade jurídica e os privilégios e imunidades mencionados no referido artigo devem ser definidos em um ou mais acôrdos distintos que serão concluídos entre a Agência representada para êste fim pelo Diretor-Geral que procederá de acôrdo com as instruções do Conselho de governadores e seus Membros;
  <p> CONSIDERANDO que, de acôrdo com o disposto no artigo XVI do Estatuto, foi adotado um acôrdo que regula as relações entre a Agência e a Organização das Nações Unidas;
  <p> CONSIDERANDO que a Assembléia Geral da Organização das Nações Unidas desejando a unificação, na medida do possível, dos privilégios e imunidades de que gozam a Organização das Nações Unidas e as diversas instituições que mantém relações com a mencionada Organização, adotou a Convenção sôbre os privilégios e imunidades das agências especializadas e que vários Estados Membros da Organização das Nações Unidas aderiram à mencionada Convenção;
  <p> O Conselho de Governadores
  <p> 1. Aprovou, sem obrigar os governos representados no Conselho, o seguinte texto, que, de uma maneira geral, repete as disposições da Convenção sôbre os privilégios e imunidades das agências especializadas.
  <p> 2. Convida os Estados Membros da Agência a examinar êste acôrdo e se o julgar oportuno, a aceitá-lo.
```

**Chunks and strategy membership:**

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `urn_lex_br_federal_decreto_1966-09-23_59309#3` | TXT | base | `pp1_agrf2` | 5–6 | 511 | ✓ | ✓ | ✓ | ✓ | ✓ |

**Chunk texts:**

`urn_lex_br_federal_decreto_1966-09-23_59309#3` (TXT):
```text
[ DECRETO Nº 59.309, DE 23 DE SETEMBRO DE 1966. | Promulga o Acôrdo sôbre Privilégios e Imunidades da Agência Internacional de Energia Atômica. ] H. Castello Branco M. Pio Corrêa ACÔRDO SÔBRE PRIVILÉGIOS E IMUNIDADES DA AGÊNCIA INTERNACIONAL DE ENERGIA ATÔMICA. CONSIDERANDO que o parágrafo C do Artigo XV do Estatuto da Agência Internacional de Energia Atômica dispõe que a capacidade jurídica e os privilégios e imunidades mencionados no referido artigo devem ser definidos em um ou mais acôrdos distintos que serão concluídos entre a Agência representada para êste fim pelo Diretor-Geral que procederá de acôrdo com as instruções do Conselho de governadores e seus Membros; CONSIDERANDO que, de acôrdo com o disposto no artigo XVI do Estatuto, foi adotado um acôrdo que regula as relações entre a Agência e a Organização das Nações Unidas; CONSIDERANDO que a Assembléia Geral da Organização das Nações Unidas desejando a unificação, na medida do possível, dos privilégios e imunidades de que gozam a Organização das Nações Unidas e as diversas instituições que mantém relações com a mencionada Organização, adotou a Convenção sôbre os privilégios e imunidades das agências especializadas e que vários Estados Membros da Organização das Nações Unidas aderiram à mencionada Convenção; O Conselho de Governadores 1. Aprovou, sem obrigar os governos representados no Conselho, o seguinte texto, que, de uma maneira geral, repete as disposições da Convenção sôbre os privilégios e imunidades das agências especializadas. 2. Convida os Estados Membros da Agência a examinar êste acôrdo e se o julgar oportuno, a aceitá-lo.
```

#### B8. `declaração_de_imposto_de_renda_retido_na_fonte_DIRF` — unit `pp1_agh2_txt1` (servico)

- File: `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_servico_2026_dirf.xml`; cited by 1 question(s); the document has 6 chunks; unit heading path: Etapas para a realização deste serviço.

**LexML parse of the unit:**

```text
pp1_agh2_txt1 [Agrupamento texto]:
  <p> Preencher declaração
  <p> Baixe o programa que corresponde ao exercício da declaração e preencha as informações que devem ser declaradas à Receita Federal.
  <p> Canais de prestação
  <p> Web :
  <p> Baixar o programa
  <p> Tempo de duração da etapa
  <p> Atendimento imediato
  <p> Enviar a declaração à Receita Federal
  <p> Após o preenchimento, grave a declaração e envie à Receita Federal utilizando o programa ReceitaNet.
  <p> O ReceitaNet valida e transmite, via Internet, as declarações de impostos e contribuições federais de pessoas físicas e jurídicas. Os arquivos podem ser transmitidos diariamente das 05 à 01 hora da manhã do dia seguinte (20 horas diárias).
  <p> Canais de prestação
  <p> Web :
  <p> Baixar o ReceitaNet
  <p> Tempo de duração da etapa
  <p> Atendimento imediato
  <p> Acompanhar o processamento da declaração
  <p> Acompanhe o processamento da declaração para verificar a situação da entrega.
  <p> Canais de prestação
  <p> Web :
  <p> Extrato do Processamento da DIRF (Simplificado)
  <p> Web :
  <p> Consultar DIRF
  <p> Tempo de duração da etapa
  <p> Atendimento imediato
```

**Chunks and strategy membership:**

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_servico_2026_dirf#4` | TXT | base | `pp1_agh2_txt1` | 7–8 | 283 | ✓ | ✓ | ✓ | ✓ | ✓ |

**Chunk texts:**

`urn_lex_br_ministerio.fazenda_secretaria.receita.federal_servico_2026_dirf#4` (TXT):
```text
[ Declaração de Imposto de Renda Retido na Fonte (DIRF) ] Etapas para a realização deste serviço Preencher declaração Baixe o programa que corresponde ao exercício da declaração e preencha as informações que devem ser declaradas à Receita Federal. Canais de prestação Web : Baixar o programa Tempo de duração da etapa Atendimento imediato Enviar a declaração à Receita Federal Após o preenchimento, grave a declaração e envie à Receita Federal utilizando o programa ReceitaNet. O ReceitaNet valida e transmite, via Internet, as declarações de impostos e contribuições federais de pessoas físicas e jurídicas. Os arquivos podem ser transmitidos diariamente das 05 à 01 hora da manhã do dia seguinte (20 horas diárias). Canais de prestação Web : Baixar o ReceitaNet Tempo de duração da etapa Atendimento imediato Acompanhar o processamento da declaração Acompanhe o processamento da declaração para verificar a situação da entrega. Canais de prestação Web : Extrato do Processamento da DIRF (Simplificado) Web : Consultar DIRF Tempo de duração da etapa Atendimento imediato
```

#### B9. `sumula_stj_125` — unit `pp1_agh7_agh3_txt1` (superior.tribunal.justica_sumula)

- File: `urn_lex_br_superior.tribunal.justica_sumula_1994-12-06_125.xml`; cited by 1 question(s); the document has 55 chunks; unit heading path: RECURSO ESPECIAL N. 52.208-SP (1994/0023969-6) ; RELATÓRIO.

**LexML parse of the unit:**

```text
pp1_agh7_agh3_txt1 [Agrupamento texto]:
  <p> O Sr. Ministro Demócrito Reinaldo: Leandro Pereira Leite, promotor de justiça da capital do Estado de São Paulo impetrou mandado de segurança contra ato do Secretário da Fazenda daquele Estado, visando a que na indenização das suas férias não gozadas por necessidade do serviço deixasse de incidir o imposto de renda.
  <p> Denegada a segurança, em primeira instância, em grau de apelação, a egrégia Sexta Câmara Civil do Tribunal de Justiça de São Paulo concedeu o mandamus, ao fundamento basilar de que não se configura hipótese de incidência de imposto de renda, porquanto da indenização por férias não gozadas não decorre acréscimo patrimonial (fl s. 259-261).
  <p> Irresignada, a Fazenda Estadual manifesta recurso especial, sob o pálio da letra a do admissivo constitucional, alegando violação ao art. 1º da Lei n. 5.021/1966 (fl s. 317-321).
  <p> Admitido na origem e contra-arrazoado (fl s. 323-326), subiram os autos e me vieram conclusos para julgamento.
  <p> É o relatório.
```

**Chunks and strategy membership:**

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `urn_lex_br_superior.tribunal.justica_sumula_1994-12-06_125#47` | TXT | base | `pp1_agh7_agh3_txt1` | 105–106 | 390 | ✓ | ✓ | ✓ | ✓ | ✓ |

**Chunk texts:**

`urn_lex_br_superior.tribunal.justica_sumula_1994-12-06_125#47` (TXT):
```text
[ SÚMULA N. 125 | O pagamento de férias não gozadas por necessidade do serviço não está sujeito à incidência do Imposto de Renda. ] RECURSO ESPECIAL N. 52.208-SP (1994/0023969-6) > RELATÓRIO O Sr. Ministro Demócrito Reinaldo: Leandro Pereira Leite, promotor de justiça da capital do Estado de São Paulo impetrou mandado de segurança contra ato do Secretário da Fazenda daquele Estado, visando a que na indenização das suas férias não gozadas por necessidade do serviço deixasse de incidir o imposto de renda. Denegada a segurança, em primeira instância, em grau de apelação, a egrégia Sexta Câmara Civil do Tribunal de Justiça de São Paulo concedeu o mandamus, ao fundamento basilar de que não se configura hipótese de incidência de imposto de renda, porquanto da indenização por férias não gozadas não decorre acréscimo patrimonial (fl s. 259-261). Irresignada, a Fazenda Estadual manifesta recurso especial, sob o pálio da letra a do admissivo constitucional, alegando violação ao art. 1º da Lei n. 5.021/1966 (fl s. 317-321). Admitido na origem e contra-arrazoado (fl s. 323-326), subiram os autos e me vieram conclusos para julgamento. É o relatório.
```

#### B10. `resol_cgsn_140_20180522` — unit `anexo12_tab3` (category-C annex of a statutory document)

- File: `resol_cgsn_140_20180522.anexo12.xml`; cited by 2 question(s); the document has 4 chunks; unit heading path: —.

**LexML parse of the unit:**

```text
anexo12_tab3 [table ]:
  | Subclasse | DENOMINAÇÃO |
  | 6431-0/00 | BANCOS MÚLTIPLOS, SEM CARTEIRA COMERCIAL |
  | 6432-8/00 | BANCOS DE INVESTIMENTO |
  | 6433-6/00 | BANCOS DE DESENVOLVIMENTO |
  | 6434-4/00 | AGÊNCIAS DE FOMENTO |
  | 6435-2/01 | SOCIEDADES DE CRÉDITO IMOBILIÁRIO |
  | 6435-2/02 | ASSOCIAÇÕES DE POUPANÇA E EMPRÉSTIMO |
  | 6435-2/03 | COMPANHIAS HIPOTECÁRIAS |
  | 6436-1/00 | SOCIEDADES DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO - FINANCEIRAS |
  | 6437-9/00 | SOCIEDADES DE CRÉDITO AO MICROEMPREENDEDOR |
  | 6438-7/01 | BANCOS DE CÂMBIO |
  | 6438-7/99 | OUTRAS INSTITUIÇÕES DE INTERMEDIAÇÃO NÃO MONETÁRIA NÃO |
  |  | ESPECIFICADAS ANTERIORMENTE |
  | 6440-9/00 | ARRENDAMENTO MERCANTIL |
  | 6450-6/00 | SOCIEDADES DE CAPITALIZAÇÃO |
  | 6461-1/00 | HOLDINGS DE INSTITUIÇÕES FINANCEIRAS |
  | 6462-0/00 | HOLDINGS DE INSTITUIÇÕES NÃO FINANCEIRAS |
  | 6463-8/00 | OUTRAS SOCIEDADES DE PARTICIPAÇÃO, EXCETO HOLDINGS |
  | 6470-1/01 | FUNDOS DE INVESTIMENTO, EXCETO PREVIDENCIÁRIOS E IMOBILIÁRIOS |
  | 6470-1/02 | FUNDOS DE INVESTIMENTO PREVIDENCIÁRIOS |
  | 6470-1/03 | FUNDOS DE INVESTIMENTO IMOBILIÁRIOS |
  | 6491-3/00 | SOCIEDADES DE FOMENTO MERCANTIL - FACTORING |
  | 6492-1/00 | SECURITIZAÇÃO DE CRÉDITOS |
  | 6499-9/01 | CLUBES DE INVESTIMENTO |
  | 6499-9/02 | SOCIEDADES DE INVESTIMENTO |
  | 6499-9/03 | FUNDO GARANTIDOR DE CRÉDITO |
  | 6499-9/04 | CAIXAS DE FINANCIAMENTO DE CORPORAÇÕES |
  | 6499-9/05 | CONCESSÃO DE CRÉDITO PELAS OSCIP |
  | 6499-9/99 | OUTRAS ATIVIDADES DE SERVIÇOS FINANCEIROS NÃO ESPECIFICADAS |
  |  | ANTERIORMENTE |
  | 6511-1/01 | SOCIEDADE SEGURADORA DE SEGUROS VIDA |
  | 6511-1/02 | PLANOS DE AUXÍLIO-FUNERAL |
  | 6512-0/00 | SOCIEDADE SEGURADORA DE SEGUROS NÃO VIDA |
  | 6520-1/00 | SOCIEDADE SEGURADORA DE SEGUROS SAÚDE |
  | 6530-8/00 | RESSEGUROS |
  | 6541-3/00 | PREVIDÊNCIA COMPLEMENTAR FECHADA |
```

**Chunks and strategy membership:**

| chunk_id | Tipo | variante | cobre_ids | Num | tokens | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---:|---|---|---|---|---|
| `resol_cgsn_140_20180522.anexo12#2` | TAB | base | `anexo12_tab3` | 3–4 | 988 | ✓ | ✓ | ✓ | ✓ | ✓ |

**Chunk texts:**

`resol_cgsn_140_20180522.anexo12#2` (TAB):
```text
[ RESOLUÇÃO Nº 140, DE 22 DE MAIO DE 2018 | Dispõe sobre o Regime Especial Unificado de Arrecadação de Tributos e Contribuições devidos pelas Microempresas e Empresas de Pequeno Porte (Simples Nacional). | Anexo 12 – ANEXO VI DA RESOLUÇÃO CGSN Nº 140, DE 2018. (ART. 8º, § 1º) ] Tabela: Subclasse | DENOMINAÇÃO ; 6431-0/00 | BANCOS MÚLTIPLOS, SEM CARTEIRA COMERCIAL ; 6432-8/00 | BANCOS DE INVESTIMENTO ; 6433-6/00 | BANCOS DE DESENVOLVIMENTO ; 6434-4/00 | AGÊNCIAS DE FOMENTO ; 6435-2/01 | SOCIEDADES DE CRÉDITO IMOBILIÁRIO ; 6435-2/02 | ASSOCIAÇÕES DE POUPANÇA E EMPRÉSTIMO ; 6435-2/03 | COMPANHIAS HIPOTECÁRIAS ; 6436-1/00 | SOCIEDADES DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO - FINANCEIRAS ; 6437-9/00 | SOCIEDADES DE CRÉDITO AO MICROEMPREENDEDOR ; 6438-7/01 | BANCOS DE CÂMBIO ; 6438-7/99 | OUTRAS INSTITUIÇÕES DE INTERMEDIAÇÃO NÃO MONETÁRIA NÃO ; | ESPECIFICADAS ANTERIORMENTE ; 6440-9/00 | ARRENDAMENTO MERCANTIL ; 6450-6/00 | SOCIEDADES DE CAPITALIZAÇÃO ; 6461-1/00 | HOLDINGS DE INSTITUIÇÕES FINANCEIRAS ; 6462-0/00 | HOLDINGS DE INSTITUIÇÕES NÃO FINANCEIRAS ; 6463-8/00 | OUTRAS SOCIEDADES DE PARTICIPAÇÃO, EXCETO HOLDINGS ; 6470-1/01 | FUNDOS DE INVESTIMENTO, EXCETO PREVIDENCIÁRIOS E IMOBILIÁRIOS ; 6470-1/02 | FUNDOS DE INVESTIMENTO PREVIDENCIÁRIOS ; 6470-1/03 | FUNDOS DE INVESTIMENTO IMOBILIÁRIOS ; 6491-3/00 | SOCIEDADES DE FOMENTO MERCANTIL - FACTORING ; 6492-1/00 | SECURITIZAÇÃO DE CRÉDITOS ; 6499-9/01 | CLUBES DE INVESTIMENTO ; 6499-9/02 | SOCIEDADES DE INVESTIMENTO ; 6499-9/03 | FUNDO GARANTIDOR DE CRÉDITO ; 6499-9/04 | CAIXAS DE FINANCIAMENTO DE CORPORAÇÕES ; 6499-9/05 | CONCESSÃO DE CRÉDITO PELAS OSCIP ; 6499-9/99 | OUTRAS ATIVIDADES DE SERVIÇOS FINANCEIROS NÃO ESPECIFICADAS ; | ANTERIORMENTE ; 6511-1/01 | SOCIEDADE SEGURADORA DE SEGUROS VIDA ; 6511-1/02 | PLANOS DE AUXÍLIO-FUNERAL ; 6512-0/00 | SOCIEDADE SEGURADORA DE SEGUROS NÃO VIDA ; 6520-1/00 | SOCIEDADE SEGURADORA DE SEGUROS SAÚDE ; 6530-8/00 | RESSEGUROS ; 6541-3/00 | PREVIDÊNCIA COMPLEMENTAR FECHADA
```

