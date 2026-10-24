#!/usr/bin/env python3
"""Move gitignored folders (LLM caches) between computers in one checked archive.

The release plan (docs/20261024_180016_hugging_face_release_plan.md §7, C1) needs the nugget caches of the
pilot and the previews, which exist only on the computer that ran them. Run both commands from the repo root;
standard library only, so any python3 works (no .venv needed).

    # on the computer that has the folders
    python3 scripts/release/transfer_caches.py pack
    # copy ../br-taxqa-r_caches_<host>_<timestamp>.tar.gz and its .sha256 to the other computer, then
    python3 scripts/release/transfer_caches.py unpack ../br-taxqa-r_caches_<host>_<timestamp>.tar.gz

The archive holds the files under their repo-relative paths plus TRANSFER_MANIFEST.json (SHA-256 of every
file). ``unpack`` checks the archive hash, refuses paths outside the packed folders, writes only missing files
(an existing file with the same hash is skipped; a different one is a conflict, kept unless --overwrite) and
verifies every file against the manifest at the end. Cache files are named by the hash of their request, so
merging into a folder that already has some of them is safe.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import socket
import sys
import tarfile
import time
from datetime import datetime
from pathlib import Path, PurePosixPath

DEFAULT_DIRS = [            # the caches missing on the second computer (2026-10-24)
    "nuggets/pilot/cache",
    "nuggets/preview/cache",
    "nuggets/preview_v2/cache",
    "nuggets/preview_v3/cache",
]
MANIFEST = "TRANSFER_MANIFEST.json"


def repo_root() -> Path:
    root = Path.cwd()
    if not ((root / "CLAUDE.md").is_file() and (root / "scripts" / "release").is_dir()):
        sys.exit("run this from the repo root (the folder holding CLAUDE.md and scripts/)")
    return root


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def safe_rel(name: str, allowed: list[str]) -> PurePosixPath:
    """Repo-relative path of an archive member, or exit if it could escape the packed folders."""
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or not any(p.is_relative_to(d) for d in allowed):
        sys.exit(f"unsafe member in archive: {name!r}")
    return p


def pack(args) -> None:
    root = repo_root()
    dirs = [d.strip("/") for d in args.dirs]
    files: dict[str, list[Path]] = {}
    for d in dirs:
        p = root / d
        if not p.is_dir():
            if not args.allow_missing:
                sys.exit(f"missing folder: {d} (use --allow-missing to pack the others)")
            print(f"skip   {d}: not found")
            continue
        files[d] = sorted(f for f in p.rglob("*") if f.is_file())
        print(f"pack   {d}: {len(files[d])} files")
    if not any(files.values()):
        sys.exit("nothing to pack")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(args.out) if args.out else root.parent / f"br-taxqa-r_caches_{socket.gethostname()}_{stamp}.tar.gz"
    manifest = {
        "created": stamp,
        "host": socket.gethostname(),
        "dirs": {d: len(fs) for d, fs in files.items()},
        "files": {},
    }
    for fs in files.values():
        for f in fs:
            manifest["files"][f.relative_to(root).as_posix()] = file_sha256(f)

    with tarfile.open(out, "w:gz") as tar:
        data = json.dumps(manifest, indent=1, sort_keys=True).encode()
        info = tarfile.TarInfo(MANIFEST)
        info.size, info.mtime = len(data), int(time.time())
        tar.addfile(info, io.BytesIO(data))
        for fs in files.values():
            for f in fs:
                tar.add(f, arcname=f.relative_to(root).as_posix(), recursive=False)

    digest = file_sha256(out)
    Path(f"{out}.sha256").write_text(f"{digest}  {out.name}\n")
    size = out.stat().st_size / 2**20
    print(f"\nwrote  {out} ({size:.1f} MB, {len(manifest['files'])} files)\n       {out}.sha256")


def unpack(args) -> None:
    root = repo_root()
    archive = Path(args.archive)
    side = Path(f"{archive}.sha256")
    if side.is_file():
        expected = side.read_text().split()[0]
        if file_sha256(archive) != expected:
            sys.exit(f"archive hash does not match {side.name}: incomplete or corrupted copy")
        print(f"ok     archive hash matches {side.name}")
    else:
        print(f"warn   no {side.name} next to the archive; skipping the archive hash check")

    with tarfile.open(archive, "r:gz") as tar:
        member = tar.getmember(MANIFEST)
        manifest = json.loads(tar.extractfile(member).read())
        allowed = list(manifest["dirs"])
        print(f"from   {manifest['host']} ({manifest['created']}): "
              + ", ".join(f"{d} {n}" for d, n in manifest["dirs"].items()))
        written = skipped = 0
        conflicts: set[str] = set()
        for m in tar:
            if m.name == MANIFEST or m.isdir():
                continue
            if not m.isfile():
                sys.exit(f"unexpected non-file member: {m.name!r}")
            rel = safe_rel(m.name, allowed)
            data = tar.extractfile(m).read()
            if sha256(data) != manifest["files"].get(m.name):
                sys.exit(f"hash mismatch inside the archive: {m.name}")
            dest = root / rel
            if dest.exists():
                if file_sha256(dest) == manifest["files"][m.name]:
                    skipped += 1
                    continue
                if not args.overwrite:
                    conflicts.add(m.name)
                    print(f"diff   {rel} exists with other content; kept (use --overwrite to replace)")
                    continue
            if not args.dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            written += 1

    verb = "would write" if args.dry_run else "wrote"
    print(f"\n{verb} {written}, already present {skipped}, conflicts {len(conflicts)}")
    if args.dry_run:
        return
    bad = [f for f, h in manifest["files"].items()
           if f not in conflicts and (not (root / f).is_file() or file_sha256(root / f) != h)]
    if bad:
        sys.exit(f"verification failed for {len(bad)} files, e.g. {bad[:3]}")
    for d, n in manifest["dirs"].items():
        print(f"check  {d}: {sum(1 for f in (root / d).rglob('*') if f.is_file())} files now (archive: {n})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack", help="archive the folders (on the computer that has them)")
    p.add_argument("--dirs", nargs="+", default=DEFAULT_DIRS, help="repo-relative folders (default: the 4 caches)")
    p.add_argument("--out", help="archive path (default: ../br-taxqa-r_caches_<host>_<timestamp>.tar.gz)")
    p.add_argument("--allow-missing", action="store_true", help="pack the folders that exist, skip the others")
    p.set_defaults(func=pack)
    u = sub.add_parser("unpack", help="restore the folders (on the target computer)")
    u.add_argument("archive")
    u.add_argument("--dry-run", action="store_true", help="check and report, write nothing")
    u.add_argument("--overwrite", action="store_true", help="replace existing files whose content differs")
    u.set_defaults(func=unpack)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
