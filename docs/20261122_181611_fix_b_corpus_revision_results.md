# Fix B (corpus revision): execution and results

**Generated:** 2026-11-22 18:16:11 (local time, from `date +%Y%m%d_%H%M%S`).
**Plan:** `20261122_164407_methodology_additions_plan_token_weighted_citations_sol_and_fix_b.md` §2 (stage 1 of §6),
scope from `20261115_172140_gold_matcher_annex_rule_and_misparsed_articles.md` §5. Executed on the user's request of
2026-11-22, with a new OpenRouter key (limit $37.30).
**Status:** **done** (B1–B8). The user reviewed this note on 2026-11-22. After the review:
- commits pushed: parser `d6e2549` (branch `extensions`) and this repo `bdbdbad` (+ the release record);
- HF repo A `eduseiti/BR-TaxQA-R` → `5886f9a`, repo B `eduseiti/BR-TaxQA-R-RAG-eval` → `4ea3a09` (§8).

**Cost:** **$0.98 on OpenRouter** (key usage; $36.32 left), plus Maritaca (direct, BRL; $0.28 at list price) and the
HF endpoint (≈ 4 min up, ≈ $0.05; the ledger books the conservative $0.44 idle-tail estimate). Under the plan's
$3–6.

| Step | Calls | List | Billed | Ledger |
|---|---:|---:|---:|---|
| Embeddings, gemini-emb-2 (377 texts) | 8 | $0.020 | $0.020 | `embeddings/costs.csv` |
| Embeddings, jua (377 texts) + reproducibility check | 6 + 3 | — | ≈ $0.05 (ledger $0.44 est.) | `embeddings/costs.csv` |
| Generation, OpenRouter (Luna, Terra) | 53 | $0.247 | $0.141 | `runs/costs.csv` |
| Generation, Maritaca (Sabiá-4, Sabiazinho-4) | 68 | $0.280 | (BRL) | `runs/costs.csv` |
| Judge (Gemini 3.8 Flash 217, Gemini 3.1 Pro 10) | 227 | $1.635 | $0.818 | `nuggets/scoring/costs.csv` |

**Backup** of every output before the revision: `../br-taxqa-r_fixB_backup_20261122/` (outside the repo, 2.9 GB):
`segmented/`, `dataset/`, `runs/` (without the LLM cache), `nuggets/scoring/` (without the cache), both embedding
stores, and the 2026-10-09 chunk file (`chunks_all_20261008.csv.gz`).

## 1. Summary

- **The 6 misparses are gone.** Two causes, two fixes:
  - **A parser rule** (sibling repo `../lexml-parser-projeto-lei`, `rotuloParser.scala`). A line `Art. N` followed by
    a citation is not an article label. "Followed by a citation" means a `;`, a comma before citation words
    (`art.`, `inciso`, `§`, `caput`, …), or "da/do Lei / Decreto / Medida Provisória / Constituição". This repairs
    RIR/2018 annex `#2754`, Lei 12.350 `#179`, Portaria Conj. 74 `#23`, Circular BC 3.432 `#30`, IN RFB 1.131 art.
    31 (2nd instance) and the three "Art. 33, inciso I:" headings of the MP 2.228-1 annex.
  - **A `.docx` repair** (`scripts/lexml/repair_docx.py`) where the source itself is wrong:
    - **DL 5.844:** the second "Art. 93" is a typo for art. 98 (it sits between arts. 97 and 99, and art. 100 cites
      "arts. 97 e 98");
    - **Lei 12.715:** the fetched page holds arts. 69–78 twice; the first copy is garbled and was deleted.
