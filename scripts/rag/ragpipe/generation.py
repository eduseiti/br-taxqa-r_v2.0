"""Stage G: answer generation from the context sets of stage C (plan §7; Phase 3).

One **answer run** = one context set × one generator × one prompt. Every question of the requested
sample gets one call, answered from its context line (``contexts.jsonl.gz``) with a versioned prompt
(``prompts/answer_v1.pt.md``; the closed-book set uses ``answer_closed_v1``). The reply is JSON:
claims, each with the context documents it rests on and a verbatim quote from each
(``docs/20261021_194457_first_rag_evaluation_readiness_costs_and_grounding.md`` §4.2, option A of
2026-10-23). The answer the judge scores is the claim texts joined in order.

Grounding checks (no LLM), per answer: quotes found in the cited block of the context, document
numbers in range, values (R$, %, dates) absent from both the context and the question. Tool use and
web search are refused by the shared client (``llm_client.ToolUseDetected``).

Outputs, under ``runs/answers/<embedding>/<retrieval run>/<prompt>/<llm>/<context_id>/``::

    answers.jsonl   one line per question: the nugget-plan contract (run_id, question_number, answer)
                    + claims, checks, cited chunks, usage, cost
    run.json        configuration, inputs (context manifest, prompt and schema hashes), counts, totals

plus ``runs/answers/<embedding>/<retrieval run>/summary.csv`` (one row per run), the per-call ledger
``runs/costs.csv`` and the raw responses in ``runs/answers/cache/`` (keyed by request; reruns are free).
"""

from __future__ import annotations

import copy
import json
import logging
import re
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from .contexts import load_contexts
from .data import InputError, Paths, load_dataset
from .runs import (REPO, RunError, base_manifest, prepare_run_dir, read_json, rel, sha256_file, sha256_json,
                   write_csv, write_json)

sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "nuggets"))
from llm_client import (LLM, BudgetExceeded, CreditsExhausted, LLMError, QuotaExhausted,  # noqa: E402
                        route_config)
from nuggetizer import values as nvalues  # noqa: E402

log = logging.getLogger("ragpipe")

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
REGISTRY = Path(__file__).resolve().parents[1] / "llms.yaml"
SAMPLES = REPO / "nuggets" / "full" / "sample.json"
USER_MARK = "\n<<<USER>>>\n"
CHECKS_VERSION = 2     # 2: quotes matched on words (punctuation ignored)
#: output tokens assumed per call by ``--dry-run`` (claims + quotes; replaced by the pilot's measurement)
EST_OUTPUT_TOKENS = 1000
#: characters per token of the instructions and the question in the ``--dry-run`` estimate (pt-BR, Qwen3)
CHARS_PER_TOKEN = 3.0
MIN_QUOTE_WORDS = 3
ABSTENTION = {"answer_v1": "As disposições fornecidas não são suficientes para responder à pergunta.",
              "answer_closed_v1": "Não sei responder a esta pergunta."}

SCHEMA = {
    "type": "object",
    "properties": {     # claims first: the model writes what the context supports before flagging an abstention
        "afirmacoes": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "texto": {"type": "string"},
                "fundamentos": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"documento": {"type": "integer"}, "trecho": {"type": "string"}},
                    "required": ["documento", "trecho"], "additionalProperties": False}}},
            "required": ["texto", "fundamentos"], "additionalProperties": False}},
        "abstencao": {"type": "boolean"}},
    "required": ["afirmacoes", "abstencao"], "additionalProperties": False}
SCHEMA_NAME = "resposta"


# ------------------------------------------------------------------------------------------------
# Registry, prompts, samples
# ------------------------------------------------------------------------------------------------

def load_registry(path: Path = REGISTRY) -> tuple[dict, float]:
    d = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return d["models"], float(d["fx_brl_per_usd"])


def resolve_llm(name: str, models: dict, fx: float, allow_disabled: bool = False) -> dict:
    """The client config of one generator: its route applied, BRL prices converted to USD."""
    if name not in models:
        raise InputError(f"unknown generator {name!r} (llms.yaml has {', '.join(models)})")
    cfg = copy.deepcopy(models[name])
    if cfg.get("enabled", True) is False and not allow_disabled:
        raise InputError(f"generator {name} is disabled in llms.yaml (enabled: false)")
    if cfg.get("price", {}).get("currency") == "BRL":
        p = cfg["price"]
        cfg["price"] = {**{k: v for k, v in p.items() if not k.startswith("per_million")},
                        **{f"brl_{k}": v for k, v in p.items() if k.startswith("per_million")},
                        **{f"usd_{k}": v / fx for k, v in p.items() if k.startswith("per_million")},
                        "fx_brl_per_usd": fx}
    return route_config(cfg, cfg.get("route", "direct"))


