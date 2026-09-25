"""Resumable shard store and release-format writers (plan §4.2, §5.6).

Each completed request batch is written atomically as ``_shards/<first_id>_<n>.npz`` (``ids``,
``vectors``). ``_shards/state.json`` holds the run fingerprint (model, revision, server, template,
input checksum): a resume with a different fingerprint is refused, so vectors from two
configurations are never mixed.
"""

from __future__ import annotations

import gzip
import io
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from .manifest import read_json, write_json


class StoreError(Exception):
    pass


class ShardStore:
    def __init__(self, root: Path):
        self.root = root
        self.dir = root / "_shards"
        self.state_path = self.dir / "state.json"

    # ----------------------------------------------------------------------------------------
    def state(self) -> dict | None:
        return read_json(self.state_path) if self.state_path.exists() else None

    def open(self, fingerprint: dict, overwrite: bool = False) -> dict:
        """Start or resume; returns the state (``fingerprint``, ``sessions``)."""
        st = self.state()
        if st and st["fingerprint"] != fingerprint:
            if not overwrite:
                diff = sorted(k for k in set(st["fingerprint"]) | set(fingerprint)
                              if st["fingerprint"].get(k) != fingerprint.get(k))
                raise StoreError(f"{self.dir} holds shards of a different configuration (differs in "
                                 f"{diff}); use --overwrite to discard them")
            self.clear()
            st = None
        if st is None:
            self.dir.mkdir(parents=True, exist_ok=True)
            st = {"fingerprint": fingerprint, "sessions": []}
            write_json(self.state_path, st)
        return st

    def add_session(self, session: dict) -> None:
        st = self.state()
        st["sessions"].append(session)
        write_json(self.state_path, st)

    def shard_files(self) -> list[Path]:
        return sorted(self.dir.glob("*.npz"))

    def done_ids(self) -> set[str]:
        done: set[str] = set()
        for p in self.shard_files():
            with np.load(p, allow_pickle=False) as z:
                done.update(z["ids"].tolist())
        return done

    def write(self, ids: list[str], vectors: np.ndarray) -> Path:
        path = self.dir / f"{ids[0]}_{len(ids)}.npz"
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "wb") as f:
            np.savez(f, ids=np.asarray(ids), vectors=vectors.astype(np.float32))
        tmp.replace(path)
        return path

    def assemble(self, ids: list[str], dim: int, out: Path) -> None:
        """Write ``vectors.npy`` [len(ids), dim] in ``ids`` order; every id exactly once."""
        pos = {i: k for k, i in enumerate(ids)}
        seen = np.zeros(len(ids), dtype=bool)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(out.name + ".tmp.npy")
        arr = np.lib.format.open_memmap(tmp, mode="w+", dtype=np.float32, shape=(len(ids), dim))
        for p in self.shard_files():
            with np.load(p, allow_pickle=False) as z:
                for i, v in zip(z["ids"].tolist(), z["vectors"]):
                    k = pos.get(i)
                    if k is None:
                        raise StoreError(f"{p.name}: id {i} is not in the input")
                    if seen[k]:
                        raise StoreError(f"id {i} appears in more than one shard")
                    arr[k] = v
                    seen[k] = True
        arr.flush()
        del arr
        if not seen.all():
            tmp.unlink()
            missing = [ids[k] for k in np.flatnonzero(~seen)[:10]]
            raise StoreError(f"{int((~seen).sum())} ids have no vector yet (e.g. {missing}); run again to resume")
        tmp.replace(out)

    def clear(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n")


def write_csv_gz(df: pd.DataFrame, path: Path) -> None:
    """Byte-deterministic gzip (no name, mtime 0), as in the segmentation step."""
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0, compresslevel=9) as gz:
        gz.write(df.to_csv(index=False, lineterminator="\n").encode("utf-8"))
    path.write_bytes(buf.getvalue())