- **Found by the new audit checks, and fixed too:**
  - **`Art . 1º`** (space before the dot) was not read as an article. Decreto 71.733 lost 37 of its articles this
    way, and Decretos 57.942, 85.306, 87.563 and Lei 4.886 (art. 49) a few each. In Decreto 57.942 the cited treaty
    arts. 1 and 10 (Q152, Q153) now exist and are matchable. They are no longer in `unmatchable_articles.tsv`.
  - **Decreto 85.306:** once the decree's own `Art . 1º/2º` were read, the attached Protocol (printed after the
    signatures) was taken as signature lines. The implicit-annex rule now also knows treaty headings (protocolo,
    acordo, convenção, tratado), so the Protocol is `decreto_85306_19801030.anexo1.xml`, with the same article ids as
    before (art2–art18; Q156 cites art. 7). Decreto 87.563's treaty also becomes an annex (generic: its "ARTIGO
    I…XXV" are still not read as articles, so its cited art. 15 stays unmatchable).
- **The "to check" cases and the 21 duplicates** were checked against the sources (§2.3). Except Lei 12.715 (above),
  every duplicate is in the source text. They are listed with their reasons in
  `scripts/lexml/reviewed_duplicate_articles.tsv`.
- **Effect on the results: negligible.**
  - Retrieval recall at 4k: unchanged at article and provision level, −0.001 at document level (Gemini).
  - Answers: 121 new generation calls, out of ≈ 23,000 answers in all runs.
  - Run-level V_strict: |Δ| ≤ 0.0034 on every full run.
  - The headline comparisons (S1 vs S2, closed book vs S2) keep their significance. Two borderline comparisons
    flip on secondary metrics (§5).

## 2. B1: corpus repair

### 2.1 Parser change (`../lexml-parser-projeto-lei`, uncommitted on top of `4c85e81`)

