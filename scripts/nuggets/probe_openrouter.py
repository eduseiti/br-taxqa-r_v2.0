#!/usr/bin/env python
"""Probe the OpenRouter route before using it (plan docs/20261020_130829_openrouter_support_plan.md §5 step 1).

One ``create_v4`` call per model on the first questions of ``preview_10``, plus Qwen variants. Checks: the
strict schema is accepted and the reply validates; the served upstream provider; the billed cost against the
list price (flex = half); reasoning tokens against the pilot's calls on the same questions.

    .venv/bin/python scripts/nuggets/nuggets.py --out nuggets/probe_openrouter sample
    .venv/bin/python scripts/nuggets/probe_openrouter.py --out nuggets/probe_openrouter --budget 0.50
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import nuggets as nx  # sets sys.path for llm_client and nuggetizer
from dotenv import load_dotenv
from llm_client import LLM, load_registry, route_config
from nuggetizer import data, schema

VARIANTS = {   # name -> (registry model, change to the openrouter params)
    "gpt-6.1-sol": ("gpt-6.1-sol", {}),
    "gemini-3.1-pro": ("gemini-3.1-pro", {}),
    "gemini-3.8-flash": ("gemini-3.8-flash", {}),
    "qwen3.8-max": ("qwen3.8-max", {}),
    "qwen3.8-max~effort_medium": ("qwen3.8-max", {"reasoning": {"effort": "medium"}}),
    "qwen3.8-max~json_schema": ("qwen3.8-max", {"response_format": "json_schema"}),
}


def pilot_calls(model: str) -> dict:
    p = nx.REPO / "nuggets" / "pilot" / "create" / model / "calls.jsonl"
    return {c["question_number"]: c for c in nx.jl_read(p)} if p.exists() else {}


def main():
    load_dotenv(nx.REPO / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(nx.REPO / "nuggets" / "probe_openrouter"))
    ap.add_argument("--n", type=int, default=3, help="first N questions of preview_10")
    ap.add_argument("--budget", type=float, required=True)
    ap.add_argument("--only", type=lambda s: s.split(","), default=None, help="variant names")
    a = ap.parse_args()
    out = Path(a.out)
    qs = nx.questions(out, "preview_10")[:a.n]
    system = nx.prompt("create_v4").read_text()
    sch = schema.strict_schema(schema.LLMNuggetList)
    reg = load_registry(nx.HERE / "models.yaml")
    rows = []
    for name, (model, change) in VARIANTS.items():
        if a.only and name not in a.only:
            continue
        cfg = copy.deepcopy(reg[model])
        cfg["openrouter"]["params"].update(change)
        m = LLM(name, route_config(cfg, "openrouter"), out / "cache", out / "costs.csv", budget_usd=a.budget)
        pilot = pilot_calls(model)
        for q in qs:
            row = {"variant": name, "question_number": q["question_number"], "params": cfg["openrouter"]["params"]}
            try:
                r = m.complete_json(system, data.user_prompt(q), sch, "nuggets",
                                    validate=schema.LLMNuggetList.model_validate, tag=f"probe:{q['question_number']}")
            except Exception as e:  # noqa: BLE001 - a probe reports failures, it does not stop on them
                row["error"] = f"{type(e).__name__}: {str(e)[:300]}"
                rows.append(row)
                print(f"{name} Q{q['question_number']}: {row['error']}", flush=True)
                continue
            p = pilot.get(q["question_number"])
            billed = r.meta.get("usd_billed")
            row |= {"n_nuggets": len(r.data["nuggets"]), "attempts": r.attempts, "from_cache": r.from_cache,
                    "provider": r.meta.get("provider"), "served": r.model_served, "usage": r.usage.__dict__,
                    "usd_standard": round(r.cost_usd, 6), "usd_billed": billed,
                    "billed_over_standard": round(billed / r.cost_usd, 3) if billed and r.cost_usd else None,
                    "latency_s": round(r.latency_s, 1), "pilot_usage": p["usage"] if p else None,
                    "pilot_n_nuggets": None}
            if p:
                pn = [n for n in nx.jl_read(nx.REPO / "nuggets" / "pilot" / "create" / model / "nuggets.jsonl")
                      if n["question_number"] == q["question_number"]]
                row["pilot_n_nuggets"] = len(pn)
            rows.append(row)
            u = r.usage
            print(f"{name} Q{q['question_number']}: {row['n_nuggets']} nuggets (pilot {row['pilot_n_nuggets']}), "
                  f"in {u.input} (cached {u.cached_input}), out {u.output}, reasoning {u.reasoning} "
                  f"(pilot {p['usage']['reasoning'] if p else '—'}), {row['provider']}, "
                  f"${r.cost_usd:.4f} list / ${billed if billed is not None else float('nan'):.4f} billed, "
                  f"{r.latency_s:.0f} s{' [cache]' if r.from_cache else ''}", flush=True)
    nx.jl_write(out / "probe.jsonl", rows)
    (out / "manifest.json").write_text(json.dumps(
        {"purpose": "OpenRouter route probe (plan §5 step 1)", "route": "openrouter", "sample": "preview_10",
         "questions": [q["question_number"] for q in qs], "variants": {k: v[1] for k, v in VARIANTS.items()},
         "prompt": "create_v4", "prompt_sha256": hashlib.sha256(nx.prompt("create_v4").read_bytes()).hexdigest()},
        indent=1))


if __name__ == "__main__":
    main()
