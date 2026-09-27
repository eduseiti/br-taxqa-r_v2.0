"""Run layout, manifests, config hashing and deterministic file writing (plan §5, §8.3)."""

from __future__ import annotations

import datetime as _dt
import gzip
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from . import __version__

SCHEMA_VERSION = 1
REPO = Path(__file__).resolve().parents[3]


class RunError(RuntimeError):
    """A run directory conflicts with the requested configuration."""


# ------------------------------------------------------------------------------------------------
# Hashing
# ------------------------------------------------------------------------------------------------

def sha256_file(path: Path, bufsize: int = 1 << 22) -> str:
    """SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(bufsize):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(obj: Any) -> str:
    """SHA-256 of the canonical JSON form of ``obj`` (sorted keys, no whitespace)."""
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------
# Provenance
# ------------------------------------------------------------------------------------------------

def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def git_info(repo: Path = REPO) -> dict:
    """Commit and dirty flag of the repository (``None`` values outside a git checkout)."""
    def run(*args: str) -> str | None:
        try:
            return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                                  check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    commit = run("rev-parse", "HEAD")
    status = run("status", "--porcelain")
    dirty_files = [line[3:] for line in status.splitlines()] if status else []
    return {"commit": commit, "dirty": bool(dirty_files), "dirty_files": dirty_files}


def script_info() -> dict:
    return {"package": "ragpipe", "version": __version__, "git": git_info(), "argv": sys.argv}


def rel(path: Path) -> str:
    """Path relative to the repository when inside it (manifests stay machine independent)."""
    path = Path(path).resolve()
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


# ------------------------------------------------------------------------------------------------
# Writing
# ------------------------------------------------------------------------------------------------

def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False, default=str) + "\n",
                    encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_csv(df: pd.DataFrame, path: Path) -> None:
    """CSV (``.csv`` or byte-reproducible ``.csv.gz``: no file name, mtime 0)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    df.to_csv(buf, index=False, lineterminator="\n", float_format="%.6g")
    data = buf.getvalue().encode("utf-8")
    if path.suffix == ".gz":
        with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0,
                                                   compresslevel=6) as gz:
            gz.write(data)
    else:
        path.write_bytes(data)


def prepare_run_dir(path: Path, config_hash: str, force: bool) -> None:
    """Create ``path``; refuse to overwrite a run made with a different configuration.

    Rerunning with the same configuration hash overwrites silently (outputs are deterministic).
    """
    manifest = path / "manifest.json"
    if manifest.exists() and not force:
        old = read_json(manifest).get("config_hash")
        if old != config_hash:
            raise RunError(f"{rel(path)} holds a run with another configuration (config_hash {old[:12]}… "
                           f"≠ {config_hash[:12]}…). Use another id/directory or pass --force to replace it.")
    path.mkdir(parents=True, exist_ok=True)


def base_manifest(kind: str) -> dict:
    return {"schema_version": SCHEMA_VERSION, "kind": kind, "created_at": now_iso(), "script": script_info()}