| File | Change |
|---|---|
| `rotulo/rotuloParser.scala` | `artigo`: `not(citacaoAposArtigo)` after the label (see §1); `opt(" .")` so `Art . 1º` is a label |
| `ProjetoLei.scala` | `anexoHeadingKeywordRe` += `protocolo`, `acordo`, `conven[cç][aã]o`, `tratado` (implicit annex after the signatures) |
| `rotulo/RotuloParserTest.scala` | `citacaoNaoEArtigo`: the 5 citation lines are not labels; real labels still are, including `Art. 2º-A. Da base…`, `Art. 10. Do valor…`, `Art . 1º`, `Art 15.`, `Art. 76, Feita…` (DL 5.844's comma typo) |

The parser's test suite passes: **42 tests**, 41 before.

A first version rejected any comma after the number. In DL 5.844 that dropped arts. 76, 121 and 205 ("Art. 76,
Feita a revisão…"), and the audit caught it. The comma rule now needs a citation word after the comma.

### 2.2 Re-parse

- **Command:** the same driver as the 2026-10-09 parse (`batch_parse.py --no-justificativa --linker …`), into a
  scratch folder. 209 converted, 0 failed, 388 XML files (+2 annexes). Provenance is in
  `lexml/articulados/PARSER_VERSION`.
- **Compared with the committed LexML** (text and structure, ignoring links). **Exactly the 14 targeted files
  change** (12 changed, 2 new annexes). The other **54 files differ only in linker output**: `Remissao`/`span`
  links, link comments, `Alteracao/@xml:base`. The linker does not reproduce the committed links (as already seen
  in 2026-10, rebuild note §5.3), so **only the 14 files were installed**, and the 54 keep their committed links.
- **Source-word coverage** (`.docx` words found in the XML) is the same as before for every changed document; the
  Lei 12.715 text is measured against the repaired `.docx`.

| File | Articles (top level) | What changed |
|---|---|---|
| `decreto_9580_20181122.anexo1` | 1050 → 1049 | the citation line before art. 211 is plain text (inside CAPÍTULO II) |
| `lei_12350_20101220` | 68 → 67 | the CAPÍTULO II title fragment is plain text |
| `port_conj_tse_srf_74_20060110` | 6 → 5 | the "Art. 81 … revogado" note is part of art. 4º, parágrafo único |
| `circ_bc_3432_20090203` | 43 → 42 | the wrapped "art. 16 da Lei nº 11.795…" line is part of art. 7º |
| `in_rfb_1131_20110221` | 86 → 85 | the wrapped "art. 31;" line is part of art. 34, I |
| `decreto_lei_5844_19430923` | 208 → 208 | `art93` (2nd) → `art98` (.docx repair) |
| `lei_12715_20120917` | 93 → 83 | the garbled copy of arts. 69–78 is gone (.docx repair) |
| `mp_2228-1_20010906.anexo1` | 3 → 0 | the three "Art. 33, inciso I/II/III:" table headings are text |
| `decreto_71733_19730118` | 19 → 56 | `Art . N` articles read (with the superseded wordings the source prints) |
| `decreto_57942_19660310` | 0 → 15 | the treaty's `Art . N` articles read; cited art. 1 and art. 10 exist |
| `decreto_85306_19801030` (+ `.anexo1`) | 17 → 2 + 17 | decree arts. 1–2; the Protocol becomes annex 1 (art2–art18) |
| `decreto_87563_19820913` (+ `.anexo1`) | 0 → 2 + 0 | decree arts. 1–2; the treaty becomes a generic annex |
| `lei_4886_19651209` | 48 → 49 | art. 49 (`Art . 49.`) |

The RIR/2018 citation line stays a loose paragraph of the chapter. It is not prefixed to art. 211, as the other
RIR article rubrics are (e.g. art. 212). The text is kept, and the difference is only layout.

### 2.3 The "to check" cases and the article-level duplicates

| Case | Verdict |
|---|---|
| MP 497 art. 31 (two wordings) | source: the original and the later MP's wording, both printed unstruck |
| Decreto 71.733 art. 2 "out of sequence" | source: two wordings of art. 2 (the first was `Art . 2º`, unread before) |
| Lei 12.715 arts. 69–78 | **fetch error**: a garbled first copy (removed, §1) |
| Decreto-Lei 58/1937 arts. 1º–4º | source: the "Disposições transitórias" number their own arts. 1º–4º |
| MP 2.228-1 annex art. 33 (×3) | misparse of "Art. 33, inciso I:" table headings (parser fix) |
| Circular BC 3.432 art. 16 | misparse (parser fix) |
| Decreto 71.733 art. 22 (and 23, 27, 28, 37) | source: compiled text with superseded wordings unstruck |
| Decreto 70.951 arts. 15, 21, 23, 32, 35, 40, 48, 79 | source: superseded wordings unstruck (found by the new check; uncited) |

Decretos 70.951 and 71.733 and MP 497 break rule D5 ("each article once, in its 2023 wording"): they keep
superseded wordings. All three are uncited, or cited only at document level (Decreto 71.733), so removing the old
wordings is left for later.

### 2.4 Audit checks (`scripts/lexml/audit_article_coverage.py`)

- **New column "out of sequence":** an article whose number breaks the sequence of its neighbours (which are 1–2
  apart).
- **Duplicate XML ids:** compared with the new `reviewed_duplicate_articles.tsv`; unreviewed ones are marked
  **new**.
- Both are warnings; the cited-missing gate is unchanged.
- **Before the repair:** 6 out of sequence and 32 unreviewed duplicates (all the misparses of §2 of the fix A
  note).
- **After:** **0 out of sequence, 0 unreviewed duplicates, gate OK.**

## 3. B2: segmentation, dataset

- **Segmentation:** `segment_all.py --jobs 16 --overwrite --allow-count-change --variants caput --frozen <2026-10-09
  chunks> --frozen-lexml-rev HEAD`. **Validation OK on all 14 checks.**
  - `diff_vs_frozen`: 612 files with unchanged LexML; 92,112 rows compared; **0 differ**.
- **`chunks_all.csv.gz`:** 104,574 → **104,625 rows**, SHA-256 `21bf98e5…910a`. Only the 15 changed files have
  different rows: 377 new texts, 308 gone.
  - **Chunk ids are renumbered inside those files**: `decreto_9580_20181122.anexo1#2754` is now the real art. 211.
  - Rows with `id_ambiguo = 1`: 1,415 → 1,343.
- **`strategies.yaml`** `expected_rows`: S1 21,514; S2/S2c 73,173; S3/S4 77,135.
- **Dataset** (`build_v2_dataset.py`):
  - Q152 (art. 10) and Q153 (art. 1) of Decreto 57.942 become matchable;
  - cited article ids found: 1,464 + 575 (annex) → 1,465 + 576;
  - `provisions.missing` 13 → 11.
  - `documents.jsonl` lists the two new annex files. Nothing else changes.

## 4. B3–B5: embeddings, retrieval, evaluation, contexts

- **Embeddings** (`embed.py corpus --extend`): 101,635 of 102,012 texts reused, **377 embedded** with each model.
- **B4, reproducibility:** 20 random unchanged texts were re-embedded on the live endpoints and compared with the
  stored vectors. The cosine is min **0.999991** for jua and **1.000000** for Gemini (script in the session
  scratchpad).
  - The jua `parity` command could not run: `parity_sample.json` dates from the 2026-09 corpus, and 5 of its ids no
    longer exist. Rebuilding the sample needs CPU reference vectors of the 4B model; this check replaces it.
  - The jua endpoint was paused again.
- **Chunk exclusions (B7 of the plan, done here, before retrieval):** the `chunks:` list of
  `scripts/rag/corpus_exclusions.yaml` is now empty. The 4 misparses no longer exist, and their old ids now name
  other chunks.
- **Retrieval:** `retrieve --force` for jua `irpf`, Gemini `irpf` and jua `irpf_with_rir1999` (`--exclusions
  none`).
- **Evaluation:** the same evaluations as fix A, with **identical parameters** (checked against the old
  manifests): main `either_containment_merge_skip` and `v2d` for both embeddings, Gemini's `v2c` and
  `either_containment_skip`, and `irpf_with_rir1999`.

**Recall at a 4k budget, all gold (main evaluation; "=" means |Δ| < 0.0005):**

| Level | jua S1 | S2 | S2c | S3 | S4 | Gemini S1 | S2 | S2c | S3 | S4 |
|---|---|---|---|---|---|---|---|---|---|---|
| document | 0.621 (=) | 0.700 (=) | 0.686 (=) | 0.691 (=) | 0.680 (=) | 0.598 → 0.597 | 0.682 → 0.681 | 0.664 → 0.663 | 0.671 → 0.670 | 0.660 → 0.659 |
| article | 0.398 (=) | 0.503 (=) | 0.480 (=) | 0.507 (=) | 0.487 (=) | 0.413 (=) | 0.515 (=) | 0.511 (=) | 0.517 (=) | 0.517 (=) |
| provision | 0.369 (=) | 0.420 (=) | 0.417 (=) | 0.429 (=) | 0.427 (=) | 0.380 (=) | 0.435 (=) | 0.438 (=) | 0.454 (=) | 0.454 (=) |

- Over all of `metrics.csv` (every view, cutoff and slice): 3,036 rows (jua) and 3,039 rows (Gemini) of 11,255
  move. Recall moves by at most ±0.009 (unit view), and by at most 0.003 in the budget view.
- **Reachability** (`reachability.csv`):
  - article items reachable 1,944 → **1,946** (Decreto 57.942 arts. 1 and 10);
  - `article_not_in_lexml` 13 → 11;
  - `only_ambiguous_matches` 1 → **0**: Q006's RIR art. 1º no longer has a misparsed twin.

**Contexts:** the same 13 jua sets, S2 4k `context_v1`, Gemini S1/S2 4k, and the 13 `irpf_with_rir1999` sets.
Questions whose **rendered context text** changed, per set:

| Set | jua `irpf` | Gemini |
|---|---|---|
| S1 2k / 4k / 8k | 5 / 7 / 12 | – / 5 / – |
| S2 2k / 4k / 8k | 2 / 6 / 12 | – / 4 / – |
| S2c / S3 / S4 4k | 7 / 5 / 6 | |
| oracle 4k / 16k | 5 / 10 | |
| wrong-S2 4k | 7 (with pinned donors, below) | |
| closed book | 0 | |

The changed questions are mostly the same few: Q155/156 (Decreto 85.306), Q152/153 (Decreto 57.942), and Q163, 193,
217, 288, 441, 451. **≈ 1% of the contexts**, as the plan estimated (§2.2).

### 4.1 Wrong-context donors: a new option, `--donors-from`

- **The problem:** the donor draw (`contexts.donors`) is one seeded sequence over all questions. A change in a few
  questions' contexts or gold shifts every later draw, and the first rebuild gave **342 of 715 questions a new
  donor** for a reason unrelated to the control.
- **The new option** (`rag.py context --donors-from`, `ragpipe.contexts.pinned_donors`) keeps the earlier donors
  wherever they still meet the strict rule, and draws only for the others. The earlier maps are saved in
  `scripts/rag/donors/`.
- **Result:** 1 donor re-drawn per run (Q267 in `irpf`, Q209 in `irpf_with_rir1999`; their old donors' contexts now
  hold a gold document of theirs), and 6 more contexts change because the donor's context changed.
- **None of these 7 is in `stratified_30`**, so the wrong-context answers are unchanged.
- The manifest records `donors_from` and `donors_redrawn`.

## 5. B6–B7: answers and judge

- **Generation:** `rag.py run --budget 74.54 --force` on `full_stage1`, `full_stage2`, `gemini_core`, `pilot` and
  `fixA_oracle` (dry runs first).
  - **121 new calls**, all finish `stop`; everything else came from the cache.
  - Besides the changed contexts, the reruns retried the **6 old errors**, the `max_tokens` failures that fix A had
    left out of scope: Sabiá-4 S2c ×2; Sabiazinho-4 S2 4k, S2c, closed book and pilot `context_v1`, 1 each
    (`errors` column of `runs.csv`). **Every answer run now has 0 errors.**
- **Stale labels:** `nuggets.py score` / `ctxsupport` keep existing labels without checking that the answer or the
  context is the same. The new `scripts/nuggets/drop_stale_labels.py --backup <backup>` compares every answer run
  and context set with the backup, and removes the labels of the changed questions from every nugget set and judge.
  It removed **240 labels**.
- **Rescoring:** each set × judge × sample group of existing folders was rerun with its own sample:
  - gold set: Flash `all`, Flash `stratified_30`, Pro `stratified_70`;
  - cross-sets: `gemini-3.1-pro.rep0` and `qwen3.8-max.rep0` (Flash);
  - `ctxsupport`: Flash `all`, `stratified_30` and `stratified_70`, and Pro `stratified_70`.

  227 calls, **0 failed**. Then `scoretable` (gold, both cross-sets, `stratified_30`) and `analyze`.

**`runs.csv`, gold set, Gemini 3.8 Flash, all.** Every run of 596 or more questions with |ΔV_strict| ≥ 0.001:

| Run | V_strict before → after |
|---|---|
| Luna S1 4k / S2 4k | 0.2713 → 0.2706 / 0.2993 → 0.2995 |
| Luna S1 4k @gemini / S2 4k @gemini | 0.2961 → 0.2948 / 0.3266 → 0.3252 |
| Luna oracle 4k | 0.3393 → 0.3359 |
| Terra S2 4k / oracle 4k | 0.3410 → 0.3423 / 0.3679 → 0.3662 |
| Sabiá-4 S3 / S4 / oracle 4k | 0.3147 → 0.3161 / 0.3075 → 0.3089 / 0.3185 → 0.3201 |
| Sabiazinho-4 S2 4k / oracle 4k | 0.2722 → 0.2736 / 0.2915 → 0.2932 |

- Pilot runs (25–30 questions): only Terra oracle 16k moves, 0.4027 → 0.4127 (25 questions).
- Closed book: V_strict unchanged for all four generators.

**`comparisons.csv`:**
- 172 of 378 comparisons move, by at most |Δ diff| 0.017.
- Headline pairs, V_strict:
  - S1 → S2 4k: Luna +0.028 → +0.029 (p .007 → .005); Terra +0.016 → +0.018 (p .11 → .08, still not
    significant); Sabiá-4 unchanged; Sabiazinho-4 +0.005 → +0.006;
  - closed book → S2: Luna +0.041; Terra −0.010 → −0.009 (p .55 → .60); Sabiá-4 +0.078; Sabiazinho-4 +0.095 →
    +0.096.
- **Flips:** two borderline secondary comparisons, both Luna S2 4k vs oracle 4k:
  - A_strict: +0.027 → +0.024, p 0.046 → 0.071;
  - W: CI lower bound 0.002 → 0.000.

## 6. B8: dashboards

- `build_dashboard_data.py`, `build_trace_data.py` and `build_explorer_data.py` were rerun (5.5 min, exit 0).
- The trace's prompt check verifies 20,258 prompts byte for byte against the rebuilt contexts.
- Its other checks pass:
  - ranks and budgets of the 59,120 per-item rows;
  - context selection of 7,865 sets;
  - templates unchanged.
- The trace and explorer data are gitignored. They go to the HF eval repo (`raw/dashboard_trace.tar.gz`) with the
  release.

## 7. Code and data changes (uncommitted)

| Path | Change |
|---|---|
| `original/articulados/lei_12715_20120917.docx`, `decreto_lei_5844_19430923.docx` | repaired by `scripts/lexml/repair_docx.py` (new; `--all --check` verifies) |
| `lexml/articulados/` | 12 files + 2 new annexes, `.err.log`s, `PARSER_VERSION` |
| `scripts/lexml/audit_article_coverage.py`, `reviewed_duplicate_articles.tsv` (new), `unmatchable_articles.tsv` (−2) | §2.4 |
| `segmented/`, `dataset/` | §3 |
| `embeddings/*/corpus/manifest.json`, `embeddings/costs.csv`, `endpoint_meter.jsonl` | §4 |
| `scripts/rag/corpus_exclusions.yaml` | `chunks: {}` with the history in a comment |
| `scripts/rag/strategies.yaml` | expected rows |
| `scripts/rag/ragpipe/contexts.py`, `rag.py`, `scripts/rag/donors/` (new) | `--donors-from` (§4.1) |
| `scripts/nuggets/drop_stale_labels.py` (new) | §5 |
| `runs/`, `nuggets/scoring/` | regenerated outputs and ledgers |
| `../lexml-parser-projeto-lei` | §2.1 (3 files) |

All test suites pass: rag (46), segmentation (49), dataset (36), parser (42). `pinned_donors` has no unit test of
its own yet.

## 8. Commits and Hugging Face release (after the review, 2026-11-22)

- **Git:**
  - `../lexml-parser-projeto-lei` `d6e2549` (branch `extensions`);
  - this repo `bdbdbad` (`main`);
  - both pushed to GitHub over HTTPS with the `gh` credential (SSH has no key on this machine).
  - `lexml/articulados/PARSER_VERSION` names the parser commit.
- **HF build** (`build_release.py`):
  - Card counts updated: 104,625 chunks; 21,514 / 73,173 / 77,135 rows per strategy; 102,012 vectors.
  - Repo A's card gets a short note on the revision, and repo B's file list gets this note.
  - `nuggets/full/cache` and `nuggets/parity_openrouter/cache` are not on this machine and did not change, so
    their archives were downloaded from the Hub and kept (`--keep-raw`). Every other archive was repacked.
- **Push** (`push_release.py`, after dry runs):
  - **repo A** `eduseiti/BR-TaxQA-R`: 2 new files (the annexes), 25 changed → **`5886f9a`**
    (`5886f9aa4a0a2c5b14aaeb1fff7cca4ce080bab5`);
  - **repo B** `eduseiti/BR-TaxQA-R-RAG-eval`: 1 new file (this note), 419 changed → **`4ea3a09`**
    (`4ea3a09d88204c0a30a7fd434cb0c517a12cb904`).
  - A dry run after the push: both repos in sync.
  - Recorded in `release/hf_release.json`.
- **Next:** stage 2 of the plan (A1, token-weighted metric) on the revised corpus.
