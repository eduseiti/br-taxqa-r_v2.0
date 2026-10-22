# RAG Phase 2 — generator contexts: implementation and run

**Generated:** 2026-10-21 21:02:51 (local time, from `date +%Y%m%d_%H%M%S`).
**Implements:** RAG plan §6 (`docs/20260927_204356_rag_pipeline_implementation_plan.md`, stage C) and the
controls of the first-evaluation note (`docs/20261021_194457_first_rag_evaluation_readiness_costs_and_grounding.md`
§2.3, §3.1, §4.2): closed-book, oracle and wrong-context sets, and per-question gold coverage for the phase 5
retrieval ↔ answer linkage.
**Cost:** $0 (no API call). **Embedding:** `jua-4b-mixed`, instruction `irpf`, rankings of 2026-10-09
(chunk file SHA-256 `a6087b7f…326a`).
**Outputs:** `runs/contexts/jua-4b-mixed/irpf/` (20 context sets × 715 questions, 46 MB; `summary.csv` and the
manifests are in git, `contexts.jsonl.gz` are not), and a new retrieval evaluation
`runs/retrieval/jua-4b-mixed/irpf/eval/either_containment_merge_skip/` (§4).
**Status:** done (decisions of §7: items 1 and 3 settled in §9–§10). **The numbers of §3–§10 are those of the corpus
with the RIR/1999; since 2026-10-22 the main run excludes it** (`docs/20261022_203625_corpus_exclusion_revoked_rir1999.md`;
the corpus of this note is the ablation run `irpf_with_rir1999`); **gate** (RAG plan §9: "contexts of a pilot sample reviewed by hand") needs the user's
review of §5, and **three decisions** (§7), the first of which changes the headline retrieval numbers.

## 1. What was built

| File | Change |
|---|---|
| `scripts/rag/ragpipe/contexts.py` (new) | Stage C driver: set specs, retrieval / closed-book / oracle / wrong-context sets, gold coverage, consistency check against the evaluation, rendering, `summary.csv` |
| `scripts/rag/ragpipe/context.py` | Header label (`source_label`, issuing body from the URN), versioned template (`Template`); selection option `containment_merge` (§4) |
| `scripts/rag/prompts/context_v1.pt.md` (new) | `[Documento {n}] {fonte}` + `{texto}`, blocks joined by a blank line |
| `scripts/rag/rag.py` | `context` and `show-context` subcommands; `--dedup containment_merge` for `evaluate` too |
| `scripts/rag/ragpipe/data.py` | `load_chunks(with_text=True)` also loads `anexo_urn`, `texto_sha256` |
| `scripts/rag/ragpipe/runs.py` | `write_jsonl_gz` (byte-reproducible); `git_info` computed once per process (`git status` took ≈ 3 s per manifest on this checkout: the test suite went from 196 s to 9 s) |
| `scripts/rag/tests/test_contexts.py` (new), `test_units.py` | 10 new tests (sets, oracle, donors, rendering, labels, epígrafe fallback, spec parsing, determinism, CLI, merge); **34 passed** |
| `scripts/rag/README.md`, `CLAUDE.md`, `.gitignore` | Phase 2 documented; `runs/contexts/**/summary.csv` versioned |

```bash
R=scripts/rag/rag.py
.venv/bin/python $R context --retrieval runs/retrieval/jua-4b-mixed/irpf \
    --sets S1@budget=4000,…,wrong:S2@budget=4000,oracle@budget=16000      # the 12 pilot sets + oracle 16k
.venv/bin/python $R evaluate --retrieval runs/retrieval/jua-4b-mixed/irpf --dedup containment_merge
.venv/bin/python $R context --retrieval runs/retrieval/jua-4b-mixed/irpf --dedup containment_merge \
    --sets S1@budget=4000,S2@budget=4000,S3@budget=4000,S2c@budget=4000,S4@budget=4000,S1@budget=8000,S2@budget=8000
.venv/bin/python $R show-context --context runs/contexts/jua-4b-mixed/irpf/S2_budget4000 --questions 350
```

