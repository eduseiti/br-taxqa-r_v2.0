#!/usr/bin/env python
"""Gold-answer nuggetization (plan: docs/20261011_224049_gold_answer_nuggetization_plan_v2.md).

Phase 0/1 subset of the plan: sample, create (synchronous calls, replicates), the 2-call importance
mode, validate, gold self-score, cross-set alignment, round trip, two-auditor review with repair,
known-answer tests and the reports. Pilot commands: scripts/nuggets/README.md.

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
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path[:0] = [str(HERE), str(HERE.parent)]

from dotenv import load_dotenv  # noqa: E402

from llm_client import LLM, BatchDeferred, QuotaExhausted, load_registry, route_config  # noqa: E402
from llm_client.client import LLMError  # noqa: E402
from llm_client import batch as llm_batch  # noqa: E402
from nuggetizer import data, pilot_report, report, schema, scoring  # noqa: E402
from nuggetizer.validate import validate  # noqa: E402

PROMPTS = HERE / "prompts"


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def jl_write(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def jl_read(path: Path):
    # split on "\n" only: str.splitlines() also splits on U+2028 etc., which can occur inside a justification
    return [json.loads(x) for x in Path(path).read_text().split("\n") if x.strip()]


def questions(out: Path, sample: str) -> list[dict]:
    qs = {q["question_number"]: q for q in jl_read(out / "input" / "questions.jsonl")}
    return [qs[n] for n in json.loads((out / "sample.json").read_text())[sample]]


BATCH: llm_batch.BatchRecorder | None = None     # set by --batch
ROUTE = "openrouter"                              # set by --route


class BatchPending(Exception):
    """Some requests were queued for a batch job; the command's outputs are not written this time."""


class QuotaBlocked(Exception):
    """Some calls hit a provider's daily quota; completed calls are cached, a rerun resumes."""


def model_cfg(name: str, route: str | None = None) -> dict:
    """Registry entry of ``name`` for the route (``--route`` by default); manifests record this."""
    return route_config(load_registry(HERE / "models.yaml")[name], route or ROUTE)


def llm(name: str, out: Path, budget: float | None, route: str | None = None) -> LLM:
    m = LLM(name, model_cfg(name, route), out / "cache", out / "costs.csv", budget_usd=budget)
    m.batch = BATCH
    return m


def longer(m: LLM, factor: int = 2) -> LLM:
    """A copy of ``m`` with ``factor`` × its output-token limit, for a reply truncated at the limit (Qwen
    auditing the 115 nuggets of Q442). The limit is in the params, so it enters only these calls' cache keys."""
    import copy
    m2 = copy.copy(m)
    k = "max_output_tokens" if "max_output_tokens" in m.params else "max_tokens"
    m2.params = {**m.params, k: m.params[k] * factor}
    return m2


def prompt(name: str) -> Path:
    return PROMPTS / f"{name}.pt.md"


def base_model(set_name: str) -> str:
    """``gpt-6.1-sol.r2`` / ``.2call`` / ``.rep1`` → ``gpt-6.1-sol`` (the registry entry)."""
    return report.base_model(set_name)


def set_nuggets(out: Path, set_name: str) -> list[dict]:
    return jl_read(out / "create" / set_name / "nuggets.jsonl")


def by_question(nugs: list[dict]) -> dict[str, list[dict]]:
    d = {}
    for n in nugs:
        d.setdefault(n["question_number"], []).append(n)
    return d


def call_row(q, role, model, r, **extra) -> dict:
    return {"question_number": q["question_number"], "role": role, "model": model, "served": r.model_served,
            "qa_tokens": q["qa_tokens"], "usage": asdict(r.usage), "usd_standard": r.cost_usd,
            "latency_s": r.latency_s, "attempts": r.attempts, "from_cache": r.from_cache, **extra}


def run_all(items, fn, workers):
    """``fn`` over ``items`` in threads. Items queued for a batch job, or blocked by a daily quota, do not
    stop the others; afterwards the run raises BatchPending / QuotaBlocked instead of returning partial
    results (the cache keeps every completed call, so the rerun is free up to where it stopped)."""
    deferred, blocked = [], []

    def safe(x):
        try:
            return fn(x)
        except (BatchDeferred, BatchPending):
            deferred.append(x)
        except (QuotaExhausted, QuotaBlocked) as e:
            blocked.append(e)

    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(safe, items))
    if blocked:
        raise QuotaBlocked(f"{len(blocked)} items blocked by a daily quota: {str(blocked[0])[:200]}")
    if deferred:
        raise BatchPending()
    return res


def write_manifest(d: Path, **kw):
    d.mkdir(parents=True, exist_ok=True)
    kw.setdefault("route", ROUTE)
    for k in [k for k in kw if k.endswith("_prompt")]:
        kw[k + "_sha256"] = sha(prompt(kw[k]))
    (d / "manifest.json").write_text(json.dumps(kw, indent=1, ensure_ascii=False, default=str))


def numbered(nugs: list[dict], prefix: str = "", imp: bool = False) -> str:
    return "\n".join(f"{prefix}{i}. " + (f"[{n['importance']}; {n['category']}] " if imp else "") + n["text"]
                      for i, n in enumerate(nugs, 1))


def assign_user(q: dict, answer: str, nugs: list[dict]) -> str:
    """User prompt of the assignment judge; identical for self-score and known-answer tests."""
    return (f"Pergunta: {q['question_text']}\n\nResposta a avaliar:\n<<<\n{answer.strip()}\n>>>"
            f"\n\nNuggets:\n{numbered(nugs)}")


def check_cover(key: str, n: int):
    def check(d):
        if sorted(x[key] for x in d[next(iter(d))]) != list(range(1, n + 1)):
            raise ValueError(f"items do not cover 1..{n} exactly once")
    return check