def public_config(cfg: dict) -> dict:
    """What run.json records of a generator (no key)."""
    keys = ("provider", "route", "model_id", "base_url", "params", "routing", "served_provider", "price",
            "context_window", "knowledge_cutoff", "api_key_env")
    return {k: cfg[k] for k in keys if k in cfg}


@dataclass(frozen=True)
class Prompt:
    name: str
    system: str
    user: str
    sha256: str

    @classmethod
    def load(cls, name: str, prompts_dir: Path = PROMPTS) -> "Prompt":
        path = Path(prompts_dir) / f"{name}.pt.md"
        if not path.exists():
            raise InputError(f"prompt {rel(path)} not found")
        text = path.read_text(encoding="utf-8")
        if text.count(USER_MARK) != 1:
            raise InputError(f"{rel(path)}: expected one line '<<<USER>>>' between the system and user parts")
        system, user = text.split(USER_MARK)
        return cls(name, system.strip(), user.strip(), sha256_file(path))

    def render(self, question: str, context: str) -> str:
        return self.user.replace("{context}", context).replace("{question}", question)


def sample_questions(sample: str, all_ids: list[str], samples_file: Path = SAMPLES) -> list[str]:
    """``all``, a sample name of ``nuggets/full/sample.json`` (``stratified_30``, …) or a comma list."""
    if sample == "all":
        return list(all_ids)
    if re.fullmatch(r"[\d,\s]+", sample):
        ids = [s.strip() for s in sample.split(",") if s.strip()]
    else:
        s = read_json(samples_file)
        if sample not in s:
            raise InputError(f"no sample {sample!r} in {rel(samples_file)}")
        ids = list(s[sample])
    unknown = [q for q in ids if q not in set(all_ids)]
    if unknown:
        raise InputError(f"unknown question numbers {unknown[:5]}")
    return ids


# ------------------------------------------------------------------------------------------------
# Grounding checks (no LLM)
# ------------------------------------------------------------------------------------------------

_BLOCK = re.compile(r"^\[Documento (\d+)\] ", re.M)
_ELLIPSIS = re.compile(r"\s*(?:\[\s*(?:\.\.\.|…)\s*\]|\(\s*(?:\.\.\.|…)\s*\)|\.\.\.|…)\s*")
_QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "«": '"', "»": '"', "‘": "'", "’": "'", "´": "'",
                         "–": "-", "—": "-", "‑": "-", " ": " "})


def split_blocks(context: str) -> dict[int, str]:
    """``{n: text of [Documento n]}`` of a rendered context (header and ementa included)."""
    marks = list(_BLOCK.finditer(context))
    return {int(m.group(1)): context[m.start(): marks[i + 1].start() if i + 1 < len(marks) else len(context)]
            for i, m in enumerate(marks)}


def norm(s: str) -> str:
    """Words only: NFKC, case-folded, punctuation and spacing dropped (``§`` and ``º`` kept as words)."""
    s = unicodedata.normalize("NFKC", s).translate(_QUOTES).casefold()
    return " ".join(re.findall(r"[\w§º°ª]+", s))


def quote_status(trecho: str, block: str | None) -> str:
    """``ok`` | ``bad_document`` | ``too_short`` | ``not_found``. The quote's words must appear in the cited
    block in the same order and contiguously (punctuation, case and spacing ignored); an ellipsis may skip
    text, whose pieces must then appear in order."""
    if block is None:
        return "bad_document"
    pieces = [p for p in (norm(x) for x in _ELLIPSIS.split(trecho)) if p]
    if sum(len(p.split()) for p in pieces) < MIN_QUOTE_WORDS:
        return "too_short"
    hay, pos = f" {norm(block)} ", 0
    for p in pieces:
        i = hay.find(f" {p} ", pos)
        if i < 0:
            return "not_found"
        pos = i + len(p) + 1
    return "ok"


def value_keys(text: str) -> set[tuple[str, object]]:
    out = set()
    for v in nvalues.extract(text):
        out.add((v["kind"], v["normalized"]))
        if v["kind"] == "date":     # a date without a year matches the same day and month with one
            out.add(("date_md", str(v["normalized"])[-5:]))
    return out