Time: 70 s for the 13 default-option sets (33 s of it loading the chunks and the Matcher), 2 min 26 s for all 20;
the merge evaluation ≈ 2 min.

## 2. Design

### 2.1 Context sets

| Spec → id | Content |
|---|---|
| `S2@budget=4000` → `S2_budget4000` | The strategy's ranking cut by `context.select` (containment de-duplication, `skip`): **the same texts as the evaluation's budget view**, in rank order |
| `closed_book` | Empty |
| `oracle@budget=4000` | The question's gold articles (rules G1–G3, annex rule `either`) as S1 article units; a gold document none of whose gold articles is matchable (e.g. the treaties promulgated by decree, "art. IX": Q154, Q155, Q158, Q159) adds its S1 chunks. Ordered by S1 rank (unranked after, in file order), cut by the budget. Empty for the **119 questions without resolved gold** |
| `wrong:S2@budget=4000` → `wrong-S2_budget4000` | The S2 4k context of a **donor**: another P&R chapter, no shared gold document, and no chunk of the question's gold documents in the donor context; seeded permutation (seed 13). The control for answers from the model's own knowledge |

Non-default options add a suffix (`S2_budget4000_dedup-containment_merge`); a set directory refuses to be
overwritten by another configuration (`--force`), as the other stages.

### 2.2 Rendering (`context_v1`)

```
[Documento 2] DECRETO Nº 3.000, DE 26 DE MARÇO DE 1999 — Art. 77, § 1º
[ DECRETO Nº 3.000, DE 26 DE MARÇO DE 1999 | Regulamenta a tributação, … ] Art. 77. § 1º Poderão ser considerados como dependentes, …
```

- `{fonte}` = document title (`documents.jsonl`) — issuing body when the title lacks it (titles of RFB/SRF acts
  read "INSTRUÇÃO NORMATIVA Nº 1.500, …"; 4,701 of 12,486 distinct headers get "Receita Federal [do Brasil]") —
  `Anexo` for annex chunks — the chunk's `citacao` — `(parte p de n)` for split articles.
- **Title fallback:** 9 documents have no title in `documents.jsonl` (seven RFB service pages: DBF, DIMOB, DMED,
  DOI, DIRF, Carnê-Leão, DIAT; two soluções de consulta). The header then uses the epígrafe of the chunk's
  `[ … ]` prefix, or its ementa when the epígrafe is a URN (the DIAT page, see §6).
- **Citation fix:** the segmentation's `citacao` writes "Art. 71., § 1º" / "Parágrafo único., II"; the header
  drops a period before a comma.
- The chunk text is unchanged: it is what was embedded and what the budget counts.

### 2.3 Gold coverage per context (phase 5 linkage)

Each line of `contexts.jsonl.gz` has `gold.{document,article,provision} = {n, full, any}` (the item keys of
`per_item.csv.gz`), by the evaluation's rules (`Matcher`; full hit = a `cobre_ids` id equal to or an ancestor of
the fragment, a containing grouping chunk, or all parts of a split article). Lines also carry, per item, rank,
score, chunk id, aliases, tokens and the header.

## 3. Results

### 3.1 Consistency with the retrieval evaluation

For the 9 retrieval sets with default options, the set of fully hit gold items equals the evaluation's
`budget_full_<B>` (`v2d_either_containment_skip`) item by item: **0 mismatches** (5,912 items per strategy; e.g.
1,936 full hits in S1 4k, 2,691 in S2 8k). The 7 merge sets match `either_containment_merge_skip`: 0 mismatches.
So the generator sees exactly the contexts the legal-provision test measured.

### 3.2 Context sets (`summary.csv`; recall = mean share of gold items fully in the context, over questions with gold)

