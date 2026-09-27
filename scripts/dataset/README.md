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

## Data files

- `reference_overrides.json`: hand-verified resolutions, keyed by v1.1 `file` value.
  `document_id: null` + `status: not_in_corpus` marks an act that is absent from the corpus. The
  `drop` list removes single (question, file) references. Every entry has a `reason`.
- `nonstat_lexml_map.tsv`: `original/nao_articulados/<stem>.docx` → `lexml/nao_articulados/<urn file>.xml`.
  Those XMLs are named after their URN, so the stem is not in the name. The map was made by
  re-parsing each `.docx` with `../lexml_parser_non_statutory` (`python -m lexml_nonstat parse`)
  and matching the URN. For 20 documents the current parser leaves the date as `0000`, while the
  committed XML has it. These were paired by authority/type/number and are marked `date-completed`.