def cmd_sample(a):
    out = Path(a.out)
    qs = data.load_questions(REPO / "dataset" / "questions.jsonl")
    jl_write(out / "input" / "questions.jsonl", qs)
    s = {"seed": 13, "method": "per answer-length decile (o200k, question + answer), "
                                 f"excluding prompt examples {sorted(data.PROMPT_EXAMPLES)}",
         "dataset_sha256": sha(REPO / "dataset" / "questions.jsonl"),
         "preview_10": data.stratified(qs, 1), "stratified_30": data.stratified(qs, 3)}
    if a.keep_from:
        # the answer fixes of the v2.0 build moved some answer lengths, so the deciles shifted: keep the
        # pilot's lists as they were (stratified_30 is also the RAG pilot sample)
        old = json.loads(Path(a.keep_from).read_text())
        s.update({k: old[k] for k in ("preview_10", "stratified_30")},
                 kept_from=a.keep_from, kept_dataset_sha256=old["dataset_sha256"])
    # full phase 2 set (prompt examples included: they need nuggets for scoring; flagged by the validator),
    # and stratified_70 = stratified_30 + 4 more per current decile, for the 10 % checks of plan v2 §5.7
    s["all"] = [q["question_number"] for q in qs]
    s7, per = data.stratified(qs, 7), {}
    for i, n in enumerate(s7):          # s7 is decile-major, 7 per decile
        if n not in s["stratified_30"]:
            per.setdefault(i // 7, []).append(n)
    s["stratified_70"] = s["stratified_30"] + [n for d in sorted(per) for n in per[d][:4]]
    assert set(s["preview_10"]) <= set(s["stratified_30"]) <= set(s["stratified_70"])
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
                                tag=f"create:{q['question_number']}" + (f":r{a.replicate}" if a.replicate else ""),
                                replicate=a.replicate)
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

        res = run_all(qs, one, a.workers)
        d = out / "create" / (name + (f".r{a.replicate}" if a.replicate else ""))
        jl_write(d / "nuggets.jsonl", [n for nugs, _ in res for n in nugs])
        jl_write(d / "calls.jsonl", [c for _, c in res])
        (d / "manifest.json").write_text(json.dumps(
            {"model": name, "replicate": a.replicate, "route": ROUTE, "registry": model_cfg(name),
             "sample": a.sample,
             "prompt": str(prompt(a.prompt).relative_to(REPO)), "prompt_sha256": sha(prompt(a.prompt)),
             "schema_sha256": hashlib.sha256(json.dumps(sch, sort_keys=True).encode()).hexdigest()},
            indent=1, ensure_ascii=False, default=str))

    run_all(a.models, run_model, len(a.models))


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
    m = llm(base_model(a.judge), out, a.budget)

    def run_set(set_name):
        nugs = jl_read(out / "create" / set_name / "nuggets.jsonl")

        def one(q):
            qn = [n for n in nugs if n["question_number"] == q["question_number"]]
            user = assign_user(q, q["answer_cleaned"], qn)

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

        res = run_all(qs, one, a.workers)
        d = out / "selfscore" / a.judge / set_name
        jl_write(d / "assignments.jsonl", [x for rows, _ in res for x in rows])
        jl_write(d / "calls.jsonl", [c for _, c in res])
        (d / "manifest.json").write_text(json.dumps(
            {"judge": a.judge, "route": ROUTE, "registry": model_cfg(a.judge), "nugget_set": set_name,
             "sample": a.sample, "prompt": str(prompt(a.prompt).relative_to(REPO)),
             "prompt_sha256": sha(prompt(a.prompt))}, indent=1, ensure_ascii=False, default=str))

    run_all(a.sets, run_set, len(a.sets))


# ------------------------------------------------------------------ phase 1: 2-call importance
def cmd_importance(a):
    """Second call of the 2-call mode: relabel vital/okay on an existing set (texts unchanged)."""
    out = Path(a.out)
    system = prompt(a.prompt).read_text()
    sch = schema.strict_schema(schema.ImportanceList)
    src = by_question(set_nuggets(out, a.source))
    m = llm(a.model, out, a.budget)

    def one(q):
        nugs = src[q["question_number"]]
        user = data.user_prompt(q) + "\n\nNuggets:\n" + "\n".join(
            f"{i}. [{n['category']}] {n['text']}" for i, n in enumerate(nugs, 1))
        r = m.complete_json(system, user, sch, "importance", validate=check_cover("nugget", len(nugs)),
                            tag=f"importance:{q['question_number']}")
        by = {x["nugget"]: x for x in r.data["labels"]}
        new = [{**{k: v for k, v in n.items() if k not in ("values", "flags", "issues", "span_match")},
                "importance": by[i]["importance"], "importance_1call": n["importance"],
                "importance_justification": by[i]["justification"]} for i, n in enumerate(nugs, 1)]
        print(f"  importance Q{q['question_number']}: {sum(x['importance'] != x['importance_1call'] for x in new)}"
              f"/{len(new)} changed, ${r.cost_usd:.4f}", flush=True)
        return new, call_row(q, "importance", a.model, r)

    res = run_all(questions(out, a.sample), one, a.workers)
    d = out / "create" / f"{a.source}.2call"
    jl_write(d / "nuggets.jsonl", [n for ns, _ in res for n in ns])
    jl_write(d / "calls.jsonl", [c for _, c in res])
    write_manifest(d, mode="2-call: texts of the source set, importance from a second call", source=a.source,
                   model=a.model, sample=a.sample, importance_prompt=a.prompt)


# ------------------------------------------------------------------ phase 1: cross-set alignment
def cmd_align(a):
    out = Path(a.out)
    system = prompt(a.prompt).read_text()
    sch = schema.strict_schema(schema.AlignmentList)
    m = llm(a.model, out, a.budget)
    qs = questions(out, a.sample)

    def run_pair(pair):
        sa, sb = pair.split(":")
        na, nb = by_question(set_nuggets(out, sa)), by_question(set_nuggets(out, sb))

        def one(q):
            qa, qb = na.get(q["question_number"], []), nb.get(q["question_number"], [])

            def check(d):
                check_cover("a", len(qa))(d)
                if any(not 1 <= b <= len(qb) for x in d["alignments"] for b in x["b"]):
                    raise ValueError("b index out of range")
                if any((x["relation"] == "none") != (not x["b"]) for x in d["alignments"]):
                    raise ValueError("relation none iff b is empty")

            user = (f"Pergunta: {q['question_text']}\n\nResposta oficial:\n<<<\n{q['answer_cleaned'].strip()}\n>>>"
                    f"\n\nConjunto A:\n{numbered(qa, 'A')}\n\nConjunto B:\n{numbered(qb, 'B')}")
            r = m.complete_json(system, user, sch, "alignments", validate=check,
                                tag=f"align:{sa}:{sb}:{q['question_number']}")
            rows = [{"question_number": q["question_number"], "a": qa[x["a"] - 1]["nugget_id"],
                     "b": [qb[i - 1]["nugget_id"] for i in x["b"]], "relation": x["relation"], "note": x["note"]}
                    for x in r.data["alignments"]]
            print(f"  align {sa}:{sb} Q{q['question_number']}: {sum(bool(x['b']) for x in rows)}/{len(rows)} matched, "
                  f"${r.cost_usd:.4f}", flush=True)
            return rows, call_row(q, "align", a.model, r, pair=pair)

        res = run_all(qs, one, a.workers)
        d = out / "align" / f"{sa}__{sb}"
        jl_write(d / "alignment.jsonl", [x for rows, _ in res for x in rows])
        jl_write(d / "calls.jsonl", [c for _, c in res])
        write_manifest(d, a_set=sa, b_set=sb, model=a.model, sample=a.sample, align_prompt=a.prompt)

    run_all(a.pairs, run_pair, len(a.pairs))