| Set | Texts | Text tokens | Rendered tokens | Header overhead | Document recall | Article recall | Article hit | Provision recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 2k | 6.3 | 1,985 | 2,245 | 13.1 % | 0.479 | 0.266 | 0.465 | 0.239 |
| S1 4k | 11.1 | 3,984 | 4,447 | 11.6 % | 0.605 | 0.383 | 0.604 | 0.353 |
| S1 8k | 20.9 | 7,985 | 8,869 | 11.1 % | 0.718 | 0.480 | 0.707 | 0.456 |
| S2 2k | 7.8 | 1,983 | 2,328 | 17.4 % | 0.575 | 0.388 | 0.609 | 0.262 |
| S2 4k | 13.7 | 3,984 | 4,593 | 15.3 % | 0.667 | 0.473 | 0.705 | 0.362 |
| S2 8k | 26.1 | 7,984 | 9,146 | 14.6 % | 0.764 | 0.569 | 0.792 | 0.471 |
| S2c 4k | 13.1 | 3,983 | 4,561 | 14.5 % | 0.636 | 0.431 | 0.680 | 0.324 |
| S3 4k | 12.7 | 3,983 | 4,555 | 14.4 % | 0.655 | 0.465 | 0.693 | 0.362 |
| S4 4k | 12.2 | 3,983 | 4,529 | 13.7 % | 0.632 | 0.428 | 0.665 | 0.338 |
| closed-book | 0 | 0 | 0 | — | 0 | 0 | 0 | 0 |
| **oracle 4k** | 4.7 | 2,062 | 2,265 | 9.8 % | 0.884 | **0.803** | 0.902 | 0.770 |
| **oracle 16k** | 10.6 | 4,980 | 5,444 | 9.3 % | 0.974 | **0.946** | 0.980 | 0.925 |
| wrong S2 4k | 13.2 | 3,984 | 4,569 | 14.7 % | **0** | **0** | 0 | 0 |

- **Header overhead 10–17 %**: a 4k context is ≈ 4.45–4.6k rendered Qwen3 tokens. The cost estimates of the
  first-evaluation note (budget + 0.9k) still hold.
- **The oracle at 4k holds 80 % of the gold articles**, not 100 %: of 1,958 gold articles, 1,293 are in it, 652 are
  reachable but do not fit in 4k (questions citing many or long articles; 248 oracle contexts are above 3.5k
  tokens), 13 are not in the LexML. At 16k it holds 95 %. Oracle 4k is the right bound for equal-budget
  comparisons, oracle 16k the ceiling.
- **Wrong context:** no question's context holds any of its gold (by construction, verified: all coverage 0);
  the strict donor rule was never relaxed; 113 donors serve two questions (the unused-donor pool runs out of
  eligible ones late in the permutation).

## 4. Finding: parents after their children repeat text (`containment` vs `containment_merge`)

`containment` (the Phase 1 rule, RAG plan §6.1) drops a child ranked after a selected parent, but keeps a
**parent ranked after its selected child**, "since the parent adds text". The child's text is then in the
context twice. Measured on the default sets:

| Set | Duplicated child tokens (share of context tokens) | Questions affected |
|---|---:|---:|
| S1 4k | 0.0 % | 1 / 715 |
| S2 4k | 9.3 % | 489 |
| S3 4k | 11.2 % | 501 |
| S2c 4k | 13.8 % | 505 |
| S4 4k | 14.5 % | 506 |
| S2 8k | 11.0 % | 607 |

Example (Q350, S2 4k): `Lei 9.250, Art. 35, caput` at rank 7, then the whole `Art. 35` at rank 12.
So at equal budget the hierarchical strategies spend 9–15 % of it on repeats, and S1 does not: a **bias against
S2–S4 in the headline comparison**, in the retrieval test and in the generator contexts alike (and two copies of
a provision are a poor context for a generator).

`containment_merge` (new option, plan §6.1 "left for later") lets that parent **replace** its selected children,
in the first child's place, using only its extra tokens. Legal-provision test, `either_containment_merge_skip` vs
`v2d_either_containment_skip` (budget view, all gold):

