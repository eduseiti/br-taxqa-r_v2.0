#!/usr/bin/env python3
"""Saxon driver for the statutory segmentation XSL (plan §3.3).

Adapted from ``run_segmentation_csv.py`` (verbatim copy in this folder). Changes:

- takes a **job list** (``xml_path``, ``out_csv``, ``params``) from the orchestrator instead of
  globbing a folder; parameters (``metadados``, ``sigla``) are set per file and cleared afterwards;
- writes one CSV per XML and returns per-file ``rows``, ``max_num_final`` (used as the offset of
  the loose-content rows, plan §2.4), duration and errors;
- compiles the stylesheet once per worker; ``--jobs N`` runs a process pool (one Saxon processor
  per worker, ``spawn`` start method);
- uses the saxonche >= 12 API (errors are raised as ``PySaxonApiError``; ``exception_occurred``
  no longer exists, which breaks the original driver on saxonche 13).

Standalone use (no parameters, so the XSL falls back to the document's own Epígrafe/Ementa)::

    .venv/bin/python scripts/segmentation/run_xsl_segmentation.py \\
        --xsl scripts/segmentation/GeraCSVporArtigoPorAgrupador.xsl \\
        --input 'lexml/articulados/*.xml' --output-dir /tmp/baseline --jobs 16
"""

from __future__ import annotations

import argparse
import csv
import glob
import io
import json
import multiprocessing as mp
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from saxonche import PySaxonProcessor

HERE = Path(__file__).resolve().parent
DEFAULT_XSL = HERE / "segmenta_estatutario.xsl"
LEXML_NS = "http://www.lexml.gov.br/1.0"
csv.field_size_limit(sys.maxsize)  # grouping rows (whole títulos) exceed the 128 KiB default


@dataclass
class Job:
    xml_path: Path
    out_csv: Path
    params: dict = field(default_factory=dict)


def is_lexml(path: Path) -> bool:
    """Cheap well-formedness + root check without a full parse of huge files."""
    from xml.etree import ElementTree as ET
    try:
        for _event, elem in ET.iterparse(path, events=("start",)):
            tag = elem.tag
            local = tag.split("}", 1)[-1] if "}" in tag else tag
            ns = tag[1:].split("}", 1)[0] if tag.startswith("{") else ""
            return local == "LexML" and (ns == LEXML_NS or ns == "")
    except ET.ParseError:
        return False
    return False


def csv_stats(csv_text: str) -> tuple[int, int]:
    """(data rows, max Num_Final) of an XSL CSV output."""
    rows, max_final = 0, 0
    reader = csv.reader(io.StringIO(csv_text))
    next(reader, None)
    for rec in reader:
        if not rec:
            continue
        rows += 1
        try:
            max_final = max(max_final, int(rec[3]))
        except (IndexError, ValueError):
            pass
    return rows, max_final


# --- worker state (one Saxon processor + compiled stylesheet per process) ---------------------
_proc = None
_exe = None


def _init_worker(xsl_path: str) -> None:
    global _proc, _exe
    _proc = PySaxonProcessor(license=False)
    xslt = _proc.new_xslt30_processor()
    _exe = xslt.compile_stylesheet(stylesheet_file=xsl_path)


def _run_one(job: Job, overwrite: bool) -> dict:
    rec = {"source": str(job.xml_path), "output": str(job.out_csv), "status": None, "rows": None,
           "max_num_final": None, "duration_ms": None, "error": None}
    t0 = time.time()
    try:
        if not is_lexml(job.xml_path):
            raise RuntimeError("not a well-formed LexML document")
        if job.out_csv.exists() and not overwrite:
            rec["status"] = "skipped"
            rec["rows"], rec["max_num_final"] = csv_stats(job.out_csv.read_text(encoding="utf-8"))
            return rec
        _exe.clear_parameters()
        for name, value in job.params.items():
            if value is not None:
                _exe.set_parameter(name, _proc.make_string_value(str(value)))
        result = _exe.transform_to_string(source_file=str(job.xml_path))
        if result is None:
            raise RuntimeError("Saxon returned no result")
        job.out_csv.parent.mkdir(parents=True, exist_ok=True)
        job.out_csv.write_text(result, encoding="utf-8")
        rec["rows"], rec["max_num_final"] = csv_stats(result)
        rec["status"] = "success"
    except Exception as exc:  # noqa: BLE001 - record any transform failure
        rec["status"] = "failure"
        rec["error"] = str(exc).strip()[:1000]
    finally:
        rec["duration_ms"] = round((time.time() - t0) * 1000, 1)
    return rec


