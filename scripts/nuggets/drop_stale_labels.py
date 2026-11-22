#!/usr/bin/env python3
"""Drop judge labels whose answer or context changed since a backup (corpus fix B, 2026-11-22).

``nuggets.py score`` and ``ctxsupport`` keep the labels already in an output folder and only add missing
questions, without checking that the answer or context they judged is still the same. After answers or
contexts are regenerated, this script compares every answer run (``answers.jsonl``: answer text, status,
abstention) and every context set (``contexts.jsonl.gz``: rendered context) with the same file under
``--backup`` and removes, from every ``score/`` and ``ctxsupport/`` folder of ``--out`` (all nugget sets and
judges), the labels of the questions that changed. A rerun of ``score`` / ``ctxsupport`` then re-judges exactly
those questions. ``calls.jsonl`` is left alone (it is a log). Prints what it removed; ``--dry-run`` removes nothing.

Usage::

    python3 scripts/nuggets/drop_stale_labels.py --backup ../br-taxqa-r_fixB_backup_20261122 [--dry-run]
"""
import argparse
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def answers(p: Path) -> dict:
    out = {}
    for line in p.open(encoding="utf-8"):
        r = json.loads(line)
        out[r["question_number"]] = (r.get("status"), r.get("abstained"), r.get("answer"))
    return out


def contexts(p: Path) -> dict:
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return {r["question_number"]: r["context"] for r in map(json.loads, f)}


def changed(new: dict, old: dict) -> set:
    return {q for q in new if q not in old or new[q] != old[q]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--backup", type=Path, required=True, help="copy of the repository before the change")
    ap.add_argument("--out", type=Path, default=ROOT / "nuggets/scoring")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    stale: dict[tuple[str, str], set] = {}          # (kind, run id or context path) -> questions
    for p in sorted((ROOT / "runs/answers").glob("*/*/*/*/*/answers.jsonl")):
        rel = p.parent.relative_to(ROOT / "runs/answers")
        old = a.backup / "runs/answers" / rel / "answers.jsonl"
        if old.exists():
            stale[("score", str(rel))] = changed(answers(p), answers(old))
    for p in sorted((ROOT / "runs/contexts").glob("*/*/*/contexts.jsonl.gz")):
        rel = p.parent.relative_to(ROOT / "runs/contexts")
        old = a.backup / "runs/contexts" / rel / "contexts.jsonl.gz"
        if old.exists():
            stale[("ctxsupport", str(rel))] = changed(contexts(p), contexts(old))
    total = 0
    for kind in ("score", "ctxsupport"):
        for lab in sorted((a.out / kind).glob("*/*/**/labels.jsonl")):
            parts = lab.parent.relative_to(a.out / kind).parts      # <set>/<judge>/<run id or context path>
            key = (kind, "/".join(parts[2:]))
            qs = stale.get(key)
            if not qs:
                continue
            lines = lab.read_text(encoding="utf-8").splitlines()
            keep = [l for l in lines if json.loads(l)["question_number"] not in qs]
            n = len(lines) - len(keep)
            if n:
                total += n
                print(f"{kind:10s} {'/'.join(parts):90s} -{n}: {' '.join(sorted(q for q in qs))[:80]}")
                if not a.dry_run:
                    lab.write_text("".join(l + "\n" for l in keep), encoding="utf-8")
    print(f"{'would remove' if a.dry_run else 'removed'} {total} labels")


if __name__ == "__main__":
    main()
