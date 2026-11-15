# Hugging Face update: the dashboard question-trace data added to the evaluation repo

**Generated:** 2026-11-15 14:17:28 (local time, from `date +%Y%m%d_%H%M%S`).
**Follows:**
- `20261110_194056_question_trace_dashboard_implementation.md`: the trace tab and its builder;
- `20261108_231904_hugging_face_update_gemini_embedding_2.md`: the previous update of repo B (same procedure).

**Why:** the trace tab (tab 8 of `docs/dashboard/index.html`) reads `docs/dashboard/data/trace/`. That folder is
gitignored (≈ 440 MB) and was not on the Hub, so on any other clone the tab showed "Trace data not found".

**Result:** repo B (`eduseiti/BR-TaxQA-R-RAG-eval`) `0a69ef9` → **`4ddc246`**
(`4ddc246f0ee7915ad0106c9660d6d90425126c92`), recorded in `release/hf_release.json`. Repo A is unchanged.

**Cost:** $0. No LLM or embedding calls were made.

## 1. What changed

| Path in B | Change |
|---|---|
| `raw/dashboard_trace.tar.gz` | **new**, 42.9 MB: 1,169 files = `index.js` + 715 `q/*.js` + 453 `doc/*.js`, stored under `docs/dashboard/data/trace/` |
| `docs/20261109_123355_results_dashboard.md`, `docs/20261110_194056_question_trace_dashboard_implementation.md` | new |
| `README.md` (card), `SHA256SUMS`, `release_manifest.json` | changed: the card describes the archive and how to restore it |

Nothing else changed (`push_release.py --dry-run`: 3 new, 3 changed, 0 only on the remote).

In git:
- `scripts/release/repo_b.yaml`: the archive is a `pack` entry, built deterministically like the cache archives.
- `scripts/release/cards/repo_b.md`: a paragraph on the archive.
- `docs/dashboard/index.html`: the "Trace data not found" message now gives the download command as well as the
  rebuild command.

## 2. Using it on another computer

From the root of a clone of the git repo (the dashboard pages and its other data are in git):

```bash
hf auth login            # the repo is gated: request access on its Hub page first
hf download eduseiti/BR-TaxQA-R-RAG-eval raw/dashboard_trace.tar.gz --repo-type dataset --local-dir .
tar -xzf raw/dashboard_trace.tar.gz                  # -> docs/dashboard/data/trace/
xdg-open docs/dashboard/index.html                   # works from file://, no server
```

The data must match the dashboard's other data (built from the same results). If the results change, rebuild
with `scripts/report/build_trace_data.py` and repack (`build_release.py --repos b --keep-raw` after removing
`raw/dashboard_trace.tar.gz` from the release tree, since `--keep-raw` keeps an existing archive).

## 3. Build and checks

```bash
.venv/bin/python scripts/report/build_trace_data.py                 # 234 s
.venv/bin/python scripts/release/build_release.py --repos b --keep-raw   # packs only the new archive
.venv/bin/python scripts/release/push_release.py --tree ../br-taxqa-r_hf_release/BR-TaxQA-R-RAG-eval \
    --repo-id eduseiti/BR-TaxQA-R-RAG-eval --dry-run                  # then without --dry-run
```

- **Builder checks:** the same values as in the implementation note §4. Chunk counts 20,461 / 68,656 / 72,061 /
  68,656 / 72,061; per-item ranks 59,120 and budget hits 295,600 all equal; context selections 7,865 equal;
  prompts 20,253 verified, with 476 skipped and 6 error rows not verifiable; label counts 29 / 29;
  `legal_basis` 625 / 29 / 23.
- **No local paths** in the trace files: a grep for `/work/`, `/root/`, `/home/` and `file:///` found nothing.
  The page loads them with relative `<script>` paths.
- **Round trip:** the archive was downloaded from the Hub at `4ddc246` and extracted into an empty folder.
  `diff -rq` against the local `docs/dashboard/data/trace/` found no differences.

## 4. Repo visibility (found during this update)

`release/hf_release.json` and the release plan §9 describe both repos as "staging (private)". On 2026-11-15 the
Hub reports both `eduseiti/BR-TaxQA-R` and `eduseiti/BR-TaxQA-R-RAG-eval` as **public and gated**. An anonymous
download returns 401 "restricted". `push_release.py` never changes visibility, so the change was made on the Hub
before this update. The new record in `hf_release.json` says "staging" without "(private)".
