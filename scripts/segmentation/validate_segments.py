#!/usr/bin/env python3
"""Validation + statistics report of a segmentation run (plan §7).

Structural checks (each reported as pass/fail with examples):
  csv_schema       every per-file CSV has the 6 columns; chunks_all.csv has 6 + 3 + §2.7 columns
  non_empty        no empty Texto body
  chunk_id_unique  chunk_id unique; urn unique except rows with id_ambiguo = 1
  provenance       unidade_id / cobre_ids / parcial_ids exist in the XML (synthetic loose-text ids
                   resolve to their p run); artigo_id and agrupadores_ids agree with the XML ancestors
  intervals        within each file, the rows (split units represented by their original interval)
                   are nested or disjoint; sub-article rows lie inside their ART/DSP interval;
                   each part lies inside its unit's interval
  coverage         one ART (or complete parts 1..n) per Artigo outside Alteracao; one DSP per
                   top-level orphan dispositivo; every kept Agrupamento and every table outside
                   dispositivos appears in a row
  cap              ART/DSP/TXT/TAB <= cap, except listed uncuttable rows, which must be < 8,192
  split_complete   parts of a split unit contain every dispositivo exactly once
  text_coverage    per file, word-multiset coverage of the S1 bodies over the document text
                   (outside Alteracao, main-document preamble, dropped Agrupamentos, prefix-only
                   elements and statutory grouping labels) >= 98 %

Statistics: rows per Tipo / strategy / category; token percentiles per Tipo and tokenizer; split
units; over-cap sub-article and grouping rows (Q7); optional Gemini countTokens sample (§2.6).
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import random
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (AGRUPADORES, ANEXO_RE, ART_DIR, CSV_COLS, DISPOSITIVOS, NAO_DIR,  # noqa: E402
                    NSMAP, ORPHAN_TYPES, SEG_DIR, L, Positions, body_of, has_disp_ancestor,
                    in_alteracao, norm, parse, read_prov, read_rows, xstring)
import strategies  # noqa: E402

HARD_LIMIT = 8192
COVERAGE_MIN = 0.98
BASIC = ("ART", "DSP", "TXT", "TAB")
SUB = ("CPT", "PAR", "INC", "ALI", "ITE")
GROUP = ("PRT", "LIV", "TIT", "SBT", "CAP", "SEC", "SSC")
WORD = re.compile(r"\w+")
SYNTH = re.compile(r"^(?P<base>.+)_p(?P<a>\d+)-p(?P<b>\d+)$")


# --------------------------------------------------------------------------------------------
# per-file checks (run in a pool)
# --------------------------------------------------------------------------------------------

def _words(s: str) -> Counter:
    return Counter(WORD.findall(s.lower()))


def source_text_elements(tree, statutory: bool, is_annex: bool, dropped_ids: set, title_el):
    """Text-bearing elements that the S1 chunks must cover (see module docstring)."""
    root = tree.getroot()
    out = []
    for e in root.iter():
        name = L(e)
        if name not in ("p", "td", "li", "Rotulo", "TituloDispositivo", "NomeAgrupador"):
            continue
        anc = list(e.iterancestors())
        names = [L(a) for a in anc]
        if "Alteracao" in names or "Metadado" in names or "td" in names or "li" in names:
            continue
        if name == "p" and "p" in names:
            continue
        if statutory:
            if "ParteFinal" in names:
                continue
            if "ParteInicial" in names and not (is_annex and "Preambulo" in names):
                continue
            if name in ("Rotulo", "NomeAgrupador") and L(e.getparent()) in AGRUPADORES:
                continue  # grouping labels are only in S3 grouping rows, by design
        else:
            agr = [a for a in anc if L(a) == "Agrupamento"]
            if agr and (agr[0].get("nome") in ("epigrafe", "ementa") or agr[0].get("id") in dropped_ids):
                continue
        if title_el is not None and (e is title_el or title_el in anc):
            continue
        out.append(e)
    return out


def check_file(args: tuple) -> dict:
    arquivo, xml_path, rows, prov, cap, dropped_ids, title_text = args
    tree = parse(xml_path)
    root = tree.getroot()
    statutory = bool(tree.xpath("//l:ProjetoNorma", namespaces=NSMAP)) or \
        bool(tree.xpath("/l:LexML/l:Anexo/*[l:Articulacao or .//l:Artigo or .//l:Caput or .//l:Paragrafo "
                        "or .//l:Inciso or .//l:Alinea or .//l:Item]", namespaces=NSMAP))
    is_annex = bool(tree.xpath("/l:LexML/l:Anexo", namespaces=NSMAP))
    res = {"arquivo": arquivo, "errors": defaultdict(list), "stats": {}}
    err = res["errors"]
    ids: dict = defaultdict(list)
    for e in root.iter():
        if isinstance(e.tag, str) and e.get("id"):
            ids[e.get("id")].append(e)

    def exists(i: str) -> bool:
        if i in ids or i == "metadado_ementa":
            return True
        m = SYNTH.match(i)
        if m:
            base = m.group("base")
            conts = ids.get(base) or [c for c in root.iter() if L(c) and L(c).lower() == base]
            for c in conts:
                n_p = sum(1 for x in c if L(x) == "p")
                if 1 <= int(m.group("a")) <= int(m.group("b")) <= n_p:
                    return True
            return False
        return i.endswith("_lista")

    # ---- provenance ----
    for r in rows:
        for i in [r["unidade_id"], *filter(None, r["cobre_ids"].split(";")),
                  *filter(None, r["parcial_ids"].split(";"))]:
            if not exists(i):
                err["provenance_missing_id"].append(f"{r['chunk_id']}: {i}")
        if r["segmentador"] in ("xsl",) or (r["Tipo"] not in ("TXT", "TAB")):
            cands = ids.get(r["unidade_id"], [])
            ok = False
            for e in cands:
                chain = [*reversed(list(e.iterancestors())), e]
                disp = [a.get("id", "") for a in chain if L(a) in DISPOSITIVOS]
                grp = [a.get("id", "") for a in chain[:-1] if L(a) in AGRUPADORES]
                art_ok = (r["artigo_id"] == "" and L(e) in AGRUPADORES) or (disp and disp[0] == r["artigo_id"])
                if art_ok and ";".join(grp) == r["agrupadores_ids"]:
                    ok = True
                    break
            if not ok:
                err["provenance_ancestors"].append(f"{r['chunk_id']}: {r['unidade_id']}")

    # ---- intervals ----
    prov_by_urn = defaultdict(list)
    for p in prov:
        prov_by_urn[p["urn"]].append(p)
    split_units: dict = defaultdict(list)       # (Tipo, base urn, occurrence) -> part rows
    unit_iv: dict = {}
    occ: Counter = Counter()
    ivs = []
    for r in rows:
        s, e = int(r["Num_Inicio"]), int(r["Num_Final"])
        if s > e:
            err["interval_inverted"].append(r["chunk_id"])
        if int(r["n_partes"]) == 1:
            ivs.append((s, e, r["chunk_id"]))
            continue
        base = r["urn"].rsplit("_p", 1)[0]
        if int(r["parte"]) == 1:
            occ[(r["Tipo"], base)] += 1
        key = (r["Tipo"], base, occ[(r["Tipo"], base)])
        split_units[key].append(r)
        pv = [p for p in prov_by_urn[r["urn"]] if "intervalo_unidade" in p]
        if pv:
            unit_iv[key] = tuple(pv[min(len(pv), occ[(r["Tipo"], base)]) - 1]["intervalo_unidade"])
        else:
            a, b = unit_iv.get(key, (s, e))
            unit_iv[key] = (min(a, s), max(b, e))
    for key, (s, e) in unit_iv.items():
        ivs.append((s, e, f"unit:{key[1].rsplit('!', 1)[-1]}"))
        for r in split_units[key]:
            if not (s <= int(r["Num_Inicio"]) and int(r["Num_Final"]) <= e):
                err["part_outside_unit"].append(r["chunk_id"])
    ivs.sort(key=lambda x: (x[0], -x[1]))
    stack: list = []
    for s, e, cid in ivs:
        while stack and stack[-1][1] < s:
            stack.pop()
        if stack and e > stack[-1][1]:
            err["intervals_crossing"].append(f"{cid} x {stack[-1][2]}")
        stack.append((s, e, cid))
    # sub-article rows inside their ART/DSP
    top_iv: dict = defaultdict(list)
    for r in rows:
        if r["Tipo"] in ("ART", "DSP") and int(r["n_partes"]) == 1:
            top_iv[r["unidade_id"]].append((int(r["Num_Inicio"]), int(r["Num_Final"])))
    for (tipo, base, _k), iv in unit_iv.items():
        if tipo in ("ART", "DSP"):
            top_iv[base.rsplit("!", 1)[-1]].append(iv)
    for r in rows:
        if r["Tipo"] in SUB and r["artigo_id"]:
            s, e = int(r["Num_Inicio"]), int(r["Num_Final"])
            if not any(a <= s and e <= b for a, b in top_iv.get(r["artigo_id"], [])):
                err["sub_outside_article"].append(r["chunk_id"])

    # ---- coverage ----
    artigos = [e for e in root.iter() if L(e) == "Artigo" and not in_alteracao(e)]
    orphans = [e for e in root.iter() if L(e) in ORPHAN_TYPES and not in_alteracao(e) and not has_disp_ancestor(e)]
    n_art_units = sum(1 for r in rows if r["Tipo"] == "ART" and int(r["parte"]) == 1)
    n_dsp_units = sum(1 for r in rows if r["Tipo"] == "DSP" and int(r["parte"]) == 1)
    if n_art_units != len(artigos):
        err["coverage_art"].append(f"{n_art_units} ART units vs {len(artigos)} Artigo")
    if n_dsp_units != len(orphans):
        err["coverage_dsp"].append(f"{n_dsp_units} DSP units vs {len(orphans)} top-level orphans")
    for (tipo, base, _k), parts in split_units.items():
        ks = sorted(int(r["parte"]) for r in parts)
        n = int(parts[0]["n_partes"])
        if ks != list(range(1, n + 1)):
            err["coverage_parts"].append(f"{base}: parts {ks} of {n}")
    seen = set()
    for r in rows:
        seen.add(r["unidade_id"])
        seen.update(filter(None, r["cobre_ids"].split(";")))
        seen.update(filter(None, r["parcial_ids"].split(";")))
    for a in root.iter(f"{{{NSMAP['l']}}}Agrupamento"):
        if a.get("nome") in ("epigrafe", "ementa") or a.get("id") in dropped_ids:
            continue
        if title_text and norm(xstring(a)) == title_text:
            continue
        has_text = any(L(c) in ("p", "ul", "ol") and norm(xstring(c)) for c in a)
        if has_text and a.get("id") not in seen:
            err["coverage_agrupamento"].append(a.get("id"))
    for t in root.iter(f"{{{NSMAP['l']}}}table"):
        if has_disp_ancestor(t) or in_alteracao(t):
            continue
        if t.get("id") not in seen:
            err["coverage_table"].append(t.get("id"))

    # ---- cap ----
    uncut = []
    for r in rows:
        if r["Tipo"] in BASIC and int(r["n_tokens"]) > cap:
            flagged = any(p.get("oversize") for p in prov_by_urn.get(r["urn"], []))
            uncut.append({"chunk_id": r["chunk_id"], "tokens": int(r["n_tokens"]), "flagged": flagged})
            if not flagged:
                err["cap_unflagged"].append(f"{r['chunk_id']} ({r['n_tokens']} tokens)")
            if int(r["n_tokens"]) >= HARD_LIMIT:
                err["cap_hard_limit"].append(f"{r['chunk_id']} ({r['n_tokens']} tokens)")
    res["stats"]["uncuttable"] = uncut

    # ---- split completeness ----
    for (tipo, base, k_occ), parts in split_units.items():
        if tipo not in ("ART", "DSP"):
            continue
        uid = parts[0]["unidade_id"]
        cands = [e for e in ids.get(uid, []) if not in_alteracao(e)]
        if not cands:
            err["split_incomplete"].append(f"{base}: root not found")
            continue
        cobre = Counter(i for r in parts for i in filter(None, r["cobre_ids"].split(";")))
        parcial = {i for r in parts for i in filter(None, r["parcial_ids"].split(";"))}
        best = None
        for rootel in cands:  # duplicate ids: the unit is the candidate its parts fit
            # the source has duplicate ids inside some units: an id covered m times is fine when
            # m elements of the unit carry it
            occ_ids = Counter(e.get("id") for e in rootel.iter() if isinstance(e.tag, str) and e.get("id"))
            problems = []
            for d in rootel.iter():
                if d is rootel or L(d) not in DISPOSITIVOS or in_alteracao(d):
                    continue
                chain = [d, *d.iterancestors()]
                chain = chain[:chain.index(rootel)]
                covered = [a for a in chain if cobre.get(a.get("id", ""), 0)]
                if len(covered) == 1 and cobre[covered[0].get("id")] == occ_ids[covered[0].get("id")]:
                    continue
                if not covered and d.get("id") in parcial:
                    continue
                problems.append(f"{d.get('id')} covered by {[a.get('id') for a in covered]}")
            if best is None or len(problems) < len(best):
                best = problems
        if best:
            err["split_incomplete"].append(f"{base}: {best[:5]}")

    # ---- text coverage (word multiset) ----
    title_el = None
    if title_text:
        for e in root.iter():
            if L(e) in ("p", "Agrupamento") and norm(xstring(e)) == title_text:
                title_el = e
                break
    src_els = source_text_elements(tree, statutory, is_annex, dropped_ids, title_el)
    src = Counter()
    for e in src_els:
        if L(e) == "p" and any(L(c) == "p" for c in e.iter() if c is not e):
            continue
        src += _words(norm(xstring(e)))
    s1 = Counter()
    for r in rows:
        if r["Tipo"] in strategies.S1:
            s1 += _words(body_of(r["Texto"]))
    total = sum(src.values())
    covered = sum(min(n, s1.get(w, 0)) for w, n in src.items())
    cov = covered / total if total else 1.0
    res["stats"]["text_coverage"] = round(cov, 4)
    res["stats"]["source_words"] = total
    if total and cov < COVERAGE_MIN:
        missing = Counter({w: n - s1.get(w, 0) for w, n in src.items() if n > s1.get(w, 0)})
        err["text_coverage"].append(f"{cov:.3f} (missing e.g. {[w for w, _ in missing.most_common(8)]})")
    res["errors"] = dict(err)
    return res


# --------------------------------------------------------------------------------------------
# Gemini countTokens sample (plan §2.6)
# --------------------------------------------------------------------------------------------

def gemini_sample(df: pd.DataFrame, n: int, model: str) -> dict:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        return {"status": "not run", "reason": "no GEMINI_API_KEY / GOOGLE_API_KEY in the environment"}
    rng = random.Random(20260924)
    idx = rng.sample(range(len(df)), min(n, len(df)))
    out, errors = [], []
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:countTokens?key={key}"
    for i in idx:
        body = json.dumps({"contents": [{"parts": [{"text": df.iloc[i]["Texto"]}]}]}).encode()
        try:
            req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as fh:
                g = json.loads(fh.read())["totalTokens"]
            out.append((int(df.iloc[i]["n_tokens"]), int(g)))
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc)[:200])
            if len(errors) > 5:
                break
    if not out:
        return {"status": "failed", "errors": errors[:5]}
    over = [(r, g) for r, g in out if g > r]
    return {"status": "run", "model": model, "n": len(out), "gemini_gt_reference": len(over),
            "max_excess": max((g - r for r, g in over), default=0),
            "max_gemini": max(g for _, g in out), "errors": errors[:5]}


# --------------------------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------------------------

def pct(s: pd.Series) -> dict:
    if s.empty:
        return {}
    q = s.quantile([0.5, 0.9, 0.99]).round().astype(int).tolist()
    return {"n": int(s.size), "p50": q[0], "p90": q[1], "p99": q[2], "max": int(s.max())}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--seg-dir", type=Path, default=SEG_DIR)
    p.add_argument("--max-tokens", type=int, default=1024)
    p.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    p.add_argument("--grouping-max-tokens", type=int, default=8192)
    p.add_argument("--gemini-sample", type=int, default=500)
    p.add_argument("--gemini-model", default="gemini-embedding-2")
    args = p.parse_args(argv)
    seg = args.seg_dir
    checks: dict = {}

    df = pd.read_csv(seg / "chunks_all.csv", dtype=str, keep_default_na=False)
    for c in ("Num_Inicio", "Num_Final", "parte", "n_partes", "n_tokens", "n_tokens_cl100k",
              "n_tokens_qwen3", "id_ambiguo"):
        df[c] = pd.to_numeric(df[c])
    run_info = json.loads((seg / "run_info.json").read_text(encoding="utf-8")) if (seg / "run_info.json").exists() else {}

    # ---- schema ----
    bad_schema = []
    for d in ("statutory", "non_statutory"):
        for c in sorted((seg / d).glob("*.csv")):
            with open(c, encoding="utf-8") as fh:
                header = fh.readline().strip().replace('"', "").split(",")
            if header != CSV_COLS:
                bad_schema.append(c.name)
            elif any(len(r) != 6 for r in [list(x.values()) for x in read_rows(c)]):
                bad_schema.append(c.name)
    expected_cols = 6 + 3 + 14 + 3
    checks["csv_schema"] = {"ok": not bad_schema and df.shape[1] == expected_cols,
                            "detail": f"chunks_all columns = {df.shape[1]} (6 + 3 + 14 provenance + 3 token counts)",
                            "examples": bad_schema[:10]}
    empty = df[df["Texto"].map(lambda t: not body_of(t).strip())]
    checks["non_empty"] = {"ok": empty.empty, "count": len(empty), "examples": empty["chunk_id"].head(10).tolist()}
    dup_cid = df[df["chunk_id"].duplicated(keep=False)]
    dup_urn = df[df["urn"].duplicated(keep=False) & (df["id_ambiguo"] == 0)]
    checks["chunk_id_unique"] = {"ok": dup_cid.empty and dup_urn.empty,
                                 "dup_chunk_id": len(dup_cid), "dup_urn_not_ambiguous": len(dup_urn),
                                 "examples": dup_urn["urn"].head(10).tolist()}

    # ---- per-file checks ----
    ns_stats = {r["arquivo"]: r["stats"] for r in run_info.get("non_statutory", [])}
    post = {r["arquivo"]: r for r in run_info.get("statutory_post", [])}
    tasks = []
    for arquivo, g in df.groupby("arquivo", sort=True):
        xml = (NAO_DIR / arquivo) if (NAO_DIR / arquivo).exists() else (ART_DIR / arquivo)
        csv_dir = seg / ("statutory" if (seg / "statutory" / (arquivo[:-4] + ".csv")).exists() else "non_statutory")
        prov = read_prov(csv_dir / (arquivo[:-4] + ".csv"))
        st = ns_stats.get(arquivo, {})
        dropped = {d["id"] for d in st.get("dropped", [])}
        title = st.get("annex_title_prefix_only") or post.get(arquivo, {}).get("loose_stats", {}).get("annex_title_prefix_only", "")
        tasks.append((arquivo, str(xml), g.to_dict("records"), prov, args.max_tokens, dropped, title))
    with ProcessPoolExecutor(max_workers=args.jobs, mp_context=mp.get_context("spawn")) as pool:
        results = list(pool.map(check_file, tasks, chunksize=4))
    agg: dict = defaultdict(list)
    coverage = {}
    uncuttable = []
    for r in results:
        for k, v in r["errors"].items():
            agg[k] += [f"{r['arquivo']}: {x}" for x in v]
        coverage[r["arquivo"]] = r["stats"].get("text_coverage")
        uncuttable += [{"arquivo": r["arquivo"], **u} for u in r["stats"].get("uncuttable", [])]
    groups = {
        "provenance": ["provenance_missing_id", "provenance_ancestors"],
        "intervals": ["interval_inverted", "intervals_crossing", "sub_outside_article", "part_outside_unit"],
        "coverage": ["coverage_art", "coverage_dsp", "coverage_parts", "coverage_agrupamento", "coverage_table"],
        "cap": ["cap_unflagged", "cap_hard_limit"],
        "split_complete": ["split_incomplete"],
        "text_coverage": ["text_coverage"],
    }
    for name, keys in groups.items():
        n = sum(len(agg.get(k, [])) for k in keys)
        checks[name] = {"ok": n == 0, "count": n,
                        "by_kind": {k: len(agg.get(k, [])) for k in keys},
                        "examples": [x for k in keys for x in agg.get(k, [])[:5]]}
    cov_vals = [v for v in coverage.values() if v is not None]
    checks["text_coverage"]["min"] = min(cov_vals) if cov_vals else None
    checks["text_coverage"]["files_below_threshold"] = sorted(
        (k, v) for k, v in coverage.items() if v is not None and v < COVERAGE_MIN)
    checks["cap"]["uncuttable"] = uncuttable

    # ---- S3 grouping limit (option 2) ----
    lim = args.grouping_max_tokens
    over_path = seg / "groupings_over_limit.csv"
    over = pd.read_csv(over_path, dtype=str, keep_default_na=False) if over_path.exists() else pd.DataFrame()
    in_all = df[df["Tipo"].isin(GROUP) & (df["n_tokens"] > lim)] if lim else df.iloc[0:0]
    overlap = set(over.get("chunk_id", [])) & set(df["chunk_id"])
    checks["grouping_limit"] = {"ok": in_all.empty and not overlap, "limit": lim,
                                "listed": len(over), "over_limit_in_chunks_all": len(in_all),
                                "listed_and_in_chunks_all": len(overlap),
                                "examples": in_all["chunk_id"].head(10).tolist()}

    # ---- statistics ----
    stats: dict = {}
    stats["rows_total"] = len(df)
    stats["rows_per_tipo"] = df["Tipo"].value_counts().to_dict()
    stats["rows_per_strategy"] = {s: int(strategies.strategy_mask(df["Tipo"], s).sum()) for s in ("S1", "S2", "S3")}
    stats["rows_per_categoria"] = df["categoria"].value_counts().to_dict()
    stats["rows_per_categoria_tipo"] = {f"{a}/{b}": int(n) for (a, b), n in df.groupby(["categoria", "Tipo"]).size().items()}
    stats["files"] = int(df["arquivo"].nunique())
    stats["tokens_per_tipo"] = {t: {"reference": pct(g["n_tokens"]), "cl100k_base": pct(g["n_tokens_cl100k"]),
                                    "qwen3": pct(g["n_tokens_qwen3"])} for t, g in df.groupby("Tipo")}
    stats["tokens_per_strategy_sum"] = {s: int(df.loc[strategies.strategy_mask(df["Tipo"], s), "n_tokens"].sum())
                                        for s in ("S1", "S2", "S3")}
    split = [s for r in run_info.get("statutory_post", []) for s in r["split"]]
    stats["split_units"] = {"units": len(split), "parts": sum(s["partes"] for s in split),
                            "leaf_split": sum(1 for s in split if s["leaf_split"])}
    stats["split_units"]["by_tipo"] = {k: int(v) for k, v in df[(df["n_partes"] > 1) & (df["parte"] == 1)
                                                                  & df["Tipo"].isin(["ART", "DSP"])]["Tipo"].value_counts().items()}
    stats["split_units"]["head_truncated"] = sum(1 for s in split if s.get("head_truncated"))
    stats["split_list"] = sorted(split, key=lambda s: -s["tokens"])
    stats["ns_split_units"] = sum(r["stats"]["split_units"] for r in run_info.get("non_statutory", []))
    stats["over_cap_non_basic"] = {t: {"over_cap": int((g["n_tokens"] > args.max_tokens).sum()),
                                       "over_8192": int((g["n_tokens"] >= HARD_LIMIT).sum()), "n": len(g)}
                                   for t, g in df[df["Tipo"].isin(SUB + GROUP)].groupby("Tipo")}
    stats["groupings_over_limit"] = {t: int(n) for t, n in over["Tipo"].value_counts().items()} if len(over) else {}
    stats["id_ambiguo_rows"] = int(df["id_ambiguo"].sum())
    stats["id_ambiguo_basic_rows"] = int(df[df["Tipo"].isin(BASIC)]["id_ambiguo"].sum())
    dropped = Counter()
    kept = []
    for r in run_info.get("non_statutory", []):
        for d in r["stats"].get("dropped", []):
            dropped[d["nome"]] += 1
        kept += [{"arquivo": r["arquivo"], **d} for d in r["stats"].get("kept_long_dropped", [])]
    stats["dropped_agrupamentos"] = dict(dropped)
    stats["kept_long_dropped"] = kept
    stats["meta_sources"] = dict(Counter(r["stats"].get("meta_source", "") for r in run_info.get("non_statutory", [])))
    stats["text_coverage_distribution"] = pct(pd.Series(cov_vals) * 1000) if cov_vals else {}
    stats["gemini_sample"] = gemini_sample(df[df["Tipo"].isin(strategies.S3)], args.gemini_sample, args.gemini_model)

    ok = all(c["ok"] for c in checks.values())
    report = {"timestamp": datetime.now().isoformat(timespec="seconds"), "ok": ok,
              "run": {k: run_info.get(k) for k in ("timestamp", "command", "flags", "saxon", "annex_counts", "timings")},
              "checks": checks, "stats": stats}
    (seg / "segmentation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str),
                                                  encoding="utf-8")
    (seg / "segmentation_report.md").write_text(render_md(report, args.max_tokens), encoding="utf-8")
    print(f"validation {'OK' if ok else 'FAILED'}: " +
          ", ".join(f"{k}={'ok' if v['ok'] else 'FAIL'}" for k, v in checks.items()))
    return 0 if ok else 1


def render_md(rep: dict, cap: int) -> str:
    st, ck, run = rep["stats"], rep["checks"], rep["run"]
    L_ = ["# Segmentation report", "", f"- Generated: {rep['timestamp']}",
          f"- Overall: **{'OK' if rep['ok'] else 'FAILED'}**", f"- Command: `{run.get('command')}`",
          f"- Flags: `{json.dumps(run.get('flags'), ensure_ascii=False)}`",
          f"- Saxon: {run.get('saxon')}; annex categories: {run.get('annex_counts')}",
          f"- Timings (s): {run.get('timings')}", "", "## Checks", "", "| Check | Result | Detail |", "|---|---|---|"]
    for k, v in ck.items():
        detail = {kk: vv for kk, vv in v.items() if kk not in ("ok", "examples", "uncuttable", "files_below_threshold")}
        L_.append(f"| {k} | {'ok' if v['ok'] else '**FAIL**'} | {json.dumps(detail, ensure_ascii=False, default=str)[:300]} |")
    fails = [(k, v["examples"]) for k, v in ck.items() if v.get("examples")]
    if fails:
        L_ += ["", "### Examples", ""]
        for k, ex in fails:
            L_.append(f"- **{k}**: " + "; ".join(f"`{e}`" for e in ex[:8]))
    L_ += ["", "## Rows", "", f"- Total rows: {st['rows_total']} in {st['files']} files",
           f"- Per strategy: {st['rows_per_strategy']}", "", "| Tipo | Rows | ref p50 | p90 | p99 | max |",
           "|---|---:|---:|---:|---:|---:|"]
    for t, n in sorted(st["rows_per_tipo"].items(), key=lambda x: -x[1]):
        r = st["tokens_per_tipo"][t]["reference"]
        L_.append(f"| {t} | {n} | {r['p50']} | {r['p90']} | {r['p99']} | {r['max']} |")
    L_ += ["", "Tokens per tokenizer (p50 / p99 / max):", "", "| Tipo | cl100k_base | Qwen3 |", "|---|---|---|"]
    for t, d in st["tokens_per_tipo"].items():
        a, b = d["cl100k_base"], d["qwen3"]
        L_.append(f"| {t} | {a['p50']} / {a['p99']} / {a['max']} | {b['p50']} / {b['p99']} / {b['max']} |")
    L_ += ["", f"- Per category: {st['rows_per_categoria']}", "",
           f"## Split units (cap {cap})", "",
           f"- ART/DSP units split: {st['split_units']['units']} into {st['split_units']['parts']} parts "
           f"({st['split_units']['by_tipo']}); within-leaf splits: {st['split_units']['leaf_split']}; "
           f"truncated HEAD (D3): {st['split_units'].get('head_truncated')}",
           f"- Non-statutory TXT/TAB units split: {st['ns_split_units']}",
           f"- Uncuttable over-cap rows: {len(ck['cap'].get('uncuttable', []))}", "",
           "| Unit | Tokens | Parts | Leaf split |", "|---|---:|---:|---|"]
    for s in st["split_list"][:40]:
        L_.append(f"| {s['rotulo']} | {s['tokens']} | {s['partes']} | {'yes' if s['leaf_split'] else ''} |")
    if len(st["split_list"]) > 40:
        L_.append(f"| … {len(st['split_list']) - 40} more (see segmentation_report.json) | | | |")
    L_ += ["", "## Over-cap rows that are not split (Q7)", "",
           f"Grouping chunks above {ck['grouping_limit']['limit']} tokens are not in chunks_all.csv "
           f"(S3 option 2): {ck['grouping_limit']['listed']} listed in `groupings_over_limit.csv` "
           f"{st.get('groupings_over_limit')}. The table counts the rows kept.", "",
           "| Tipo | Rows | > cap | ≥ 8,192 |", "|---|---:|---:|---:|"]
    for t, d in st["over_cap_non_basic"].items():
        L_.append(f"| {t} | {d['n']} | {d['over_cap']} | {d['over_8192']} |")
    L_ += ["", "## Other", "",
           f"- Rows with `id_ambiguo = 1`: {st['id_ambiguo_rows']} (basic units: {st['id_ambiguo_basic_rows']})",
           f"- Dropped Agrupamentos (Q4): {st['dropped_agrupamentos']}",
           f"- Long 'dropped' Agrupamentos kept as TXT (D2): {len(st['kept_long_dropped'])}",
           f"- Non-statutory metadata sources: {st['meta_sources']}",
           f"- Text coverage (‰) distribution: {st['text_coverage_distribution']}; files below "
           f"{COVERAGE_MIN:.0%}: {ck['text_coverage'].get('files_below_threshold')}",
           f"- Gemini countTokens sample: {st['gemini_sample']}", ""]
    return "\n".join(L_)


if __name__ == "__main__":
    sys.exit(main())
