# Segmentation pipeline

Implements `docs/20260924_123747_segmentation_implementation_plan.md` (design) on top of
`docs/20260923_193852_segmentation_strategies_for_rag_experiments.md` (strategies S1/S2/S3). The
execution log with findings and deviations is `docs/20260924_175304_segmentation_execution_log.md`.
The caput text variants (S4/S2c) follow `docs/20261005_184116_segmentation_s3_vs_lima_ementa_and_caput_strategy_plan.md`
(C1–C10), as adapted by `docs/20261007_180833_corpus_fixes_and_full_rebuild_plan.md` §4.

## Environment

Python 3.12, from the repository root:

```bash
python3 -m venv --system-site-packages --without-pip .venv      # ensurepip is not installed here
pip --python .venv/bin/python install -r scripts/segmentation/requirements.txt
```

The `hf:Qwen/Qwen3-Embedding-4B` tokenizer is loaded from its `tokenizer.json` with the
`tokenizers` library (downloaded once from the HF Hub, then used from the cache; no weights).

## Run

```bash
.venv/bin/python scripts/segmentation/segment_all.py --jobs 16 --overwrite --variants caput
# with the report-only comparison against a previous chunk set (rebuild plan §4, diff_vs_frozen):
.venv/bin/python scripts/segmentation/segment_all.py --jobs 16 --overwrite --allow-count-change \
    --frozen <old chunks_all.csv.gz> --frozen-lexml-rev <git rev of lexml/ for it>
```

Outputs in `segmented/`:

| Path | Content |
|---|---|
| `annex_manifest.csv` | router decision per annex (category A/B/C, loose content, parent, metadata) |
| `statutory/<file>.csv` | XSL rows (+ split parts, + loose-content TXT/TAB rows) of main docs and A/B annexes |
| `non_statutory/<file>.csv` | TXT/TAB rows of `nao_articulados` and category-C annexes |
| `*/<file>.prov.jsonl` | provenance of Python-built rows (split parts, loose/non-statutory units) |
| `groupings_over_limit.csv` | S3 grouping rows above `--grouping-max-tokens` (8,192), left out of `chunks_all.csv` |
| `chunks_all.csv.gz` | versioned, byte-deterministic gzip of `chunks_all.csv` (≈ 21 MB; the plain CSV, ≈ 130 MB, is above GitHub's 100 MB limit and is gitignored). `pd.read_csv` reads it directly |
| `chunks_all.csv` | all rows + `arquivo, segmentador, categoria` + provenance (§2.7) + token counts + `texto_sha256` (first 16 hex of the SHA-256 of `Texto`) |
| `run_info.json` | command line, flags, git commit (+ dirty flag), output SHA-256s, timings, per-file step results |
| `segmentation_report.{md,json}` | validation checks and statistics |

Useful flags: `--variants caput` (default; `''` = base rows only), `--only '<glob>'` (regenerate some files; the merge and validation still cover all),
`--max-tokens 1024`, `--tokenizer max:tiktoken:cl100k_base,hf:Qwen/Qwen3-Embedding-4B`,
`--ementa-max-tokens 128`, `--grouping-max-tokens 8192`, `--keep-dropped-min-chars 300` (0 = drop every
assinatura/localDataFecho/preliminar, the plan's Q4 default).

Embeddings should be keyed by `chunk_id` **and** `texto_sha256`: `chunk_id` is `<file stem>#<row>`,
so a re-run that adds or splits rows renumbers the rest of that file.

Strategies are filters over `chunks_all.csv` (`strategies.py`): S1 = ART, DSP, TXT, TAB;
S2 = S1 + CPT, PAR, INC, ALI, ITE; S3 = S2 + groupings; S2c / S4 = S2 / S3 with the `caput` variant.

### Text variants (caput plan D-A/D-B)

The XSL writes paragraph-family rows (PAR, and INC/ALI/ITE under a `Paragrafo` of an `Artigo`)
**without** the caput sentence (`caput_em_paragrafo=nao`, the default): these are the `base` rows
of S1–S3. Step 6 adds, right after each such row, its `caput` variant (`add_caput_variants.py`):
the same unit with the caput's opening sentence after the article label (the old X3b text; the XSL
gives the same with `caput_em_paragrafo=frase`, parity-tested). Columns:

| Column | `base` row | `caput` row |
|---|---|---|
| `variante` | `base` | `caput` |
| `chunk_id` | `<stem>#<seq>` | `<stem>#c<seq>` (same `<seq>` as its base twin) |
| `contexto_ids` | empty | id of the caput whose sentence was added |
| everything else | | copied from the base twin, except `Texto`, `texto_sha256` and token counts |

Per unit a strategy keeps the first listed variant that exists (`strategies.py`): S1–S3 `[base]`,
S2c/S4 `[caput, base]`. Split ART/DSP parts get no variant: their HEAD keeps the caput sentence
(caput plan Q2), so S1 is unchanged.

## Files

| File | Role |
|---|---|
| `GeraCSVporArtigoPorAgrupador.xsl`, `run_segmentation_csv.py` | verbatim originals (reference; the driver does not run on saxonche 13) |
| `segmenta_estatutario.xsl` | amended XSL (X1–X9) |
| `run_xsl_segmentation.py` | Saxon driver (job list, parameters, process pool) |
| `common.py` | metadata, Python mirror of the XSL text rules, calculaPos, tokenizer, splitting helpers, CSV I/O |
| `classify_annexes.py` | annex router |
| `segment_non_statutory.py` | lxml segmenter (document / loose modes) |
| `split_oversize.py` | structural split of ART/DSP rows above the cap |
| `add_caput_variants.py` | `caput` variant of paragraph-family rows (used by step 6) |
| `segment_all.py` | orchestrator + provenance merge |
| `validate_segments.py` | checks + report |
| `strategies.py` | S1/S2/S3/S2c/S4 filters (`Tipo`s + variants) |
| `tests/` | pytest (`.venv/bin/python -m pytest scripts/segmentation/tests`) |