def _run_chunk(args: tuple[list[Job], bool]) -> list[dict]:
    jobs, overwrite = args
    return [_run_one(j, overwrite) for j in jobs]


def run_jobs(jobs: list[Job], xsl: Path = DEFAULT_XSL, n_jobs: int = 1,
             overwrite: bool = True) -> list[dict]:
    """Run the XSL on every job; returns one record per job, in job order."""
    if n_jobs <= 1:
        _init_worker(str(xsl))
        return [_run_one(j, overwrite) for j in jobs]
    # Largest files first, so the pool is not left waiting for one big file at the end.
    order = sorted(range(len(jobs)), key=lambda i: -jobs[i].xml_path.stat().st_size)
    out: dict[int, dict] = {}
    ctx = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=n_jobs, mp_context=ctx, initializer=_init_worker,
                             initargs=(str(xsl),)) as pool:
        futs = {pool.submit(_run_chunk, ([jobs[i]], overwrite)): i for i in order}
        for fut, i in futs.items():
            out[i] = fut.result()[0]
    return [out[i] for i in range(len(jobs))]


def saxon_version() -> str:
    try:
        with PySaxonProcessor(license=False) as proc:
            return proc.version
    except Exception:  # noqa: BLE001
        return "unknown"


def write_reports(out_dir: Path, basename: str, summary: dict, records: list[dict]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{basename}.json").write_text(
        json.dumps({"summary": summary, "documents": records}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    lines = ["# XSL segmentation report", ""]
    for k in ("timestamp", "stylesheet", "engine", "total_documents", "success", "failure",
              "skipped", "total_rows", "wall_clock_s"):
        lines.append(f"- {k}: {summary.get(k)}")
    lines += ["", "| Source | Status | Rows | Time (ms) | Error |", "|---|---|---|---|---|"]
    for r in records:
        lines.append(f"| {Path(r['source']).name} | {r['status']} | {r['rows'] or ''} | "
                     f"{r['duration_ms']} | {r['error'] or ''} |")
    (out_dir / f"{basename}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_summary(records: list[dict], xsl: Path, elapsed: float) -> dict:
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "stylesheet": str(xsl),
        "engine": f"saxonche / {saxon_version()}",
        "total_documents": len(records),
        "success": sum(r["status"] == "success" for r in records),
        "failure": sum(r["status"] == "failure" for r in records),
        "skipped": sum(r["status"] == "skipped" for r in records),
        "total_rows": sum(r["rows"] or 0 for r in records),
        "wall_clock_s": round(elapsed, 2),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--xsl", type=Path, default=DEFAULT_XSL)
    p.add_argument("--input", nargs="+", required=True, help="XML files or glob patterns.")
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--jobs", type=int, default=1)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--report", default="xsl_report")
    p.add_argument("--param", action="append", default=[], metavar="NAME=VALUE",
                   help="Stylesheet parameter applied to every file.")
    args = p.parse_args(argv)

    paths = sorted({Path(f) for pat in args.input for f in glob.glob(pat)}
                   | {Path(x) for x in args.input if Path(x).is_file()})
    paths = [x for x in paths if x.suffix == ".xml"]
    params = dict(kv.split("=", 1) for kv in args.param)
    jobs = [Job(x, args.output_dir / (x.name[:-4] + ".csv"), params) for x in paths]
    t0 = time.time()
    records = run_jobs(jobs, args.xsl, args.jobs, args.overwrite)
    summary = build_summary(records, args.xsl, time.time() - t0)
    write_reports(args.output_dir, args.report, summary, records)
    for r in records:
        if r["status"] == "failure":
            print(f"  [FAIL] {Path(r['source']).name}  <- {r['error']}")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["failure"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