| Strategy | Article recall 4k: containment → merge | Provision recall 4k | Provision full recall 4k | Article context precision 4k |
|---|---|---|---|---|
| S1 | 0.383 → 0.383 | 0.353 → 0.353 | 0.204 → 0.204 | 0.124 → 0.124 |
| S2 | 0.473 → **0.495** (+0.022) | 0.362 → **0.404** (+0.042) | 0.210 → 0.244 | 0.157 → 0.138 |
| S3 | 0.465 → 0.494 (+0.029) | 0.362 → 0.409 (+0.048) | 0.219 → 0.260 | 0.171 → 0.154 |
| S2c | 0.431 → 0.468 (+0.037) | 0.324 → 0.402 (+0.078) | 0.186 → 0.238 | 0.179 → 0.147 |
| S4 | 0.428 → 0.468 (+0.039) | 0.338 → 0.408 (+0.070) | 0.206 → 0.253 | 0.189 → 0.163 |

Gains are similar at 2k and 8k (+0.014 to +0.036 article recall) and smaller at 16k. Paired S1 → S2 article
recall difference: 2k +0.122 → **+0.136**, 4k +0.090 → **+0.111**, 8k +0.089 → **+0.107** (all p < 0.001); S2 → S3
stays not significant (−0.001 to −0.003). Context precision drops 1–4 points: the parents bring their non-gold
siblings with them. The caput variants (S2c, S4) gain most: they repeat the caput sentence in every child, so a
later parent repeated more. The merged contexts hold fewer, longer texts (S2 4k: 12.6 vs 13.7).

The merge evaluation's comparisons use the default pairs (S1:S2, S2:S3); the caput pairs can be added with
`--comparisons` if merge is adopted.

## 5. Hand review (gate): what to look at

`show-context` prints the items (rank, tokens, chunk, header) and the rendered text of any question and set. I
read Q012 and Q350 (both in `stratified_30`) across the sets; Q350 (sogro/sogra as dependents, gold Lei 9.250
art. 35):

- **S1 4k** (9 texts): IN RFB 1.500 art. 90 (2 parts), **Lei 9.250 art. 35 (gold, rank 2)**, Solução de Consulta
  Cosit 15/2016, Decreto-Lei 1.493 art. 2º, Decreto 3.000/1999 art. 77…
- **S2 4k** (11): IN 1.500 art. 90 caput, Decreto 3.000 art. 77 § 1º, IN 1.500 art. 90 part 1, RIR/2018 art. 71 § 1º,
  Lei 9.250 art. 35 caput **and** art. 35 (the repeat of §4)…
- **S2 4k merge** (13): the caput is absorbed by art. 90 part 1, art. 35 appears once; the freed tokens bring
  in IN SRF 81 art. 14, IN 1.500 art. 100 § 1º, Lei 12.973 art. 25…
- **oracle 4k**: Lei 9.250 art. 35 only (723 tokens). **wrong S2 4k**: donor Q628 (another chapter), 17 texts, no
  gold.

Things the reviewer should judge on 3–5 pilot questions: header readability; whether the `[ Epígrafe | Ementa ]`
prefix repeated in every block is acceptable (part of the 10–17 % overhead); the presence of **revoked
regulations** (Decreto 3.000/1999, the RIR/1999, next to Decreto 9.580/2018), which the P&R cites and the corpus
therefore contains: a temporal-grounding risk the answer prompt and the value checks must handle, not a context
bug.

## 6. Corpus issues found (not fixed)

1. **DIAT service page** (`urn_lex_br_…_servico_2026_diat.xml`, 1 chunk): its epígrafe is the URN
   (`[ urn:lex:br:…;diat | Documento de Informação e Apuração do ITR (Diat) ]`), so the embedded text starts with a
   URN. Cause: no title declared for it. The header works around it; the chunk text needs a re-parse with a title
   (`scripts/lexml/nonstat_metadata.tsv`) and a re-embedding of one text.