def check_answer(data: dict, ctx_line: dict, question: str) -> tuple[list[dict], dict, list[str]]:
    """Claims with per-quote status, the answer's checks, and the cited chunk ids."""
    blocks = split_blocks(ctx_line["context"])
    by_n = {it["n"]: it for it in ctx_line["items"]}
    claims, cited = [], []
    n_quotes = n_ok = n_bad_doc = grounded = 0
    for c in data.get("afirmacoes") or []:
        funds = []
        for f in c.get("fundamentos") or []:
            st = quote_status(f.get("trecho", ""), blocks.get(f.get("documento")))
            funds.append({**f, "status": st})
            n_quotes += 1
            n_ok += st == "ok"
            n_bad_doc += st == "bad_document"
            it = by_n.get(f.get("documento"))
            if it and it["chunk_id"] not in cited:
                cited.append(it["chunk_id"])
        grounded += any(f["status"] == "ok" for f in funds)
        claims.append({"texto": c.get("texto", ""), "fundamentos": funds})
    answer_text = "\n".join(c["texto"] for c in claims)
    present = value_keys(ctx_line["context"] + "\n" + question)
    missing = []
    for v in nvalues.extract(answer_text):
        k = (v["kind"], v["normalized"])
        if k in present or (v["kind"] == "date" and ("date_md", str(v["normalized"])[-5:]) in present):
            continue
        missing.append(v["raw"])
    checks = {"n_claims": len(claims), "n_quotes": n_quotes, "quotes_ok": n_ok, "quotes_bad_document": n_bad_doc,
              "claims_grounded": grounded, "claims_without_quote": sum(not c["fundamentos"] for c in claims),
              "values_not_in_context": missing,
              "abstention_inconsistent": bool(data.get("abstencao")) and bool(claims)}
    return claims, checks, cited


def validate_shape(data: dict) -> None:
    """Retry trigger: the reply must have the schema's shape (the strict schema should already ensure it)."""
    if not isinstance(data, dict) or not isinstance(data.get("abstencao"), bool) \
            or not isinstance(data.get("afirmacoes"), list):
        raise ValueError("reply is not {abstencao, afirmacoes}")
    for c in data["afirmacoes"]:
        if not isinstance(c, dict) or not isinstance(c.get("texto"), str) or not isinstance(c.get("fundamentos"), list):
            raise ValueError("claim is not {texto, fundamentos}")
        for f in c["fundamentos"]:
            if not isinstance(f, dict) or not isinstance(f.get("documento"), int) or not isinstance(f.get("trecho"), str):
                raise ValueError("fundamento is not {documento, trecho}")


# ------------------------------------------------------------------------------------------------
# Runs
# ------------------------------------------------------------------------------------------------

@dataclass
class GenConfig:
    contexts: Path                           # runs/contexts/<embedding>/<retrieval run>
    sets: tuple[str, ...]                    # context ids under it
    llms: tuple[str, ...]
    sample: str = "stratified_30"
    prompt: str = "answer_v1"
    closed_prompt: str = "answer_closed_v1"
    workers: int = 8                         # concurrent calls per generator
    budget_usd: float | None = None          # cap on the ledger total (runs/costs.csv); required unless dry_run
    dry_run: bool = False
    force: bool = False
    registry: Path = REGISTRY
    experiment: str | None = None            # name of the experiment file, recorded in run.json

    def prompt_for(self, kind: str) -> str:
        return self.closed_prompt if kind == "closed_book" else self.prompt


@dataclass
class Run:
    llm_name: str
    cfg: dict
    context_id: str
    context_dir: Path
    prompt: Prompt
    out: Path
    run_id: str
    lines: list[dict]                        # context lines of the sample
    context_manifest: dict
    config_hash: str = ""
    results: dict = field(default_factory=dict)


