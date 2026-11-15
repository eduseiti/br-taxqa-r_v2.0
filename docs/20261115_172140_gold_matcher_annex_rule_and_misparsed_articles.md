# Gold matcher: the annex rule and misparsed article chunks — audit and fix plan

**Generated:** 2026-11-15 17:21:40 (local time, from `date +%Y%m%d_%H%M%S`).
**Status:**
- **Fix A** (matcher + chunk exclusions + reruns, §4): **done on 2026-11-15**. Results, costs and two deviations
  from §4 are in `20261115_181838_fix_a_gold_matcher_results.md`: only 4 chunks were pure junk and are excluded; a
  second instance is no longer resolved by a first-instance rule, but reported.
- **Fix B** (corpus revision, §5): **pending**, deferred to a planned corpus revision. Recorded in `CLAUDE.md`
  under "Pending corpus revision" so that it is not missed.

**Found:** in the corpus & question explorer (`20261115_145149_corpus_and_question_explorer.md`). On Q006, the "Gold
segments by strategy" of RIR/2018 art. 1º listed three chunks. Only one is right: art. 1º of the annex (the
Regulamento). The other two are art. 1º of the Decreto itself ("Fica aprovado o Regulamento…") and a citation line
inside the annex, parsed as an article.

**Not a dashboard bug:** the explorer calls the evaluation's own matcher (`ragpipe.relevance.Matcher`). The same
matcher is used by:
- the retrieval evaluation;
- the oracle-context builder;
- the legal-provision (citation) score of the answers.

## 1. The two causes

### 1.1 Annex rule `either` ignores the file the reference names (G3)

`annex_rule = "either"` (retrieval plan §4.2, G3) counts article N of the main file **or of any annex** of the
document as the gold article. It was chosen for citations such as "RIR/2018, art. X", which do not say whether they
mean the decree or its annex.

Two places drop the file:
- `Matcher._match_provision` adds the files of `article_files()` to `item.lexml_file`, even when the reference's
  provision names the file explicitly (here `lexml/articulados/decreto_9580_20181122.anexo1.xml`).
- Article-level gold items carry no file at all (key `(document_id, article_id)`), so they always take every file
  that has the article id.

The 2026-09-27 audit (`20260927_222210_retrieval_legal_provision_test_jua.md` §4) counted 3 article items affected
and judged `either` vs `main_first` negligible. That count is unchanged. The matcher still lets the main file in
when the reference names the annex.

### 1.2 Misparsed "articles": citation lines turned into `Art. N` (G4 gap)

The statutory parser turned some lines that cite other laws into articles with their own id. In RIR/2018 annex
(`decreto_9580_20181122.anexo1.xml`), the line before art. 211, "Art. 1º, art. 2º e art. 4º ao art. 71 da Lei nº
12.973, de 13 de maio de 2014", became chunk `decreto_9580_20181122.anexo1#2754`, with `artigo_id = art1`.

The matcher groups chunks by `(arquivo, artigo_id)`, so that chunk counts as art. 1º of the annex. G4 flags only
items reachable **only** through `id_ambiguo = 1` chunks, and the real art. 1º is also there. So nothing was reported.

## 2. Corpus-wide check (2026-11-15)

Scripts kept in the session scratchpad; the method is reproducible from this description.

**Annex rule.** Over all gold items (1,958 article, 2,230 provision), the matcher adds chunks from a file other than
the one the reference names for:
- 3 article items: **Q006 art. 1º, Q220 art. 5º, Q264 art. 4º**;
- 4 provision items: the same 3 questions; Q220 has two provisions.

All are RIR/2018 (`decreto_9580_20181122`): the annex is cited, and the decree's art. 1º, 4º and 5º are added.

**Misparsed articles.** The check flags any `ART` chunk whose number breaks the sequence of its neighbours (the
neighbours are consecutive and it is not between them), plus duplicated `(file, article id)` instances. It found 9
suspect chunks.

