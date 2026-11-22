#!/usr/bin/env python3
"""Stage the corpus & question explorer (and the results dashboard it links to) and upload it to a static
Hugging Face Space.

Run from the repo root after build_dashboard_data.py, build_trace_data.py and build_explorer_data.py. Reads
HF_RELEASE_TOKEN from .env. Creates the Space **private unless --public** and never changes the visibility of an
existing Space (that stays a manual step on the Hub).

    .venv/bin/python scripts/release/push_space.py --dry-run     # stage and compare with the remote
    .venv/bin/python scripts/release/push_space.py               # stage and upload

The staged tree (default ../br-taxqa-r_hf_release/space/) keeps the sibling layout the pages expect:

    README.md               scripts/release/cards/space.md (front matter: sdk static, app_file index.html)
    space_manifest.json     git commit, build time, file count and bytes
    index.html, data/...    the explorer (docs/explorer/), its ../dashboard/ paths rewritten to dashboard/
    dashboard/index.html, dashboard/data/...   (the explorer reads dashboard/data/trace/)

A static Space serves only the folder that holds app_file, so the explorer cannot sit in explorer/ and reach
../dashboard/ as it does in docs/: it goes to the root and its three ../dashboard/ references are rewritten.

Files on the Space that are not in the tree are deleted only with --delete-extra.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values
from huggingface_hub import CommitOperationDelete, HfApi
from huggingface_hub.errors import RepositoryNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from push_release import local_files, sha256  # noqa: E402

CARD = Path("scripts/release/cards/space.md")
# (source, target in the Space); each must exist
PARTS = [
    (Path("docs/explorer/index.html"), "index.html"),
    (Path("docs/explorer/data"), "data"),
    (Path("docs/dashboard/index.html"), "dashboard/index.html"),
    (Path("docs/dashboard/data"), "dashboard/data"),
]
REQUIRED = ["data/index.js", "dashboard/data/trace/index.js", "dashboard/data/core.js",
            "dashboard/data/questions.js", "dashboard/data/contexts.js", "dashboard/data/docs.js"]


def git_state() -> dict:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True,
                                check=True).stdout.strip())
    return {"commit": commit, "dirty": dirty}


def stage(out: Path) -> dict:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copy2(CARD, out / "README.md")
    for src, dst in PARTS:
        if not src.exists():
            sys.exit(f"missing {src}: run the dashboard / trace / explorer builders first")
        target = out / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, target)
        else:
            shutil.copy2(src, target)
    page = out / "index.html"
    html = page.read_text(encoding="utf-8")
    n = html.count("../dashboard/")
    if n != 3:
        sys.exit(f"expected 3 '../dashboard/' references in docs/explorer/index.html, found {n}: check the rewrite")
    page.write_text(html.replace("../dashboard/", "dashboard/"), encoding="utf-8")
    for rel in REQUIRED:
        if not (out / rel).is_file():
            sys.exit(f"staged tree lacks {rel}")
    files = local_files(out)
    manifest = {
        "name": "BR-TaxQA-R explorer",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git": git_state(),
        "n_files": len(files) + 1,
        "bytes": sum(f.stat().st_size for f in files.values()),
        "largest": max(((p, f.stat().st_size) for p, f in files.items()), key=lambda x: x[1]),
    }
    (out / "space_manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return manifest


def diff(api: HfApi, repo_id: str, tree: Path) -> tuple[list[str], list[str], list[str]]:
    local = local_files(tree)
    try:
        remote = {e.path: e for e in api.list_repo_tree(repo_id, repo_type="space", recursive=True, expand=True)
                  if getattr(e, "size", None) is not None}
    except RepositoryNotFoundError:
        remote = {}
    added = [p for p in local if p not in remote]
    changed = []
    for p, f in local.items():
        e = remote.get(p)
        if e is None or p == "space_manifest.json":
            continue
        lfs = getattr(e, "lfs", None)
        if (lfs and lfs.sha256 != sha256(f)) or (not lfs and e.size != f.stat().st_size):
            changed.append(p)
    extra = [p for p in remote if p not in local and p != ".gitattributes"]
    return added, changed, extra


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-id", default="eduseiti/BR-TaxQA-R-explorer")
    ap.add_argument("--out", default="../br-taxqa-r_hf_release/space", help="staging folder (recreated)")
    ap.add_argument("--public", action="store_true", help="create the Space public (default: private)")
    ap.add_argument("--dry-run", action="store_true", help="stage and compare, do not upload")
    ap.add_argument("--delete-extra", action="store_true", help="delete Space files that are not in the tree")
    ap.add_argument("--message", default=None, help="commit message")
    args = ap.parse_args()

    if not (Path("CLAUDE.md").is_file() and Path("scripts/release").is_dir()):
        sys.exit("run this from the repo root")
    token = dotenv_values(".env").get("HF_RELEASE_TOKEN") or os.environ.get("HF_RELEASE_TOKEN")
    if not token:
        sys.exit("HF_RELEASE_TOKEN is not set in .env")
    tree = Path(args.out).resolve()
    manifest = stage(tree)
    print(f"staged {tree}: {manifest['n_files']} files, {manifest['bytes'] / 1e6:.1f} MB"
          f" (largest {manifest['largest'][0]}, {manifest['largest'][1] / 1e6:.1f} MB)"
          f"; git {manifest['git']['commit'][:7]}{' dirty' if manifest['git']['dirty'] else ''}")

    api = HfApi(token=token)
    added, changed, extra = diff(api, args.repo_id, tree)
    print(f"{args.repo_id}: {len(added)} new, {len(changed)} changed, {len(extra)} only on the remote"
          f" ({'deleted' if args.delete_extra else 'kept'})")
    for label, items in (("new", added), ("changed", changed), ("remote only", extra)):
        for p in items[:10]:
            print(f"  {label:11s} {p}")
        if len(items) > 10:
            print(f"  … {len(items) - 10} more {label}")
    if args.dry_run:
        return

    url = api.create_repo(args.repo_id, repo_type="space", space_sdk="static", private=not args.public,
                          exist_ok=True)
    info = api.space_info(args.repo_id)
    print(f"space  {url} (private={info.private})")
    message = args.message or f"explorer (git {manifest['git']['commit'][:7]}" \
                              f"{', dirty' if manifest['git']['dirty'] else ''})"
    api.upload_folder(repo_id=args.repo_id, repo_type="space", folder_path=tree, commit_message=message)
    if extra and args.delete_extra:
        api.create_commit(args.repo_id, repo_type="space", operations=[CommitOperationDelete(p) for p in extra],
                          commit_message=f"{message}: remove files not in the tree")
    head = api.space_info(args.repo_id).sha
    added, changed, _ = diff(api, args.repo_id, tree)
    print(f"done   {args.repo_id} @ {head}"
          + (f"; NOT in sync: {len(added)} missing, {len(changed)} different" if added or changed else "; in sync"))
    sub = args.repo_id.replace("/", "-").replace("_", "-").replace(".", "-").lower()
    print(f"page   https://huggingface.co/spaces/{args.repo_id}\n"
          f"direct https://{sub}.static.hf.space/")


if __name__ == "__main__":
    main()
