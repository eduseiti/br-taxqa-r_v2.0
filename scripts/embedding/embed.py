#!/usr/bin/env python3
"""Embed the BR-TaxQA-R chunks and questions with one configured model.

Plan: docs/20260925_122058_embedding_implementation_plan.md. Usage (from the repository root):

  python scripts/embedding/embed.py models
  python scripts/embedding/embed.py check    --model jua-4b-mixed --resume
  python scripts/embedding/embed.py parity   --model jua-4b-mixed
  python scripts/embedding/embed.py corpus   --model jua-4b-mixed --dry-run
  python scripts/embedding/embed.py corpus   --model jua-4b-mixed --resume
  python scripts/embedding/embed.py queries  --model jua-4b-mixed [--instruction-name irpf]
  python scripts/embedding/embed.py finalize --model jua-4b-mixed --kind corpus
  python scripts/embedding/embed.py endpoint --model jua-4b-mixed {status|resume|pause}
  python scripts/embedding/embed.py costs    summary [--markdown]
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from embedding import costs, endpoint, parity  # noqa: E402
from embedding.config import (DEFAULT_CORPUS, DEFAULT_QUERIES, EMB_DIR, PARITY_SAMPLE, REPO, ConfigError,  # noqa: E402
                              ModelConfig, get_model, load_config)
from embedding.corpus import CorpusError, load_corpus, load_queries  # noqa: E402
from embedding.manifest import now_iso, read_json, script_info, sha256_file, sha256_json, write_json  # noqa: E402
from embedding.providers import ProviderError, get_provider  # noqa: E402
from embedding.runner import NORM_TOL, run  # noqa: E402
from embedding.store import ShardStore, StoreError, write_csv, write_csv_gz  # noqa: E402
from embedding.tokens import LengthError, guard, load_counter  # noqa: E402

log = logging.getLogger("embedding")
SCHEMA_VERSION = 1


# ================================================================================================
# Helpers
# ================================================================================================

def setup_logging(cfg: ModelConfig | None, verbose: bool) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if cfg is not None:
        cfg.out_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(cfg.out_dir / "run.log", encoding="utf-8"))
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S", force=True)
    for noisy in ("huggingface_hub", "urllib3", "httpx", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(REPO))
    except ValueError:
        return str(p)


def load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO / ".env", override=False)
    except ImportError:
        pass


def server_fingerprint(cfg: ModelConfig, info: dict, ep_desc: dict | None) -> dict:
    """What must match between a parity check and a corpus run (and between resumed sessions)."""
    image = None
    if ep_desc:
        image = ep_desc["config"].get("model", {}).get("image")
    return {"model_id": cfg.model_id, "revision": cfg.revision,
            "endpoint_repository": ep_desc and ep_desc["repository"],
            "endpoint_revision": ep_desc and ep_desc["revision"], "endpoint_image": image,
            "server_model_id": info.get("model_id"), "server_model_sha": info.get("model_sha"),
            "server_dtype": info.get("model_dtype"), "server_version": info.get("version"),
            "pooling": pooling_of(info)}


def pooling_of(info: dict) -> str | None:
    p = (info.get("model_type") or {}).get("embedding", {}).get("pooling") if isinstance(info.get("model_type"), dict) else None
    return p.replace("-", "_") if isinstance(p, str) else p


class EndpointSession:
    """Resumes (if asked) and meters the endpoint while the command works; optionally pauses it
    afterwards; writes the cost-ledger rows. A no-op for providers without an endpoint."""

    def __init__(self, cfg: ModelConfig, activity: str, resume: bool, pause_after: bool):
        self.cfg, self.activity, self.resume, self.pause_after = cfg, activity, resume, pause_after
        self.run_id = f"{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self.ep = self.meter = None
        self.desc: dict | None = None
        self.notes = ""

    def __enter__(self) -> "EndpointSession":
        if self.cfg.provider != "tei":
            return self
        self.ep = endpoint.get_endpoint(self.cfg)
        if self.ep is not None:
            self.meter = endpoint.Meter(self.ep, self.cfg.out_dir / "endpoint_meter.jsonl", self.run_id).start()
            try:
                endpoint.ensure_running(self.ep, self.resume, on_resume=self.meter.sample)
            except BaseException:
                self.meter.stop()
                raise
            self.desc = endpoint.describe(self.ep)
        return self

    def url(self) -> str | None:
        return self.cfg.endpoint_url() or (self.ep.url if self.ep is not None else None)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.ep is None:
            return
        if exc_type is not None:
            self.notes = f"failed: {exc_type.__name__}"
        if self.pause_after:
            log.info("pausing endpoint %s", self.ep.name)
            try:
                self.ep.pause()
                for _ in range(24):
                    self.ep.fetch()
                    if endpoint.state(self.ep)["state"] == "paused":
                        break
                    time.sleep(5)
            except Exception as e:  # noqa: BLE001
                log.error("could not pause the endpoint (%s): pause it in the UI!", e)
        m = self.meter.stop()
        idle = endpoint.scale_to_zero_minutes(self.ep) if m.get("final_billed_replicas") else 0
        rows = costs.endpoint_rows(self.cfg.out_root / "costs.csv", self.cfg, self.activity, self.run_id, m,
                                   idle_minutes=idle, notes=self.notes)
        usd = sum(float(r["usd"] or 0) for r in rows)
        log.info("metered %.1f replica-minutes%s; estimated $%.2f (ledger: embeddings/costs.csv)",
                 m.get("replica_minutes", 0), f" + {idle} min idle tail" if idle else "", usd)
        if not self.pause_after and m.get("final_state") == "running":
            log.info("endpoint left running; it scales to zero after %d min idle, or run "
                     "`embed.py endpoint --model %s pause`", endpoint.scale_to_zero_minutes(self.ep), self.cfg.slug)


def count_tokens(cfg: ModelConfig, texts: list[str]) -> list[int]:
    t0 = time.monotonic()
    counts = load_counter(cfg.tokenizer)(texts)
    log.info("counted tokens of %d texts with %s in %.1fs (total %d, max %d)", len(texts), cfg.tokenizer,
             time.monotonic() - t0, sum(counts), max(counts) if counts else 0)
    return counts


def parity_gate(cfg: ModelConfig, sfp: dict, skip: bool) -> dict:
    path = cfg.out_dir / "parity.json"
    if cfg.provider == "fake":
        return {"status": "not applicable (fake provider)"}
    if skip:
        log.warning("parity gate skipped (--skip-parity): recorded in the manifest")
        return {"status": "skipped (--skip-parity)"}
    if not path.exists():
        raise ConfigError(f"no parity check for {cfg.slug}: run `embed.py parity --model {cfg.slug}` first "
                          "(or --skip-parity)")
    p = read_json(path)
    if p.get("server_fingerprint") != sfp:
        diff = sorted(k for k in sfp if p.get("server_fingerprint", {}).get(k) != sfp[k])
        raise ConfigError(f"parity.json was made against a different server (differs in {diff}); "
                          f"re-run `embed.py parity --model {cfg.slug}`")
    if not p.get("passed"):
        raise ConfigError(f"parity check failed for {cfg.slug} ({p.get('checks')}); see plan §3.8 "
                          "(DTYPE=float32 or vLLM), or --skip-parity")
    return {"status": "passed", "path": rel(path), "created_at": p.get("created_at"),
            "metrics": p.get("metrics")}


def token_stats(n: list[int]) -> dict:
    a = np.asarray(n)
    return {"total": int(a.sum()), "max": int(a.max()), "p50": int(np.percentile(a, 50)),
            "p90": int(np.percentile(a, 90)), "p99": int(np.percentile(a, 99))} if len(a) else {}


def check_norms(path: Path, block: int = 8192) -> dict:
    v = np.load(path, mmap_mode="r")
    lo, hi = np.inf, -np.inf
    for s in range(0, len(v), block):
        n = np.linalg.norm(v[s:s + block], axis=1)
        lo, hi = min(lo, float(n.min())), max(hi, float(n.max()))
    return {"norm_min": lo, "norm_max": hi, "norms_ok": bool(abs(lo - 1) <= NORM_TOL and abs(hi - 1) <= NORM_TOL)}


def aggregate_sessions(sessions: list[dict]) -> dict:
    keys = ("n_texts", "n_tokens", "wall_s", "requests", "retries", "errors", "renormalized")
    agg = {k: sum(s.get(k) or 0 for s in sessions) for k in keys}
    agg["tokens_per_s"] = round(agg["n_tokens"] / agg["wall_s"], 1) if agg["wall_s"] else None
    return {"start": sessions[0]["start"] if sessions else None, "end": sessions[-1].get("end") if sessions else None,
            **agg, "n_sessions": len(sessions), "sessions": sessions}


# ================================================================================================
# Inputs per kind
# ================================================================================================

def corpus_inputs(cfg: ModelConfig, args) -> dict:
    t0 = time.monotonic()
    c = load_corpus(Path(args.input), args.id_col, args.text_col)
    log.info("loaded %s: %d rows, %d unique texts (%.1fs)", Path(args.input).name, c.info["rows"],
             c.info["unique_texts"], time.monotonic() - t0)
    sent = [cfg.render_document(t) for t in c.texts["text"]]
    return {"kind": "corpus", "ids": c.texts["text_id"].tolist(), "texts": sent, "corpus": c,
            "input": c.info, "template": cfg.document_template, "instruction_name": None,
            "out": cfg.out_dir / "corpus"}


def query_inputs(cfg: ModelConfig, args) -> dict:
    q, info = load_queries(Path(args.input), args.id_field, args.text_field)
    name = args.instruction_name or cfg.instruction_name
    sent = [cfg.render_query(t, name) for t in q["text"]]
    return {"kind": "queries", "ids": q["query_id"].tolist(), "texts": sent, "queries": q, "input": info,
            "template": cfg.query_template, "instruction_name": name,
            "instruction": cfg.instruction(name) if "{instruction}" in cfg.query_template else None,
            "out": cfg.out_dir / "queries" / name}


def store_fingerprint(cfg: ModelConfig, inp: dict, sfp: dict) -> dict:
    return {"kind": inp["kind"], "model": cfg.slug, "provider": cfg.provider, "dim": cfg.dim,
            "template": inp["template"], "instruction": inp.get("instruction"),
            "input_sha256": inp["input"]["sha256"], "server": sfp}


# ================================================================================================
# Finalize
# ================================================================================================

def finalize(cfg: ModelConfig, inp: dict, n_tokens: list[int], store: ShardStore, extra: dict) -> Path:
    out: Path = inp["out"]
    st = store.state()
    if st is None:
        raise StoreError(f"nothing to finalize in {out}")
    vec_path = out / "vectors.npy"
    log.info("assembling %d vectors into %s", len(inp["ids"]), rel(vec_path))
    store.assemble(inp["ids"], cfg.dim, vec_path)
    norms = check_norms(vec_path)
    if not norms["norms_ok"]:
        raise StoreError(f"vector norms outside 1±{NORM_TOL}: {norms}")
    files = {"vectors.npy": vec_path}
    if inp["kind"] == "corpus":
        texts = pd.DataFrame({"row": range(len(inp["ids"])), "text_id": inp["ids"], "n_tokens": n_tokens})
        write_csv(texts, out / "texts.csv")
        write_csv_gz(inp["corpus"].chunk_map, out / "chunk_map.csv.gz")
        files |= {"texts.csv": out / "texts.csv", "chunk_map.csv.gz": out / "chunk_map.csv.gz"}
    else:
        qdf = pd.DataFrame({"row": range(len(inp["ids"])), "query_id": inp["ids"], "n_tokens": n_tokens,
                            "text_sent": inp["texts"]})
        write_csv(qdf, out / "queries.csv")
        files |= {"queries.csv": out / "queries.csv"}
    ctx = st.get("context", {})
    manifest = {
        "schema_version": SCHEMA_VERSION, "created_at": now_iso(), "kind": inp["kind"], "script": script_info(),
        "model": {"slug": cfg.slug, "provider": cfg.provider, "model_id": cfg.model_id, "revision": cfg.revision,
                  "dim": cfg.dim, "template": inp["template"], "instruction_name": inp.get("instruction_name"),
                  "instruction": inp.get("instruction"), "tokenizer": cfg.tokenizer,
                  "max_input_tokens": cfg.max_input_tokens},
        "server": {"info": ctx.get("server_info"), "endpoint": ctx.get("endpoint"),
                   "fingerprint": st["fingerprint"]["server"]},
        "input": {**inp["input"], "tokens": token_stats(n_tokens)},
        "output": {"shape": [len(inp["ids"]), cfg.dim], "dtype": "float32", **norms,
                   "sha256": {k: sha256_file(p) for k, p in files.items()}},
        "run": aggregate_sessions(st["sessions"]),
        "parity": ctx.get("parity"),
        **extra,
    }
    write_json(out / "manifest.json", manifest)
    store.clear()
    log.info("finalized %s (manifest.json written, shards removed)", rel(out))
    return out / "manifest.json"


# ================================================================================================
# Commands
# ================================================================================================

def cmd_models(args) -> int:
    import os
    for slug, c in load_config(args.config, args.out_root).items():
        url = "set" if c.endpoint_url() else ("from endpoint API" if c.endpoint_name else "NOT SET")
        env = f"{c.endpoint_url_env}: {url}" if c.provider == "tei" else ""
        tok = "" if c.provider != "tei" else f"HF_TOKEN: {'set' if os.environ.get('HF_TOKEN') else 'NOT SET'}"
        print(f"{slug:18} {c.provider:5} {c.model_id:32} dim={c.dim:<5} {env}  {tok}")
    return 0


def cmd_check(args, cfg: ModelConfig) -> int:
    probes = ["Art. 1º Teste.",
              "Quem está obrigado a apresentar a Declaração de Ajuste Anual? Ação, exceção, cônjuge, § 2º.",
              cfg.render_query("Quem está obrigado a apresentar a Declaração de Ajuste Anual?")]
    report: dict = {"created_at": now_iso(), "model": cfg.slug, "checks": {}}
    with EndpointSession(cfg, "smoke", args.resume, args.pause_after) as es:
        prov = get_provider(cfg, es.url())
        info = prov.info()
        report |= {"server_info": info, "endpoint": es.desc, "server_fingerprint": server_fingerprint(cfg, info, es.desc)}
        ch = report["checks"]
        if cfg.provider == "tei" and not cfg.request_opt("openai_compat", False):
            ch["max_input_length"] = (info.get("max_input_length", 0) >= cfg.max_input_tokens,
                                      info.get("max_input_length"))
            ch["auto_truncate_off"] = (info.get("auto_truncate") is False, info.get("auto_truncate"))
            if cfg.expected_pooling:
                ch["pooling"] = (pooling_of(info) == cfg.expected_pooling, pooling_of(info))
            client = load_counter(cfg.tokenizer)(probes)
            server = prov.tokenize(probes)
            ch["tokenizer_matches_server"] = (client == server, {"client": client, "server": server})
        if es.desc:
            ch["endpoint_repository"] = (es.desc["repository"] == cfg.model_id, es.desc["repository"])
            ch["endpoint_revision"] = (es.desc["revision"] == cfg.revision, es.desc["revision"])
        elif info.get("model_sha") and cfg.revision:
            ch["server_model_sha"] = (info["model_sha"] == cfg.revision, info["model_sha"])
        v = prov.embed(probes)
        norms = np.linalg.norm(v, axis=1)
        ch["dimension"] = (v.shape[1] == cfg.dim, int(v.shape[1]))
        ch["normalized"] = (bool(np.all(np.abs(norms - 1) <= NORM_TOL)), [round(float(x), 6) for x in norms])
        ch["finite"] = (bool(np.isfinite(v).all()), None)
    report["checks"] = {k: {"ok": bool(ok), "value": val} for k, (ok, val) in report["checks"].items()}
    report["passed"] = all(c["ok"] for c in report["checks"].values())
    write_json(cfg.out_dir / "check.json", report)
    for k, c in report["checks"].items():
        print(f"  {'OK  ' if c['ok'] else 'FAIL'} {k}: {c['value']}")
    print(f"check {'PASSED' if report['passed'] else 'FAILED'} -> {rel(cfg.out_dir / 'check.json')}")
    return 0 if report["passed"] else 1


def load_parity_sample(args, cfg: ModelConfig):
    sample_path = Path(args.sample)
    corpus = load_corpus(Path(args.input))
    queries, _ = load_queries(Path(args.queries))
    if args.make_sample:
        if sample_path.exists() and not args.overwrite:
            raise ConfigError(f"{sample_path.name} exists; --overwrite to rebuild it")
        sample = parity.make_sample(corpus.rows, queries) | {"corpus_sha256": corpus.info["sha256"],
                                                             "queries_sha256": sha256_file(Path(args.queries))}
        write_json(sample_path, sample)
        log.info("wrote %s", rel(sample_path))
    elif not sample_path.exists():
        raise ConfigError(f"{sample_path.name} is missing: run `embed.py parity --model … --make-sample`")
    sample = read_json(sample_path)
    by_id = dict(zip(corpus.texts["text_id"], corpus.texts["text"]))
    qby = dict(zip(queries["query_id"], queries["text"]))
    missing = [i for i in sample["text_ids"] if i not in by_id] + [q for q in sample["query_ids"] if q not in qby]
    if missing:
        raise ConfigError(f"parity sample ids not in the inputs: {missing[:5]} (corpus changed? --make-sample --overwrite)")
    name = args.instruction_name or cfg.instruction_name
    strings = ([cfg.render_document(by_id[i]) for i in sample["text_ids"]]
               + [cfg.render_query(qby[q], name) for q in sample["query_ids"]])
    return sample, strings, name


def cmd_parity(args, cfg: ModelConfig) -> int:
    sample, strings, iname = load_parity_sample(args, cfg)
    if args.make_sample and not (args.reference_only or args.reference):
        return 0
    n_texts = len(sample["text_ids"])
    n_tok = load_counter(cfg.tokenizer)(strings)
    guard([f"sample#{k}" for k in range(len(strings))], n_tok, cfg.max_input_tokens)
    ref_cfg = {"dtype": "bfloat16", "trust_remote_code": False} | cfg.reference
    key = sha256_json({"model": cfg.model_id, "revision": cfg.revision, "strings": strings, "ref": ref_cfg})
    cache = Path(args.out) if args.out else cfg.out_dir / "parity_reference.npz"
    src = Path(args.reference) if args.reference else cache
    ref = None
    if src.exists():
        z = np.load(src, allow_pickle=False)
        if str(z["key"]) == key:
            ref, ref_info = z["vectors"], read_json(src.with_suffix(".json"))
            log.info("using reference vectors from %s", src)
        elif args.reference:
            raise ConfigError(f"{src} was computed for different inputs/model (key mismatch)")
    if ref is None:
        log.info("computing the reference (%s, %s, %d texts, max %d tokens); slow on CPU", ref_cfg["dtype"],
                 args.device, len(strings), max(n_tok))
        ref, ref_info = parity.reference_vectors(cfg.model_id, cfg.revision, strings, ref_cfg["dtype"], args.device,
                                                 ref_cfg["trust_remote_code"], cfg.max_input_tokens)
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez(cache, vectors=ref, key=np.asarray(key))
        write_json(cache.with_suffix(".json"), ref_info)
        log.info("reference saved to %s", cache)
    if args.reference_only:
        return 0
    with EndpointSession(cfg, "parity", args.resume, args.pause_after) as es:
        prov = get_provider(cfg, es.url())
        info = prov.info()
        served = np.concatenate([prov.embed(strings[s:s + 8]) for s in range(0, len(strings), 8)])
        sfp = server_fingerprint(cfg, info, es.desc)
    served = served / np.linalg.norm(served, axis=1, keepdims=True)
    res = parity.compare(served, ref, n_texts, cfg.parity)
    out = {"created_at": now_iso(), "model": cfg.slug, "server_fingerprint": sfp, "server_info": info,
           "reference": ref_info, "instruction_name": iname, "sample_sha256": sha256_file(Path(args.sample)),
           "thresholds": cfg.parity, **res,
           "items": [{"id": i, "kind": "text"} for i in sample["text_ids"]]
           + [{"id": q, "kind": "query"} for q in sample["query_ids"]]}
    write_json(cfg.out_dir / "parity.json", out)
    m = res["metrics"]
    print(f"cos median {m['cos_median']:.6f}  min {m['cos_min']:.6f}  p1 {m['cos_p1']:.6f}  "
          f"top-1 {m['top1_agree']}/{m['n_queries']}  tau min {m['kendall_tau_min']:.4f}")
    print(f"parity {'PASSED' if res['passed'] else 'FAILED'} {res['checks']} -> "
          f"{rel(cfg.out_dir / 'parity.json')}")
    return 0 if res["passed"] else 1


def previous_store(out: Path, cfg: ModelConfig, inp: dict) -> dict:
    """The finalized corpus store in ``out``, for ``--extend``: text_id -> row, plus checks that its
    vectors are interchangeable with a new run (same model, revision, template, dimension)."""
    man_path = out / "manifest.json"
    if not man_path.exists():
        raise StoreError(f"--extend: no finalized store in {rel(out)}")
    man = read_json(man_path)
    m = man["model"]
    want = {"model_id": cfg.model_id, "revision": cfg.revision, "dim": cfg.dim, "template": inp["template"]}
    diff = {k: (m.get(k), v) for k, v in want.items() if m.get(k) != v}
    if diff:
        raise StoreError(f"--extend: the stored vectors were made with a different configuration: {diff}")
    texts = pd.read_csv(out / "texts.csv", dtype={"text_id": str})
    if sha256_file(out / "vectors.npy") != man["output"]["sha256"]["vectors.npy"]:
        raise StoreError("--extend: vectors.npy does not match its manifest")
    return {"manifest": man, "manifest_sha256": sha256_file(man_path),
            "row": dict(zip(texts["text_id"], texts["row"])), "server": man["server"]["fingerprint"]}


def seed_reused(store: ShardStore, prev: dict, ids: list[str], out: Path, block: int = 4096) -> int:
    """Copy the stored vectors of the texts that are still in the input into the shard store, so
    only new texts are sent and ``assemble`` works unchanged. Returns the number reused."""
    done = store.done_ids()
    reuse = [i for i in ids if i in prev["row"] and i not in done]
    if reuse:
        V = np.load(out / "vectors.npy", mmap_mode="r")
        for j in range(0, len(reuse), block):
            part = reuse[j:j + block]
            store.write(part, np.asarray(V[[prev["row"][i] for i in part]]))
    return sum(1 for i in ids if i in prev["row"])


def cmd_embed(args, cfg: ModelConfig, kind: str) -> int:
    inp = corpus_inputs(cfg, args) if kind == "corpus" else query_inputs(cfg, args)
    out: Path = inp["out"]
    extend = getattr(args, "extend", False)
    if (out / "manifest.json").exists() and not (args.overwrite or extend):
        print(f"{rel(out)} is already finalized; --overwrite to redo it, or --extend to embed only new texts")
        return 0
    prev = previous_store(out, cfg, inp) if extend else None
    if prev:
        new = sum(1 for i in inp["ids"] if i not in prev["row"])
        log.info("--extend: %d of %d texts are in the stored vectors; %d new", len(inp["ids"]) - new,
                 len(inp["ids"]), new)
    n_tok = count_tokens(cfg, inp["texts"])
    guard(inp["ids"], n_tok, cfg.max_input_tokens)
    mi, mt = cfg.request_opt("max_inputs", 32), cfg.request_opt("max_request_tokens", 16384)
    conc = args.concurrency or cfg.request_opt("concurrency", 4)
    if args.dry_run:
        from embedding.runner import pack
        sent = [n for i, n in zip(inp["ids"], n_tok) if not prev or i not in prev["row"]]
        nreq = len(pack(sent, mi, mt))
        print(f"{kind}: {len(inp['ids'])} texts, {len(sent)} to send, {sum(sent):,} tokens "
              f"(max {max(sent, default=0)}), {nreq} requests of <= {mi} inputs / {mt} tokens, concurrency {conc}")
        n_tok = sent
        tps, price = cfg.request_opt("expected_tokens_per_s", None), cfg.price.get("usd_per_hour")
        if tps and price:
            h = sum(n_tok) / tps / 3600
            print(f"expected ~{h:.1f} h at {tps} tok/s -> ~${h * price:.2f} (+ start-up and idle)")
        else:
            print("no cost estimate: set request.expected_tokens_per_s after measuring the first minutes")
        return 0
    store = ShardStore(out)
    activity = kind
    with EndpointSession(cfg, activity, args.resume, args.pause_after) as es:
        prov = get_provider(cfg, es.url())
        info = prov.info()
        sfp = server_fingerprint(cfg, info, es.desc)
        gate = parity_gate(cfg, sfp, args.skip_parity)
        extra = {"cost_ledger": "embeddings/costs.csv"}
        if prev:
            if prev["server"] != sfp:
                raise StoreError("--extend: the stored vectors come from a different server configuration "
                                 f"({prev['server']} vs {sfp})")
            fp = store_fingerprint(cfg, inp, sfp) | {"extends": prev["manifest_sha256"]}
            store.open(fp, overwrite=args.overwrite)
            reused = seed_reused(store, prev, inp["ids"], out)
            extra["extend"] = {"previous_manifest_sha256": prev["manifest_sha256"],
                               "previous_input": prev["manifest"]["input"],
                               "previous_output_sha256": prev["manifest"]["output"]["sha256"],
                               "reused_texts": reused, "embedded_texts": len(inp["ids"]) - reused,
                               "dropped_texts": len(set(prev["row"]) - set(inp["ids"]))}
        else:
            store.open(store_fingerprint(cfg, inp, sfp), overwrite=args.overwrite)
        st = store.state()
        st["context"] = {"server_info": info, "endpoint": es.desc, "parity": gate, "run_id": es.run_id}
        if prev:
            st["context"]["extend"] = extra["extend"]
        write_json(store.state_path, st)
        run(prov, store, inp["ids"], inp["texts"], n_tok, cfg.dim, mi, mt, conc, progress=not args.no_progress)
    finalize(cfg, inp, n_tok, store, extra)
    return 0


def cmd_finalize(args, cfg: ModelConfig) -> int:
    inp = corpus_inputs(cfg, args) if args.kind == "corpus" else query_inputs(cfg, args)
    store = ShardStore(inp["out"])
    extra = {"cost_ledger": "embeddings/costs.csv"}
    if (store.state() or {}).get("context", {}).get("extend"):
        extra["extend"] = store.state()["context"]["extend"]
    finalize(cfg, inp, count_tokens(cfg, inp["texts"]), store, extra)
    return 0


def cmd_endpoint(args, cfg: ModelConfig) -> int:
    ep = endpoint.get_endpoint(cfg, required=True)
    if args.action == "resume":
        ep.resume()
        ep.wait(timeout=1800)
        print("running (not metered: usage between commands is not in the ledger, plan §9.3)")
    elif args.action == "pause":
        ep.pause()
    ep.fetch()
    s = endpoint.state(ep)
    print(f"{ep.namespace}/{ep.name}: {s['state']} (ready {s['ready']}/{s['target']}), "
          f"{ep.repository}@{ep.revision}, {ep.raw.get('compute', {}).get('instanceType')}, {ep.url}")
    return 0


def cmd_costs(args, config_path) -> int:
    ledger = (args.out_root or EMB_DIR) / "costs.csv"
    if args.action == "summary":
        print(costs.summary(ledger, args.by, args.markdown))
        return 0
    cfg = get_model(args.model, config_path, args.out_root)
    price = cfg.price.get("usd_per_hour") if args.replica_minutes else cfg.price.get("usd_per_million_tokens")
    if args.replica_minutes:
        unit, q = "replica_minutes", args.replica_minutes
        usd = args.usd if args.usd is not None else (q * price / 60 if price else "")
    else:
        unit, q = "tokens", args.tokens or ""
        usd = args.usd if args.usd is not None else (q * price / 1e6 if price and q else "")
    row = costs.append(ledger, model_slug=cfg.slug, activity=args.activity, provider=args.provider,
                       billing_unit=unit, quantity=q, unit_price_usd=price or "",
                       price_checked=cfg.price.get("checked", ""), usd=usd, source=args.source,
                       notes=args.notes or "", timestamp_start=now_iso())
    print(f"added {row['row_id']}: {unit}={q} usd={usd}")
    return 0


# ================================================================================================
# CLI
# ================================================================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=None, help="model registry (default: scripts/embedding/models.yaml)")
    p.add_argument("--out-root", default=None, type=Path, help="output root (default: embeddings/)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def model_arg(sp):
        sp.add_argument("--model", required=True, help="model slug from models.yaml")

    def endpoint_args(sp, pause_default: bool):
        sp.add_argument("--resume", action="store_true", help="resume the endpoint if it is paused")
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--pause-after", dest="pause_after", action="store_true", default=pause_default,
                       help="pause the endpoint when done" + (" (default)" if pause_default else ""))
        g.add_argument("--no-pause-after", dest="pause_after", action="store_false",
                       help="leave the endpoint running (it scales to zero after its idle timeout)")

    def corpus_args(sp):
        sp.add_argument("--input", default=str(DEFAULT_CORPUS), help="chunks file (csv[.gz]/parquet/jsonl)")
        sp.add_argument("--id-col", default="chunk_id")
        sp.add_argument("--text-col", default="Texto")

    def query_args(sp):
        sp.add_argument("--input", default=str(DEFAULT_QUERIES), help="questions file (json/jsonl/csv)")
        sp.add_argument("--id-field", default="question_number")
        sp.add_argument("--text-field", default="question_text")
        sp.add_argument("--instruction-name", default=None, help="key of defaults.instructions in models.yaml")

    sub.add_parser("models", help="list configured models and whether their credentials are set")

    sp = sub.add_parser("check", help="connectivity, /info, tokenizer and 1-request smoke test",
                        epilog="example: embed.py check --model jua-4b-mixed --resume")
    model_arg(sp)
    endpoint_args(sp, pause_default=False)

    sp = sub.add_parser("parity", help="served vs reference embeddings on the fixed sample (plan §5.4)",
                        epilog="examples:\n  embed.py parity --model jua-4b-mixed --make-sample\n"
                               "  embed.py parity --model jua-4b-mixed --reference-only\n"
                               "  embed.py parity --model jua-4b-mixed --resume",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    model_arg(sp)
    corpus_args(sp)
    sp.add_argument("--queries", default=str(DEFAULT_QUERIES))
    sp.add_argument("--instruction-name", default=None)
    sp.add_argument("--sample", default=str(PARITY_SAMPLE), help="parity sample ids (default: parity_sample.json)")
    sp.add_argument("--make-sample", action="store_true", help="(re)build the parity sample")
    sp.add_argument("--overwrite", action="store_true")
    sp.add_argument("--reference-only", action="store_true", help="compute the reference vectors and stop")
    sp.add_argument("--reference", default=None, help="use reference vectors computed elsewhere (.npz)")
    sp.add_argument("--out", default=None, help="where to save the reference (.npz)")
    sp.add_argument("--device", default="cpu", help="device for the reference (cpu, cuda)")
    endpoint_args(sp, pause_default=False)

    for kind, helptext in (("corpus", "embed the unique chunk texts"), ("queries", "embed the questions")):
        sp = sub.add_parser(kind, help=helptext,
                            epilog=f"examples:\n  embed.py {kind} --model jua-4b-mixed --dry-run\n"
                                   f"  embed.py {kind} --model jua-4b-mixed --resume",
                            formatter_class=argparse.RawDescriptionHelpFormatter)
        model_arg(sp)
        corpus_args(sp) if kind == "corpus" else query_args(sp)
        sp.add_argument("--dry-run", action="store_true", help="count tokens and requests; send nothing")
        sp.add_argument("--overwrite", action="store_true", help="discard existing shards / outputs")
        if kind == "corpus":
            sp.add_argument("--extend", action="store_true",
                            help="embed by text hash: reuse the finalized vectors of every text still in the "
                                 "input and send only the new texts (same model, revision, template and server)")
        sp.add_argument("--skip-parity", action="store_true", help="run without a passing parity.json")
        sp.add_argument("--concurrency", type=int, default=None)
        sp.add_argument("--no-progress", action="store_true")
        endpoint_args(sp, pause_default=(kind == "corpus"))

    sp = sub.add_parser("finalize", help="assemble shards into the release format (after an interrupted run)")
    model_arg(sp)
    sp.add_argument("--kind", choices=("corpus", "queries"), default="corpus")
    sp.add_argument("--input", default=None)
    sp.add_argument("--id-col", default="chunk_id")
    sp.add_argument("--text-col", default="Texto")
    sp.add_argument("--id-field", default="question_number")
    sp.add_argument("--text-field", default="question_text")
    sp.add_argument("--instruction-name", default=None)

    sp = sub.add_parser("endpoint", help="status / resume / pause the model's HF endpoint")
    model_arg(sp)
    sp.add_argument("action", choices=("status", "resume", "pause"))

    sp = sub.add_parser("costs", help="cost ledger: summary, or add a manual row (plan §9)",
                        epilog="examples:\n  embed.py costs summary --markdown\n"
                               "  embed.py costs add --model jua-4b-mixed --activity other --replica-minutes 12 "
                               "--notes 'UI playground'",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    sp.add_argument("action", choices=("summary", "add"))
    sp.add_argument("--by", choices=("model", "activity", "provider"), default="model")
    sp.add_argument("--markdown", action="store_true")
    sp.add_argument("--model")
    sp.add_argument("--activity", choices=costs.ACTIVITIES, default="other")
    sp.add_argument("--provider", default="hf_endpoint")
    sp.add_argument("--replica-minutes", type=float)
    sp.add_argument("--tokens", type=int)
    sp.add_argument("--usd", type=float)
    sp.add_argument("--source", choices=("auto_estimate", "provider_reported", "invoice"), default="invoice")
    sp.add_argument("--notes")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_env()
    try:
        if args.cmd == "models":
            setup_logging(None, args.verbose)
            return cmd_models(args)
        if args.cmd == "costs":
            setup_logging(None, args.verbose)
            if args.action == "add" and not args.model:
                raise ConfigError("costs add needs --model")
            return cmd_costs(args, args.config)
        cfg = get_model(args.model, args.config, args.out_root)
        setup_logging(cfg, args.verbose)
        if args.cmd == "finalize" and args.input is None:
            args.input = str(DEFAULT_CORPUS if args.kind == "corpus" else DEFAULT_QUERIES)
        return {"check": lambda: cmd_check(args, cfg), "parity": lambda: cmd_parity(args, cfg),
                "corpus": lambda: cmd_embed(args, cfg, "corpus"), "queries": lambda: cmd_embed(args, cfg, "queries"),
                "finalize": lambda: cmd_finalize(args, cfg), "endpoint": lambda: cmd_endpoint(args, cfg)}[args.cmd]()
    except (ConfigError, CorpusError, StoreError, LengthError, ProviderError) as e:
        log.error("%s", e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