# ------------------------------------------------------------------ phase 1: round trip
def cmd_roundtrip(a):
    out = Path(a.out)
    sw, sc = prompt(a.write_prompt).read_text(), prompt(a.check_prompt).read_text()
    schw, schc = schema.strict_schema(schema.Reconstruction), schema.strict_schema(schema.MissingList)
    mw, mc = llm(a.writer, out, a.budget), llm(a.checker, out, a.budget)
    nugs = by_question(set_nuggets(out, a.set))

    def one(q):
        facts = "\n".join(f"- {n['text']}" for n in nugs[q["question_number"]])
        rw = mw.complete_json(sw, f"Pergunta: {q['question_text']}\n\nFatos:\n{facts}", schw, "answer",
                              tag=f"roundtrip_write:{a.set}:{q['question_number']}")
        rec = rw.data["answer"]
        user = (f"Pergunta: {q['question_text']}\n\nResposta oficial:\n<<<\n{q['answer_cleaned'].strip()}\n>>>"
                f"\n\nReconstrução:\n<<<\n{rec.strip()}\n>>>")
        rc = mc.complete_json(sc, user, schc, "missing", tag=f"roundtrip_check:{a.set}:{q['question_number']}")
        miss = [{"question_number": q["question_number"], **x} for x in rc.data["missing"]]
        print(f"  roundtrip Q{q['question_number']}: {len(miss)} missing, ${rw.cost_usd + rc.cost_usd:.4f}", flush=True)
        return ({"question_number": q["question_number"], "reconstruction": rec}, miss,
                [call_row(q, "roundtrip_write", a.writer, rw), call_row(q, "roundtrip_check", a.checker, rc)])

    res = run_all(questions(out, a.sample), one, a.workers)
    d = out / "roundtrip" / (a.name or a.set)
    jl_write(d / "reconstructions.jsonl", [r for r, _, _ in res])
    jl_write(d / "missing.jsonl", [x for _, ms, _ in res for x in ms])
    jl_write(d / "calls.jsonl", [c for _, _, cs in res for c in cs])
    write_manifest(d, nugget_set=a.set, writer=a.writer, checker=a.checker, sample=a.sample,
                   write_prompt=a.write_prompt, check_prompt=a.check_prompt)


# ------------------------------------------------------------------ phase 1: omission candidates
def omission_candidates(out: Path, primary: str, others: list[str]) -> dict[str, list[str]]:
    """Per question: facts made by both other families but matched by no primary nugget (§3.5.2),
    plus the round-trip findings (§3.5.4). Read from the alignments of the *base* primary set."""
    cand = {}
    if len(others) == 2:
        o1, o2 = others
        p1 = jl_read(out / "align" / f"{primary}__{o1}" / "alignment.jsonl")
        p2 = jl_read(out / "align" / f"{primary}__{o2}" / "alignment.jsonl")
        x12 = jl_read(out / "align" / f"{o1}__{o2}" / "alignment.jsonl")
        hit1 = {b for r in p1 for b in r["b"]}
        hit2 = {b for r in p2 for b in r["b"]}
        n1 = {n["nugget_id"]: n for n in set_nuggets(out, o1)}
        for r in x12:
            g = r["a"]
            if g in hit1 or r["relation"] in ("none", "conflict"):
                continue
            if all(b not in hit2 for b in r["b"]):
                cand.setdefault(r["question_number"], []).append(
                    f"(feito por outros dois criadores) {n1[g]['text']} [trecho: «{n1[g]['source_span']}»]")
    rt = out / "roundtrip" / primary / "missing.jsonl"
    for x in jl_read(rt) if rt.exists() else []:
        cand.setdefault(x["question_number"], []).append(
            f"(ida e volta, {x['problem']}) {x['description']} [trecho: «{x['source_span']}»]")
    return cand


# ------------------------------------------------------------------ phase 1: two-auditor review
def cmd_audit(a):
    out = Path(a.out)
    system = prompt(a.prompt).read_text()
    sch = schema.strict_schema(schema.Audit)
    nugs = by_question(set_nuggets(out, a.set))
    cand = omission_candidates(out, a.candidates_from or base_model(a.set), a.others) if a.others else {}
    m = llm(a.auditor, out, a.budget)
    qs = [q for q in questions(out, a.sample) if not a.only or q["question_number"] in a.only]

    def one(q):
        qn = nugs[q["question_number"]]
        c = cand.get(q["question_number"], [])
        user = (data.user_prompt(q) + f"\n\nNuggets:\n{numbered(qn, imp=True)}\n\nCandidatos a omissão:\n" +
                ("\n".join(f"- {x}" for x in c) if c else "(nenhum)"))

        def check(d):
            check_cover("nugget", len(qn))({"nuggets": d["nuggets"]})
            if any(not (1 <= x["a"] <= len(qn) and 1 <= x["b"] <= len(qn)) for x in d["redundant"]):
                raise ValueError("redundant index out of range")

        tag = f"audit:{a.set}:{q['question_number']}"
        try:
            r = m.complete_json(system, user, sch, "audit", validate=check, tag=tag)
        except LLMError as e:
            if "truncated" not in str(e):
                raise
            r = longer(m).complete_json(system, user, sch, "audit", validate=check, tag=tag + ":long")
        rows = [{"nugget_id": qn[x["nugget"] - 1]["nugget_id"], **{k: v for k, v in x.items() if k != "nugget"}}
                for x in r.data["nuggets"]]
        qrow = {"question_number": q["question_number"], "n_candidates": len(c), "omissions": r.data["omissions"],
                "redundant": [[qn[x["a"] - 1]["nugget_id"], qn[x["b"] - 1]["nugget_id"]] for x in r.data["redundant"]]}
        bad = sum(not all(x[k] for k in CHECKS) for x in rows)
        print(f"  audit {a.auditor} on {a.set} Q{q['question_number']}: {bad}/{len(rows)} flagged, "
              f"{len(qrow['omissions'])} omissions, ${r.cost_usd:.4f}", flush=True)
        return rows, qrow, call_row(q, "audit", a.auditor, r, set=a.set)

    res = run_all(qs, one, a.workers)
    d = out / "audit" / a.set / a.auditor
    jl_write(d / "nuggets.jsonl", [x for rows, _, _ in res for x in rows])
    jl_write(d / "questions.jsonl", [q for _, q, _ in res])
    jl_write(d / "calls.jsonl", [c for _, _, c in res])
    write_manifest(d, nugget_set=a.set, auditor=a.auditor, sample=a.sample, only=a.only, others=a.others,
                   audit_prompt=a.prompt)


CHECKS = ["c1_faithful", "c2_self_contained", "c3_one_unit", "c4_importance"]


