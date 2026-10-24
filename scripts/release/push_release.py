#!/usr/bin/env python3
"""Upload a release tree built by build_release.py to a Hugging Face dataset repo (plan §6.2).

Run from the repo root. Reads HF_RELEASE_TOKEN from .env (the HF_TOKEN there is the inference-only embedding
token). Creates the repo if needed, **private unless --public**, and never changes the visibility of an
existing repo, moves it or deletes it: those stay manual steps (plan §5.3).

    .venv/bin/python scripts/release/push_release.py --tree ../br-taxqa-r_hf_release/BR-TaxQA-R \\
        --repo-id eduseiti/BR-TaxQA-R --dry-run
    .venv/bin/python scripts/release/push_release.py --tree ../br-taxqa-r_hf_release/BR-TaxQA-R \\
        --repo-id eduseiti/BR-TaxQA-R

--dry-run compares the tree with the remote (by SHA-256 for LFS/Xet files, by size otherwise) and lists what
would be added, changed or deleted. Files on the remote that are not in the tree are deleted only with
--delete-extra. --large uses upload_large_folder (resumable; for the 1 GB vectors), which cannot delete files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from dotenv import dotenv_values
from huggingface_hub import CommitOperationDelete, HfApi
from huggingface_hub.errors import RepositoryNotFoundError

SKIP = (".cache/",)          # upload_large_folder state inside the tree


def local_files(tree: Path) -> dict[str, Path]:
    return {f.relative_to(tree).as_posix(): f for f in sorted(tree.rglob("*"))
            if f.is_file() and not f.relative_to(tree).as_posix().startswith(SKIP)}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def diff(api: HfApi, repo_id: str, tree: Path) -> tuple[list[str], list[str], list[str]]:
    local = local_files(tree)
    try:
        remote = {e.path: e for e in api.list_repo_tree(repo_id, repo_type="dataset", recursive=True, expand=True)
                  if getattr(e, "size", None) is not None}
    except RepositoryNotFoundError:
        remote = {}
    added = [p for p in local if p not in remote]
    changed = []
    for p, f in local.items():
        e = remote.get(p)
        if e is None:
            continue
        lfs = getattr(e, "lfs", None)
        if (lfs and lfs.sha256 != sha256(f)) or (not lfs and e.size != f.stat().st_size):
            changed.append(p)
    extra = [p for p in remote if p not in local and p != ".gitattributes"]
    return added, changed, extra


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tree", required=True)
    ap.add_argument("--repo-id", required=True)
    ap.add_argument("--public", action="store_true", help="create the repo public (default: private)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--large", action="store_true", help="upload_large_folder (resumable, many/large files)")
    ap.add_argument("--delete-extra", action="store_true", help="delete remote files that are not in the tree")
    ap.add_argument("--create-pr", action="store_true", help="open the commit as a PR (not with --large)")
    ap.add_argument("--message", default=None, help="commit message")
    ap.add_argument("--tag", help="tag the resulting main revision")
    args = ap.parse_args()

    if not (Path("CLAUDE.md").is_file() and Path("scripts/release").is_dir()):
        sys.exit("run this from the repo root")
    token = dotenv_values(".env").get("HF_RELEASE_TOKEN") or os.environ.get("HF_RELEASE_TOKEN")
    if not token:
        sys.exit("HF_RELEASE_TOKEN is not set in .env")
    tree = Path(args.tree).resolve()
    manifest = json.loads((tree / "release_manifest.json").read_text(encoding="utf-8"))
    api = HfApi(token=token)

    added, changed, extra = diff(api, args.repo_id, tree)
    print(f"{args.repo_id}: {len(added)} new, {len(changed)} changed, {len(extra)} only on the remote"
          f" ({'deleted' if args.delete_extra else 'kept'})")
    for label, items in (("new", added), ("changed", changed), ("remote only", extra)):
        for p in items[:15]:
            print(f"  {label:11s} {p}")
        if len(items) > 15:
            print(f"  … {len(items) - 15} more {label}")
    if args.dry_run:
        return

    url = api.create_repo(args.repo_id, repo_type="dataset", private=not args.public, exist_ok=True)
    info = api.dataset_info(args.repo_id)
    print(f"repo   {url} (private={info.private})")
    message = args.message or f"{manifest['name']} release (git {manifest['git']['commit'][:7]}" \
                              f"{', dirty' if manifest['git']['dirty'] else ''})"
    if args.large:
        if args.create_pr or (extra and args.delete_extra):
            sys.exit("--large cannot open a PR or delete files; run without --large for that")
        api.upload_large_folder(repo_id=args.repo_id, repo_type="dataset", folder_path=tree,
                                ignore_patterns=[".cache/**"], print_report=False)
    elif added or changed or (extra and args.delete_extra):
        api.upload_folder(repo_id=args.repo_id, repo_type="dataset", folder_path=tree, commit_message=message,
                          ignore_patterns=[".cache/**"], create_pr=args.create_pr,
                          delete_patterns=None)
        if extra and args.delete_extra:
            api.create_commit(args.repo_id, repo_type="dataset", create_pr=args.create_pr,
                              operations=[CommitOperationDelete(p) for p in extra],
                              commit_message=f"{message}: remove files not in the release")
    else:
        print("nothing to upload")

    head = api.dataset_info(args.repo_id).sha
    if args.tag:
        api.create_tag(args.repo_id, repo_type="dataset", tag=args.tag, revision=head,
                       tag_message=f"{manifest['name']} {args.tag}")
    added, changed, _ = diff(api, args.repo_id, tree)
    print(f"done   {args.repo_id} @ {head}" + (f", tag {args.tag}" if args.tag else "")
          + (f"; NOT in sync: {len(added)} missing, {len(changed)} different" if added or changed else "; in sync"))


if __name__ == "__main__":
    main()