2. **Missing titles** in `documents.jsonl` for 9 documents (§2.2): `build_v2_dataset.py` could take them from the
   LexML epígrafe.
3. Long `citacao` values in some non-statutory chunks (159 headers > 220 characters: section headings used as the
   citation, e.g. NOTA PGFN/CRJ 1104/2017). Readable; left as is.

## 7. Decisions for the user

1. **De-duplication of the contexts (and of the headline retrieval test): `containment` or
   `containment_merge`?** Recommendation: **`containment_merge`** for the generator contexts and as the
   headline of the legal-provision test, with `containment` reported as the Phase 1 variant. It removes a
   bias against S2–S4 and duplicated text in the prompts. It changes the headline S1 → S2 gap (4k article
   recall +0.090 → +0.111), so the retrieval note's numbers would be restated. If adopted, the default
   `--dedup` of `context` and `evaluate` changes, the merge evaluation becomes the headline (it already
   exists), and the pilot sets are rebuilt (≈ 1 min).
2. **Oracle budget:** recommendation: run **both** oracle 4k (equal budget) and oracle 16k (ceiling) in the
   generation pilot; oracle 16k adds 30 calls per generator to the 11-context pilot grid.
3. **Header:** keep `context_v1` (title per block, ≈ 10–17 % overhead) for the pilot (recommended), or make a
   `context_v2` that names the issuing body and the citation only, since the chunk prefix already carries the
   title and ementa (saves ≈ 5–8 % of the input).

## 8. Next

RAG Phase 3 (generation): `llms.yaml` (Sabiá-4, Sabiazinho-4 on the Maritaca route; `gpt-5.6-terra`,
`gpt-5.6-luna` on OpenRouter; DeepSeek disabled here), `answer_v1` with the grounding rules and the reply checks
of the first-evaluation note §4.1, `--dry-run` cost estimate from `rendered_tokens_qwen3`, then the 30-question
pilot. The contexts are read through `contexts.jsonl.gz`, whose `context_id` and `gold` go into the answer lines.

## 9. Addendum (2026-10-21, after the user's review): `containment_merge` adopted

**Decision (user):** `containment_merge` is the default selection rule, for the generator contexts and for
the headline legal-provision test (§7 item 1). `containment` stays as the Phase 1 variant
(`eval/v2d_either_containment_skip`).

- Code: default `dedup` of `select`, `EvalConfig`, `ContextConfig` and the `evaluate` / `context` CLI is
  `containment_merge`; default comparisons of `evaluate` are now the five pairs S1:S2, S2:S3, S2:S2c, S3:S4,
  S1:S2c. Tests updated (34 passed).
- Rerun: `rag.py evaluate --retrieval runs/retrieval/jua-4b-mixed/irpf --force` → headline
  `eval/either_containment_merge_skip` (with the five pairs); the context folder was rebuilt with the default
  sets + `oracle@budget=16000` (13 sets, no suffix; the `_dedup-containment_merge` and containment sets of §3–§4
  are gone, regenerable with `--dedup`). Consistency with the headline evaluation: 0 mismatches.
- Headline article recall at 4k (budget view, all gold): S1 0.383, S2 0.495, S3 0.494, S2c 0.468, S4 0.468.
  Paired: S1 → S2 **+0.111** (CI 0.090–0.135), S2 → S3 −0.001 (n.s.), S2 → S2c −0.027 (CI −0.043 to −0.011),
  S3 → S4 −0.026 (CI −0.042 to −0.011), S1 → S2c +0.085. Under `containment` the caput variants lost ≈ 0.04 to
  their base strategies; under merge ≈ 0.027.

**Budget fill rule (user question).** Texts are taken in rank order and never truncated. With
`overflow=skip` (default) a text that does not fit the remaining budget is passed over and filling continues
with lower-ranked texts that do fit; scanning ends when no remaining candidate fits (the suffix minimum of the
token counts) or the 1,000 ranked texts are used up. With `overflow=stop` filling ends at the first text that
does not fit. A merged parent needs only its tokens minus those of the children it replaces. The context is
therefore never above the budget, and slightly below it:

