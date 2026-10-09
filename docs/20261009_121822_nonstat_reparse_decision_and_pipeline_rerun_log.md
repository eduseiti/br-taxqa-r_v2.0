# Non-Statutory Re-Parse: Decision, Execution Log and the Pipeline Re-Run (v2d IR result)

**Generated:** 2026-10-09 12:18:22 (local time, from `date +%Y%m%d_%H%M%S`)
**About:** the user asked for (a) a check of the activities recorded in
`docs/20261008_010441_corpus_rebuild_results.md` (**the results note**),
`docs/20261008_133726_corpus_rebuild_review_answers.md` (**the review note**) and
`docs/20261008_190226_reference_fixes_and_label_only_articles_investigation.md` (**the investigation
note**); (b) a decision on whether every non-statutory document must be re-parsed before re-segmenting
and re-embedding with `jua-4b-mixed`; and (c) an updated IR result after all the fixes, with every
command recorded for audit and reproduction.
**Status (2026-10-09 14:38):** all done. The note was written in two phases. §0–§7 date from the
morning, when the dataset build was blocked because fetcher commit `c7f4b8f` was only on the user's
other computer. §8–§10 date from the afternoon, after the user brought the commit over and decided to
go on without the other computer's referee cache. They record the execution and the **updated IR
result (eval `v2d_either_containment_skip`, §9)**. Committed on 2026-10-09 (§10.2):
`a80a5cf` (`.docx` fixes + `lexml/nao_articulados/`), `f13bcf3` (`segmented/`), `31293c5` (`dataset/`),
`ffbc7a3` (`strategies.yaml`, `embeddings/` manifests, `runs/`, this note), then the clean-tree dataset
rebuild (`build_report.json` only). Scratch outputs and tools are in
`$S` = `/tmp/claude-0/-work-unicamp-articles-RAG-evaluation-br-taxqa-r-v2-0/36df1725-581b-4996-9f90-469e4024fdaa/scratchpad`
(volatile; the scripts the reproduction needs are inlined or described in §3.4 and §8.2).

---

## 0. Summary

**Outcome (afternoon, §8–§9).** The non-statutory corpus was re-parsed and installed (fixed linker,
repaired SC 140/194). The whole corpus was re-segmented (104,574 rows) and the dataset rebuilt against
`c7f4b8f` (1,916 references, 13 missing fragments, all treaty articles). The corpus was re-embedded
in full with `jua-4b-mixed` (101,943 texts, $1.23), then retrieved and evaluated. **The IR picture of
2026-10-08 holds.** S2 is the best strategy at 4k (document 0.667, article 0.473, provision 0.362;
sub-article provision gold 0.425). Adding the caput sentence still hurts (S2c − S2 and S4 − S3 are
negative at every level and budget, p ≤ 0.002). Every headline number moved by at most +0.006. The
corpus fixes matter for individual questions (the treaty provisions 142-03 and 157-01 are now real
chunks, ranked 17 and 6) and for the gold, not for the averages.

**Morning analysis (§1–§7):**

- **Yes, all non-statutory documents must be re-parsed** (§2). There are three reasons:
  1. two sources changed: SC Cosit 140/2015 and 194/2015 (`fed0813`);
  2. the linker was rebuilt with the "art. N, caput" fix (`../lexml-linker` `51874d9`). The non-statutory
     parser renders a `Remissao` for every paragraph, so every file with a citation is affected;
  3. the statutory side already carries the fixed links (`a94c2bf`, 54 files with link-only changes),
     and the two halves of the corpus should come from the same linker.
- **The parser's linker cache must be replaced, not reused.** `lexml_nonstat` keys its linker cache by
  (context URN, paragraph text) only, by design (`src/lexml_nonstat/refs/cache.py`). All 16,315
  entries in `../lexml_parser_non_statutory/.cache/linker` predate the linker build (2026-10-08 17:29).
  Re-running the R3c command as recorded would silently re-serve the old links. The re-parse used a new
  `.cache/linker_51874d9`.
- **Re-parse result (scratch):** 245/245 files, exit 0, deterministic. A second run made 0 referee calls
  and wrote byte-identical files. Against the committed `lexml/nao_articulados/`: 83 identical,
  131 link-only, 8 link-span-only (text equal), **23 with a different structure** (§3).
- **The 23 structural differences are mostly unintended.** Only SC 140/2015 and SC 194/2015 should
  change in text. The other 21 come from **31 referee cache misses**. The local
  `/tmp/lexml_referee_cache` holds only answers from 2026-09-16. The 513 answers bought by the
  2026-10-08 R3c parse are not on this machine: that parse ran on the user's other computer, like the
  fetcher commit. The fresh answers moved borderline headings in 21 cited documents (§4).