def plan_runs(cfg: GenConfig, paths: Paths) -> tuple[list[Run], dict[str, str]]:
    root = Path(cfg.contexts)
    if not root.is_dir():
        raise InputError(f"{rel(root)} is not a context folder; run `rag.py context`")
    embedding, retrieval_run = root.parent.name, root.name
    ds = load_dataset(paths.dataset)
    questions = dict(zip(ds.questions["question_number"], ds.questions["question_text"]))
    qids = sample_questions(cfg.sample, ds.question_ids)
    models, fx = load_registry(cfg.registry)
    llm_cfgs = {n: resolve_llm(n, models, fx) for n in cfg.llms}
    prompts: dict[str, Prompt] = {}
    runs = []
    for cid in cfg.sets:
        cdir = root / cid
        if not (cdir / "manifest.json").exists():
            raise InputError(f"no context set {cid} in {rel(root)}")
        cman = read_json(cdir / "manifest.json")
        sha = sha256_file(cdir / "contexts.jsonl.gz")
        if sha != cman["outputs"]["contexts.jsonl.gz"]["sha256"]:
            raise InputError(f"{rel(cdir / 'contexts.jsonl.gz')} changed after `rag.py context`; rebuild it")
        by_q = {ln["question_number"]: ln for ln in load_contexts(cdir)}
        lines = [by_q[q] for q in qids]
        kind = cman["params"]["set"]
        pname = cfg.prompt_for(kind)
        prompts.setdefault(pname, Prompt.load(pname))
        for name, lc in llm_cfgs.items():
            out = paths.runs / "answers" / embedding / retrieval_run / pname / name / cid
            run_id = f"{embedding}/{retrieval_run}/{pname}/{name}/{cid}"
            r = Run(name, lc, cid, cdir, prompts[pname], out, run_id, lines,
                    {"path": rel(cdir / "manifest.json"), "config_hash": cman["config_hash"],
                     "contexts_sha256": sha, "set": kind, "template": cman["params"].get("template")})
            r.config_hash = sha256_json({"llm": public_config(lc), "prompt": {"name": pname, "sha256": r.prompt.sha256},
                                         "schema": sha256_json(SCHEMA), "context": r.context_manifest,
                                         "checks_version": CHECKS_VERSION})
            runs.append(r)
    return runs, questions


def estimate(runs: list[Run], questions: dict[str, str], cache_dir: Path) -> pd.DataFrame:
    """Calls and list-price cost per run (input: rendered context + instructions + question)."""
    rows = []
    for r in runs:
        m = LLM(r.llm_name, r.cfg, cache_dir, offline=True)
        n_calls = n_cached = 0
        tin = 0.0
        for ln in r.lines:
            if ln["kind"] != "closed_book" and ln["n_texts"] == 0:
                continue
            user = r.prompt.render(questions[ln["question_number"]], ln["context"])
            n_calls += 1
            if m.is_cached(r.prompt.system, user, SCHEMA):
                n_cached += 1
                continue
            ctx_tokens = ln["rendered_tokens_qwen3"]           # None when the contexts were built without counts
            if ctx_tokens is None:
                ctx_tokens = ln["rendered_chars"] / CHARS_PER_TOKEN
            tin += ctx_tokens + (len(r.prompt.system) + len(user) - ln["rendered_chars"]) / CHARS_PER_TOKEN
        p = r.cfg["price"]
        new = n_calls - n_cached
        usd = (tin * p["usd_per_million_input"] + new * EST_OUTPUT_TOKENS * p["usd_per_million_output"]) / 1e6
        rows.append({"run_id": r.run_id, "llm": r.llm_name, "context_id": r.context_id, "calls": n_calls,
                     "cached": n_cached, "new_calls": new, "est_input_tokens": round(tin),
                     "est_output_tokens": new * EST_OUTPUT_TOKENS, "est_usd_list": round(usd, 4)})
    return pd.DataFrame(rows)


def answer_line(r: Run, ln: dict, question: str, res=None, error: str | None = None) -> dict:
    base = {"run_id": r.run_id, "question_number": ln["question_number"], "context_id": r.context_id,
            "n_texts": ln["n_texts"], "rendered_tokens_qwen3": ln["rendered_tokens_qwen3"]}
    if error is not None:
        return {**base, "status": "error", "answer": None, "error": error}
    if res is None:
        return {**base, "status": "skipped", "answer": None, "reason": "empty_context"}
    claims, checks, cited = check_answer(res.data, ln, question)
    abstained = not claims      # abstencao with no claim, or an empty claim list (abstencao with claims is flagged)
    answer = ABSTENTION.get(r.prompt.name, ABSTENTION["answer_v1"]) if not claims else "\n".join(c["texto"] for c in claims)
    return {**base, "status": "ok", "answer": answer, "abstained": abstained, "claims": claims, "checks": checks,
            "cited_chunk_ids": cited, "answer_chars": len(answer) if claims else 0,
            "usage": res.usage.__dict__, "usd_list": round(res.cost_usd, 6), "usd_billed": res.meta.get("usd_billed"),
            "from_cache": res.from_cache, "model_served": res.model_served,
            "provider_served": res.meta.get("provider"), "finish": res.meta.get("finish"),
            "attempts": res.attempts, "latency_s": round(res.latency_s, 1), "cache_key": res.cache_key}


