#!/usr/bin/env python3
"""Build the Hugging Face release trees (docs/20261024_180016_hugging_face_release_plan.md §6.1).

Run from the repo root. Copies the files listed in scripts/release/repo_{a,b}.yaml into <out>/<name>/ under the
paths of the git repo, packs the LLM caches as tar.gz, writes the flat viewer tables, the card, LICENSE,
release_manifest.json and SHA256SUMS, then checks the tree. Nothing is uploaded (push_release.py does that).

    .venv/bin/python scripts/release/build_release.py                 # both repos -> ../br-taxqa-r_hf_release/
    .venv/bin/python scripts/release/build_release.py --repos a --out /tmp/rel

Checks (the build fails on any): secret-like strings in every file, caches included; local absolute paths left
after the rewrite; paths in documents.jsonl that are missing from tree A; row counts listed under `counts:`.
Copies are rewritten, never the sources: the repo's absolute path becomes repo-relative and its parent folder
(the sibling repos) becomes `../`.
"""
from __future__ import annotations

import argparse
import fnmatch
import gzip
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO = Path.cwd()
# a key must not start inside a longer token: encrypted reasoning blobs (base64) contain "sk-", "hf_", "AIza" by chance
SECRET = re.compile(rb"(?<![A-Za-z0-9+/_-])(sk-or-v1-[A-Za-z0-9]{20,}|sk-proj-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{32,}|hf_[A-Za-z0-9]{30,}"
                    rb"|AIza[0-9A-Za-z_-]{30,}|Bearer [A-Za-z0-9._-]{20,})")
LOCAL_PATH = re.compile(rb"(/work/|/home/|/root/|/tmp/|/mnt/[a-z]/|[A-Z]:\\\\Users)")
SCRATCH = re.compile(rb"/tmp/[^\"\s`']*?/scratchpad/")     # Claude Code session folders
TEXT_SUFFIXES = {".json", ".jsonl", ".csv", ".tsv", ".md", ".txt", ".yaml", ".yml", ".log", ".xml", ""}
LICENSE_TEXT = """Creative Commons Attribution 4.0 International (CC BY 4.0)
https://creativecommons.org/licenses/by/4.0/legalcode

This dataset is released under CC BY 4.0, as BR-TaxQA-R v1.1.

The legal texts of the corpus (statutes, decrees, normative instructions and other official acts, and the
decisions and opinions of public authorities) are not protected by copyright in Brazil (Lei nº 9.610/1998,
art. 8º, IV). The questions and gold answers come from Receita Federal do Brasil's "Perguntas e Respostas IRPF
2024" (v1.0, 2024-05-03).
"""


def die(msg: str) -> None:
    sys.exit(f"build failed: {msg}")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def matches(rel: str, patterns: list[str]) -> bool:
    # fnmatch's `*` also crosses `/`, so "**/x" must match "x" at the top too
    return any(fnmatch.fnmatch(rel, p) or (p.startswith("**/") and fnmatch.fnmatch(rel, p[3:])) for p in patterns)


def copy_entries(spec: dict, tree: Path) -> int:
    n = 0
    for e in spec.get("copy", []):
        src = REPO / e["from"]
        if not src.is_dir():
            die(f"missing source folder {e['from']}")
        hits = 0
        for f in sorted(src.rglob("*")):
            rel = f.relative_to(src).as_posix()
            if not f.is_file() or not matches(rel, e["include"]) or matches(rel, e.get("exclude", [])):
                continue
            dst = tree / e["to"] / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
            hits += 1
        if not hits:
            die(f"no file matched {e}")
        print(f"copy   {e['from']} -> {e['to']}: {hits} files")
        n += hits
    return n


