# Release tooling

Scripts for the Hugging Face release (`docs/20261024_180016_hugging_face_release_plan.md`).

## `transfer_caches.py`: copy gitignored folders between computers

The LLM caches are gitignored, so they exist only on the computer that made them. The release needs
the nugget caches of the pilot and the previews (plan §7, C1), which are on the other computer:

- `nuggets/pilot/cache/`
- `nuggets/preview/cache/`
- `nuggets/preview_v2/cache/`
- `nuggets/preview_v3/cache/`

Run both steps **from the repo root**. Only the standard library is used, so any `python3` works.

```bash
# 1. on the computer that has the folders (after git pull, so the script is there)
python3 scripts/release/transfer_caches.py pack
#    -> ../br-taxqa-r_caches_<host>_<timestamp>.tar.gz and .tar.gz.sha256 (next to the repo, not in it)

# 2. copy both files to the target computer, then from its repo root
python3 scripts/release/transfer_caches.py unpack ../br-taxqa-r_caches_<host>_<timestamp>.tar.gz --dry-run
python3 scripts/release/transfer_caches.py unpack ../br-taxqa-r_caches_<host>_<timestamp>.tar.gz
```

- `pack` stops if one of the folders is missing. `--allow-missing` packs the others, and
  `--dirs a/b c/d` packs other repo-relative folders. `--out` sets the archive path.
- `unpack` checks the archive against its `.sha256`, and refuses paths outside the packed folders.
  It writes only missing files: an identical existing file is skipped, and a different one is
  reported and kept unless you pass `--overwrite`. At the end it checks every file against the
  SHA-256 list stored in the archive (`TRANSFER_MANIFEST.json`). Cache files are named by the hash
  of their request, so unpacking into a folder that already holds some of them is safe.

## `build_release.py` and `push_release.py`: the Hugging Face release

`repo_a.yaml` (benchmark → `BR-TaxQA-R`) and `repo_b.yaml` (evaluation data → `BR-TaxQA-R-RAG-eval`) list what
goes into each repo. `cards/repo_{a,b}.md` are the dataset cards (`README.md` on the Hub). Install the
dependencies once: `uv pip install --python .venv/bin/python -r scripts/release/requirements.txt`.

```bash
# 1. build the trees (no upload): copies, packs the LLM caches into raw/*.tar.gz, writes the viewer tables,
#    rewrites local paths in the copies, checks secrets / paths / row counts, writes SHA256SUMS
.venv/bin/python scripts/release/build_release.py --out <dir>             # both repos; --repos a|b for one
.venv/bin/python scripts/release/build_release.py --repos b --keep-raw --out <dir>   # reuse the packed caches

# 2. upload (reads HF_RELEASE_TOKEN from .env; creates the repo private unless --public)
.venv/bin/python scripts/release/push_release.py --tree <dir>/BR-TaxQA-R --repo-id eduseiti/BR-TaxQA-R --dry-run
.venv/bin/python scripts/release/push_release.py --tree <dir>/BR-TaxQA-R --repo-id eduseiti/BR-TaxQA-R
.venv/bin/python scripts/release/push_release.py --tree <dir>/BR-TaxQA-R-RAG-eval \
    --repo-id eduseiti/BR-TaxQA-R-RAG-eval --large                       # resumable; for the 1 GB vectors
```

Two points about `datasets` that shaped the layout:
- **It reads every config of a repo with one reader.** So repo A's configs are all JSON Lines, and
  `segmented/chunks_all.jsonl.gz` is a viewer copy of the CSV. Repo B's configs are all Parquet copies in
  `tables/`.
- **`all` is a reserved split name.** So repo B's splits are called `results`.

The dataset viewer does not run on private repos of non-PRO accounts. Check it after publication.
Published revisions are recorded in `release/hf_release.json`.