def run_summary(lines: list[dict]) -> dict:
    ok = [ln for ln in lines if ln["status"] == "ok"]
    ans = [ln for ln in ok if not ln["abstained"]]
    nq = sum(ln["checks"]["n_quotes"] for ln in ok)
    ncl = sum(ln["checks"]["n_claims"] for ln in ok)
    new = [ln for ln in ok if not ln["from_cache"]]

    def mean(xs):
        xs = list(xs)
        return round(sum(xs) / len(xs), 4) if xs else None
    return {"questions": len(lines), "ok": len(ok), "errors": sum(ln["status"] == "error" for ln in lines),
            "skipped": sum(ln["status"] == "skipped" for ln in lines),
            "abstention_rate": mean(ln["abstained"] for ln in ok),
            "mean_claims": mean(ln["checks"]["n_claims"] for ln in ans),
            "mean_answer_chars": mean(ln["answer_chars"] for ln in ans),
            "mean_input_tokens": mean(ln["usage"]["input"] for ln in ok),
            "mean_output_tokens": mean(ln["usage"]["output"] for ln in ok),
            "max_output_tokens": max((ln["usage"]["output"] for ln in ok), default=None),
            "quote_ok_rate": round(sum(ln["checks"]["quotes_ok"] for ln in ok) / nq, 4) if nq else None,
            "quote_bad_document": sum(ln["checks"]["quotes_bad_document"] for ln in ok),
            "claim_grounded_rate": round(sum(ln["checks"]["claims_grounded"] for ln in ok) / ncl, 4) if ncl else None,
            "answers_with_value_not_in_context": mean(bool(ln["checks"]["values_not_in_context"]) for ln in ans),
            "abstention_inconsistent": sum(ln["checks"]["abstention_inconsistent"] for ln in ok),
            "retried": sum(ln["attempts"] > 1 for ln in ok),
            "usd_list": round(sum(ln["usd_list"] for ln in ok), 6),
            "usd_billed_new_calls": round(sum(ln["usd_billed"] or ln["usd_list"] for ln in new), 6),
            "new_calls": len(new)}


def write_run(r: Run, cfg: GenConfig, new_lines: list[dict], complete: bool) -> dict:
    """Merge the new lines into the run's ``answers.jsonl`` (lines of other questions are kept) and write run.json."""
    path = r.out / "answers.jsonl"
    old = {}
    same = (r.out / "run.json").exists() and read_json(r.out / "run.json").get("config_hash") == r.config_hash
    if path.exists() and same:     # --force over another configuration starts the file afresh
        old = {d["question_number"]: d for d in map(json.loads, path.read_text(encoding="utf-8").splitlines())}
    old.update({d["question_number"]: d for d in new_lines})
    lines = [old[q] for q in sorted(old)]
    path.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in lines), encoding="utf-8")
    stats = run_summary(lines)
    man = base_manifest("answers")
    man.update({"config_hash": r.config_hash, "run_id": r.run_id, "complete": complete,
                "experiment": cfg.experiment, "sample_requested": cfg.sample,
                "llm": {"name": r.llm_name, **public_config(r.cfg)},
                "prompt": {"name": r.prompt.name, "path": rel(PROMPTS / f"{r.prompt.name}.pt.md"),
                           "sha256": r.prompt.sha256},
                "schema": {"name": SCHEMA_NAME, "sha256": sha256_json(SCHEMA)}, "checks_version": CHECKS_VERSION,
                "context": r.context_manifest, "counts": stats,
                "outputs": {"answers.jsonl": {"sha256": sha256_file(path)}}})
    write_json(r.out / "run.json", man)
    return {"run_id": r.run_id, "prompt": r.prompt.name, "llm": r.llm_name, "context_id": r.context_id, **stats}