- **Recommendation (superseded by the user's decision D1 in §8: proceed without that cache):** do not install this parse. Bring two things from the other computer, the fetcher
  commit `c7f4b8f` **and** that computer's `/tmp/lexml_referee_cache`. Merge the cache, re-run the
  parse (§6, step P1), and check that only SC 140, SC 194 and links change. Then run the rest of
  §6 unchanged.
- **Source repairs only partly worked.** The SC 140/2015 `.docx` still has the layout table with the
  "natalista…" body fragments (review note B1). SC 194/2015 still has one glued word ("ouexigir") (§3.3).
- **The statutory corpus is reproducible from committed code.** A jar rebuilt at
  `../lexml-parser-projeto-lei` `4c85e81` re-parses all 209 `.docx` into 386 XML files that are
  byte-identical to `lexml/articulados/` (§5.2). That folder needs no further work before the
  re-segmentation.

---

## 1. What the three notes leave pending, and the state found on 2026-10-09

| Item (source) | State on 2026-10-09 |
|---|---|
| Statutory re-parse after F1–F3, linker fix, RIR/1999 LIVROs, "III-A" (investigation note §2.4, §3) | **Done** in `a94c2bf` (`lexml/articulados/PARSER_VERSION`: 209 `.docx`, 386 XML, label-only articles 440 → 1). The parser fix was uncommitted at parse time; it is now `../lexml-parser-projeto-lei` `4c85e81` |
| Removed documents (`in_rfb_1911`, `lei_3071`, `lei_5869`, `decreto_7030`, `in_rfb_1505`) | `.docx` removed (`fed0813`, `6c6fdde`); no leftover XML in `lexml/articulados/` (checked: every XML stem has a `.docx`) |
| SC Cosit 140/2015 and 194/2015 `.docx` repairs (review note N7/B1/B2) | Committed in `fed0813`; **not re-parsed** (the committed non-statutory XML is from `bf79a58`, 2026-10-08 00:39) |
| Linker fix (review note §2.5, O6) | Committed (`../lexml-linker` `51874d9`); `/usr/local/bin/linkertool` → binary sha256 `6b4cf768…b28f` (built 2026-10-08 17:29); used by the statutory parse; **not yet used** for non-statutory documents |
| Reference fixes 144-05 + 10 pairs (investigation note §1) | In `scripts/dataset/reference_overrides.json` (`6c6fdde`); **`dataset/` not rebuilt** |
| Fetcher `c7f4b8f` (investigation note §1.4) | **Not on this machine**: `../br-taxqa-document-fetcher` is at `d4b7323`, `git fetch` fails (no SSH key), and no other clone exists. The user confirmed it was never pushed |
| Segmentation, embeddings, retrieval | Still from 2026-10-08 (R7/R8/R9). They predate the statutory re-parse and are therefore stale |
| `lexml_parser_non_statutory` code | Unchanged since `e8c3d1e`, the commit used by R3c |

---

## 2. Decision: re-parse every non-statutory document

The question was whether re-parsing only SC 140 and SC 194 (`lexml_nonstat parse` takes a file list)
would do. It would not:

1. **Linker.** The linker fix changes `Remissao` spans and targets in non-statutory text as much as in
   statutory text. In the scratch parse, links rose from 4,561 to 5,277, links resolved down to an
   article (`!art…`) from 1,700 to 3,808, and the defective `…;NNNN!cpt` links (article lost) fell from
   153 to 20. 139 of 245 files change only through links (§3). Chunk text does not use links. The
   released LexML does, and so would any later citation graph.
2. **Consistency.** `lexml/articulados` was parsed with the fixed linker on 2026-10-08. Leaving
   `lexml/nao_articulados` on the old one would mix two linker versions in one release.
3. **Cost.** A full parse takes about 5 minutes. With a warm referee cache it makes no API calls.

The linker cache detail matters for (1). The cache docstring says a linker upgrade "must show up as a
reviewed diff in a re-recorded fixture rather than as a new cache key". So reusing `.cache/linker`
gives the **old** answers with no error. A new cache directory, named after the linker commit, is
required.

---

## 3. Execution log (non-statutory re-parse, scratch)

Every command below ran on 2026-10-09 on this machine, in the order given.

### 3.1 Commands

```bash
# E0. State checks (read-only)
cd /work/unicamp/articles/RAG_evaluation/br-taxqa-r_v2.0
git log --oneline -8 -- lexml/nao_articulados original/nao_articulados scripts/lexml
for r in lexml_parser_non_statutory lexml-parser-projeto-lei lexml-linker br-taxqa-document-fetcher; do
  git -C ../$r log --oneline -6; git -C ../$r status --short; done
git -C ../br-taxqa-document-fetcher fetch          # fails: "Please make sure you have the correct access rights"
git -C ../br-taxqa-document-fetcher cat-file -t c7f4b8f   # fatal: Not a valid object name
sha256sum "$(readlink -f /usr/local/bin/linkertool)"      # 6b4cf7683bf0483f35e1712e54ce578d113a44b0115f46240fc9bc433303b28f
stat -c '%y' "$(readlink -f /usr/local/bin/linkertool)"   # 2026-10-08 17:29:31
find ../lexml_parser_non_statutory/.cache/linker -newer "$(readlink -f /usr/local/bin/linkertool)" | wc -l   # 0 (of 16,315)
comm -13 <(ls original/articulados/ | sed 's/\.docx$//' | sort) \
         <(ls lexml/articulados/*.xml | xargs -n1 basename | sed -E 's/(\.anexo[0-9]+)?\.xml$//' | sort -u)   # empty

# E1. Back up the referee cache (it lives in /tmp)
S=/tmp/claude-0/-work-unicamp-articles-RAG-evaluation-br-taxqa-r-v2-0/36df1725-581b-4996-9f90-469e4024fdaa/scratchpad
mkdir -p $S/nonstat_out $S/backup
cp -a /tmp/lexml_referee_cache $S/backup/lexml_referee_cache_20261009      # 630 entries

# E2. Full non-statutory parse: R3c's command with a NEW linker cache and a scratch output folder
cd ../lexml_parser_non_statutory && set -a && . ./.env && set +a && \
LC_ALL=C.UTF-8 PYTHONPATH=src python3 -m lexml_nonstat parse --emitter=generico-aninhado \
    --generation=proposed --referee=api --referee-cache=/tmp/lexml_referee_cache \
    --linker=/usr/local/bin/linkertool --linker-cache=.cache/linker_51874d9 \
    --metadata ../br-taxqa-r_v2.0/scripts/lexml/nonstat_metadata.tsv \
    -o $S/nonstat_out \
    ../br-taxqa-r_v2.0/original/nao_articulados/*.docx ../br-taxqa-r_v2.0/lexml/nao_articulados/_text/*.txt \
    > $S/nonstat_parse.log 2>&1
# exit 0; 245 XML files; referee cache 630 -> 661 entries (31 API calls, model gpt-5.6-luna)

# E3. Determinism: same command again, into $S/nonstat_out2
#     -> exit 0; referee cache 661 -> 661 (no calls); `diff -rq $S/nonstat_out $S/nonstat_out2`: identical

# E4. Classify the differences against the committed folder (scripts in $S/tools/, listed in §3.4)
.venv/bin/python $S/tools/diff_lexml.py  lexml/nao_articulados $S/nonstat_out    # identical / link-only / other
.venv/bin/python $S/tools/diff_lexml2.py lexml/nao_articulados $S/nonstat_out    # text equal? structure equal?
comm -13 <(ls $S/backup/lexml_referee_cache_20261009) <(ls /tmp/lexml_referee_cache) > $S/new_referee_keys.txt
```

### 3.2 Result

| Class (vs committed `lexml/nao_articulados/`, 245 files) | Files |
|---|---:|
| byte-identical | 83 |
| differ only in `Remissao` elements (links stripped → identical XML) | 131 |
| text and structure equal, but a `Remissao` now spans more text (e.g. "Lei 13709/2018, art. 5º, II" becomes one link instead of "Lei 13709/2018" + plain ", art. 5º, II"): the 7 service pages and ADI STF 5.422 | 8 |
| text changed by the source repair, structure equal: SC 194/2015 | 1 |
| **structure changed** (headings / hierarchy): SC 140/2015 (source repair) + 21 others (§4) | 22 |
| | **245** |

(`diff_lexml2.py` prints 23 "text differs" rows: 22 structural plus SC 194. Its text comparison counts a
heading moved into a `Rotulo` as a text change.)

### 3.3 The two repaired sources

- **SC 194/2015 (B2).** The glued words "setembrode", "Decretonº" and "ouexigir" appear 5 times in the
  committed XML and once in the new one. The one left is "constituir **ouexigir** créditos tributários":
  the repaired `.docx` still has it.
- **SC 140/2015 (B1).** The repaired `.docx` has 107 paragraphs (129 before). It **still holds the
  one-table layout block** whose cells are body-text fragments ("natalista, a qual afirma que o
  nascituro…"). The new XML still has `pp1_tab1` with those fragments, so the broken `TAB` chunk of
  the review note stays. To fix it, unwrap the table in the `.docx` (copy the cell paragraphs into the
  body in reading order), then re-parse.

### 3.4 Scratch tools

- `$S/tools/diff_lexml.py OLD NEW`: byte-identical / identical after `etree.strip_tags(Remissao)` /
  other. For "other" it prints word counts and a word-level `difflib` change count.
- `$S/tools/diff_lexml2.py OLD NEW`: for each changed file, compares the whitespace-normalized
  concatenated text with links stripped, and the element skeleton (tag, `id`, `nome` of every
  non-inline element in document order).

---

## 4. Finding: the referee cache of the 2026-10-08 parse is not on this machine

- All 630 entries of `/tmp/lexml_referee_cache` (and of the E1 backup) date from **2026-09-16**. The
  results note says that R3c (2026-10-08 00:31) bought 513 new answers and that "the cache now holds
  554". None of those answers is here. Together with the missing fetcher commit, this shows that R1–R10
  ran on the user's other computer, apart from the later statutory re-parse.
- The cache key is `sha256(model, kind, excerpt, ctx[, next_ctx])`, and all entries, old and new, are
  for `gpt-5.6-luna` (the current `LEXML_REFEREE_MODEL`). The 31 misses are 19 `own_articulation` and
  12 `heading` questions ("DECRETA:", "TRIBUTAÇÃO NA FONTE", formulas such as "IRF = (BCIR - P).i -
  PD", quoted "Art. N" lines). Only 3 of them repeat an excerpt already in the local cache, with a
  different context. One of those 3 got a different verdict: "Art. 133. Fica isento…", `quoted` before
  and `own` now.
- Effect: **21 cited documents** get different borderline headings and nesting. These are 17 SCs/SCI,
  4 PGFN pareceres/notes and Súmula STJ 125. Together they are cited by 25 questions (079, 177, 180,
  229, 235, 246, 282, 307, 335, 416, 421, 460, 539, 540, 560, 583, 600, 601, 618–620, 646, 657); 384
  cites SC 140, which changes anyway. The text is the same up to heading placement, but chunk
  boundaries and the `heading > heading` path at the start of chunks move. This is noise, not a fix. If
  installed, it would mix with the effect the next IR run is meant to measure.
- The parse **is** deterministic once the cache is warm (E3). With the other computer's cache the
  committed decisions come back, and only the new questions from the SC 140/194 repairs need the API.

---

## 5. Blockers and checks

### 5.1 Blocked: dataset build

`scripts/dataset/build_v2_dataset.py` reads the canonical list
`../br-taxqa-document-fetcher/output_canonical/canonical_referred_documents.json` (`--canonical`,
line 280). The list maps each v1.1 reference file name to the cited act. The 27 corrections of R4
(`c7f4b8f`: `fix_canonical_records.py` + `canonical_corrections_20261008.json`) exist only on the
other computer. Building against `d4b7323` would undo them: 19 names unresolved, and 150-03 and 280-08
would point at the wrong documents (investigation note §1.3). Without a rebuild, `dataset/` still has
144-05 → `decreto_7030_20091214`, which is no longer in the corpus, and none of the 10 reference fixes.
So no IR result can be produced on the fixed gold yet.

### 5.2 Statutory reproducibility check (`4c85e81`)

`lexml/articulados/PARSER_VERSION` records the parse as "c587f6b + UNCOMMITTED working tree" with
`ArtigoSemCaputTest.scala` sha256 `360b7167…`. The committed `4c85e81` has that file at `0afda6e4…`
(the test changed after the parse), so the check rebuilt the jar at `4c85e81` and re-parsed:

```bash
cp -a ../lexml-parser-projeto-lei/target/lexml-parser-projeto-lei-1.15.0-onejar.jar $S/backup/onejar_4f1b97.jar   # the jar of a94c2bf
cd ../lexml-parser-projeto-lei && LC_ALL=C.UTF-8 mvn -q -Ponejar package -DskipTests   # HEAD 4c85e81, clean tree; 78 s
sha256sum target/lexml-parser-projeto-lei-1.15.0-onejar.jar   # a018af01…6c57 (jar bytes differ: build timestamps)
cd ../br-taxqa-r_v2.0 && python3 ../lexml-parser-projeto-lei/scripts/batch_parse.py --no-justificativa \
    --linker /usr/local/bin/linkertool original/articulados $S/stat_out > $S/stat_parse.log 2>&1
diff -rq lexml/articulados $S/stat_out | grep '\.xml differ'
```

Result: exit 0, `converted=209 skipped=0 failed=0`, 386 XML files (27 min 41 s). **All 386 are
byte-identical** to the committed `lexml/articulados/` (`xml differ: 0`; the only extra file in the
committed folder is `main_body_lexml.txt`). The committed statutory corpus is therefore reproduced by
`../lexml-parser-projeto-lei` `4c85e81`. The uncommitted tree recorded in `PARSER_VERSION` differed
from it only in the test file.

---

## 6. Remaining pipeline (to run once `c7f4b8f` and the referee cache are here)

Run from `/work/unicamp/articles/RAG_evaluation/br-taxqa-r_v2.0` unless noted. The order follows the
results note (segmentation before the dataset build, which checks `cited_documents_without_chunks`
against the chunks).

```bash
S=<scratch dir>

# P0. Bring the inputs from the other computer
#   (other computer)  git -C br-taxqa-document-fetcher push origin main          # c7f4b8f
#   (other computer)  tar czf referee_cache_20261008.tgz -C /tmp lexml_referee_cache
git -C ../br-taxqa-document-fetcher pull && git -C ../br-taxqa-document-fetcher log -1 --format=%H   # must contain c7f4b8f
mkdir -p $S/rc && tar xzf referee_cache_20261008.tgz -C $S/rc
cp -a $S/rc/lexml_referee_cache/. /tmp/lexml_referee_cache/      # other computer's answers win on equal keys
# Better (O7): keep the merged cache outside /tmp, e.g. ../lexml_parser_non_statutory/.cache/referee, and
# pass that path to --referee-cache below.

# P1. Non-statutory re-parse (= E2, output to a fresh folder)
cd ../lexml_parser_non_statutory && set -a && . ./.env && set +a && \
LC_ALL=C.UTF-8 PYTHONPATH=src python3 -m lexml_nonstat parse --emitter=generico-aninhado \
    --generation=proposed --referee=api --referee-cache=/tmp/lexml_referee_cache \
    --linker=/usr/local/bin/linkertool --linker-cache=.cache/linker_51874d9 \
    --metadata ../br-taxqa-r_v2.0/scripts/lexml/nonstat_metadata.tsv \
    -o ../br-taxqa-r_v2.0/lexml/nao_articulados_new \
    ../br-taxqa-r_v2.0/original/nao_articulados/*.docx ../br-taxqa-r_v2.0/lexml/nao_articulados/_text/*.txt
cd ../br-taxqa-r_v2.0
.venv/bin/python $S/tools/diff_lexml2.py lexml/nao_articulados lexml/nao_articulados_new
#   gate: structure changes only in SC 140/2015 (and SC 194 text); everything else link-only or identical
cp lexml/nao_articulados/PARSER_VERSION lexml/nao_articulados_new/ && cp -a lexml/nao_articulados/_text lexml/nao_articulados_new/
rm -r lexml/nao_articulados && mv lexml/nao_articulados_new lexml/nao_articulados
#   edit PARSER_VERSION: linker 51874d9 / sha256 6b4cf768…, --linker-cache=.cache/linker_51874d9, date, result
python3 scripts/lexml/nonstat_lexml_map.py                      # must leave nonstat_lexml_map.tsv unchanged (same URNs)
git add -A lexml/nao_articulados scripts/dataset/nonstat_lexml_map.tsv && git commit

# P2. Segmentation (frozen = the committed R7 chunk set; its LexML = 280121b)
git show HEAD:segmented/chunks_all.csv.gz > $S/chunks_all_r7.csv.gz
.venv/bin/python scripts/segmentation/segment_all.py --jobs 16 --overwrite --allow-count-change \
    --variants caput --frozen $S/chunks_all_r7.csv.gz --frozen-lexml-rev 280121b
#   gate: validation OK; diff_vs_frozen: 0 differences for documents whose LexML is unchanged since 280121b
git add segmented && git commit

# P3. Dataset
python3 scripts/dataset/build_v2_dataset.py --questions ../br-taxqa-document-fetcher/questions_QA_2024_v1.1.json
#   gates: build_report.json git.fetcher_commit = c7f4b8f…; references 1,917 -> 1,916 (144-05 dropped);
#   the 8 overridden references matchable; fragment_ids_missing 25 -> 13 (142-03 and 157-01 matchable after F1);
#   cited_documents_without_chunks = []; decreto_7030/in_rfb_1505 not in documents.jsonl
python3 -m pytest scripts/dataset/tests
git add dataset scripts/dataset && git commit

# P4. Embeddings (only new texts; resumes the paused endpoint, pauses it at the end)
.venv/bin/python scripts/embedding/embed.py corpus --model jua-4b-mixed --extend --dry-run
.venv/bin/python scripts/embedding/embed.py corpus --model jua-4b-mixed --extend --resume

# P5. Retrieval and evaluation (new eval id; the v2c evaluation stays readable)
R=scripts/rag/rag.py
.venv/bin/python $R check    --embedding jua-4b-mixed
.venv/bin/python $R retrieve --embedding jua-4b-mixed --force
.venv/bin/python $R evaluate --retrieval runs/retrieval/jua-4b-mixed/irpf \
    --eval-id v2d_either_containment_skip --comparisons S1:S2,S2:S3,S2:S2c,S3:S4,S1:S2c
git add embeddings runs && git commit
```

---

## 7. Other points found

| # | Point | Suggestion |
|---|---|---|
| X1 | `lexml/articulados/PARSER_VERSION` names an uncommitted tree | §5.2 confirmed byte-identical output: replace it with `4c85e81` |
| X2 | `../lexml-parser-projeto-lei/target/…-onejar.jar` is now the `4c85e81` build (sha256 `a018af01…`); the `a94c2bf` jar (`4f1b97af…`) is in `$S/backup/onejar_4f1b97.jar` | Record the new sha256 in `PARSER_VERSION` together with X1 |
| X3 | SC 140/2015 layout table and SC 194/2015 "ouexigir" (§3.3) | Fix the `.docx` before P1 if wanted; P1 then covers it |
| X4 | Referee cache volatility (results note O7): the cache in `/tmp` is now known to differ between computers | Keep one merged cache in a versioned or backed-up location; record its path in `PARSER_VERSION` |
| X5 | `.cache/linker` of the non-statutory parser is stale (pre-`51874d9`) | Delete it once P1 is installed, so it cannot be used by mistake |
| X6 | `segmented/chunks_all.csv` (uncompressed, gitignored) dates from 2026-09-25 | Stale; `segment_all.py` rewrites it in P2 |

---

## 8. Execution after the user's decisions (2026-10-09, afternoon)

Decisions taken by the user after §0–§7 were written:

- **D1.** The fetcher commit `c7f4b8f` was brought to this computer. The other computer's referee cache
  was **not**: the user asked whether it was really needed. The answer was no, at the cost of the 21
  referee-driven heading changes of §4, so the parse proceeds with the local cache.
- **D2.** The user fixed the SC Cosit 140/2015 and 194/2015 `.docx` again (X3). Both now have no table
  and no glued words (sha256 `65aa4fd9…89e5`, `6452628c…5403`; working tree, not committed).
- The referee is the OpenAI API (`LEXML_REFEREE_BASE_URL=https://api.openai.com/…`, model
  `gpt-5.6-luna`), with the key in `../lexml_parser_non_statutory/.env`. No new key was needed.

### 8.1 P0/P1: referee cache made persistent, final non-statutory parse, install

```bash
cd /work/unicamp/articles/RAG_evaluation/br-taxqa-r_v2.0
git -C ../br-taxqa-document-fetcher log --oneline -1          # c7f4b8f Correct 27 canonical records …
git -C ../br-taxqa-document-fetcher status --short            # " M br_legal_parser" (dirty submodule; recorded as fetcher_dirty)

# referee cache out of /tmp (X4); .cache is gitignored in that repo
mkdir -p ../lexml_parser_non_statutory/.cache/referee
cp -a /tmp/lexml_referee_cache/. ../lexml_parser_non_statutory/.cache/referee/      # 661 entries

# final parse into a fresh folder
cd ../lexml_parser_non_statutory && set -a && . ./.env && set +a && \
LC_ALL=C.UTF-8 PYTHONPATH=src python3 -m lexml_nonstat parse --emitter=generico-aninhado \
    --generation=proposed --referee=api --referee-cache=.cache/referee \
    --linker=/usr/local/bin/linkertool --linker-cache=.cache/linker_51874d9 \
    --metadata ../br-taxqa-r_v2.0/scripts/lexml/nonstat_metadata.tsv \
    -o ../br-taxqa-r_v2.0/lexml/nao_articulados_new \
    ../br-taxqa-r_v2.0/original/nao_articulados/*.docx ../br-taxqa-r_v2.0/lexml/nao_articulados/_text/*.txt \
    > ../br-taxqa-r_v2.0/lexml/nao_articulados_new.log 2>&1
# exit 0, 1 min 42 s, 245 XML, referee cache 661 -> 661 (0 API calls)
cd ../br-taxqa-r_v2.0
diff -rq $S/nonstat_out lexml/nao_articulados_new         # only SC 140/2015 and SC 194/2015 differ (the D2 fixes)
.venv/bin/python $S/tools/diff_lexml.py lexml/nao_articulados lexml/nao_articulados_new
#   identical 83, remissao_only 131, other 31 (= 8 link-span-only + SC 140 + SC 194 + the 21 of §4)
#   SC 140: 0 <table>; SC 194: 0 glued words

# install (keep _text/, write a new PARSER_VERSION)
mv lexml/nao_articulados/_text lexml/nao_articulados_new/_text
rm lexml/nao_articulados/*.xml lexml/nao_articulados/PARSER_VERSION && rmdir lexml/nao_articulados
mv lexml/nao_articulados_new lexml/nao_articulados
mv lexml/nao_articulados_new.log $S/nonstat_parse_final.log
#   lexml/nao_articulados/PARSER_VERSION rewritten by hand (parser e8c3d1e, command, linker 51874d9 +
#   .cache/linker_51874d9, referee cache .cache/referee with 661 answers, result)
python3 scripts/lexml/nonstat_lexml_map.py                  # "244 stems"; nonstat_lexml_map.tsv unchanged
```

`git status`: 162 non-statutory XML files modified (= 245 − 83 identical), plus `PARSER_VERSION`.

### 8.2 P2: segmentation

```bash
git show HEAD:segmented/chunks_all.csv.gz > $S/chunks_all_r7.csv.gz          # the R7 chunk set (280121b)
.venv/bin/python scripts/segmentation/segment_all.py --jobs 16 --overwrite --allow-count-change \
    --variants caput --frozen $S/chunks_all_r7.csv.gz --frozen-lexml-rev 280121b > $S/segment_all.log 2>&1
# exit 0, 91 s of pipeline (2 min 51 s wall with validation)
```

| | R7 (2026-10-08) | Now |
|---|---:|---:|
| Router A / B / C | 12 / 50 / 179 | 12 / 35 / 130 |
| XSL files / rows | 276 / 83,569 | 256 / 72,415 |
| ART/DSP rows split → parts | 655 → 1,746 | 606 → 1,626 |
| Loose rows | 697 | 388 (61 files) |
| Non-statutory files / rows | 424 / 3,486 | 375 / 3,450 |
| `chunks_all.csv` rows (base + caput) | 118,766 (88,600 + 30,166) | **104,574 (77,080 + 27,494)** |
| S1 / S2 / S3 / S2c / S4 rows | 26,364 / 83,496 / 88,600 / 83,496 / 88,600 | 21,497 / 73,118 / 77,080 / 73,118 / 77,080 |
| Grouping rows over 8,192 tokens (left out) | 243 | 193 |
| Unique texts | 115,582 | 101,943 |

Most of the drop comes from the five removed documents: Lei 3.071/1916 (Civil Code of 1916), Lei
5.869/1973 (CPC of 1973), IN RFB 1.911/2019 with 60 annexes, Decreto 7.030/2009 and IN RFB
1.505/2014. The rest comes from the statutory re-parse: the D2/D3 fixes, and loose chunks of the
treaty files absorbed into their articles.

**Validation:** all 14 checks `ok`. **`diff_vs_frozen` needs care.** It reports `rows_text_differs: 8555`
of 31,605 rows for the 364 files whose LexML is byte-identical to `280121b`. This is not a regression.
The check compares each new row's **caput variant** with the frozen text (`expected = cap_by_base…`,
`validate_segments.py:433`). That was right for R7, whose frozen set predated the caput plan, so its
paragraph rows carried the caput sentence. It is wrong now that the frozen set is R7, which has
caput-free base rows. A variant-matched comparison (`$S/tools/diff_chunks_same_variant.py`, key =
`arquivo, variante, Tipo, urn, Num_Inicio, Num_Final, parte`) gives:

```bash
.venv/bin/python $S/tools/diff_chunks_same_variant.py $S/chunks_all_r7.csv.gz 280121b
# files_unchanged_lexml 364, rows_compared 31605 (base 23050, caput 8555), rows_text_differs 0,
# rows_only_new 0, rows_only_frozen 0
```

The 8,555 are exactly the caput rows. Base and caput texts are unchanged wherever the LexML is unchanged.
(X7: make `diff_vs_frozen` compare variant by variant when the frozen set already has a `variante`
column.)

### 8.3 P3: dataset

```bash
mkdir -p $S/dataset_prev && cp -a dataset/. $S/dataset_prev/
python3 scripts/dataset/build_v2_dataset.py --questions ../br-taxqa-document-fetcher/questions_QA_2024_v1.1.json \
    > $S/build_dataset.log 2>&1                      # exit 0
python3 -m pytest -q scripts/dataset/tests           # 36 passed
```

- `questions 715  references 1916 {'auto_exact': 1815, 'auto_undated': 30, 'override': 71}  documents 453
  (cited 446)  dropped 10  articles found 1464+575 (annex)/2052  provisions {'found_in_main': 1654,
  'found_in_annex': 616, 'without_id': 36, 'missing': 13}`.
- `build_report.json → git`: `fetcher_commit c7f4b8f…`, `fetcher_dirty: true` (the submodule), `commit
  a94c2bf`, `dirty: true` (this uncommitted run).
- Reference diff against the previous `dataset/`: **removed 144-05**; provisions changed for **018-01,
  093-02, 093-06, 209-01, 460-03, 683-02, 708-01, 708-11** (the overrides, with `provisions_note`) and
  for **142-03 → `art34_cpt_ali4` and 157-01 → `art21_cpt_ali4`, now `matchable: true`** (the F1–F3
  statutory fix). Nothing else changed. In particular 150-03 and 280-08 keep their documents, so the
  stale-list artifacts of the investigation note are gone.
- `validation.fragment_ids_missing`: **13**, all treaty articles of O1 (25 before).
  `article_ids_missing_unexplained = []`, `documents_without_chunks = []`, `cited_documents_without_chunks = []`.
- `documents_not_cited` (7): the 5 service pages, `par_cosit_26_20000629`, `sc_cosit_153_20140611`
  (review note N2: they should get references, not be removed).

### 8.4 P4: embeddings (full, not `--extend`)

The `--extend` dry run failed: `FileNotFoundError: embeddings/jua-4b-mixed/corpus/texts.csv`. The
finalized corpus store (texts and vectors, gitignored) is also on the other computer. Only its
`manifest.json` is versioned. The query vectors are here (`embeddings/jua-4b-mixed/queries/irpf/`). The
corpus is therefore embedded in full:

```bash
.venv/bin/python scripts/embedding/embed.py corpus --model jua-4b-mixed --extend --dry-run      # FileNotFoundError (above)
.venv/bin/python scripts/embedding/embed.py corpus --model jua-4b-mixed --dry-run               # "already finalized; --overwrite …"
cp embeddings/jua-4b-mixed/corpus/manifest.json $S/backup/corpus_manifest_20261008.json
.venv/bin/python scripts/embedding/embed.py corpus --model jua-4b-mixed --overwrite --dry-run
#   101943 texts, 27,981,664 tokens (max 8104), 1593 requests of <= 64 inputs / 32768 tokens, concurrency 8
.venv/bin/python scripts/embedding/embed.py corpus --model jua-4b-mixed --overwrite --resume --no-progress \
    > $S/embed_corpus.log 2>&1
```

Result: exit 0 in 92 min 48 s. `session complete: 101943 texts, 27981664 tokens in 5425s (5157.7 tok/s),
requests=1612 retries=19`. The 19 retries were HTTP 503 at 13:33 and 14:17, all recovered. **91.2
replica-minutes, $1.23** (`embeddings/costs.csv`, run `20261009T130234-1437c3`). The endpoint was paused
at the end (`endpoint_meter.jsonl`: `paused`). The vectors are `[101,943 × 2,560]` float32, norms in
[0.99999994, 1.0000001], with no NaN:

```bash
.venv/bin/python -c "import numpy as np; v=np.load('embeddings/jua-4b-mixed/corpus/vectors.npy', mmap_mode='r'); \
  n=np.linalg.norm(v, axis=1); print(v.shape, v.dtype, n.min(), n.max(), np.isnan(v).any())"
```

The 715 query vectors (`embeddings/jua-4b-mixed/queries/irpf/`, 2026-09-25) were reused: the
questions did not change, and `rag.py check` verifies them.

### 8.5 P5: retrieval and evaluation

```bash
R=scripts/rag/rag.py
.venv/bin/python $R check --embedding jua-4b-mixed > $S/rag_check.log 2>&1
#   "Check: OK": 104,574 chunks, 101,943 unique texts = corpus vectors, 715 query vectors, 715 questions,
#   1,916 references, 0 not in the corpus, 453 documents, 0 without chunks
.venv/bin/python $R retrieve --embedding jua-4b-mixed --force > $S/rag_retrieve.log 2>&1
#   exit 0, but warnings "strategy S1: 21497 chunk rows, strategies.yaml expects 26364 (other chunk file?)" (all 5)
#   -> scripts/rag/strategies.yaml: expected_rows updated to 21,497 / 73,118 / 77,080 / 73,118 / 77,080 and its
#      header comment to the new chunk file (SHA-256 a6087b7f…326a); then again:
.venv/bin/python $R retrieve --embedding jua-4b-mixed --force > $S/rag_retrieve.log 2>&1    # exit 0, 0 warnings, 38 s
#   texts per strategy: S1 21,458; S2 72,960; S3 76,922; S2c 70,500; S4 74,462
.venv/bin/python $R evaluate --retrieval runs/retrieval/jua-4b-mixed/irpf \
    --eval-id v2d_either_containment_skip --comparisons S1:S2,S2:S3,S2:S2c,S3:S4,S1:S2c \
    > $S/rag_evaluate.log 2>&1                                                                  # exit 0, 45 s
```

Output: `runs/retrieval/jua-4b-mixed/irpf/eval/v2d_either_containment_skip/` (`report.md`, `metrics.csv`,
`comparisons.csv`, `reachability.csv`, `manifest.json`; `per_item/per_question/metrics_by_chapter`
are gitignored). The settings are the same as `v2c`: annex rule `either`, containment de-duplication,
overflow `skip`, Qwen3-token budgets, 10,000 bootstrap resamples, seed 13. The `v2c` evaluation folder
is untouched. Its rankings were replaced, as in R9, and can only be regenerated with the 2026-10-08
vectors on the other computer.

---

## 9. Updated IR result (`v2d`) vs 2026-10-08 (`v2c`)

**Gold.** 1,724 document items (1,725 before: 144-05 dropped), 1,958 article and 2,230 provision items.
Unreachable: 13 articles (the treaty articles, unchanged) and **48 provisions (57 before)**. The 8
re-mapped references and 142-03/157-01 became reachable. Provision oracle 0.969 (0.965 before).

### 9.1 Recall at 4k tokens, all resolved gold (v2c → v2d)

| Level | S1 | S2 | S3 | S2c | S4 |
|---|---|---|---|---|---|
| document | 0.604 → 0.605 | 0.665 → **0.667** | 0.652 → 0.655 | 0.631 → 0.636 | 0.627 → 0.632 |
| article | 0.379 → 0.383 | 0.473 → **0.473** | 0.464 → 0.465 | 0.428 → 0.431 | 0.426 → 0.428 |
| provision | 0.347 → 0.353 | 0.361 → **0.362** | 0.361 → **0.362** | 0.321 → 0.324 | 0.334 → 0.338 |
| provision, sub-article gold (366 q.) | 0.313 → 0.316 | 0.424 → **0.425** | 0.409 → 0.414 | 0.370 → 0.368 | 0.367 → 0.371 |
| provision, whole-article gold (429 → 430 q.) | 0.337 → **0.344** | 0.266 → 0.268 | 0.270 → 0.270 | 0.237 → 0.242 | 0.259 → 0.262 |
| document, non-statutory gold (195 q.) | 0.669 → **0.666** | 0.628 → 0.626 | 0.611 → 0.614 | 0.628 → 0.633 | 0.606 → 0.611 |

### 9.2 Recall by budget (v2d, all resolved gold)

| Level | Strategy | 1k | 2k | 4k | 8k | 16k |
|---|---|---:|---:|---:|---:|---:|
| document | S1 | 0.372 | 0.479 | 0.605 | 0.718 | 0.803 |
| | S2 | **0.489** | **0.575** | **0.667** | **0.764** | **0.832** |
| | S3 | 0.482 | 0.564 | 0.655 | 0.745 | 0.815 |
| | S2c | 0.445 | 0.538 | 0.636 | 0.731 | 0.808 |
| | S4 | 0.444 | 0.533 | 0.632 | 0.717 | 0.795 |
| article | S1 | 0.170 | 0.266 | 0.383 | 0.480 | 0.566 |
| | S2 | **0.307** | **0.388** | **0.473** | **0.569** | 0.650 |
| | S3 | 0.305 | 0.379 | 0.465 | 0.567 | **0.661** |
| | S2c | 0.273 | 0.347 | 0.431 | 0.531 | 0.619 |
| | S4 | 0.271 | 0.348 | 0.428 | 0.531 | 0.627 |
| provision | S1 | 0.157 | 0.239 | 0.353 | 0.456 | 0.533 |
| | S2 | 0.188 | **0.262** | **0.362** | 0.471 | 0.566 |
| | S3 | **0.194** | 0.261 | **0.362** | **0.484** | **0.586** |
| | S2c | 0.164 | 0.226 | 0.324 | 0.440 | 0.542 |
| | S4 | 0.171 | 0.231 | 0.338 | 0.452 | 0.560 |

Context precision (provision, 4k): S1 0.117, S2 0.145, S3 0.160, S2c 0.163, S4 0.176. S3 keeps its
advantage at large budgets (16k: 0.123 vs S2 0.078).

### 9.3 Paired comparisons (recall, budget view; difference [95 % CI], permutation p)

| Pair | Level | 1k | 4k | 16k |
|---|---|---|---|---|
| S2 − S1 | document | +0.117 [+0.092, +0.142] p<0.001 | +0.062 [+0.042, +0.082] p<0.001 | +0.029 [+0.015, +0.044] p<0.001 |
| S2 − S1 | article | +0.138 [+0.112, +0.165] p<0.001 | +0.090 [+0.067, +0.113] p<0.001 | +0.084 [+0.065, +0.104] p<0.001 |
| S2 − S1 | provision | +0.030 [+0.008, +0.053] p=0.007 | +0.009 [−0.016, +0.035] p=0.46 | +0.033 [+0.016, +0.051] p<0.001 |
| S3 − S2 | document | −0.007 [−0.014, −0.001] p=0.03 | −0.011 [−0.021, −0.003] p=0.01 | −0.018 [−0.026, −0.010] p<0.001 |
| S3 − S2 | article | −0.003 p=0.53 | −0.008 p=0.11 | +0.011 [−0.001, +0.024] p=0.07 |
| S3 − S2 | provision | +0.006 p=0.12 | −0.001 p=0.90 | +0.020 [+0.007, +0.033] p=0.003 |
| **S2c − S2** | document | −0.043 [−0.061, −0.026] p<0.001 | −0.031 [−0.045, −0.018] p<0.001 | −0.024 [−0.034, −0.015] p<0.001 |
| **S2c − S2** | article | −0.034 [−0.054, −0.015] p<0.001 | −0.041 [−0.058, −0.025] p<0.001 | −0.031 [−0.044, −0.019] p<0.001 |
| **S2c − S2** | provision | −0.023 [−0.038, −0.009] p<0.001 | −0.038 [−0.054, −0.023] p<0.001 | −0.024 [−0.035, −0.014] p<0.001 |
| **S4 − S3** | document | −0.038 [−0.056, −0.021] p<0.001 | −0.023 [−0.037, −0.009] p<0.001 | −0.020 [−0.029, −0.011] p<0.001 |
| **S4 − S3** | article | −0.033 [−0.053, −0.014] p=0.001 | −0.037 [−0.053, −0.021] p<0.001 | −0.034 [−0.048, −0.021] p<0.001 |
| **S4 − S3** | provision | −0.023 [−0.037, −0.009] p=0.002 | −0.024 [−0.038, −0.010] p<0.001 | −0.026 [−0.039, −0.014] p<0.001 |
| S2c − S1 | provision | +0.007 p=0.54 | −0.029 [−0.053, −0.005] p=0.02 | +0.009 p=0.30 |

(The p-values are rounded; the permutation test floor is 0.0001. All rows are in `comparisons.csv`.)

### 9.4 Reading

- **Conclusions unchanged.** Sub-article units help (S2 − S1: +9 article points and +11 sub-article
  provision points at 4k). The caput sentence hurts (S2c − S2 and S4 − S3: −2 to −4 points at every
  level and budget, all significant). Groupings are about neutral for recall and better for context
  precision at 8k/16k. The size and significance of every v2c difference is reproduced, to within 0.01.
- **Why the averages barely move.** The fixes touch few gold items: 10 reference pairs, 1 dropped
  reference, and the treaty documents of the N3 questions (142–160). The removed documents were
  distractors that were rarely retrieved. The corpus shrank by 12 % in chunks, and S1 gains the most
  (+0.006 provision, +0.007 whole-article), which suggests that some old distractors were long
  articles of the two removed codes. Four things changed at once: corpus, chunks, gold and vectors
  (a fresh full embedding). A per-question attribution would need the v2c per-item tables, which are
  on the other computer.
- **The N3 treaty items now have content** (`per_item.csv.gz`, `rank_full`, S1/S2/S3):
  142-03 `decreto_56435 art34_cpt_ali4` 17/34/36; 157-01 `decreto_5128 annex art21_cpt_ali4` 86/6/6;
  151-02 `decreto_57784 art15` 10/13/13; 151-01 `decreto_50656 art47` 134/271/190; 153-02 `decreto_67542
  art141` 259/507/418. Before the statutory fix their `ART` chunks held only "Artigo N", so the
  article chunk could not match the question at all.
- **Non-statutory document recall** is stable (S1 0.666, S2 0.626). S1 > S2 there is expected:
  non-statutory units are the same `TXT` chunks in every strategy, and S2's larger pool of statutory
  sub-article chunks competes for the same budget.

---

## 10. Full reproduction sequence (from the committed state `a94c2bf` + the user's two `.docx` fixes)

```bash
# 0. inputs
git -C ../br-taxqa-document-fetcher log -1 --format=%H        # c7f4b8faf8b8df84520e6e957d7a0890513f4a52
git -C ../lexml_parser_non_statutory log -1 --format=%H       # e8c3d1ee72ec6e37320bf27bbd540411d40bc405
git -C ../lexml-parser-projeto-lei log -1 --format=%H         # 4c85e81de4bffaa7cdacb4b405f0d04d66e87bd5
sha256sum "$(readlink -f /usr/local/bin/linkertool)"          # 6b4cf768…b28f (lexml-linker 51874d9)
# referee cache: ../lexml_parser_non_statutory/.cache/referee (661 answers); without it, ~31 new
# answers are bought and borderline headings may differ (§4)

# 1. statutory LexML (only to verify; byte-identical to lexml/articulados, §5.2; 28 min)
(cd ../lexml-parser-projeto-lei && LC_ALL=C.UTF-8 mvn -q -Ponejar package -DskipTests)
python3 ../lexml-parser-projeto-lei/scripts/batch_parse.py --no-justificativa \
    --linker /usr/local/bin/linkertool original/articulados <out>

# 2. non-statutory LexML (§8.1)
(cd ../lexml_parser_non_statutory && set -a && . ./.env && set +a && \
 LC_ALL=C.UTF-8 PYTHONPATH=src python3 -m lexml_nonstat parse --emitter=generico-aninhado \
    --generation=proposed --referee=api --referee-cache=.cache/referee \
    --linker=/usr/local/bin/linkertool --linker-cache=.cache/linker_51874d9 \
    --metadata ../br-taxqa-r_v2.0/scripts/lexml/nonstat_metadata.tsv \
    -o ../br-taxqa-r_v2.0/lexml/nao_articulados_new \
    ../br-taxqa-r_v2.0/original/nao_articulados/*.docx ../br-taxqa-r_v2.0/lexml/nao_articulados/_text/*.txt)
#    then swap folders keeping _text/ and PARSER_VERSION (§8.1)
python3 scripts/lexml/nonstat_lexml_map.py

# 3. segmentation (§8.2)
.venv/bin/python scripts/segmentation/segment_all.py --jobs 16 --overwrite --allow-count-change \
    --variants caput --frozen <R7 chunks_all.csv.gz> --frozen-lexml-rev 280121b

# 4. dataset (§8.3)
python3 scripts/dataset/build_v2_dataset.py --questions ../br-taxqa-document-fetcher/questions_QA_2024_v1.1.json
python3 -m pytest -q scripts/dataset/tests

# 5. embeddings (§8.4; ~93 min, ~$1.2)
.venv/bin/python scripts/embedding/embed.py corpus --model jua-4b-mixed --overwrite --resume --no-progress

# 6. retrieval and evaluation (§8.5)
.venv/bin/python scripts/rag/rag.py check    --embedding jua-4b-mixed
.venv/bin/python scripts/rag/rag.py retrieve --embedding jua-4b-mixed --force
.venv/bin/python scripts/rag/rag.py evaluate --retrieval runs/retrieval/jua-4b-mixed/irpf \
    --eval-id v2d_either_containment_skip --comparisons S1:S2,S2:S3,S2:S2c,S3:S4,S1:S2c
```

### 10.1 Checksums of this run

| File | SHA-256 |
|---|---|
| `segmented/chunks_all.csv.gz` | `a6087b7f19ff5b02cc0863523b6dd423f6feddf291fe9f11e7f08d45146c326a` |
| `original/nao_articulados/sc_cosit_140_20150605.docx` | `65aa4fd94549bb96bc4041c52e5e8858abc2948e78a1ea315bc3ba98ba3889e5` |
| `original/nao_articulados/sc_cosit_194_20150805.docx` | `6452628c187a0d6ece83569886d4ae5383ccae071f2f09e0a4cb6a9a89875403` |
| parser jar (`4c85e81` build) | `a018af018ffd88ccd96316418df78788a443201aa4217a6545fecac59f6c6c57` |

### 10.2 Still open

- ~~Commit~~ **done**: (1) `a80a5cf` the two `.docx` fixes + `lexml/nao_articulados`; (2) `f13bcf3`
  `segmented/`; (3) `31293c5` `dataset/`; (4) `ffbc7a3` `scripts/rag/strategies.yaml` + `embeddings/`
  manifests and costs + `runs/` + this note. Then, on the clean tree at `ffbc7a3`:
  `python3 scripts/dataset/build_v2_dataset.py --questions ../br-taxqa-document-fetcher/questions_QA_2024_v1.1.json`
  (exit 0, same summary line as §8.3). Only `build_report.json` changed (`commit ffbc7a3…`, `dirty: false`,
  timestamp); the three `.jsonl` files were byte-identical. Committed with this status update.
- ~~X1/X2~~ **done**: `lexml/articulados/PARSER_VERSION` now names `4c85e81` and jar sha256 `a018af01…6c57`
  (old jar hash kept for the record) and adds a `verification` line pointing at §5.2.
- ~~X5~~ **done**: `rm -rf ../lexml_parser_non_statutory/.cache/linker` (16,315 pre-`51874d9` entries, 20 MB;
  gitignored there). `.cache/linker_51874d9` and `.cache/referee` remain.
- ~~X7~~ **done**: `diff_vs_frozen` compares variant by variant (key + `variante`) when the frozen set has a
  `variante` column, and keeps the old caput-vs-frozen comparison for older sets; it reports `by_variant`.
  New `scripts/segmentation/tests/test_diff_vs_frozen.py` (3 tests). On the real data (R7 frozen set,
  `--frozen-lexml-rev 280121b`): 364 unchanged files, 31,605 rows compared, **0 differ** (was 8,555).
- Pre-existing test failure (not from X7; it fails on the committed tree too):
  `test_python_segmenters.py::test_loose_offset_keeps_intervals_disjoint` expects a loose tax table before
  LIVRO I in `decreto_9580_20181122.anexo1.xml` (RIR/2018). Since the statutory re-parse `a94c2bf` that
  table is no longer before LIVRO I (first `<table` at offset 368,028, after `<Livro` at 482; at `0ef6d67` it
  was at 519, before `<Livro` at 1,036), so the test's premise is stale. The other 47 segmentation tests pass.
- The fetcher's dirty submodule (`br_legal_parser`) makes `fetcher_dirty: true`.
- Vectors and rankings exist only on the computer that made them. Back up `embeddings/jua-4b-mixed/corpus/`
  (≈ 1 GB) or release it on the HF Hub, so a later `--extend` run can reuse it.
- Results note O1 (treaty texts), O5 (nonstat tests), O8 (other embedding models) and review note N2
  (Q029 and Q576 references) are unchanged.