def pack_caches(spec: dict, tree: Path) -> None:
    for out, src in spec.get("pack", {}).items():
        d = REPO / src
        files = sorted(f for f in d.rglob("*") if f.is_file()) if d.is_dir() else []
        if not files:
            die(f"cache {src} missing or empty")
        dst = tree / out
        if dst.exists():                        # kept from the previous build (--keep-raw)
            print(f"keep   {out}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "wb") as raw:           # deterministic: sorted names, fixed mtime/owner, no gzip timestamp
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz, tarfile.open(fileobj=gz, mode="w") as tar:
                for f in files:
                    data = f.read_bytes()
                    if SECRET.search(data):
                        die(f"secret-like string in {f}")
                    info = tarfile.TarInfo(f.relative_to(REPO).as_posix())
                    info.size, info.mtime, info.mode = len(data), 0, 0o644
                    tar.addfile(info, io.BytesIO(data))
        print(f"pack   {src} -> {out}: {len(files)} files, {dst.stat().st_size / 2**20:.1f} MB")


def jl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def run_parts(run_id: str) -> dict:
    # jua-4b-mixed/irpf/<prompt>/<llm>/<context_id>
    emb, instr, prompt, llm, ctx = run_id.split("/")
    return {"run_id": run_id, "embedding": emb, "instruction": instr, "prompt": prompt, "llm": llm, "context_id": ctx}


def flat_answers(tree: Path) -> list[dict]:
    rows = []
    for f in sorted((REPO / "runs/answers/jua-4b-mixed").rglob("answers.jsonl")):
        run = list(jl(f))
        sample = "all" if len(run) == 715 else "stratified_30"
        for r in run:
            u = r.get("usage") or {}
            rows.append({**run_parts(r["run_id"]), "sample": sample, "question_number": r["question_number"],
                         "status": r["status"], "answer": r.get("answer"), "abstained": r.get("abstained"),
                         "claims_json": json.dumps(r.get("claims"), ensure_ascii=False),
                         "cited_chunk_ids": r.get("cited_chunk_ids") or [], "answer_chars": r.get("answer_chars"),
                         "n_texts": r.get("n_texts"), "rendered_tokens_qwen3": r.get("rendered_tokens_qwen3"),
                         "input_tokens": u.get("input"), "output_tokens": u.get("output"),
                         "usd_list": r.get("usd_list"), "model_served": r.get("model_served"),
                         "finish": r.get("finish"), "cache_key": r.get("cache_key")})
    return rows


def flat_labels(tree: Path) -> list[dict]:
    rows = []
    base = REPO / "nuggets/scoring/score/gold-v0-auto/gemini-3.8-flash"
    for f in sorted(base.rglob("labels.jsonl")):
        man = json.loads((f.parent / "manifest.json").read_text(encoding="utf-8"))
        parts = run_parts(man["run_id"])
        for r in jl(f):
            for lab in r["labels"]:
                rows.append({**parts, "nugget_set": "gold-v0-auto", "judge": "gemini-3.8-flash",
                             "question_number": r["question_number"], "source": r.get("source"),
                             "nugget_id": lab["nugget_id"], "label": lab["label"],
                             "justification": lab.get("justification")})
    return rows


def typed_csv(path: Path):
    """Read a CSV keeping ids as strings: a column becomes numeric only if every value parses and no integer
    has a leading zero ("001" stays a string)."""
    import pandas as pd
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    for c in df.columns:
        s = df[c].dropna()
        if len(s) and s.str.fullmatch(r"-?(0|[1-9]\d*)").all():
            df[c] = pd.to_numeric(df[c]).astype("Int64")
        elif len(s) and s.str.fullmatch(r"-?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?|-?inf|nan").all() \
                and not s.str.fullmatch(r"0\d+").any():
            df[c] = pd.to_numeric(df[c]).astype("float64")
        else:
            df[c] = df[c].astype("string")
    return df


def write_flat(spec: dict, tree: Path) -> None:
    """Viewer tables. `datasets` uses one reader per repo, so every config of a repo has one format: JSON Lines
    in repo A, Parquet in repo B. In .jsonl(.gz) output, missing strings are written as "" (as in the CSV),
    because the JSON reader cannot type a column whose first rows are all null."""
    import pandas as pd
    makers = {"answers": flat_answers, "labels": flat_labels}
    for out, kind in spec.get("flat", {}).items():
        df = typed_csv(REPO / kind["csv"]) if isinstance(kind, dict) else pd.DataFrame(makers[kind](tree))
        dst = tree / out
        dst.parent.mkdir(parents=True, exist_ok=True)
        if out.endswith(".parquet"):
            df.to_parquet(dst, index=False, compression="zstd")
        else:
            for c in df.columns:
                if str(df[c].dtype) in ("string", "object") and df[c].isna().any():
                    df[c] = df[c].fillna("")
            df.to_json(dst, orient="records", lines=True, force_ascii=False,
                       compression={"method": "gzip", "mtime": 0} if out.endswith(".gz") else None)
        print(f"flat   {out}: {len(df)} rows")


def rewrite_and_check(tree: Path) -> None:
    """Rewrite local absolute paths in the copies, then fail on any secret or local path left."""
    repo_abs, parent_abs = str(REPO).encode() + b"/", str(REPO.parent).encode() + b"/"
    problems = []
    for f in sorted(tree.rglob("*")):
        if not f.is_file() or f.suffix in {".npy", ".docx", ".pdf"} or f.name.endswith(".tar.gz"):
            continue            # binaries; the caches were checked while packing
        gz = f.suffix == ".gz"
        data = gzip.decompress(f.read_bytes()) if gz else f.read_bytes()
        if Path(f.stem if gz else f.name).suffix not in TEXT_SUFFIXES:
            continue
        new = SCRATCH.sub(b"<scratchpad>/", data.replace(repo_abs, b"").replace(str(REPO).encode(), b".")
                          .replace(parent_abs, b"../"))
        if new != data:
            f.write_bytes(gzip.compress(new, mtime=0) if gz else new)
            print(f"path   rewrote {f.relative_to(tree)}")
        rel = f.relative_to(tree)
        if m := SECRET.search(new):
            problems.append(f"secret-like string in {rel}: {m.group(0)[:8]}…")
        if m := LOCAL_PATH.search(new):
            problems.append(f"local path in {rel}: {new[m.start():m.start() + 60]!r}")
    if problems:
        die("\n  " + "\n  ".join(problems[:40]) + (f"\n  … {len(problems)} in total" if len(problems) > 40 else ""))


def count_rows(path: Path) -> int:
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq
        return pq.read_metadata(path).num_rows
    opener = gzip.open if path.suffix == ".gz" else open
    if ".csv" in path.name:
        import csv
        csv.field_size_limit(1 << 30)
        with opener(path, "rt", encoding="utf-8", newline="") as f:
            return sum(1 for _ in csv.reader(f)) - 1
    with opener(path, "rt", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def check_tree(spec: dict, tree: Path) -> None:
    for rel, n in spec.get("counts", {}).items():
        got = count_rows(tree / rel)
        if got != n:
            die(f"{rel}: {got} rows, expected {n}")
        print(f"count  {rel}: {got}")
    docs = tree / "dataset/documents.jsonl"
    if docs.exists():
        missing = [p for r in jl(docs) for p in [r["original_file"], r["lexml_file"], *r["lexml_annex_files"]]
                   if p and not (tree / p).is_file()]
        if missing:
            die(f"{len(missing)} paths of documents.jsonl missing from the tree, e.g. {missing[:3]}")
        print("check  every documents.jsonl path is in the tree")


def git_state() -> dict:
    def git(*a):
        return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


def finish(spec: dict, tree: Path) -> None:
    card = REPO / spec["card"]
    shutil.copy2(card, tree / "README.md")
    (tree / "LICENSE").write_text(LICENSE_TEXT, encoding="utf-8")
    files = sorted(f for f in tree.rglob("*") if f.is_file() and ".cache" not in f.parts
                   and f.name not in {"SHA256SUMS", "release_manifest.json"})
    sums = {f.relative_to(tree).as_posix(): file_sha256(f) for f in files}
    (tree / "SHA256SUMS").write_text("".join(f"{h}  {p}\n" for p, h in sums.items()), encoding="utf-8")
    manifest = {"name": spec["name"], "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "git": git_state(), "n_files": len(sums), "bytes": sum(f.stat().st_size for f in files),
                "spec": spec}
    (tree / "release_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n",
                                                encoding="utf-8")
    print(f"done   {tree}: {len(sums)} files, {manifest['bytes'] / 2**20:.0f} MB")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repos", nargs="+", choices=["a", "b"], default=["a", "b"])
    ap.add_argument("--out", default="../br-taxqa-r_hf_release", help="parent folder of the trees")
    ap.add_argument("--keep-raw", action="store_true",
                    help="reuse raw/*.tar.gz of the previous build (only when the caches have not changed)")
    args = ap.parse_args()
    if not ((REPO / "CLAUDE.md").is_file() and (REPO / "scripts/release").is_dir()):
        sys.exit("run this from the repo root")
    for key in args.repos:
        spec = yaml.safe_load((REPO / f"scripts/release/repo_{key}.yaml").read_text(encoding="utf-8"))
        tree = Path(args.out).resolve() / spec["name"]
        kept = tree.parent / f".{spec['name']}.raw"
        if args.keep_raw and (tree / "raw").is_dir():
            shutil.rmtree(kept, ignore_errors=True)
            (tree / "raw").rename(kept)
        if tree.exists():
            shutil.rmtree(tree)          # a build is always from scratch, except the archives kept by --keep-raw
        tree.mkdir(parents=True)
        if args.keep_raw and kept.is_dir():
            kept.rename(tree / "raw")
        print(f"\n== {spec['name']} -> {tree}")
        copy_entries(spec, tree)
        pack_caches(spec, tree)
        write_flat(spec, tree)
        rewrite_and_check(tree)
        check_tree(spec, tree)
        finish(spec, tree)


if __name__ == "__main__":
    main()