| Set | Unused budget: mean / median / max | Deepest rank used: median / p90 / max | Tokens from texts ranked > 50 |
|---|---|---|---:|
| S1 2k | 15 / 13 / 55 | 21 / 213 / 962 | 1.0 % |
| S1 4k | 16 / 13 / 59 | 28 / 227 / 962 | 0.6 % |
| S2 4k | 16 / 14 / 66 | 36 / 333 / 996 | 1.4 % |
| S4 4k | 17 / 13 / 71 | 48 / 372 / 986 | 4.0 % |
| S2 8k | 16 / 14 / 85 | 63 / 374 / 997 | 6.2 % |

The budget counts only chunk texts (`n_tokens_qwen3`); the rendered context with headers is 10–17 % larger
(§3.2). The deep-rank fillers are small texts (often < 100 tokens) that close the last gap; `overflow=stop`
would avoid them at the cost of less filled contexts, probably more so for S1, whose texts are longer
(not measured).

## 10. Addendum (2026-10-22): `context_v2` adopted

**Why** (user question on §7 item 3): `context_v1` repeats the document identification twice per block: in the
header (9.5–11 % of the rendered tokens at 4k) and in the chunk's `[ Epígrafe | Ementa ]` prefix (17.8–23.4 %);
together **≈ 30 %** of the prompt (S1 30.9 %, S2 34.5 %, S4 29.7 %, oracle 26.0 %; Qwen3 tokens). The template
enters every generation request, so it had to be fixed before the pilot. **Decision (user): `context_v2`**, the
default of `rag.py context`.

**Rule.** The segmentation writes one prefix per file: `[ epígrafe | ementa ]` or `[ epígrafe ]` in a main file
(453 files; the first field equals the `documents.jsonl` title wherever there is one), `[ epígrafe | ementa |
annex label ]` in an annex (172 files); the only irregular one is the DIAT page (`[ urn | name ]`, §6). `context_v2`
removes the prefix from `{texto}`; the epígrafe is in the header already, the **annex label replaces "Anexo"** in
the header, and the **ementa is shown once per document** (`Ementa: …` line on its first block in the context;
skipped when it equals the title, as for DIAT). The selection is unchanged: the budget counts the full chunk text,
so the contexts hold the same texts as the evaluation (0 mismatches on the 9 retrieval sets after the rebuild).

| Set | Text tokens (budget) | Rendered, `context_v1` | Rendered, `context_v2` |
|---|---:|---:|---:|
| S1 4k | 3,984 | 4,447 | **3,812** |
| S2 4k | 3,984 | 4,532 | **3,814** (−16 %) |
| S4 4k | 3,983 | 4,456 | 3,867 |
| S2 8k | 7,984 | 9,035 | 7,505 |
| oracle 4k | 2,062 | 2,265 | 1,965 |
| oracle 16k | 4,979 | 5,443 | 4,621 |

(v1 figures are those of the merge sets of §9.)

**Pilot ablation:** `S2_budget4000_context_v1` (S2 4k rendered with `context_v1`) is kept next to the 13 default
sets, so the pilot can compare the two templates on the same texts (≈ 30 calls per generator).

**Code:** `prompts/context_v2.pt.md` (new; placeholder `{ementa}`); `context.split_prefix`, `Template.per_document_ementa`,
`source_label(…, annex_label)`; `contexts.describe` renders per template and tracks the documents already shown;
`ContextConfig.template` / `--template` default `context_v2`. Tests: 35 passed.

**Seen in the review sample:** the ementa parsed for Solução de Consulta Cosit 15/2016 is "(Republicação - publicação
anterior em 11 de abril de 2016)" (a parsing quirk of that document, harmless); RIR/2018 annex blocks read "Anexo 1 –
ANEXO" (the annex has no title of its own).