def _spans_match(s1: str, s2: str, ans: str) -> bool:
    from nuggetizer.known_answer import find
    r1, r2 = find(s1, ans), find(s2, ans)
    if r1 and r2:
        ov = max(0, min(r1[1], r2[1]) - max(r1[0], r2[0]))
        return ov >= 0.5 * min(r1[1] - r1[0], r2[1] - r2[0])
    from nuggetizer.validate import norm
    return norm(s1)[:60] == norm(s2)[:60]


def agreed_issues(out: Path, set_name: str, auditors: list[str], qs: list[dict]) -> dict[str, list[str]]:
    """Per question, the issues to repair: a nugget flagged by both auditors (any check), an
    omission whose span both auditors give, a redundant pair both give, and hard validator errors."""
    aud = {x: {r["nugget_id"]: r for r in jl_read(out / "audit" / set_name / x / "nuggets.jsonl")} for x in auditors}
    aq = {x: {r["question_number"]: r for r in jl_read(out / "audit" / set_name / x / "questions.jsonl")} for x in auditors}
    val = json.loads((out / "create" / set_name / "validation.json").read_text())
    nugs = by_question(set_nuggets(out, set_name))
    a1, a2 = auditors
    issues = {}
    for q in qs:
        qn = q["question_number"]
        if qn not in aq[a1] or qn not in aq[a2]:
            continue
        lst = []
        for i, n in enumerate(nugs[qn], 1):
            r1, r2 = aud[a1].get(n["nugget_id"]), aud[a2].get(n["nugget_id"])
            f1 = [k for k in CHECKS if r1 and not r1[k]]
            f2 = [k for k in CHECKS if r2 and not r2[k]]
            if f1 and f2:   # flagged by both auditors, on the same check or not (plan v2 §3.5.3)
                lst.append(f"Nugget {i}. Revisor 1 ({', '.join(f1)}): {r1['problem']} Sugestão: {r1['fix']} "
                           f"| Revisor 2 ({', '.join(f2)}): {r2['problem']} Sugestão: {r2['fix']}")
        for o in aq[a1][qn]["omissions"]:
            if any(_spans_match(o["source_span"], p["source_span"], q["answer_cleaned"]) for p in aq[a2][qn]["omissions"]):
                lst.append(f"Omissão: {o['fact']} [trecho: «{o['source_span']}»]")
        red2 = {tuple(sorted(p)) for p in aq[a2][qn]["redundant"]}
        ids = [n["nugget_id"] for n in nugs[qn]]
        for p in aq[a1][qn]["redundant"]:
            if tuple(sorted(p)) in red2:
                lst.append(f"Redundância: nuggets {ids.index(p[0]) + 1} e {ids.index(p[1]) + 1} carregam o mesmo fato.")
        vq = next(r for r in val["questions"] if r["question_number"] == qn)
        for e in vq["errors"]:
            where = f"nugget {ids.index(e['nugget_id']) + 1}" if e["nugget_id"] else "resposta"
            lst.append(f"Erro mecânico ({where}): {e['code']} {e['detail']}")
        if lst:
            issues[qn] = lst
    return issues


def validator_issues(out: Path, set_name: str) -> dict[str, list[str]]:
    """Per question, the hard validator errors only (phase 2: before the auditors run)."""
    val = json.loads((out / "create" / set_name / "validation.json").read_text())
    ids = {qn: [n["nugget_id"] for n in ns] for qn, ns in by_question(set_nuggets(out, set_name)).items()}
    issues = {}
    for vq in val["questions"]:
        for e in vq["errors"]:
            where = f"nugget {ids[vq['question_number']].index(e['nugget_id']) + 1}" if e["nugget_id"] else "resposta"
            issues.setdefault(vq["question_number"], []).append(f"Erro mecânico ({where}): {e['code']} {e['detail']}")
    return issues


def cmd_repair(a):
    out = Path(a.out)
    system = prompt(a.create_prompt).read_text() + prompt(a.prompt).read_text()
    sch = schema.strict_schema(schema.LLMNuggetList)
    qs = questions(out, a.sample)
    issues = agreed_issues(out, a.set, a.auditors, qs) if a.auditors else validator_issues(out, a.set)
    src = by_question(set_nuggets(out, a.set))
    m = llm(a.model, out, a.budget)
    print(f"repair {a.set}: {len(issues)} questions with agreed issues, {sum(map(len, issues.values()))} issues")

    def check(d):
        schema.LLMNuggetList.model_validate(d)
        if not d["nuggets"]:
            raise ValueError("empty nugget list")

    def one(q):
        qn = q["question_number"]
        if qn not in issues:
            return src[qn], None
        cur = "\n".join(f"{i}. " + json.dumps({k: n[k] for k in ("text", "importance", "category", "legal_basis",
                                                                    "source_span")}, ensure_ascii=False)
                        for i, n in enumerate(src[qn], 1))
        user = (data.user_prompt(q) + f"\n\nNuggets atuais:\n{cur}\n\nProblemas apontados:\n" +
                "\n".join(f"- {x}" for x in issues[qn]))
        r = m.complete_json(system, user, sch, "nuggets", validate=check, tag=f"repair:{a.set}:{qn}")
        nugs = [{"nugget_id": f"Q{qn}_N{i:02d}", "question_number": qn, "ordinal": i, **n}
                for i, n in enumerate(r.data["nuggets"], 1)]
        print(f"  repair Q{qn}: {len(src[qn])} → {len(nugs)} nuggets ({len(issues[qn])} issues), ${r.cost_usd:.4f}",
              flush=True)
        return nugs, call_row(q, "repair", a.model, r, issues=issues[qn])

    res = run_all(qs, one, a.workers)
    d = out / "create" / a.new
    jl_write(d / "nuggets.jsonl", [n for ns, _ in res for n in ns])
    jl_write(d / "calls.jsonl", [c for _, c in res if c])
    write_manifest(d, mode="repair", source=a.set, auditors=a.auditors, model=a.model, sample=a.sample,
                   repaired=sorted(issues), create_prompt=a.create_prompt, repair_prompt=a.prompt)