| Chunk | Text (start) | Verdict |
|---|---|---|
| `decreto_9580_20181122.anexo1#2754` | "Art. 1º , art. 2º e art. 4º ao art. 71 da Lei nº 12.973, de 13 de maio de 2014" | **misparse** (citation line) |
| `lei_12350_20101220#179` | "Art. 19. DA LEI Nº 10.973, DE 2 DE DEZEMBRO DE 2004, E O ART. 21 DA LEI Nº 11.196…" | **misparse** (heading) |
| `port_conj_tse_srf_74_20060110#23` | "Art. 81. da Lei nº 9.504/1997 revogado pelo art. 15 da Lei nº 13.165/2015." | **misparse** (note) |
| `in_rfb_1131_20110221#172` | "Art. 31. ; II – as doações ou patrocínios…" | **misparse** (fragment) |
| `circ_bc_3432_20090203#30` | "Art. 16. da Lei nº 11.795, de 2008, pressupõe a:" | **misparse** (citation) |
| `decreto_lei_5844_19430923#391` | "Da exploração de películas cinematográficas estrangeiras Art. 93. Considera‑se…" | **misparse** (heading glued on; duplicate art93 out of sequence) |
| `mp_497_20100727#81` | "Art. 31. O disposto no art. 22 produz efeitos…" | to check against the source (duplicate art31) |
| `decreto_71733_19730118#49` | "Art. 2º A competência estabelecida neste Decreto…" | to check (out of sequence, not duplicated) |
| `port_conj_tse_srf_74_20060110#24` | "Art. 5º Esta portaria entra em vigor…" | real: flagged only because of the misparsed art. 81 before it |

**Duplicates.** 96 `(file, article id)` pairs in 23 files have more than one separate instance. 21 are at article
level:
- Lei 12.715 arts. 69–78;
- Decreto-Lei 58/1937 arts. 1º–4º;
- MP 2.228-1 annex art. 33 (three times);
- Circular BC 3.432 art. 16;
- Decreto 71.733 art. 22;
- plus the misparses above.

The rest are alíneas, items and paragraphs repeated in treaty annexes and forms. Most look like text repeated in the
source documents, not parser errors; check each one in the corpus revision. **Only Q006 has a gold item on a
duplicated id.**

## 3. Effect on the results

- **Retrieval:**
  - No suspect chunk is in any retrieved generator context: S1, S2, S3, S2c, S4, every budget, both embeddings, and
    the wrong-context control.
  - For the affected gold items, the first-hit ranks and the context hits at 1k–16k are the same in all 10 runs
    whether or not the wrong chunks count. The right annex chunk is always reached first or at the same budget.
  - **No retrieval metric changes.**
- **Oracle contexts** (built with the matcher), 4k and 16k:
  - Q006, Q220 and Q264 also hold the decree article (88–108 tokens). Q006 also holds the misparsed `#2754`
    (128 tokens).
  - Q438 cites the whole portaria, so its oracle context also holds the misparsed "Art. 81" line.
  - Through the oracle contexts, this reaches the oracle answers (4 generators × oracle 4k) and the oracle
    nugget-support labels of these **4 questions out of 715**.
- **Legal-provision score of answers:** the same matcher, so an answer citing the decree article instead of the
  annex counts as correct for Q006, Q220 and Q264. Not yet checked whether any answer did. Check it in step 6 of §4.

## 4. Fix A — matcher, chunk exclusions, reruns (done 2026-11-15; see the results note)

**Code changes:**
1. **Annex rule, provision level:** `Matcher._match_provision` matches only `item.lexml_file` when the reference
   names one. `either` applies only to provisions without a file.
2. **Annex rule, article level:** article gold items carry the file(s) their reference's provisions name, when every
   provision of the reference names the same file. They match only that file. Otherwise `either` stays as it is.
3. **Duplicated ids (G4):**
   - a chunk in a separate instance of the article id does not hit the gold article;
   - the evaluation report lists every gold item that matches more than one instance, not only the items
     reachable solely through `id_ambiguo = 1` chunks.

   Picking the right instance: the one that holds the fragment the reference names. Otherwise the first instance in
   file order. The misparses are all later ones.
