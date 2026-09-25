"""Provenance helpers: git state, checksums, JSON writing (plan §4.4)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]      # scripts/embedding


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def git_state() -> dict:
    """HEAD commit and whether the embedding code had uncommitted changes."""
    def git(*a):
        return subprocess.run(["git", *a], cwd=HERE, capture_output=True, text=True).stdout.strip()
    try:
        dirty = git("status", "--porcelain", "--", str(HERE))
        return {"commit": git("rev-parse", "HEAD"), "dirty": bool(dirty),
                "dirty_files": dirty.splitlines()[:20]}
    except OSError:
        return {"commit": None}


def script_info() -> dict:
    from . import __version__
    return {"version": __version__, "git": git_state(), "argv": sys.argv}


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