# ------------------------------------------------------------------ phase 3: freeze (plan v2 §3.5.3, D10)
def cmd_freeze(a):
    """Write the frozen set: nuggets still flagged by both auditors on C1 are dropped; every other auditor
    flag (one auditor, or both on another check) is kept and listed on the nugget (``audit``). Stability:
    how many families made a matching nugget (plan v2 §3.5.2), from the alignments of ``--aligned``; null
    for the questions whose nuggets changed after that set."""
    out, dest = Path(a.out), Path(a.dest)
    nugs = set_nuggets(out, a.set)
    aud = {x: {r["nugget_id"]: r for r in jl_read(out / "audit" / a.set / x / "nuggets.jsonl")} for x in a.auditors}
    al = {}
    for o in a.others:
        al[o] = {r["a"]: r["relation"] for r in jl_read(out / "align" / f"{a.aligned}__{o}" / "alignment.jsonl")}
    base = {n["nugget_id"]: n["text"] for n in set_nuggets(out, a.aligned)}
    keep, dropped = [], []
    for n in nugs:
        fl = {x: [k for k in CHECKS if not aud[x][n["nugget_id"]][k]] for x in a.auditors if n["nugget_id"] in aud[x]}
        fl = {x: v for x, v in fl.items() if v}
        n = {**n, "audit": {x: {"failed": v, "problem": aud[x][n["nugget_id"]]["problem"]} for x, v in fl.items()}}
        same_text = base.get(n["nugget_id"]) == n["text"]
        n["stability"] = (1 + sum(al[o].get(n["nugget_id"]) in pilot_report.MATCH for o in a.others)
                          if same_text and all(n["nugget_id"] in al[o] for o in a.others) else None)
        if len(fl) == len(a.auditors) and all("c1_faithful" in v for v in fl.values()):
            dropped.append(n)
        else:
            keep.append(n)
    for qn, ns in by_question(keep).items():     # renumber after a drop; the source id is kept
        for i, n in enumerate(ns, 1):
            n["source_nugget_id"], n["nugget_id"], n["ordinal"] = n["nugget_id"], f"Q{qn}_N{i:02d}", i
    jl_write(dest / "nuggets.jsonl", keep)
    jl_write(dest / "dropped.jsonl", dropped)
    write_manifest(dest, mode="freeze (plan v2 §3.5.3, D10)", source=a.set, auditors=a.auditors, aligned=a.aligned,
                   others=a.others, n_nuggets=len(keep), n_dropped=len(dropped),
                   n_flagged_one=sum(len(n["audit"]) == 1 for n in keep),
                   n_flagged_both=sum(len(n["audit"]) == 2 for n in keep))
    print(f"frozen {len(keep)} nuggets ({len(dropped)} dropped) → {dest}")


# ------------------------------------------------------------------ phase 1: planted errors (auditor test)
def cmd_plant(a):
    from nuggetizer import planted
    out = Path(a.out)
    src = by_question(set_nuggets(out, a.set))
    allnugs, log = [], []
    for k, q in enumerate(questions(out, a.sample)):
        ns, rec = planted.plant(q["question_number"], src[q["question_number"]], k)
        allnugs += [{kk: v for kk, v in n.items() if kk not in ("values", "flags", "issues", "span_match")} for n in ns]
        if rec:
            log.append(rec)
    d = out / "create" / f"{a.set}.planted"
    jl_write(d / "nuggets.jsonl", allnugs)
    jl_write(d / "planted.jsonl", log)
    jl_write(d / "calls.jsonl", [])
    write_manifest(d, mode="planted errors (auditor sensitivity test)", source=a.set, sample=a.sample)
    print(f"{len(log)} planted:", dict(Counter(x["type"] for x in log)))


# ------------------------------------------------------------------ phase 1: known-answer tests
def cmd_known(a):
    from nuggetizer import known_answer as ka
    out = Path(a.out)
    d = out / "known" / a.set
    qs = questions(out, a.sample)
    nugs = by_question(set_nuggets(out, a.set))
    if a.action == "build":
        allq = jl_read(out / "input" / "questions.jsonl")
        corpus = None
        if a.corpus:        # article chunks (S1) of the legal corpus, for the VP tests
            import csv
            csv.field_size_limit(sys.maxsize)
            with open(a.corpus, newline="") as f:
                corpus = ka.CorpusValues([r["Texto"] for r in csv.DictReader(f)
                                          if r["Tipo"] == "ART" and r["variante"] == "base"])
        tests = [t for q in qs for t in ka.build(q, nugs[q["question_number"]], allq, corpus=corpus)]
        jl_write(d / "tests.jsonl", tests)
        print(f"{len(tests)} tests:", dict(sorted(Counter(t["type"] for t in tests).items())))
        return
    qd = {q["question_number"]: q for q in qs}
    tests = [t for t in jl_read(d / "tests.jsonl") if t["question_number"] in qd]
    if a.types:
        tests = [t for t in tests if t["type"] in a.types]
    system = prompt(a.prompt).read_text()
    sch = schema.strict_schema(schema.AssignmentList)
    m = llm(a.judge, out, a.budget)

    def one(t):
        q, qn = qd[t["question_number"]], nugs[t["question_number"]]
        try:
            r = m.complete_json(system, assign_user(q, t["answer"], qn), sch, "assignments",
                                validate=check_cover("nugget", len(qn)), tag=f"known:{t['test_id']}")
        except QuotaExhausted:   # partial results are written; a rerun completes them from the cache
            return [], None
        by = {x["nugget"]: x for x in r.data["assignments"]}
        rows = [{"test_id": t["test_id"], "nugget_id": n["nugget_id"], "label": by[i]["label"],
                 "justification": by[i]["justification"]} for i, n in enumerate(qn, 1)]
        return rows, call_row(q, "known", a.judge, r, test_id=t["test_id"], n_nuggets=len(qn))

    res = run_all(tests, one, a.workers)
    jd = d / (a.judge + (f".{a.name}" if a.name else ""))
    jl_write(jd / "labels.jsonl", [x for rows, _ in res for x in rows])
    jl_write(jd / "calls.jsonl", [c for _, c in res if c])
    missing = [t["test_id"] for t, (_, c) in zip(tests, res) if c is None]
    write_manifest(jd, nugget_set=a.set, judge=a.judge, sample=a.sample, types=a.types, assign_prompt=a.prompt,
                   missing_tests=missing)
    if missing:
        print(f"PARTIAL: {len(missing)} tests not judged (daily quota); rerun the same command to complete")
    labels = {}
    for x in jl_read(jd / "labels.jsonl"):
        labels.setdefault(x["test_id"], {})[x["nugget_id"]] = x["label"]
    met = ka.metrics(tests, labels, {n["nugget_id"]: n for ns in nugs.values() for n in ns})
    (jd / "metrics.json").write_text(json.dumps(met, indent=1))
    print(json.dumps(met["_pooled"], indent=1))


# ------------------------------------------------------------------ phase 5: scoring of RAG answers
FULL = REPO / "nuggets" / "full"           # questions and samples of the 715-question runs
EST_USD = {"score": 0.0018, "ctxsupport": 0.0035}   # Flash flex per call, before the ledger has rows of the role


