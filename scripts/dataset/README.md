# Dataset build (BR-TaxQA-R v2.0)

Builds `dataset/{questions,references,documents}.jsonl` and `dataset/build_report.json` from the
v1.1 questions, the fetcher's canonical document list and this repository's `original/` and
`lexml/`. Design and findings: `docs/20260927_180401_dataset_v2_format_and_reference_fixes.md`.

```bash
python3 scripts/dataset/build_v2_dataset.py            # defaults below; about 2 s
python3 scripts/dataset/build_v2_dataset.py --help
```

| Option | Default |
|---|---|
| `--questions` | `../questions_QA_2024_v1.1_manual_fix.json` (same bytes as HF `questions_QA_2024_v1.1.json`) |
| `--canonical` | `../br-taxqa-document-fetcher/output_canonical/canonical_referred_documents.json` |
| `--chunks` | `segmented/chunks_all.csv.gz` (only used to report documents without chunks) |
| `--out` | `dataset/` |

Needs `lxml`. The build fails if a v1.1 reference file name resolves to no document and has no entry
in `reference_overrides.json`, so a new or renamed reference cannot be lost silently.

**Canonical list.** Resolution reads the fetcher's corrected list
(`../br-taxqa-document-fetcher/output_canonical/canonical_referred_documents.json`): a record with a
`correction` resolves automatically and passes its reason on as `resolution_note`; a record with
`status` (`nonexistent_act`, `not_found`) resolves to no document. `build_report.json` records the
list's SHA-256 and the fetcher's git commit. Fix a wrong act there
(`scripts/fix_canonical_records.py`), not with a `not_in_corpus` override here.

**Guards** (rebuild plan §3.3): the build fails on a dead override (file name not in the canonical
list, or dropped by every citing question) and on a contradiction (`not_in_corpus` while the
canonical record resolves); it warns on redundant overrides, on overrides for file names no question
cites (still needed: every canonical file name must resolve), and on documents no question cites.

**Unmatchable provisions.** `provisions[].matchable` is false when the fragment is in no LexML file;
`article_ids_unmatchable` lists cited articles the LexML lacks, with the reasons of
`scripts/lexml/unmatchable_articles.tsv`. `validation.article_ids_missing_unexplained` must stay
empty.

Provisions are parsed from the Q&A citation text by `citations.py` (design and cross-check in
`docs/20260927_213420_reference_provisions_from_citation_text.md`). The build also fails if a
citation in the text cannot be attributed to any v1.1 reference. Tests:

```bash
python3 -m pytest scripts/dataset/tests
```

## Data files

- `reference_overrides.json`: hand-verified resolutions, keyed by v1.1 `file` value.
  `document_id: null` + `status: not_in_corpus` marks an act that is absent from the corpus. The
  `drop` list removes single (question, file) references. The `citations` list replaces the
  provisions parsed from the text of one (question, origin, file) reference with a citation written
  by hand, for the few the text cannot express as written (treaty numbering, a typo, "a referida
  lei"). Every entry has a `reason`.
- `answer_overrides.json`: hand-verified fixes to v1.1 `answer_cleaned` (the gold answer), as
  `find`/`replace` edits per question, each pinned to the SHA-256 of the v1.1 text and to an exact
  occurrence count, so a changed input makes the build fail. Also the rule that removes the lines made
  only of punctuation left by the v1 cleaning (`build_report.json` → `answer_overrides`). Why:
  `docs/20261012_192640_nuggetization_phase1_pilot.md` §8.
- `nonstat_lexml_map.tsv`: `original/nao_articulados/<stem>.{docx,pdf}` → `lexml/nao_articulados/<urn file>.xml`.
  Those XMLs are named after their URN, so the stem is not in the name. Since the 2026-10-08 rebuild
  every non-statutory source is parsed with a **declared** URN (`scripts/lexml/nonstat_metadata.tsv`,
  `lexml_nonstat parse --metadata`), and this map is regenerated from the parse output with
  `python3 scripts/lexml/nonstat_lexml_map.py` (match `declared-urn`).