# The corpus & question explorer on a Hugging Face Space

**Generated:** 2026-11-22 23:37:23 (local time, from `date +%Y%m%d_%H%M%S`).
**Space:** [`eduseiti/BR-TaxQA-R-explorer`](https://huggingface.co/spaces/eduseiti/BR-TaxQA-R-explorer), **private**
(staging), HF commit `be4bdf9`. Direct URL: `https://eduseiti-br-taxqa-r-explorer.static.hf.space/`.
**Tooling:** `scripts/release/push_space.py`, card `scripts/release/cards/space.md`; record in `release/hf_release.json`.

## 1. Why a static Space

The explorer (`docs/explorer/`, `20261115_145149_corpus_and_question_explorer.md`) is a static page. It loads its
data with `<script src>`, not `fetch`, and uses no CDN. The results dashboard loads `marked` from cdnjs. Both run
from any static host without a build step. Dataset repos serve files as downloads and don't run them as pages,
so the explorer can't be served from repo B. A Space with `sdk: static` can.

## 2. Layout

| Space path | Source | Size |
|---|---|---|
| `index.html`, `data/` | `docs/explorer/` (`../dashboard/` paths rewritten to `dashboard/`) | 17 MB, 717 files |
| `dashboard/index.html`, `dashboard/data/` | `docs/dashboard/` (incl. `data/trace/`, read by the explorer) | ≈ 498 MB, ≈ 1,240 files |
| `README.md` | `scripts/release/cards/space.md` (`sdk: static`, `app_file: index.html`) | |
| `space_manifest.json` | git commit, build time, files, bytes | |

In total: 1,957 files, 515 MB. The largest file is `dashboard/data/trace/doc/d097.js` (12.5 MB, stored with
LFS/Xet). The data is the same as `raw/dashboard_trace.tar.gz` and `raw/dashboard_explorer.tar.gz` in repo B `74fc95f`,
built from git `622a803` after A3.

**A static Space serves only the folder that holds `app_file`.** The first upload kept the `docs/` layout
(`explorer/index.html` as `app_file`, `dashboard/` as its sibling). The page then loaded, but every path outside
`explorer/` returned 404, including `../dashboard/data/trace/`. The second upload puts the explorer at the root.
`push_space.py` rewrites its three `../dashboard/` references, and it stops if that count changes.

## 3. Checks

- With a signed Space token (`/api/spaces/<id>/jwt`, `?__sign=`), every type of file returns 200 with a
  JavaScript content type: the explorer index and a question, the dashboard core, the trace index, a trace
  question, and the 12.5 MB `d097.js`.
- Screenshots in headless Chrome: `#/q/123` (official answer with the nugget spans, nugget strips) and `#/d` (the
  453 documents with chunk counts per strategy) render with their data.

## 4. Notes

- **Visibility.** The Space is private: only the owner sees it, when logged in. Repo B is public and gated, but a
  public Space would show the same answers, labels and contexts without the gate. Make it public together with
  the final release: change the visibility on the Hub or run `push_space.py --public` on a new Space.
- **Deep links.** On huggingface.co the page runs in an iframe, so the `#/q/<n>` and `#/d/<id>` addresses don't
  show in the address bar. Share the direct URL with the hash, e.g. `…static.hf.space/#/q/123`.
- **Updates.** The Space is a frozen copy. After rebuilding the dashboard, trace or explorer data, run
  `push_space.py --delete-extra` and add an entry to `release/hf_release.json`.