def scoring_set(name: str) -> tuple[str, dict[str, list[dict]]]:
    """``gold`` → the frozen primary set (``nuggets/gold/v0-auto``); else a set of ``nuggets/full/create``."""
    path = REPO / "nuggets" / "gold" / "v0-auto" / "nuggets.jsonl" if name == "gold" else \
        FULL / "create" / name / "nuggets.jsonl"
    return ("gold-v0-auto" if name == "gold" else name), by_question(jl_read(path))


def scoring_questions(sample: str) -> dict[str, dict]:
    qs = {q["question_number"]: q for q in jl_read(FULL / "input" / "questions.jsonl")}
    if sample == "all":
        return qs
    return {n: qs[n] for n in json.loads((FULL / "sample.json").read_text())[sample]}


def expand_dirs(patterns: list[str], marker: str) -> list[Path]:
    """Directories given directly or by glob (relative to the repo root) that contain ``marker``."""
    ds = []
    for p in patterns:
        hits = sorted(REPO.glob(p)) if any(c in p for c in "*?[") else [REPO / p]
        ds += [h for h in hits if (h / marker).exists()]
    if not ds:
        sys.exit(f"no directory with {marker} matches {patterns}")
    return list(dict.fromkeys(ds))


def judge_items(a, role: str, jobs: list[tuple[Path, list[dict]]], nugs: dict, qs: dict, prompt_name: str):
    """One judge call per item (``source == judge``); the others get ``not_support`` for every nugget without a
    call. ``jobs``: (output dir, items). Labels of other questions already in an output dir are kept."""
    out = Path(a.out)
    system = prompt(prompt_name).read_text()
    sch = schema.strict_schema(schema.AssignmentList)
    m = llm(a.judge, out, a.budget)
    flat = [(d, it) for d, items in jobs for it in items if it["question_number"] in nugs]
    calls = [(d, it) for d, it in flat if it["source"] == "judge"]
    if a.dry_run:
        new = sum(not m.is_cached(system, assign_user(qs[it["question_number"]], it["text"],
                                                       nugs[it["question_number"]]), sch) for _, it in calls)
        led = [r for r in jl_ledger(out / "costs.csv") if r["tag"].startswith(role + ":")]
        per = (sum(float(r["usd_billed"] or r["usd_standard"]) for r in led) / len(led)) if led else EST_USD[role]
        print(f"{len(jobs)} outputs, {len(flat)} items, {len(calls)} need the judge, {new} not cached; "
              f"≈ ${new * per:.2f} at ${per:.4f} per call ({'ledger mean' if led else 'estimate'}). Nothing was sent.")
        return

    def one(x):
        d, it = x
        q, qn = qs[it["question_number"]], nugs[it["question_number"]]
        if it["source"] != "judge":
            return d, {"question_number": q["question_number"], "source": it["source"],
                       "labels": [{"nugget_id": n["nugget_id"], "label": "not_support", "justification": ""}
                                  for n in qn]}, None
        try:
            r = m.complete_json(system, assign_user(q, it["text"], qn), sch, "assignments",
                                validate=check_cover("nugget", len(qn)),
                                tag=f"{role}:{d.relative_to(out)}:{q['question_number']}")
        except (LLMError, ValueError) as e:
            if type(e).__name__ in ("BudgetExceeded", "CreditsExhausted"):
                raise
            print(f"  FAILED {d.relative_to(out)} Q{q['question_number']}: {str(e)[:200]}", flush=True)
            return d, None, None
        by = {x["nugget"]: x for x in r.data["assignments"]}
        row = {"question_number": q["question_number"], "source": "judge",
               "labels": [{"nugget_id": n["nugget_id"], "label": by[i]["label"],
                           "justification": by[i]["justification"]} for i, n in enumerate(qn, 1)]}
        return d, row, call_row(q, role, a.judge, r, n_nuggets=len(qn))

    res = run_all(flat, one, a.workers)
    failed = sum(row is None for _, row, _ in res)
    for d, _ in jobs:
        rows = {x["question_number"]: x for x in (jl_read(d / "labels.jsonl") if (d / "labels.jsonl").exists() else [])}
        cl = {x["question_number"]: x for x in (jl_read(d / "calls.jsonl") if (d / "calls.jsonl").exists() else [])}
        for dd, row, c in res:
            if dd == d and row:
                rows[row["question_number"]] = row
                if c:
                    cl[c["question_number"]] = c
        jl_write(d / "labels.jsonl", [rows[k] for k in sorted(rows)])
        jl_write(d / "calls.jsonl", [cl[k] for k in sorted(cl)])
    n_new = sum(1 for _, _, c in res if c and not c["from_cache"])
    usd = sum(c["usd_standard"] for _, _, c in res if c and not c["from_cache"])
    print(f"{len(flat)} items in {len(jobs)} outputs: {n_new} new judge calls (${usd:.2f} list), {failed} failed")
    return failed


def jl_ledger(path: Path) -> list[dict]:
    import csv
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def cmd_score(a):
    """Judge each answer of the runs against a nugget set (plan v2 §5.2; ``assign_v2``)."""
    set_name, nugs = scoring_set(a.set)
    qs = scoring_questions(a.sample)
    jobs = []
    for rd in expand_dirs(a.runs, "answers.jsonl"):
        run_id = json.loads((rd / "run.json").read_text())["run_id"]
        d = Path(a.out) / "score" / set_name / a.judge / run_id
        jobs.append((d, scoring.answer_items(rd, set(qs))))
        if not a.dry_run:
            write_manifest(d, kind="score", run=str(rd.relative_to(REPO)), run_id=run_id, nugget_set=set_name,
                           judge=a.judge, registry=model_cfg(a.judge), sample=a.sample, assign_prompt=a.prompt)
    judge_items(a, "score", jobs, nugs, qs, a.prompt)


def cmd_ctxsupport(a):
    """Judge the gold nuggets against each context (first-evaluation note §4.3; ``assign_ctx_v1``)."""
    set_name, nugs = scoring_set(a.set)
    qs = scoring_questions(a.sample)
    jobs = []
    for cd in expand_dirs(a.contexts, "contexts.jsonl.gz"):
        rel_ctx = cd.relative_to(REPO / "runs" / "contexts")
        d = Path(a.out) / "ctxsupport" / set_name / a.judge / rel_ctx
        jobs.append((d, scoring.context_items(cd, set(qs))))
        if not a.dry_run:
            write_manifest(d, kind="ctxsupport", contexts=str(cd.relative_to(REPO)), nugget_set=set_name,
                           judge=a.judge, registry=model_cfg(a.judge), sample=a.sample, assign_prompt=a.prompt)
    judge_items(a, "ctxsupport", jobs, nugs, qs, a.prompt)