def run_generation(cfg: GenConfig, paths: Paths = Paths()) -> tuple[Path, pd.DataFrame]:
    """Plan, size and (unless ``dry_run``) execute the runs; return the summary folder and table."""
    runs, questions = plan_runs(cfg, paths)
    cache_dir = paths.runs / "answers" / "cache"
    est = estimate(runs, questions, cache_dir)
    root = paths.runs / "answers" / Path(cfg.contexts).parent.name / Path(cfg.contexts).name
    if cfg.dry_run:
        return root, est
    if cfg.budget_usd is None:
        raise InputError("--budget is required (USD cap on the total of runs/costs.csv); size the grid with --dry-run")
    for r in runs:     # before any call: refuse to mix configurations in one run folder
        man = r.out / "run.json"
        if man.exists() and not cfg.force and read_json(man).get("config_hash") != r.config_hash:
            raise RunError(f"{rel(r.out)} holds a run with another configuration; pass --force to replace it")
    ledger = paths.runs / "costs.csv"
    clients = {n: LLM(n, runs[[r.llm_name for r in runs].index(n)].cfg, cache_dir, ledger,
                      budget_usd=cfg.budget_usd, check_billed=True) for n in dict.fromkeys(r.llm_name for r in runs)}
    sems = {n: threading.Semaphore(cfg.workers) for n in clients}
    stop = threading.Event()
    fatal: list[str] = []

    def task(r: Run, ln: dict):
        q = ln["question_number"]
        if stop.is_set():
            return None
        if ln["kind"] != "closed_book" and ln["n_texts"] == 0:
            return answer_line(r, ln, questions[q])
        user = r.prompt.render(questions[q], ln["context"])
        with sems[r.llm_name]:
            if stop.is_set():
                return None
            try:
                res = clients[r.llm_name].complete_json(r.prompt.system, user, SCHEMA, SCHEMA_NAME,
                                                        validate=validate_shape, tag=f"answer:{r.context_id}:{q}")
            except (BudgetExceeded, CreditsExhausted, QuotaExhausted) as e:
                stop.set()
                fatal.append(f"{type(e).__name__}: {e}")
                return None
            except LLMError as e:
                log.warning("%s Q%s: %s", r.run_id, q, e)
                return answer_line(r, ln, questions[q], error=f"{type(e).__name__}: {str(e)[:500]}")
            except Exception as e:  # noqa: BLE001 - recorded per question, never silently dropped
                log.warning("%s Q%s: %s", r.run_id, q, e)
                return answer_line(r, ln, questions[q], error=f"{type(e).__name__}: {str(e)[:500]}")
        return answer_line(r, ln, questions[q], res)

    t0 = time.time()
    jobs = [(r, ln) for r in runs for ln in r.lines]
    log.info("%d runs, %d questions each, %d calls at most (%d cached); estimated list cost $%.2f",
             len(runs), len(runs[0].lines) if runs else 0, int(est["calls"].sum()), int(est["cached"].sum()),
             est["est_usd_list"].sum())
    done = 0
    with ThreadPoolExecutor(max_workers=cfg.workers * len(clients)) as ex:
        futs = [(r, ex.submit(task, r, ln)) for r, ln in jobs]
        for r, f in futs:
            line = f.result()
            if line is not None:
                r.results[line["question_number"]] = line
            done += 1
            if done % 100 == 0:
                log.info("%d / %d answered (%.0fs)", done, len(jobs), time.time() - t0)
    rows = []
    for r in runs:
        prepare_run_dir(r.out, r.config_hash, True)    # mismatches were refused above (or --force)
        lines = list(r.results.values())
        rows.append(write_run(r, cfg, lines, complete=len(lines) == len(r.lines)))
    write_summary(root, pd.DataFrame(rows))
    if fatal:
        raise RunError(f"stopped: {fatal[0]} — the finished calls are cached and written; rerun the same command "
                       "to resume")
    log.info("generation done in %.0fs", time.time() - t0)
    return root, pd.DataFrame(rows)


def write_summary(root: Path, new: pd.DataFrame) -> None:
    """``summary.csv``: one row per answer run; rows of other runs are kept."""
    path = root / "summary.csv"
    if path.exists():
        old = pd.read_csv(path, keep_default_na=False)
        new = pd.concat([old[~old["run_id"].isin(new["run_id"])], new], ignore_index=True)
    write_csv(new.sort_values("run_id", kind="stable"), path)


def load_answers(run_dir: Path) -> list[dict]:
    path = Path(run_dir) / "answers.jsonl"
    if not path.exists():
        raise InputError(f"{rel(path)} not found; run `rag.py generate` first")
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def load_experiment(path: Path) -> dict:
    """An experiment file (``scripts/rag/experiments/*.yaml``): name, contexts, sets, llms, sample, prompts."""
    d = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in ("name", "contexts", "sets", "llms") if k not in d]
    if missing:
        raise InputError(f"{rel(path)}: missing {missing}")
    return d
