# Segmentation pipeline

Implements `docs/20260924_123747_segmentation_implementation_plan.md` (design) on top of
`docs/20260923_193852_segmentation_strategies_for_rag_experiments.md` (strategies S1/S2/S3). The
execution log with findings and deviations is `docs/20260924_175304_segmentation_execution_log.md`.

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
.venv/bin/python scripts/segmentation/segment_all.py --jobs 16 --overwrite
```

Outputs in `segmented/`:

| Path | Content |
|---|---|
| `annex_manifest.csv` | router decision per annex (category A/B/C, loose content, parent, metadata) |
| `statutory/<file>.csv` | XSL rows (+ split parts, + loose-content TXT/TAB rows) of main docs and A/B annexes |
| `non_statutory/<file>.csv` | TXT/TAB rows of `nao_articulados` and category-C annexes |
| `*/<file>.prov.jsonl` | provenance of Python-built rows (split parts, loose/non-statutory units) |
| `groupings_over_limit.csv` | S3 grouping rows above `--grouping-max-tokens` (8,192), left out of `chunks_all.csv` |
| `chunks_all.csv` | all rows + `arquivo, segmentador, categoria` + provenance (§2.7) + token counts |
| `run_info.json` | command line, flags, timings, per-file step results |
| `segmentation_report.{md,json}` | validation checks and statistics |

Useful flags: `--only '<glob>'` (regenerate some files; the merge and validation still cover all),
`--max-tokens 1024`, `--tokenizer max:tiktoken:cl100k_base,hf:Qwen/Qwen3-Embedding-4B`,
`--ementa-max-tokens 128`, `--grouping-max-tokens 8192`, `--keep-dropped-min-chars 300` (0 = drop every
assinatura/localDataFecho/preliminar, the plan's Q4 default).

Strategies are filters over `chunks_all.csv` (`strategies.py`): S1 = ART, DSP, TXT, TAB;
S2 = S1 + CPT, PAR, INC, ALI, ITE; S3 = S2 + groupings.

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
| `segment_all.py` | orchestrator + provenance merge |
| `validate_segments.py` | checks + report |
| `strategies.py` | S1/S2/S3 filters |
| `tests/` | pytest (`.venv/bin/python -m pytest scripts/segmentation/tests`) |
