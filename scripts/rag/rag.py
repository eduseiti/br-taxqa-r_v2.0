#!/usr/bin/env python3
"""RAG pipeline of the BR-TaxQA-R v2.0 segmentation experiment — Phase 1: retrieval and its
evaluation (the legal-provision test).

Plan: docs/20260927_204356_rag_pipeline_implementation_plan.md. Usage (from the repository root):

  python scripts/rag/rag.py check    --embedding jua-4b-mixed
  python scripts/rag/rag.py retrieve --embedding jua-4b-mixed [--instruction irpf] [--strategies S1,S2,S3] [--top-n 1000]
  python scripts/rag/rag.py evaluate --retrieval runs/retrieval/jua-4b-mixed/irpf [--annex-rule either]
  python scripts/rag/rag.py compare  --retrieval runs/retrieval/jua-4b-mixed/irpf --a S1 --b S2
  python scripts/rag/rag.py report   --eval runs/retrieval/jua-4b-mixed/irpf/eval/either_containment_skip
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

from ragpipe.data import (InputError, Paths, check_inputs, default_instruction, load_chunks,  # noqa: E402
                          load_dataset, load_embedding)
from ragpipe.evaluation import EvalConfig, compare, run_evaluation  # noqa: E402
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
                          block_size=args.block_size, hash_vectors=not args.no_hash, force=args.force)
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
    sp.add_argument("--dedup", choices=("containment", "none"), default="containment")
    sp.add_argument("--overflow", choices=("skip", "stop"), default="skip")
    sp.add_argument("--strategies", help="comma list (default: all in the retrieval run)")
    sp.add_argument("--comparisons", help="pairs A:B, comma separated (default S1:S2,S2:S3)")
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
