#!/usr/bin/env python
"""Gold-answer nuggetization (plan: docs/20261011_224049_gold_answer_nuggetization_plan_v2.md).

Preview subset of the plan: sample, create (synchronous calls), validate, gold self-score and the
report with measured tokens and an extrapolated cost estimate.

    P=.venv/bin/python; N=scripts/nuggets/nuggets.py
    $P $N sample
    $P $N create --models gpt-6.1-sol,gemini-3.1-pro,qwen3.8-max
    $P $N validate
    $P $N selfscore --judge gemini-3.8-flash --sets gpt-6.1-sol,gemini-3.1-pro,qwen3.8-max
    $P $N report
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path[:0] = [str(HERE), str(HERE.parent)]

from dotenv import load_dotenv  # noqa: E402

from llm_client import LLM, load_registry  # noqa: E402
from nuggetizer import data, report, schema  # noqa: E402
from nuggetizer.validate import validate  # noqa: E402

PROMPTS = HERE / "prompts"


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def jl_write(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def jl_read(path: Path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def questions(out: Path, sample: str) -> list[dict]:
    qs = {q["question_number"]: q for q in jl_read(out / "input" / "questions.jsonl")}
    return [qs[n] for n in json.loads((out / "sample.json").read_text())[sample]]


def llm(name: str, out: Path, budget: float | None) -> LLM:
    reg = load_registry(HERE / "models.yaml")
    return LLM(name, reg[name], out / "cache", out / "costs.csv", budget_usd=budget)


def prompt(name: str) -> Path:
    return PROMPTS / f"{name}.pt.md"


def cmd_sample(a):
    out = Path(a.out)
    qs = data.load_questions(REPO / "dataset" / "questions.jsonl")
    jl_write(out / "input" / "questions.jsonl", qs)
    s = {"seed": 13, "method": "per answer-length decile (o200k, question + answer), "
                                 f"excluding prompt examples {sorted(data.PROMPT_EXAMPLES)}",
         "dataset_sha256": sha(REPO / "dataset" / "questions.jsonl"),
         "preview_10": data.stratified(qs, 1), "stratified_30": data.stratified(qs, 3)}
    assert set(s["preview_10"]) <= set(s["stratified_30"])
    (out / "sample.json").write_text(json.dumps(s, indent=1))
    print("preview_10:", " ".join(s["preview_10"]))


def cmd_create(a):
    out = Path(a.out)
    system = prompt(a.prompt).read_text()
    sch = schema.strict_schema(schema.LLMNuggetList)
    qs = questions(out, a.sample)

    def check(d):
        schema.LLMNuggetList.model_validate(d)
        if not d["nuggets"]:
            raise ValueError("empty nugget list")

    def run_model(name):
        m = llm(name, out, a.budget)

        def one(q):
            r = m.complete_json(system, data.user_prompt(q), sch, "nuggets", validate=check,
                                tag=f"create:{q['question_number']}")
            nugs = []
            for i, n in enumerate(r.data["nuggets"], 1):
                nugs.append({"nugget_id": f"Q{q['question_number']}_N{i:02d}", "question_number": q["question_number"],
                             "ordinal": i, **n})
            call = {"question_number": q["question_number"], "role": "create", "model": name,
                    "served": r.model_served, "qa_tokens": q["qa_tokens"], "usage": asdict(r.usage),
                    "usd_standard": r.cost_usd, "latency_s": r.latency_s, "attempts": r.attempts,
                    "from_cache": r.from_cache, "cache_key": r.cache_key}
            print(f"  {name} Q{q['question_number']}: {len(nugs)} nuggets, {r.usage.output} out "
                  f"({r.usage.reasoning} reasoning), ${r.cost_usd:.4f}{' [cache]' if r.from_cache else ''}",
                  flush=True)
            return nugs, call

        with ThreadPoolExecutor(a.workers) as ex:
            res = list(ex.map(one, qs))
        d = out / "create" / name
        jl_write(d / "nuggets.jsonl", [n for nugs, _ in res for n in nugs])
        jl_write(d / "calls.jsonl", [c for _, c in res])
        (d / "manifest.json").write_text(json.dumps(
            {"model": name, "registry": load_registry(HERE / "models.yaml")[name], "sample": a.sample,
             "prompt": str(prompt(a.prompt).relative_to(REPO)), "prompt_sha256": sha(prompt(a.prompt)),
             "schema_sha256": hashlib.sha256(json.dumps(sch, sort_keys=True).encode()).hexdigest()},
            indent=1, ensure_ascii=False, default=str))

    with ThreadPoolExecutor(len(a.models)) as ex:
        list(ex.map(run_model, a.models))


def cmd_validate(a):
    out = Path(a.out)
    qs = {q["question_number"]: q for q in questions(out, a.sample)}
    for d in sorted((out / "create").iterdir()):
        nugs = jl_read(d / "nuggets.jsonl")
        reports = []
        for qn, q in qs.items():
            reports.append(validate(q, [n for n in nugs if n["question_number"] == qn]))
        jl_write(d / "nuggets.jsonl", nugs)
        tot = {"errors": sum(len(r["errors"]) for r in reports), "warnings": sum(len(r["warnings"]) for r in reports)}
        (d / "validation.json").write_text(json.dumps({"totals": tot, "questions": reports}, indent=1,
                                                      ensure_ascii=False))
        print(f"{d.name}: {len(nugs)} nuggets, {tot['errors']} errors, {tot['warnings']} warnings")


def cmd_selfscore(a):
    out = Path(a.out)
    system = prompt(a.prompt).read_text()
    sch = schema.strict_schema(schema.AssignmentList)
    qs = questions(out, a.sample)
    m = llm(a.judge, out, a.budget)

    def run_set(set_name):
        nugs = jl_read(out / "create" / set_name / "nuggets.jsonl")

        def one(q):
            qn = [n for n in nugs if n["question_number"] == q["question_number"]]
            listing = "\n".join(f"{i}. {n['text']}" for i, n in enumerate(qn, 1))
            user = (f"Pergunta: {q['question_text']}\n\nResposta a avaliar:\n<<<\n{q['answer_cleaned'].strip()}\n>>>"
                    f"\n\nNuggets:\n{listing}")

            def check(d):
                schema.AssignmentList.model_validate(d)
                if sorted(x["nugget"] for x in d["assignments"]) != list(range(1, len(qn) + 1)):
                    raise ValueError("assignments do not cover the nuggets 1..n exactly once")

            r = m.complete_json(system, user, sch, "assignments", validate=check,
                                tag=f"selfscore:{set_name}:{q['question_number']}")
            by = {x["nugget"]: x for x in r.data["assignments"]}
            rows = [{"nugget_id": n["nugget_id"], "label": by[i]["label"], "justification": by[i]["justification"]}
                    for i, n in enumerate(qn, 1)]
            call = {"question_number": q["question_number"], "role": "judge", "model": a.judge, "set": set_name,
                    "served": r.model_served, "qa_tokens": q["qa_tokens"], "n_nuggets": len(qn),
                    "usage": asdict(r.usage), "usd_standard": r.cost_usd, "latency_s": r.latency_s,
                    "attempts": r.attempts, "from_cache": r.from_cache}
            print(f"  {a.judge} on {set_name} Q{q['question_number']}: "
                  f"{sum(x['label'] == 'support' for x in rows)}/{len(rows)} support, ${r.cost_usd:.4f}", flush=True)
            return rows, call

        with ThreadPoolExecutor(a.workers) as ex:
            res = list(ex.map(one, qs))
        d = out / "selfscore" / a.judge / set_name
        jl_write(d / "assignments.jsonl", [x for rows, _ in res for x in rows])
        jl_write(d / "calls.jsonl", [c for _, c in res])
        (d / "manifest.json").write_text(json.dumps(
            {"judge": a.judge, "registry": load_registry(HERE / "models.yaml")[a.judge], "nugget_set": set_name,
             "sample": a.sample, "prompt": str(prompt(a.prompt).relative_to(REPO)),
             "prompt_sha256": sha(prompt(a.prompt))}, indent=1, ensure_ascii=False, default=str))

    with ThreadPoolExecutor(len(a.sets)) as ex:
        list(ex.map(run_set, a.sets))


def cmd_report(a):
    out = Path(a.out)
    path = report.build(out, questions(out, a.sample), load_registry(HERE / "models.yaml"),
                        jl_read(out / "input" / "questions.jsonl"))
    print("report:", path)


def main():
    load_dotenv(REPO / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(REPO / "nuggets" / "preview"))
    ap.add_argument("--sample", default="preview_10")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--budget", type=float, default=None,
                    help="stop before any call once the --out ledger (costs.csv) reaches this many USD")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("sample").set_defaults(fn=cmd_sample)
    p = sp.add_parser("create")
    p.add_argument("--models", type=lambda s: s.split(","), required=True)
    p.add_argument("--prompt", default="create_v2", help="file stem in prompts/")
    p.set_defaults(fn=cmd_create)
    sp.add_parser("validate").set_defaults(fn=cmd_validate)
    p = sp.add_parser("selfscore")
    p.add_argument("--judge", required=True)
    p.add_argument("--sets", type=lambda s: s.split(","), required=True)
    p.add_argument("--prompt", default="assign_v2", help="file stem in prompts/")
    p.set_defaults(fn=cmd_selfscore)
    sp.add_parser("report").set_defaults(fn=cmd_report)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
