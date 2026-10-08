#!/usr/bin/env python3
"""Segmentation orchestrator (plan §6).

1.  manifest = classify_annexes(lexml/articulados)                     -> segmented/annex_manifest.csv
2.  statutory jobs = main documents + A + B annexes, metadados = common.metadata_for(file)
3.  run_xsl_segmentation(jobs)                                          -> segmented/statutory/*.csv
3b. split_oversize on every statutory CSV (ART/DSP above the cap -> parts, §5b)
4.  loose p/table of statutory files -> segment_non_statutory loose mode (appended, offset
    max_num_final + 1); main documents too (deviation D1), annex preambles included
5.  segment_non_statutory document mode on lexml/nao_articulados/* and category C
                                                                        -> segmented/non_statutory/*.csv
6.  merge into segmented/chunks_all.csv (+ arquivo, segmentador, categoria, provenance §2.7,
    token counts); with --variants caput (default), every paragraph-family XSL row is followed by
    its caput-sentence variant row (add_caput_variants.py, caput plan D-A/D-B)
7.  validate_segments -> segmented/segmentation_report.{md,json}; non-zero exit on failure

Usage:
    .venv/bin/python scripts/segmentation/segment_all.py --jobs 16 --overwrite
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import subprocess
import re
import json
import multiprocessing as mp
import os
import sys
import time
from collections import Counter, defaultdict, deque
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (AGRUPADORES, ANEXO_RE, ART_DIR, DEFAULT_EMENTA_MAX_TOKENS,  # noqa: E402
                    DEFAULT_MAX_TOKENS, DEFAULT_TOKENIZER, DISPOSITIVOS, L, NAO_DIR, SEG_DIR,
                    agrupadores, citacao, disp_ancestors, doc_urn, get_tokenizer, is_annex_tree,
                    metadata_for, parse, read_prov, read_rows, xsl_row_elements)
import classify_annexes  # noqa: E402
from add_caput_variants import VARIANTS, caput_variant  # noqa: E402
import run_xsl_segmentation as rxs  # noqa: E402

PROV_COLS = ["chunk_id", "doc_urn", "anexo_urn", "nivel", "unidade_id", "artigo_id",
             "agrupadores_ids", "agrupadores_rotulos", "citacao", "parte", "n_partes",
             "cobre_ids", "parcial_ids", "id_ambiguo", "variante", "contexto_ids"]
EXTRA_COLS = ["arquivo", "segmentador", "categoria"]
TOKEN_COLS = ["n_tokens", "n_tokens_cl100k", "n_tokens_qwen3", "texto_sha256"]
GROUP_TIPOS = ("PRT", "LIV", "TIT", "SBT", "CAP", "SEC", "SSC")


# --------------------------------------------------------------------------------------------
# worker state
# --------------------------------------------------------------------------------------------
_TOK = None
_CFG: dict = {}


def _init(cfg: dict) -> None:
    global _TOK, _CFG
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    import logging
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    _CFG = cfg
    _TOK = get_tokenizer(cfg["tokenizer"])


def _pool(n: int, cfg: dict):
    return ProcessPoolExecutor(max_workers=n, mp_context=mp.get_context("spawn"),
                               initializer=_init, initargs=(cfg,))


def _map(pool, fn, args: list, sizes: list[int] | None = None) -> list:
    """pool.map, largest inputs first, results in input order."""
    order = sorted(range(len(args)), key=lambda i: -(sizes[i] if sizes else 0))
    futs = {i: pool.submit(fn, args[i]) for i in order}
    return [futs[i].result() for i in range(len(args))]


# --------------------------------------------------------------------------------------------
# step workers
# --------------------------------------------------------------------------------------------

def w_meta(path: str) -> dict:
    m = metadata_for(Path(path), _TOK, _CFG["ementa_max_tokens"])
    return {"text": m.text(), "truncated": m.truncated, "source": m.source,
            "ementa_tokens": _TOK.count(m.ementa) if m.ementa else 0}


def w_statutory_post(args: tuple) -> dict:
    """3b + 4 for one statutory file: split oversize ART/DSP rows, then append loose content."""
    from segment_non_statutory import segment_loose
    from split_oversize import split_csv
    xml, csv_path, meta_text, max_num_final, has_loose, include_preambulo = args
    xml, csv_path = Path(xml), Path(csv_path)
    tree = parse(xml)
    t0 = time.time()
    res = split_csv(csv_path, xml, meta_text, _TOK, _CFG["max_tokens"], tree=tree)
    out = {"arquivo": xml.name, "split": res["split"], "rows_xsl": res["rows_in"],
           "rows_after_split": res["rows_out"], "loose_rows": 0, "loose_stats": {}}
    if has_loose:
        meta = metadata_for(xml, _TOK, _CFG["ementa_max_tokens"], tree=tree)
        if meta.text() != meta_text:
            raise RuntimeError(f"{xml.name}: metadata differs between steps 2 and 4")
        lres = segment_loose(xml, csv_path, (max_num_final or 0) + 1, _TOK, _CFG["max_tokens"],
                             include_preambulo, meta=meta, tree=tree)
        out["loose_rows"] = len(lres.rows)
        out["loose_stats"] = {k: v for k, v in lres.stats.items() if v}
    out["seconds"] = round(time.time() - t0, 2)
    _TOK.clear_cache()
    return out


def w_document(args: tuple) -> dict:
    from segment_non_statutory import segment_document
    xml, out_csv = Path(args[0]), Path(args[1])
    t0 = time.time()
    res = segment_document(xml, out_csv, _TOK, _CFG["max_tokens"], _CFG["ementa_max_tokens"],
                           _CFG["keep_dropped_min_chars"])
    _TOK.clear_cache()
    return {"arquivo": xml.name, "rows": len(res.rows), "stats": res.stats,
            "seconds": round(time.time() - t0, 2)}


def _dump(v) -> str:
    return ";".join(v) if isinstance(v, list) else ("" if v is None else str(v))


def w_provenance(args: tuple) -> list[dict]:
    """Step 6 for one CSV: provenance columns (§2.7) + token counts."""
    csv_path, xml, categoria, segmentador_default = Path(args[0]), Path(args[1]), args[2], args[3]
    rows = read_rows(csv_path)
    if not rows:
        return []
    tree = parse(xml)
    urn = doc_urn(tree)
    annex = is_annex_tree(tree)
    anexo_urn = urn if annex else ""
    d_urn = re.sub(r"!anexo\d+$", "", urn)
    all_ids = Counter(e.get("id") for e in tree.getroot().iter() if isinstance(e.tag, str) and e.get("id"))
    # XSL element lookup: (Tipo, id) -> elements in document order
    by_key: dict = defaultdict(list)
    if segmentador_default == "xsl":
        for tipo, e in xsl_row_elements(tree):
            by_key[(tipo, e.get("id", ""))].append(e)
    used: Counter = Counter()
    prov: dict = defaultdict(deque)
    for rec in read_prov(csv_path):
        prov[rec["urn"]].append(rec)
    stem = xml.name[:-4]
    variants = _CFG.get("variants", ())
    out = []
    current_split: dict = {}
    for seq, r in enumerate(rows, 1):
        rec = prov[r["urn"]].popleft() if prov.get(r["urn"]) else None
        row = dict(r)
        row.update(arquivo=xml.name, categoria=categoria, chunk_id=f"{stem}#{seq}",
                   doc_urn=d_urn, anexo_urn=anexo_urn, nivel=r["Tipo"])
        if rec is not None and r["Tipo"] in ("TXT", "TAB"):
            row.update(segmentador="python", unidade_id=rec["unidade_id"], artigo_id="",
                       agrupadores_ids=_dump(rec["agrupadores_ids"]),
                       agrupadores_rotulos=" ; ".join(rec["agrupadores_rotulos"]),
                       citacao=rec["citacao"], parte=rec["parte"], n_partes=rec["n_partes"],
                       cobre_ids=_dump(rec["cobre_ids"]), parcial_ids=_dump(rec["parcial_ids"]))
            ids = [rec["unidade_id"]]
        else:
            tipo = r["Tipo"]
            if rec is not None:  # a part of a split ART/DSP
                uid = rec["unidade_id"]
                key = (tipo, uid)
                if rec["parte"] == 1:
                    current_split[key] = by_key[key][used[key]]
                    used[key] += 1
                e = current_split[key]
                parte, n_partes = rec["parte"], rec["n_partes"]
                cobre, parcial = rec["cobre_ids"], rec["parcial_ids"]
                segm = "python"
            else:
                uid = r["urn"].rsplit("!", 1)[-1]
                key = (tipo, uid)
                e = by_key[key][used[key]]
                used[key] += 1
                parte, n_partes, cobre, parcial = 1, 1, [uid], []
                segm = "xsl"
            if L(e) in AGRUPADORES:
                artigo = ""
            else:
                top = ([*disp_ancestors(e), e])[0]
                artigo = top.get("id", "")
            g_ids, g_labels = agrupadores(e)
            row.update(segmentador=segm, unidade_id=uid, artigo_id=artigo,
                       agrupadores_ids=";".join(g_ids), agrupadores_rotulos=" ; ".join(g_labels),
                       citacao=citacao(e), parte=parte, n_partes=n_partes,
                       cobre_ids=";".join(cobre), parcial_ids=";".join(parcial))
            ids = [uid, *cobre]
        row["id_ambiguo"] = int(any(all_ids.get(i, 0) > 1 for i in ids if i))
        row.update(variante="base", contexto_ids="")
        out.append(row)
        if "caput" in variants and row["segmentador"] == "xsl":
            cv = caput_variant(e, r["Tipo"], r["Texto"])
            if cv is not None:
                out.append({**row, "Texto": cv[0], "chunk_id": f"{stem}#c{seq}", "variante": "caput",
                            "contexto_ids": cv[1]})
    leaves = _TOK.leaves() if _TOK.kind == "max" else [_TOK]
    texts = [r["Texto"] for r in out]
    per = [lf.count_many(texts) for lf in leaves]
    for i, r in enumerate(out):
        r["texto_sha256"] = hashlib.sha256(r["Texto"].encode("utf-8")).hexdigest()[:16]
        r["n_tokens"] = max(p[i] for p in per)
        r["n_tokens_cl100k"] = per[0][i] if len(per) > 0 else ""
        r["n_tokens_qwen3"] = per[1][i] if len(per) > 1 else ""
    _TOK.clear_cache()
    return out


def git_state() -> dict:
    """Code version of the run: HEAD commit and whether the segmentation code/inputs had
    uncommitted changes (a dirty run cannot be traced back to a commit exactly)."""
    def git(*a):
        return subprocess.run(["git", *a], cwd=HERE, capture_output=True, text=True).stdout.strip()
    try:
        dirty = git("status", "--porcelain", "--", str(HERE), str(ART_DIR.parent))
        return {"commit": git("rev-parse", "HEAD"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
                "dirty": bool(dirty), "dirty_files": dirty.splitlines()[:20]}
    except OSError:
        return {"commit": None}


def write_gzip(src: Path, dst: Path) -> None:
    """Byte-deterministic gzip (no name, mtime 0): the versioned copy of chunks_all.csv, which is
    above GitHub's 100 MB file limit uncompressed (the plain CSV is gitignored)."""
    import gzip
    with open(src, "rb") as fi, open(dst, "wb") as raw, \
            gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as fo:
        for block in iter(lambda: fi.read(1 << 20), b""):
            fo.write(block)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# --------------------------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------------------------

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--only", default=None, help="glob on XML file names to (re)generate")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    p.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    p.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    p.add_argument("--ementa-max-tokens", type=int, default=DEFAULT_EMENTA_MAX_TOKENS)
    p.add_argument("--keep-dropped-min-chars", type=int, default=300)
    p.add_argument("--allow-count-change", action="store_true")
    p.add_argument("--out-dir", type=Path, default=SEG_DIR)
    p.add_argument("--grouping-max-tokens", type=int, default=8192,
                   help="S3 grouping chunks (PRT…SSC) above this many reference tokens are left out of "
                        "chunks_all.csv and listed in groupings_over_limit.csv (0 = keep all)")
    p.add_argument("--skip-validation", action="store_true")
    p.add_argument("--variants", default="caput",
                   help=f"comma-separated text variants to add ({', '.join(VARIANTS)}; '' = none)")
    p.add_argument("--frozen", type=Path, default=None,
                   help="previous chunks_all.csv.gz for the diff_vs_frozen report of the validation")
    p.add_argument("--frozen-lexml-rev", default=None,
                   help="git revision of lexml/ that produced --frozen (documents whose LexML is "
                        "unchanged since then are compared row by row)")
    args = p.parse_args(argv)
    variants = tuple(v for v in args.variants.split(",") if v)
    if set(variants) - set(VARIANTS):
        p.error(f"unknown variants: {set(variants) - set(VARIANTS)}")

    cfg = {"tokenizer": args.tokenizer, "max_tokens": args.max_tokens,
           "ementa_max_tokens": args.ementa_max_tokens,
           "keep_dropped_min_chars": args.keep_dropped_min_chars, "variants": variants}
    out = args.out_dir
    stat_dir, ns_dir = out / "statutory", out / "non_statutory"
    timings: dict = {}
    t_all = time.time()
    sel = (lambda path: fnmatch.fnmatch(path.name, args.only)) if args.only else (lambda path: True)

    def need(csv_path: Path) -> bool:
        return args.overwrite or not csv_path.exists()

    with _pool(args.jobs, cfg) as pool:
        # 1. router -----------------------------------------------------------------------
        t0 = time.time()
        annexes = sorted(x for x in ART_DIR.glob("*.xml") if ANEXO_RE.search(x.name[:-4]))
        tok = get_tokenizer(args.tokenizer)
        decisions = classify_annexes.classify_all(tok=tok, ementa_max_tokens=args.ementa_max_tokens)
        counts = classify_annexes.check_counts(decisions, args.allow_count_change)
        classify_annexes.write_manifest(decisions, out / "annex_manifest.csv")
        cat_of = {d.arquivo: d.categoria for d in decisions}
        timings["1_router_s"] = round(time.time() - t0, 1)
        print(f"[1] router: {counts}", flush=True)

        # 2. statutory jobs + metadata ------------------------------------------------------
        t0 = time.time()
        mains = sorted(x for x in ART_DIR.glob("*.xml") if not ANEXO_RE.search(x.name[:-4]))
        stat_files = [x for x in mains + [a for a in annexes if cat_of[a.name] in ("A", "B")]
                      if sel(x) and need(stat_dir / (x.name[:-4] + ".csv"))]
        metas = _map(pool, w_meta, [str(x) for x in stat_files], [x.stat().st_size for x in stat_files])
        meta_of = {x.name: m for x, m in zip(stat_files, metas)}
        timings["2_metadata_s"] = round(time.time() - t0, 1)
        print(f"[2] statutory files: {len(stat_files)}", flush=True)

    # 3. XSL ----------------------------------------------------------------------------------
    t0 = time.time()
    jobs = [rxs.Job(x, stat_dir / (x.name[:-4] + ".csv"), {"metadados": meta_of[x.name]["text"],
                                                               # document-uri() URL-encodes non-ASCII names
                                                               "sigla": x.name[:-4],
                                                               # caput plan D-A: base rows carry no caput
                                                               "caput_em_paragrafo": "nao"})
            for x in stat_files]
    xsl_recs = rxs.run_jobs(jobs, n_jobs=args.jobs, overwrite=True)
    failures = [r for r in xsl_recs if r["status"] != "success"]
    timings["3_xsl_s"] = round(time.time() - t0, 1)
    print(f"[3] XSL: {len(xsl_recs)} files, {sum(r['rows'] or 0 for r in xsl_recs)} rows, "
          f"{len(failures)} failures, {timings['3_xsl_s']} s", flush=True)
    if failures:
        for f in failures:
            print("   FAIL", f["source"], f["error"])
        return 1

    with _pool(args.jobs, cfg) as pool:
        # 3b + 4. split + loose -------------------------------------------------------------
        t0 = time.time()
        post_args = []
        for x, rec in zip(stat_files, xsl_recs):
            tree_loose = classify_annexes.loose_elements(parse(x), include_preambulo=x.name in cat_of)
            post_args.append((str(x), str(stat_dir / (x.name[:-4] + ".csv")), meta_of[x.name]["text"],
                              rec["max_num_final"], bool(tree_loose), x.name in cat_of))
        post = _map(pool, w_statutory_post, post_args, [x.stat().st_size for x in stat_files])
        timings["3b_4_split_loose_s"] = round(time.time() - t0, 1)
        print(f"[3b] split: {sum(len(r['split']) for r in post)} ART/DSP rows split into "
              f"{sum(s['partes'] for r in post for s in r['split'])} parts", flush=True)
        print(f"[4] loose: {sum(r['loose_rows'] for r in post)} rows in "
              f"{sum(1 for r in post if r['loose_rows'])} files", flush=True)

        # 5. non-statutory ------------------------------------------------------------------
        t0 = time.time()
        docs = [x for x in sorted(NAO_DIR.glob("*.xml")) + [a for a in annexes if cat_of[a.name] == "C"]
                if sel(x) and need(ns_dir / (x.name[:-4] + ".csv"))]
        ns = _map(pool, w_document, [(str(x), str(ns_dir / (x.name[:-4] + ".csv"))) for x in docs],
                  [x.stat().st_size for x in docs])
        timings["5_non_statutory_s"] = round(time.time() - t0, 1)
        print(f"[5] non-statutory: {len(docs)} files, {sum(r['rows'] for r in ns)} rows", flush=True)

        # 6. merge + provenance -------------------------------------------------------------
        t0 = time.time()
        merge_args = []
        for x in mains + [a for a in annexes if cat_of[a.name] in ("A", "B")]:
            c = stat_dir / (x.name[:-4] + ".csv")
            if c.exists():
                merge_args.append((str(c), str(x), cat_of.get(x.name, "main"), "xsl"))
        for x in sorted(NAO_DIR.glob("*.xml")) + [a for a in annexes if cat_of[a.name] == "C"]:
            c = ns_dir / (x.name[:-4] + ".csv")
            if c.exists():
                merge_args.append((str(c), str(x), cat_of.get(x.name, "nao_articulado"), "python"))
        parts = _map(pool, w_provenance, merge_args, [Path(a[0]).stat().st_size for a in merge_args])
        df = pd.DataFrame([r for rows in parts for r in rows])
        cols = ["Tipo", "Rotulo", "Num_Inicio", "Num_Final", "Texto", "urn"] + EXTRA_COLS + PROV_COLS + TOKEN_COLS
        df = df[cols]
        # S3 option 2 (decided 2026-09-24): keep only the grouping chunks that fit the embedding
        # models' 8,192-token input; list the others (their rows stay in the per-file CSVs)
        over = df["Tipo"].isin(GROUP_TIPOS) & (df["n_tokens"] > args.grouping_max_tokens) \
            if args.grouping_max_tokens else pd.Series(False, index=df.index)
        df[over].drop(columns=["Texto"]).assign(n_chars=df.loc[over, "Texto"].str.len()) \
            .sort_values("n_tokens", ascending=False) \
            .to_csv(out / "groupings_over_limit.csv", index=False, quoting=1, lineterminator="\n")
        df = df[~over]
        df.to_csv(out / "chunks_all.csv", index=False, quoting=1, lineterminator="\n")
        write_gzip(out / "chunks_all.csv", out / "chunks_all.csv.gz")
        timings["6_merge_s"] = round(time.time() - t0, 1)
        print(f"[6] chunks_all.csv: {len(df)} rows; {int(over.sum())} grouping rows over "
              f"{args.grouping_max_tokens} tokens -> groupings_over_limit.csv", flush=True)

    timings["total_s"] = round(time.time() - t_all, 1)
    run_info = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "git": git_state(),
        "outputs_sha256": {name: file_sha256(out / name)
                           for name in ("chunks_all.csv", "chunks_all.csv.gz", "groupings_over_limit.csv",
                                        "annex_manifest.csv")
                           if (out / name).exists()},
        "command": " ".join([Path(sys.executable).name] + sys.argv),
        "flags": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        "saxon": rxs.saxon_version(),
        "annex_counts": counts,
        "timings": timings,
        "xsl": [{k: r[k] for k in ("source", "rows", "max_num_final", "duration_ms")} for r in xsl_recs],
        "metadata": {k: v for k, v in meta_of.items()},
        "statutory_post": post,
        "non_statutory": ns,
    }
    prev_path = out / "run_info.json"
    if args.only and prev_path.exists():
        # --only regenerates some files: keep the per-file results of the others
        prev = json.loads(prev_path.read_text(encoding="utf-8"))
        for key, name_of in (("xsl", lambda r: Path(r["source"]).name), ("statutory_post", lambda r: r["arquivo"]),
                             ("non_statutory", lambda r: r["arquivo"])):
            new_names = {name_of(r) for r in run_info[key]}
            run_info[key] = [r for r in prev.get(key, []) if name_of(r) not in new_names] + run_info[key]
        run_info["metadata"] = {**prev.get("metadata", {}), **run_info["metadata"]}
        run_info["previous_full_run"] = prev.get("previous_full_run") or {k: prev.get(k) for k in ("timestamp", "command")}
    (out / "run_info.json").write_text(json.dumps(run_info, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"total {timings['total_s']} s", flush=True)
    if args.skip_validation:
        return 0
    # 7. validation --------------------------------------------------------------------------
    import validate_segments
    vargs = ["--seg-dir", str(out), "--jobs", str(args.jobs), "--max-tokens", str(args.max_tokens),
             "--grouping-max-tokens", str(args.grouping_max_tokens)]
    if args.frozen:
        vargs += ["--frozen", str(args.frozen)]
        if args.frozen_lexml_rev:
            vargs += ["--frozen-lexml-rev", args.frozen_lexml_rev]
    return validate_segments.main(vargs)


if __name__ == "__main__":
    sys.exit(main())
