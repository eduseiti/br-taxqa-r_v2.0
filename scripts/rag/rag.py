#!/usr/bin/env python3
"""RAG pipeline of the BR-TaxQA-R v2.0 segmentation experiment — Phase 1: retrieval and its
evaluation (the legal-provision test); Phase 2: generator contexts; Phase 3: answer generation.

Plan: docs/20260927_204356_rag_pipeline_implementation_plan.md. Usage (from the repository root):

  python scripts/rag/rag.py check    --embedding jua-4b-mixed
  python scripts/rag/rag.py retrieve --embedding jua-4b-mixed [--instruction irpf] [--strategies S1,S2,S3] [--top-n 1000]
  python scripts/rag/rag.py evaluate --retrieval runs/retrieval/jua-4b-mixed/irpf [--annex-rule either]
  python scripts/rag/rag.py compare  --retrieval runs/retrieval/jua-4b-mixed/irpf --a S1 --b S2
  python scripts/rag/rag.py report   --eval runs/retrieval/jua-4b-mixed/irpf/eval/either_containment_skip
  python scripts/rag/rag.py context  --retrieval runs/retrieval/jua-4b-mixed/irpf [--sets S2@budget=4000,closed_book]
  python scripts/rag/rag.py show-context --context runs/contexts/jua-4b-mixed/irpf/S2_budget4000 --questions 012
  python scripts/rag/rag.py generate --contexts runs/contexts/jua-4b-mixed/irpf --sets S2_budget4000 --llms sabia-4 \
      --sample stratified_30 --budget 5 [--dry-run]
  python scripts/rag/rag.py run      --experiment scripts/rag/experiments/pilot.yaml --budget 30 [--dry-run]
  python scripts/rag/rag.py show-answers --run runs/answers/jua-4b-mixed/irpf/answer_v1/sabia-4/S2_budget4000 --questions 350
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pandas as pd  # noqa: E402

from ragpipe.contexts import DEFAULT_SETS, ContextConfig, load_contexts, run_contexts  # noqa: E402
from ragpipe.data import (InputError, Paths, check_inputs, default_instruction, load_chunks,  # noqa: E402
                          load_dataset, load_embedding)
from ragpipe.evaluation import EvalConfig, compare, run_evaluation  # noqa: E402
from ragpipe.generation import GenConfig, load_answers, load_experiment, run_generation  # noqa: E402
from ragpipe.relevance import ANNEX_RULES  # noqa: E402
from ragpipe.report import comparison_table, write_report  # noqa: E402
from ragpipe.retrieval import RetrievalConfig, run_retrieval  # noqa: E402
from ragpipe.runs import RunError, rel, sha256_file, write_csv  # noqa: E402

log = logging.getLogger("ragpipe")


def int_list(s: str) -> tuple[int, ...]:
    return tuple(int(x) for x in s.split(",") if x.strip())


def str_list(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def paths_from(args: argparse.Namespace) -> Paths:
    d = Paths()
    return Paths(repo=d.repo, chunks=Path(args.chunks) if args.chunks else d.chunks,
                 dataset=Path(args.dataset) if args.dataset else d.dataset,
                 embeddings=Path(args.embeddings_dir) if args.embeddings_dir else d.embeddings,
                 runs=Path(args.runs_dir) if args.runs_dir else d.runs,
                 strategies=Path(args.strategies_file) if args.strategies_file else d.strategies,
                 chapters=d.chapters)


# ------------------------------------------------------------------------------------------------
# Subcommands
# ------------------------------------------------------------------------------------------------

def cmd_check(args: argparse.Namespace) -> int:
    paths = paths_from(args)
    instruction = args.instruction or default_instruction(paths.embeddings, args.embedding)
    chunks = load_chunks(paths.chunks)
    rep = check_inputs(chunks, sha256_file(paths.chunks), load_embedding(paths.embeddings, args.embedding, instruction),
                       load_dataset(paths.dataset), hash_vectors=not args.no_hash)
    print(json.dumps(rep.to_dict(), indent=2, ensure_ascii=False))
    print("check: OK" if rep.ok else "check: FAILED", file=sys.stderr)
    return 0 if rep.ok else 1


def cmd_retrieve(args: argparse.Namespace) -> int:
    paths = paths_from(args)
    instruction = args.instruction or default_instruction(paths.embeddings, args.embedding)
    cfg = RetrievalConfig(embedding=args.embedding, instruction=instruction,
                          strategies=str_list(args.strategies) if args.strategies else None, top_n=args.top_n,
                          block_size=args.block_size, hash_vectors=not args.no_hash, force=args.force,
                          run_name=args.run_name,
                          exclusions=None if args.exclusions == "none" else (Path(args.exclusions) if args.exclusions
                                                                             else "default"))
    out = run_retrieval(cfg, paths)
    print(f"rankings written to {rel(out)}")
    return 0


def eval_config(args: argparse.Namespace) -> EvalConfig:
    pairs = tuple(tuple(p.split(":")) for p in str_list(args.comparisons)) if args.comparisons else EvalConfig.comparisons
    return EvalConfig(annex_rule=args.annex_rule, budgets=int_list(args.budgets), unit_ks=int_list(args.unit_ks),
                      raw_ks=int_list(args.raw_ks), dedup=args.dedup, overflow=args.overflow,
                      strategies=str_list(args.strategies) if args.strategies else None, comparisons=pairs,
                      n_resamples=args.resamples, seed=args.seed, eval_id=args.eval_id, force=args.force)


def cmd_evaluate(args: argparse.Namespace) -> int:
    paths = paths_from(args)
    out = run_evaluation(Path(args.retrieval), eval_config(args), paths)
    print(f"evaluation written to {rel(out)} (see report.md)")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    eval_dir = Path(args.retrieval) / "eval" / (args.eval_id or EvalConfig(annex_rule=args.annex_rule).resolved_eval_id)
    pq_path = eval_dir / "per_question.csv.gz"
    if not pq_path.exists():
        raise InputError(f"{rel(pq_path)} not found; run `rag.py evaluate --retrieval {args.retrieval}` first")
    pq = pd.read_csv(pq_path, dtype={"question_number": str, "cutoff": str})
    views = tuple(str_list(args.views))
    c = compare(pq, args.a, args.b, args.resamples, args.seed, views=views)
    if c.empty:
        raise InputError(f"no per-question rows for both {args.a} and {args.b} in {rel(pq_path)}")
    out = eval_dir / f"compare_{args.a}_vs_{args.b}.csv"
    write_csv(c, out)
    print(comparison_table(c, []))
    print(f"\nall metrics: {rel(out)}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    out = write_report(Path(args.eval))
    print(f"report written to {rel(out)}")
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    paths = paths_from(args)
    cfg = ContextConfig(sets=tuple(str_list(args.sets)), dedup=args.dedup, overflow=args.overflow, order=args.order,
                        template=args.template, annex_rule=args.annex_rule, oracle_strategy=args.oracle_strategy,
                        seed=args.seed, count_tokens=not args.no_token_count, eval_id=args.eval_id, force=args.force)
    out = run_contexts(Path(args.retrieval), cfg, paths)
    print(f"contexts written under {rel(out)} (see summary.csv)")
    return 0


def cmd_show_context(args: argparse.Namespace) -> int:
    lines = {ln["question_number"]: ln for ln in load_contexts(Path(args.context))}
    for q in str_list(args.questions):
        ln = lines.get(q)
        if ln is None:
            raise InputError(f"question {q} not in {args.context}")
        cov = "; ".join(f"{lv} {len(c['full'])}/{c['n']}" for lv, c in ln["gold"].items() if c["n"])
        print(f"## {ln['context_id']} — question {q}" + (f" (donor {ln['donor_question']})" if "donor_question" in ln
                                                        else ""))
        print(f"{ln['n_texts']} texts, {ln['context_tokens_qwen3']} text tokens, "
              f"{ln['rendered_tokens_qwen3']} rendered tokens (Qwen3); gold in context: {cov or 'no gold'}\n")
        for it in ln["items"]:
            print(f"  {it['n']:>3}  rank {it['rank'] if it['rank'] is not None else '-':>4}  {it['tokens_qwen3']:>5} tok  "
                  f"{it['chunk_id']}  {it['fonte']}")
        if not args.no_text:
            print("\n" + (ln["context"] if args.max_chars <= 0 else ln["context"][:args.max_chars]))
        print()
    return 0


def print_generation(root: Path, df: pd.DataFrame, dry_run: bool) -> None:
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    if dry_run:
        print(df.drop(columns=["run_id"]).to_string(index=False))
        print(f"\n{len(df)} runs, {int(df['calls'].sum())} calls ({int(df['cached'].sum())} cached), "
              f"estimated list cost ${df['est_usd_list'].sum():.2f} "
              f"(output assumed {int(df['est_output_tokens'].sum() / max(int(df['new_calls'].sum()), 1))} "
              "tokens per call; flex endpoints bill about half). Nothing was sent.")
        return
    cols = ["llm", "context_id", "ok", "errors", "skipped", "abstention_rate", "mean_claims", "quote_ok_rate",
            "claim_grounded_rate", "mean_output_tokens", "usd_list"]
    print(df[cols].to_string(index=False))
    print(f"\nanswers written under {rel(root)} (see summary.csv); list cost of these runs ${df['usd_list'].sum():.2f}")


def generation_config(args: argparse.Namespace, **over) -> GenConfig:
    kw = dict(workers=args.workers, budget_usd=args.budget, dry_run=args.dry_run, force=args.force)
    if args.registry:
        kw["registry"] = Path(args.registry)
    kw.update(over)
    return GenConfig(**kw)


def cmd_generate(args: argparse.Namespace) -> int:
    cfg = generation_config(args, contexts=Path(args.contexts), sets=tuple(str_list(args.sets)),
                            llms=tuple(str_list(args.llms)), sample=args.sample, prompt=args.prompt,
                            closed_prompt=args.closed_prompt)
    root, df = run_generation(cfg, paths_from(args))
    print_generation(root, df, args.dry_run)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    e = load_experiment(Path(args.experiment))
    prompts = e.get("prompts", {})
    cfg = generation_config(args, contexts=Path(e["contexts"]), sets=tuple(e["sets"]), llms=tuple(e["llms"]),
                            sample=args.sample or str(e.get("sample", "stratified_30")),
                            prompt=prompts.get("default", "answer_v1"),
                            closed_prompt=prompts.get("closed_book", "answer_closed_v1"),
                            experiment=f"{e['name']} ({rel(Path(args.experiment))})")
    root, df = run_generation(cfg, paths_from(args))
    print_generation(root, df, args.dry_run)
    return 0


def cmd_show_answers(args: argparse.Namespace) -> int:
    lines = {ln["question_number"]: ln for ln in load_answers(Path(args.run))}
    for q in str_list(args.questions):
        ln = lines.get(q)
        if ln is None:
            raise InputError(f"question {q} not in {args.run}")
        print(f"## {ln['run_id']} — question {q} ({ln['status']})")
        if ln["status"] != "ok":
            print(ln.get("error") or ln.get("reason"), "\n")
            continue
        c = ln["checks"]
        print(f"{c['n_claims']} claims, {c['claims_grounded']} grounded; quotes {c['quotes_ok']}/{c['n_quotes']} ok; "
              f"values not in context: {c['values_not_in_context'] or '-'}; tokens {ln['usage']['input']} in / "
              f"{ln['usage']['output']} out\n")
        if ln["abstained"]:
            print(f"[abstention] {ln['answer']}\n")
        for i, cl in enumerate(ln["claims"], 1):
            print(f"{i}. {cl['texto']}")
            for f in cl["fundamentos"]:
                print(f"     [Documento {f['documento']}] {f['status']}: \"{f['trecho']}\"")
        print()
    return 0


# ------------------------------------------------------------------------------------------------
# Parser
# ------------------------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    fmt = argparse.RawDescriptionHelpFormatter
    p = argparse.ArgumentParser(description=__doc__, formatter_class=fmt)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        g = sp.add_argument_group("input/output locations (defaults: the repository layout)")
        g.add_argument("--chunks", help="chunk CSV (default segmented/chunks_all.csv.gz)")
        g.add_argument("--dataset", help="directory with questions/references/documents.jsonl (default dataset/)")
        g.add_argument("--embeddings-dir", help="embedding outputs (default embeddings/)")
        g.add_argument("--runs-dir", help="run outputs (default runs/)")
        g.add_argument("--strategies-file", help="strategy definitions (default scripts/rag/strategies.yaml)")

    def epilog(s: str) -> str:
        return "example:\n  " + textwrap.dedent(s).strip()

    sp = sub.add_parser("check", help="input checks only (plan §8.3)", formatter_class=fmt,
                        epilog=epilog("python scripts/rag/rag.py check --embedding jua-4b-mixed"))
    sp.add_argument("--embedding", required=True, help="embedding slug under embeddings/")
    sp.add_argument("--instruction", help="query instruction name (default: irpf, or the only one)")
    sp.add_argument("--no-hash", action="store_true", help="skip hashing the vector files")
    common(sp)
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("retrieve", help="stage R: rank the chunks of each strategy", formatter_class=fmt,
                        epilog=epilog("python scripts/rag/rag.py retrieve --embedding jua-4b-mixed --strategies S1,S2,S3"))
    sp.add_argument("--embedding", required=True, help="embedding slug under embeddings/")
    sp.add_argument("--instruction", help="query instruction name (default: irpf, or the only one)")
    sp.add_argument("--strategies", help="comma list (default: all in strategies.yaml)")
    sp.add_argument("--top-n", type=int, default=1000, help="texts kept per question and strategy (default 1000)")
    sp.add_argument("--block-size", type=int, default=128, help="queries per scoring block (default 128)")
    sp.add_argument("--run-name", help="output runs/retrieval/<embedding>/<run name> (default: the instruction)")
    sp.add_argument("--exclusions", help="corpus exclusion list (default scripts/rag/corpus_exclusions.yaml; "
                                         "'none' for no exclusion)")
    sp.add_argument("--no-hash", action="store_true", help="skip hashing the vector files")
    sp.add_argument("--force", action="store_true", help="replace a run made with another configuration")
    common(sp)
    sp.set_defaults(func=cmd_retrieve)

    sp = sub.add_parser("evaluate", help="stage RE: the legal-provision retrieval test", formatter_class=fmt,
                        epilog=epilog("python scripts/rag/rag.py evaluate --retrieval runs/retrieval/jua-4b-mixed/irpf"))
    sp.add_argument("--retrieval", required=True, help="retrieval run directory")
    sp.add_argument("--annex-rule", choices=ANNEX_RULES, default="either", help="G3 main/annex rule (default either)")
    sp.add_argument("--budgets", default="1000,2000,4000,8000,16000", help="token budgets (Qwen3 tokens)")
    sp.add_argument("--unit-ks", default="1,3,5,10,20,50,100", help="cutoffs of the unit-projection view")
    sp.add_argument("--raw-ks", default="1,5,10,20,50,100,1000", help="cutoffs of the raw-rank view")
    sp.add_argument("--dedup", choices=("containment_merge", "containment", "none"), default="containment_merge")
    sp.add_argument("--overflow", choices=("skip", "stop"), default="skip")
    sp.add_argument("--strategies", help="comma list (default: all in the retrieval run)")
    sp.add_argument("--comparisons", help="pairs A:B, comma separated (default S1:S2,S2:S3,S2:S2c,S3:S4,S1:S2c)")
    sp.add_argument("--resamples", type=int, default=10_000)
    sp.add_argument("--seed", type=int, default=13)
    sp.add_argument("--eval-id", help="output name under eval/ (default <annex_rule>_<dedup>_<overflow>)")
    sp.add_argument("--force", action="store_true", help="replace an evaluation made with another configuration")
    common(sp)
    sp.set_defaults(func=cmd_evaluate)

    sp = sub.add_parser("compare", help="paired comparison of two strategies", formatter_class=fmt,
                        epilog=epilog("python scripts/rag/rag.py compare --retrieval runs/retrieval/jua-4b-mixed/irpf "
                                      "--a S1 --b S2"))
    sp.add_argument("--retrieval", required=True, help="retrieval run directory")
    sp.add_argument("--a", required=True, help="baseline strategy")
    sp.add_argument("--b", required=True, help="strategy compared with the baseline (diff = b − a)")
    sp.add_argument("--annex-rule", choices=ANNEX_RULES, default="either", help="selects the default eval id")
    sp.add_argument("--eval-id", help="evaluation to read (default <annex_rule>_containment_skip)")
    sp.add_argument("--views", default="budget,unit,raw")
    sp.add_argument("--resamples", type=int, default=10_000)
    sp.add_argument("--seed", type=int, default=13)
    sp.set_defaults(func=cmd_compare)

    sp = sub.add_parser("report", help="regenerate report.md of an evaluation", formatter_class=fmt,
                        epilog=epilog("python scripts/rag/rag.py report --eval "
                                      "runs/retrieval/jua-4b-mixed/irpf/eval/either_containment_skip"))
    sp.add_argument("--eval", required=True, help="evaluation directory")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("context", help="stage C: build the generator contexts (plan §6)", formatter_class=fmt,
                        epilog=epilog("python scripts/rag/rag.py context --retrieval runs/retrieval/jua-4b-mixed/irpf "
                                      "--sets S1@budget=4000,S2@budget=4000,closed_book,oracle@budget=4000"))
    sp.add_argument("--retrieval", required=True, help="retrieval run directory")
    sp.add_argument("--sets", default=",".join(DEFAULT_SETS),
                    help="context sets: <strategy>@budget=<tokens> | <strategy>@k=<n> | closed_book | "
                         "oracle@<cutoff> | wrong:<strategy>@<cutoff> (default: the pilot grid)")
    sp.add_argument("--dedup", choices=("containment_merge", "containment", "none"), default="containment_merge")
    sp.add_argument("--overflow", choices=("skip", "stop"), default="skip")
    sp.add_argument("--order", choices=("score", "document"), default="score",
                    help="order of the selected texts in the context (default: retrieval score)")
    sp.add_argument("--template", default="context_v2", help="prompts/<name>.pt.md (default context_v2)")
    sp.add_argument("--annex-rule", choices=ANNEX_RULES, default="either", help="G3 rule for gold coverage and oracle")
    sp.add_argument("--oracle-strategy", default="S1", help="units of the oracle context (default S1: articles)")
    sp.add_argument("--seed", type=int, default=13, help="seed of the wrong-context donors")
    sp.add_argument("--eval-id", help="evaluation for the consistency check (default: a matching one)")
    sp.add_argument("--no-token-count", action="store_true", help="skip Qwen3 counts of the rendered contexts")
    sp.add_argument("--force", action="store_true", help="replace context sets made with another configuration")
    common(sp)
    sp.set_defaults(func=cmd_context)

    sp = sub.add_parser("show-context", help="print the contexts of some questions", formatter_class=fmt,
                        epilog=epilog("python scripts/rag/rag.py show-context --context "
                                      "runs/contexts/jua-4b-mixed/irpf/S2_budget4000 --questions 012,345"))
    sp.add_argument("--context", required=True, help="context set directory")
    sp.add_argument("--questions", required=True, help="comma list of question numbers")
    sp.add_argument("--no-text", action="store_true", help="list the items only")
    sp.add_argument("--max-chars", type=int, default=0, help="truncate the rendered context (0: full)")
    sp.set_defaults(func=cmd_show_context)

    def gen_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--budget", type=float, help="USD cap on the total of runs/costs.csv (required unless --dry-run)")
        sp.add_argument("--dry-run", action="store_true", help="print the grid, calls and estimated cost; send nothing")
        sp.add_argument("--workers", type=int, default=8, help="concurrent calls per generator (default 8)")
        sp.add_argument("--force", action="store_true", help="replace answer runs made with another configuration")
        sp.add_argument("--registry", help="generator registry (default scripts/rag/llms.yaml)")
        common(sp)

    sp = sub.add_parser("generate", help="stage G: answer the questions from context sets (plan §7)",
                        formatter_class=fmt,
                        epilog=epilog("python scripts/rag/rag.py generate --contexts runs/contexts/jua-4b-mixed/irpf "
                                      "--sets S1_budget4000,S2_budget4000 --llms sabiazinho-4 --budget 2 --dry-run"))
    sp.add_argument("--contexts", required=True, help="context folder runs/contexts/<embedding>/<retrieval run>")
    sp.add_argument("--sets", required=True, help="comma list of context ids (folders under --contexts)")
    sp.add_argument("--llms", required=True, help="comma list of generators of scripts/rag/llms.yaml")
    sp.add_argument("--sample", default="stratified_30",
                    help="questions: all | a sample of nuggets/full/sample.json | comma list (default stratified_30)")
    sp.add_argument("--prompt", default="answer_v1", help="prompt of the context sets (default answer_v1)")
    sp.add_argument("--closed-prompt", default="answer_closed_v1", help="prompt of closed_book (default answer_closed_v1)")
    gen_common(sp)
    sp.set_defaults(func=cmd_generate)

    sp = sub.add_parser("run", help="stage G from a versioned experiment file", formatter_class=fmt,
                        epilog=epilog("python scripts/rag/rag.py run --experiment scripts/rag/experiments/pilot.yaml "
                                      "--dry-run"))
    sp.add_argument("--experiment", required=True, help="scripts/rag/experiments/<name>.yaml")
    sp.add_argument("--sample", help="override the experiment's sample")
    gen_common(sp)
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("show-answers", help="print the answers of some questions", formatter_class=fmt,
                        epilog=epilog("python scripts/rag/rag.py show-answers --run "
                                      "runs/answers/jua-4b-mixed/irpf/answer_v1/sabia-4/S2_budget4000 --questions 350"))
    sp.add_argument("--run", required=True, help="answer run directory")
    sp.add_argument("--questions", required=True, help="comma list of question numbers")
    sp.set_defaults(func=cmd_show_answers)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    try:
        return args.func(args)
    except (InputError, RunError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
