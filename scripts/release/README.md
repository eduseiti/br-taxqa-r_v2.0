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