4. **Chunk-level exclusions:**
   - `scripts/rag/corpus_exclusions.yaml` gets a `chunks:` section with the 6 misparsed chunk ids (§2), each with
     its reason, and with the chunk ids of the S2/S2c/S3/S4 sub-units of the same misparsed articles.
   - `ragpipe.exclusions.Exclusions.row_mask` handles it.
   - Retrieval drops them; no re-embedding is needed.
   - Check the two "to check" rows of §2 against the source before adding them.

**Reruns:**

| Step | Command (see the phase notes) | Cost |
|---|---|---|
| 5. Retrieval with the new exclusions | `rag.py retrieve`, both embeddings (≈ 30 s each). Rankings lose only the excluded chunks. | $0 |
| 6. Evaluation | `rag.py evaluate` main eval `either_containment_merge_skip`, both embeddings. Then compare `metrics.csv` and `per_item.csv.gz` with the current ones; expected: only the affected items' rows. Check the legal-provision score of the answers of Q006/220/264 (§3). | $0 |
| 7. Generator contexts | `rag.py context` (≈ 70 s). Expected: only the oracle 4k/16k contexts of Q006, Q220, Q264, Q438 change; verify that every retrieved context is byte-identical. | $0 |
| 8. Oracle answers | the 4 generators × oracle 4k for those 4 questions = 16 calls (the rest come from the LLM cache). Check whether pilot runs with oracle 16k include them. | ≈ $0.07 |
| 9. Judge | rescore the 16 answers (`nuggets.py score`), oracle context support 4k/16k for the 4 questions (`ctxsupport`, 8 calls). Then `scoretable`, `analyze`. | ≈ $0.15 |
| 10. Dashboards | `build_dashboard_data.py`, `build_trace_data.py`, `build_explorer_data.py` | $0 |
| 11. Hugging Face | repo B update (`build_release.py --repos b --keep-raw`, `push_release.py`). Repo A does not change: no corpus file changes. | $0 |

**Total:** ≈ $0.25 of the $150 OpenRouter budget. Pass `--budget` on every LLM run (CLAUDE.md) and record the
costs in the ledgers.

**Expected change in the headline numbers:**
- retrieved-context runs: none;
- oracle runs: 4 of 715 questions.

Report the before/after values of `runs.csv` and the retrieval `metrics.csv` in the results note of this fix.

## 5. Fix B — corpus revision (pending; do not lose)

The parser output itself is wrong for at least the 6 documents of §2. Chunk exclusions (A.4) hide the bad chunks
from retrieval, but:
- the LexML files and `segmented/` still hold them;
- their text is missing from the article it belongs to, where it was a heading or a citation note;
- the benchmark on Hugging Face (repo A) ships them.

**To do in the next corpus revision:**
1. Repair the parse of the 6 documents (and the 2 "to check" ones if confirmed). The fix belongs in the sibling
   parser `../lexml-parser-projeto-lei/` (statutory) or in a `.docx` repair under `scripts/lexml/`, as for the
   earlier repairs (`20261007_180833_corpus_fixes_and_full_rebuild_plan.md`). Then re-parse.
2. Review the 21 article-level duplicate ids (§2) against the sources: Lei 12.715 arts. 69–78, Decreto-Lei 58/1937
   arts. 1º–4º, MP 2.228-1 annex art. 33, etc. Repeated source text is fine; parser duplication is not.
3. Add both checks of §2 to the article-coverage audit in `scripts/lexml/`:
   - article numbers out of sequence;
   - duplicated `(file, article id)` instances.

   The next rebuild then reports them.
4. Re-segment (the amended XSL in `scripts/`). Chunk ids within the repaired documents are renumbered.
5. Re-embed only the chunks whose text changed (both embeddings; cents). That includes the S3/S4 grouping chunks
   that contain them.
6. Rerun retrieval, evaluation and contexts. Answers whose prompt text is unchanged come from the LLM cache at no
   cost; regenerate and rescore only those that changed.
7. Remove the chunk-level exclusions of A.4 that the repair makes unnecessary.
8. New release of **repo A** (the benchmark: LexML, chunks) and repo B.

Trigger: the next planned corpus revision, or before the public release (moving the HF repos to `unicamp-dl`),
whichever comes first.