def cmd_scoretable(a):
    """Per-question scores, run means and paired comparisons of every scored run (no LLM)."""
    import pandas as pd
    out = Path(a.out)
    set_name, nugs = scoring_set(a.set)
    base = out / "score" / set_name / a.judge
    frames = []
    for lp in sorted(base.glob("**/labels.jsonl")):
        man = json.loads((lp.parent / "manifest.json").read_text())
        run = json.loads((REPO / man["run"] / "run.json").read_text())
        ans = {x["question_number"]: x for x in jl_read(REPO / man["run"] / "answers.jsonl")}
        pq = scoring.per_question(lp, nugs, {"run_id": man["run_id"], "llm": run["llm"]["name"],
                                              "prompt": run["prompt"]["name"], "context_id": man["run_id"].split("/")[-1]})
        pq["answer_chars"] = [len(ans[q].get("answer") or "") for q in pq.question_number]
        frames.append(pq)
    pq = pd.concat(frames, ignore_index=True)
    sample = set(scoring_questions(a.sample)) if a.sample != "all" else None
    if sample:
        pq = pq[pq.question_number.isin(sample)]
    d = out / "tables" / set_name / a.judge / a.sample
    d.mkdir(parents=True, exist_ok=True)
    pq.to_csv(d / "per_question.csv.gz", index=False)
    runs = pq.groupby(["llm", "context_id"]).agg(
        n=("question_number", "size"), **{m: (m, "mean") for m in scoring.METRICS},
        abstained=("source", lambda s: (s == "abstained").mean()), errors=("source", lambda s: (s == "error").sum()),
        answer_chars=("answer_chars", "mean")).reset_index()
    runs.to_csv(d / "runs.csv", index=False, float_format="%.4f")
    pairs = [p for p in scoring.PAIRS if {p[0], p[1]} <= set(pq.context_id)]
    cmp = pd.concat([scoring.compare(pq, x, y, ["llm"], a.resamples) for x, y in pairs], ignore_index=True)
    cmp.to_csv(d / "comparisons.csv", index=False, float_format="%.4f")
    ctx = out / "ctxsupport" / set_name / a.judge
    cframes = [scoring.per_question(lp, nugs, {"contexts": str(lp.parent.relative_to(ctx)),
                                              "context_id": lp.parent.name})
               for lp in sorted(ctx.glob("**/labels.jsonl"))]
    if cframes:
        cq = pd.concat(cframes, ignore_index=True)
        if sample:
            cq = cq[cq.question_number.isin(sample)]
        cq.to_csv(d / "ctxsupport_per_question.csv.gz", index=False)
        cq.groupby("context_id").agg(n=("question_number", "size"), **{m: (m, "mean") for m in scoring.METRICS}) \
            .reset_index().to_csv(d / "ctxsupport_runs.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 200)
    print(runs.to_string(index=False, float_format="%.3f"))
    print(cmp[cmp.metric == "V_strict"].drop(columns="metric").to_string(index=False, float_format="%.3f"))
    print("tables:", d)


def cmd_report(a):
    out = Path(a.out)
    path = report.build(out, questions(out, a.sample), load_registry(HERE / "models.yaml"),
                        jl_read(out / "input" / "questions.jsonl"))
    print("report:", path)


def cmd_batch(a):
    """Poll the batch jobs of --out and write finished results into its cache and ledger."""
    out = Path(a.out)
    names = {json.loads(p.read_text())["model"] for p in (out / "batches").glob("*.json")}
    llms = {n: llm(n, out, None, route="direct") for n in names}     # batch jobs are direct-route only
    for m in llms.values():
        m.batch = None
    if a.action == "wait":
        s = llm_batch.wait(out, llms, every_s=a.every)
    elif a.action == "collect":
        s = llm_batch.collect(out, llms)
    else:
        s = [json.loads(p.read_text()) for p in sorted((out / "batches").glob("*.json"))]
        s = [{k: x.get(k) for k in ("job", "model", "state", "n_requests", "n_cached", "n_failed",
                                     "estimated_usd_billed", "last_poll")} for x in s]
    for x in s:
        print(json.dumps(x, ensure_ascii=False))


def cmd_openrouter_key(a):
    """Credit limit and usage of the OpenRouter key (no cost)."""
    import os

    import httpx
    from llm_client.client import OPENROUTER
    r = httpx.get(f"{OPENROUTER}/key", headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
                  timeout=60)
    r.raise_for_status()
    d = r.json().get("data", {})
    print(json.dumps({k: d.get(k) for k in ("label", "limit", "limit_remaining", "usage", "usage_daily",
                                            "expires_at")}, indent=1))


def cmd_pilotreport(a):
    out = Path(a.out)
    path = pilot_report.build(out, questions(out, a.sample), load_registry(HERE / "models.yaml"),
                              jl_read(out / "input" / "questions.jsonl"), primary=a.primary, others=tuple(a.others),
                              sample_name=a.sample,
                              name="report_pilot.md" if a.sample == "stratified_30" else "report_full.md")
    print("report:", path)


def main():
    load_dotenv(REPO / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(REPO / "nuggets" / "preview"))
    ap.add_argument("--sample", default="preview_10")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--budget", type=float, default=None,
                    help="stop before any call once the --out ledger (costs.csv) reaches this many USD")
    ap.add_argument("--batch", action="store_true",
                    help="queue every uncached OpenAI/Gemini request in Batch API jobs instead of calling it; "
                         "then `batch wait` and rerun the same command without --batch (direct route only)")
    ap.add_argument("--route", choices=["direct", "openrouter"], default="openrouter",
                    help="OpenRouter (default; registry `openrouter:` blocks, flex for GPT/Gemini) or the direct "
                         "provider APIs (the route of the preview and pilot runs and of their caches)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("sample")
    p.add_argument("--keep-from", default=None,
                   help="sample.json whose preview_10 / stratified_30 lists are kept verbatim")
    p.set_defaults(fn=cmd_sample)
    p = sp.add_parser("create")
    p.add_argument("--models", type=lambda s: s.split(","), required=True)
    p.add_argument("--prompt", default="create_v4", help="file stem in prompts/")
    p.add_argument("--replicate", type=int, default=0,
                   help="N > 0: a fresh sample of the same request (enters the cache key), written to <model>.rN")
    p.set_defaults(fn=cmd_create)
    sp.add_parser("validate").set_defaults(fn=cmd_validate)
    p = sp.add_parser("selfscore")
    p.add_argument("--judge", required=True)
    p.add_argument("--sets", type=lambda s: s.split(","), required=True)
    p.add_argument("--prompt", default="assign_v2", help="file stem in prompts/")
    p.set_defaults(fn=cmd_selfscore)
    p = sp.add_parser("importance", help="2-call mode: importance in a second call")
    p.add_argument("--source", required=True, help="nugget set whose texts are relabelled")
    p.add_argument("--model", default="gpt-6.1-sol")
    p.add_argument("--prompt", default="importance_v1")
    p.set_defaults(fn=cmd_importance)
    p = sp.add_parser("align", help="cross-set alignment (plan v2 §3.5.2)")
    p.add_argument("--pairs", type=lambda s: s.split(","), required=True, help="A:B,...")
    p.add_argument("--model", default="gemini-3.8-flash")
    p.add_argument("--prompt", default="align_v1")
    p.set_defaults(fn=cmd_align)
    p = sp.add_parser("roundtrip", help="round trip (plan v2 §3.5.4)")
    p.add_argument("--set", required=True)
    p.add_argument("--writer", default="gemini-3.8-flash")
    p.add_argument("--checker", default="qwen3.8-max")
    p.add_argument("--write-prompt", default="roundtrip_write_v1")
    p.add_argument("--check-prompt", default="roundtrip_check_v2")
    p.add_argument("--name", default=None, help="output folder under roundtrip/ (default: the set)")
    p.set_defaults(fn=cmd_roundtrip)
    p = sp.add_parser("audit", help="one auditor on one set (plan v2 §3.5.3)")
    p.add_argument("--set", required=True)
    p.add_argument("--auditor", required=True)
    p.add_argument("--others", type=lambda s: s.split(","), default=None,
                   help="the two other families' sets, for omission candidates")
    p.add_argument("--candidates-from", default=None, help="primary set whose alignments give the candidates")
    p.add_argument("--only", type=lambda s: s.split(","), default=None, help="question numbers")
    p.add_argument("--prompt", default="audit_v1")
    p.set_defaults(fn=cmd_audit)
    p = sp.add_parser("repair", help="repair the issues both auditors agree on")
    p.add_argument("--set", required=True)
    p.add_argument("--auditors", type=lambda s: s.split(","), default=None,
                   help="the two auditors; omitted: repair the hard validator errors only (phase 2)")
    p.add_argument("--new", required=True, help="name of the repaired set")
    p.add_argument("--model", default="gpt-6.1-sol")
    p.add_argument("--create-prompt", default="create_v4")
    p.add_argument("--prompt", default="repair_v1")
    p.set_defaults(fn=cmd_repair)
    p = sp.add_parser("freeze", help="write the frozen set (C1 failures of both auditors dropped)")
    p.add_argument("--set", required=True)
    p.add_argument("--auditors", type=lambda s: s.split(","), default=["gemini-3.1-pro", "qwen3.8-max"])
    p.add_argument("--aligned", required=True, help="primary set of the cross-family alignments")
    p.add_argument("--others", type=lambda s: s.split(","), required=True, help="the other families' sets")
    p.add_argument("--dest", default=str(REPO / "nuggets" / "gold" / "v0-auto"))
    p.set_defaults(fn=cmd_freeze)
    p = sp.add_parser("plant", help="one planted error per question, to test the auditors")
    p.add_argument("--set", required=True)
    p.set_defaults(fn=cmd_plant)
    p = sp.add_parser("known", help="known-answer tests (plan v2 §5.7)")
    p.add_argument("action", choices=["build", "judge"])
    p.add_argument("--set", required=True)
    p.add_argument("--judge", default="gemini-3.8-flash")
    p.add_argument("--types", type=lambda s: s.split(","), default=None)
    p.add_argument("--corpus", default=str(REPO / "segmented" / "chunks_all.csv"),
                   help="build: chunk CSV whose article chunks give the VP values ('' to skip VP)")
    p.add_argument("--name", default=None, help="judge: output folder <judge>.<name> (e.g. a subset run)")
    p.add_argument("--prompt", default="assign_v2")
    p.set_defaults(fn=cmd_known)
    p = sp.add_parser("score", help="phase 5: judge RAG answers against a nugget set (plan v2 §5.2)")
    p.add_argument("--runs", nargs="+", required=True,
                   help="answer run dirs or globs relative to the repo (runs/answers/<run_id>)")
    p.add_argument("--set", default="gold", help="'gold' (nuggets/gold/v0-auto) or a set of nuggets/full/create")
    p.add_argument("--judge", default="gemini-3.8-flash")
    p.add_argument("--prompt", default="assign_v2")
    p.add_argument("--dry-run", action="store_true", help="count the uncached judge calls and estimate the cost")
    p.set_defaults(fn=cmd_score)
    p = sp.add_parser("ctxsupport", help="phase 5: judge the nuggets against the contexts themselves")
    p.add_argument("--contexts", nargs="+", required=True, help="context set dirs or globs (runs/contexts/…)")
    p.add_argument("--set", default="gold")
    p.add_argument("--judge", default="gemini-3.8-flash")
    p.add_argument("--prompt", default="assign_ctx_v1")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_ctxsupport)
    p = sp.add_parser("scoretable", help="phase 5: per-question scores, run means, paired comparisons (no LLM)")
    p.add_argument("--set", default="gold")
    p.add_argument("--judge", default="gemini-3.8-flash")
    p.add_argument("--resamples", type=int, default=10_000)
    p.set_defaults(fn=cmd_scoretable)
    sp.add_parser("report").set_defaults(fn=cmd_report)
    p = sp.add_parser("pilotreport", help="report_pilot.md (stratified_30) or report_full.md (other samples)")
    p.add_argument("--primary", default="gpt-6.1-sol", help="primary set of the alignments")
    p.add_argument("--others", type=lambda s: s.split(","), default=["gemini-3.1-pro", "qwen3.8-max"])
    p.set_defaults(fn=cmd_pilotreport)
    p = sp.add_parser("batch", help="batch jobs of --out: status | collect | wait")
    p.add_argument("action", choices=["status", "collect", "wait"])
    p.add_argument("--every", type=int, default=120, help="wait: seconds between polls")
    p.set_defaults(fn=cmd_batch)
    sp.add_parser("openrouter-key", help="credit limit and usage of OPENROUTER_API_KEY").set_defaults(
        fn=cmd_openrouter_key)
    a = ap.parse_args()
    global BATCH, ROUTE
    ROUTE = a.route
    if a.batch and ROUTE != "direct":
        sys.exit("--batch is for the direct route; through OpenRouter, GPT and Gemini use the flex endpoints")
    if a.batch:
        BATCH = llm_batch.BatchRecorder(Path(a.out))
    try:
        a.fn(a)
    except BatchPending:
        jobs = BATCH.submit(a.budget, Path(a.out) / "costs.csv", note=" ".join(sys.argv[1:]))
        for j in jobs:
            print(f"submitted {j['job']} ({j['model']}): {j['n_requests']} requests, "
                  f"≈ ${j['estimated_usd_billed']:.2f} billed")
        print("outputs not written yet: `batch wait`, then rerun this command without --batch")
    except QuotaBlocked as e:
        sys.exit(f"stopped: {e}\ncompleted calls are cached; rerun the same command after the quota resets")


if __name__ == "__main__":
    main()
