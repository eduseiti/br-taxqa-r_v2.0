"""Phase 5 analyses that need no LLM, on top of the judge labels of ``nuggets.py score`` / ``ctxsupport``.

- value checks next to the judge (plan v2 §5.4): value hit, value conflict, temporal substitution, and the
  "values not in context" proxy of RAG Phase 3 with spelled-out numbers fixed (Phase 3 note §6.3);
- legal-provision score of the answers' citations (plan v2 §5.5): the cited context texts against the gold
  provisions, with the matcher of the retrieval evaluation, so citation and retrieval scores are comparable;
- retrieval ↔ answer linkage (first-evaluation note §3.1) and utilisation / leakage per nugget (§4.3 there);
- robustness of the comparisons (plan v2 §5.3, §5.6): slices, perturbed nugget sets, stable-only nuggets, the
  cross-set comparisons and the agreement of two judges on real answers.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from . import scoring, values
from .scoring import CREDIT, REPO, jl

RETRIEVAL = REPO / "runs" / "retrieval" / "jua-4b-mixed" / "irpf"
STRICT = {k: float(k == "support") for k in CREDIT}


# ------------------------------------------------------------------ labels in long form

def nugget_labels(base: Path) -> pd.DataFrame:
    """One row per (output, nugget) of every ``labels.jsonl`` under ``base`` (score or ctxsupport outputs)."""
    rows = []
    for lp in sorted(Path(base).glob("**/labels.jsonl")):
        man = json.loads((lp.parent / "manifest.json").read_text())
        if man["kind"] == "score":
            run = json.loads((REPO / man["run"] / "run.json").read_text())
            meta = {"run_id": man["run_id"], "run": man["run"], "llm": run["llm"]["name"],
                    "context_id": man["run_id"].split("/")[-1]}
        else:
            meta = {"contexts": man["contexts"], "context_id": lp.parent.name}
        for x in jl(lp):
            for y in x["labels"]:
                rows.append({**meta, "question_number": x["question_number"], "source": x["source"],
                             "nugget_id": y["nugget_id"], "label": y["label"]})
    return pd.DataFrame(rows)


def nugget_table(nugs: dict[str, list[dict]]) -> pd.DataFrame:
    return pd.DataFrame([{"nugget_id": n["nugget_id"], "question_number": q, "importance": n["importance"],
                          "category": n["category"], "pgd": bool(n["flags"].get("procedimento_pgd")),
                          "temporal": bool(n["flags"].get("temporal")), "stability": n.get("stability"),
                          "audit_flagged": bool(n.get("audit")), "has_values": bool(n["values"])}
                         for q, ns in nugs.items() for n in ns])


def per_question_long(lab: pd.DataFrame, nt: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Per-question scores (``scoring.question_scores``) of a long label table, restricted to its nuggets."""
    imp = dict(zip(nt.nugget_id, nt.importance))
    rows = []
    for key, g in lab.groupby(by + ["question_number"], sort=False):
        rows.append({**dict(zip(by + ["question_number"], key)),
                     **scoring.question_scores(g.label.tolist(), [imp[n] for n in g.nugget_id])})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ value checks (plan v2 §5.4)

def value_keys(text: str) -> set[tuple]:
    out = set()
    for v in values.extract(values.digits_for_words(text)):
        out.add((v["kind"], v["normalized"]))
        if v["kind"] == "date":
            out.add(("date_md", str(v["normalized"])[-5:]))
    return out


def _number_part(v: dict) -> str:
    return v["raw"].replace("R$", "").strip() if v["kind"] == "brl" else re.match(r"[\d,]+", v["raw"]).group(0)


class CorpusNear:
    """Values of the same kind written within ``window`` characters of a value in the legal corpus (article
    chunks): the candidates for a temporal substitution (the same item in another year's table or wording)."""

    def __init__(self, texts: list[str], window: int = 300):
        self.texts = [values.digits_for_words(t) if "por cento" in t else t for t in texts]
        self.window, self._memo = window, {}

    def near(self, v: dict) -> set:
        key = (v["kind"], v["normalized"])
        if key not in self._memo:
            num = _number_part(v)
            pat = re.compile(rf"R\$\s*{re.escape(num)}(?![\d,])" if v["kind"] == "brl"
                             else rf"(?<![\d.,]){re.escape(num)}\s*%")
            out = set()
            for t in self.texts:
                if num not in t:
                    continue
                for m in pat.finditer(t):
                    w = t[max(0, m.start() - self.window): m.end() + self.window]
                    out |= {(x["kind"], x["normalized"]) for x in values.extract(w) if x["kind"] == v["kind"]}
            out.discard(key)
            self._memo[key] = out
        return self._memo[key]


def _date_parts(norm: str) -> tuple[str | None, str]:
    return (None if norm.startswith("--") else norm[:4]), norm[-5:]


def value_check(v: dict, ans: set, known: set) -> tuple[bool, list]:
    """(hit, conflicting answer values) of one nugget value. ``known``: every value of the question's nuggets and
    of its text (never a conflict). R$: another amount at 0.5–2×; %: another rate; dates: the same day and month
    in another year, or another day of the same month and year."""
    k, x = v["kind"], v["normalized"]
    if k == "date":
        y0, md0 = _date_parts(x)
        hit = (k, x) in ans or ((y0 is None) and ("date_md", md0) in ans) or \
            any(kk == "date" and _date_parts(n)[0] is None and _date_parts(n)[1] == md0 for kk, n in ans)
        conf = []
        for kk, n in ans:
            if kk != "date" or (kk, n) in known or hit:
                continue
            y1, md1 = _date_parts(n)
            if y0 and y1 and ((md1 == md0 and y1 != y0) or (y1 == y0 and md1[:2] == md0[:2] and md1 != md0)):
                conf.append(n)
        return hit, conf
    hit = (k, x) in ans
    if hit:
        return True, []
    conf = [n for kk, n in ans if kk == k and (kk, n) not in known and (k != "brl" or 0.5 * x <= n <= 2 * x)]
    return False, conf


_WORD = re.compile(r"[a-zà-ú]{4,}")
_STOP = set("para pela pelo pelas pelos como sobre entre desde quando onde qual quais seja sejam será serão deve "
            "devem pode podem caso essa esse esta este isso nesse nessa também ainda mesmo mesma sido sendo".split())


def _content(text: str) -> set[str]:
    return set(_WORD.findall(text.lower())) - _STOP


def slot_sentence(nugget_text: str, sentences: list[str], min_overlap: float = 0.4) -> str:
    """The answer sentence that best restates the nugget (share of the nugget's content words), or ''."""
    nw = _content(nugget_text)
    best, score = "", 0.0
    for s in sentences:
        o = len(nw & _content(s)) / len(nw) if nw else 0.0
        if o > score:
            best, score = s, o
    return best if score >= min_overlap else ""


def value_checks(lab: pd.DataFrame, nugs: dict, qs: dict, answers: dict, near: CorpusNear) -> pd.DataFrame:
    """One row per (run, nugget with values): judge label, value hit (anywhere in the answer), conflict (another
    value of the same kind in the answer sentence that best restates the nugget, or the answer's only value of
    that kind when the nugget has the question's only one: the "same slot") and temporal
    substitution (that value is another period's value of the provision: same day and month in another year, or
    an amount / rate the corpus writes next to the nugget's value)."""
    known = {q: set().union(*[{(v["kind"], v["normalized"]) for v in n["values"]} for n in ns],
                            value_keys(qs[q]["question_text"])) for q, ns in nugs.items() if q in qs}
    by_id = {n["nugget_id"]: n for ns in nugs.values() for n in ns}
    kinds = {q: Counter(v["kind"] for n in ns for v in n["values"]) for q, ns in nugs.items()}
    rows = []
    sub = lab[lab.nugget_id.map(lambda i: bool(by_id[i]["values"]))]
    for (run_id, q), g in sub.groupby(["run_id", "question_number"], sort=False):
        text = answers[run_id].get(q, "")
        ans = value_keys(text)
        sentences = [x for x in re.split(r"(?<=[.;:])\s+(?=[A-ZÀ-Ú])|\n", text) if x.strip()]
        for r in g.itertuples():
            n = by_id[r.nugget_id]
            slot = value_keys(slot_sentence(n["text"], sentences))
            hits, confs, temporal = [], [], False
            for v in n["values"]:
                h = value_check(v, ans, known[q])[0]
                # the only value of its kind in the question's nuggets and in the answer: the same slot
                sole = {x for x in ans if x[0] == v["kind"]}
                sk = slot | sole if kinds[q][v["kind"]] == 1 and len(sole) == 1 else slot
                c = [] if h else value_check(v, sk, known[q])[1]
                hits.append(h)
                confs += c
                if c and v["kind"] == "date":
                    temporal |= any(_date_parts(x)[1] == _date_parts(v["normalized"])[1] for x in c)
                elif c:
                    temporal |= bool(set((v["kind"], x) for x in c) & near.near(v))
            rows.append({"run_id": run_id, "llm": r.llm, "context_id": r.context_id, "question_number": q,
                         "nugget_id": r.nugget_id, "importance": n["importance"], "label": r.label,
                         "source": r.source, "kinds": ",".join(sorted({v["kind"] for v in n["values"]})),
                         "value_hit": all(hits), "any_value_hit": any(hits), "conflict": bool(confs) and not any(hits),
                         "temporal_substitution": temporal and not any(hits), "conflicting": ";".join(map(str, confs))})
    return pd.DataFrame(rows)


def value_summary(vc: pd.DataFrame) -> pd.DataFrame:
    """Per run: value hit, the judge's ``support`` against the hit, conflicts and their ``contradicts`` rate."""
    def agg(g):
        j = g[g.source == "judge"]
        sup = j.label == "support"
        return pd.Series({
            "n": len(g), "value_hit": g.value_hit.mean(), "support": (g.label == "support").mean(),
            "support_given_hit": sup[j.value_hit].mean(), "hit_given_support": j.value_hit[sup].mean(),
            "agree": (sup == j.value_hit).mean(), "conflict": g.conflict.mean(),
            "contradicts_given_conflict": (j.label[j.conflict] == "contradicts").mean(),
            "conflict_given_contradicts": j.conflict[j.label == "contradicts"].mean(),
            "temporal_substitution": g.temporal_substitution.mean(), "n_conflict": int(g.conflict.sum()),
            "n_temporal": int(g.temporal_substitution.sum())})
    return vc.groupby(["llm", "context_id"]).apply(agg, include_groups=False).reset_index()


def values_not_in_context(run_dir: Path, ctx: dict[str, dict], qs: dict) -> dict:
    """The Phase 3 proxy with spelled-out numbers and "1°" fixed: answers with a value in neither the context nor
    the question (``old`` is the proxy as written by ``rag.py run``)."""
    flags, old = [], []
    for ln in jl(Path(run_dir) / "answers.jsonl"):
        if ln["status"] != "ok" or ln.get("abstained") or ln["question_number"] not in ctx:
            continue
        q = ln["question_number"]
        present = value_keys(ctx[q]["context"] + "\n" + qs[q]["question_text"])
        miss = [v for v in values.extract(values.digits_for_words(ln.get("answer") or ""))
                if (v["kind"], v["normalized"]) not in present
                and not (v["kind"] == "date" and ("date_md", str(v["normalized"])[-5:]) in present)]
        flags.append(bool(miss))
        old.append(bool(ln.get("checks", {}).get("values_not_in_context")))
    return {"n_answers": len(flags), "with_value_not_in_context": float(np.mean(flags)) if flags else np.nan,
            "as_in_phase3": float(np.mean(old)) if old else np.nan}


# ------------------------------------------------------------------ legal-provision score of citations (§5.5)

class ProvisionScorer:
    """Gold coverage of a list of context texts, with the matcher and the gold items of ``rag.py context``."""

    def __init__(self, annex_rule: str = "either"):
        from ragpipe.contexts import Item, coverage
        from ragpipe.data import Paths, load_chunks, load_dataset
        from ragpipe.relevance import Matcher, gold_items
        paths = Paths()
        rman = json.loads((RETRIEVAL / "manifest.json").read_text())
        chunks = load_chunks(paths.chunks)
        ds = load_dataset(paths.dataset)
        main_file = {d: Path(f).name for d, f in zip(ds.documents["document_id"], ds.documents["lexml_file"]) if f}
        self.inp = SimpleNamespace(gold=gold_items(ds), matcher=Matcher(
            chunks, ds.file_to_document(), main_file, frozenset(rman["strategies"]["grouping_tipos"]), annex_rule))
        self.row = dict(zip(chunks["chunk_id"], range(len(chunks))))
        self.Item, self.coverage, self._memo = Item, coverage, {}

    def item(self, it: dict):
        return self.Item(rows=np.array([self.row[c] for c in [it["chunk_id"], *it["alias_chunk_ids"]]]),
                         rank=None, score=None, text_id=it["text_id"])

    def hits(self, q: str, it: dict) -> dict:
        """Per level: does this one text hit (fully or partly) a gold unit of ``q``?"""
        k = (q, it["text_id"])
        if k not in self._memo:
            cov = self.coverage(self.inp, q, [self.item(it)])
            self._memo[k] = {lv: bool(c["any"]) for lv, c in cov.items()}
        return self._memo[k]

    def answer(self, q: str, ctx_line: dict, cited: list[str]) -> list[dict]:
        items = [it for it in ctx_line["items"] if it["chunk_id"] in set(cited)]
        cov = self.coverage(self.inp, q, [self.item(it) for it in items])
        out = []
        for lv, c in cov.items():
            if not c["n"]:
                continue
            ctx_full = len(ctx_line["gold"][lv]["full"])
            h_cited = [self.hits(q, it)[lv] for it in items]
            h_ctx = [self.hits(q, it)[lv] for it in ctx_line["items"]]
            out.append({"level": lv, "n_gold": c["n"], "n_cited": len(items), "n_texts": len(ctx_line["items"]),
                        "cited_recall": len(c["full"]) / c["n"], "context_recall": ctx_full / c["n"],
                        "cited_of_context_gold": len(c["full"]) / ctx_full if ctx_full else np.nan,
                        "cited_precision": float(np.mean(h_cited)) if h_cited else np.nan,
                        "context_precision": float(np.mean(h_ctx)) if h_ctx else np.nan})
        return out


def citation_scores(runs: list[tuple[str, Path]], contexts_root: Path, qids: set) -> pd.DataFrame:
    """Per (run, question, level): the legal-provision score of the texts the answer cites."""
    sc = ProvisionScorer()
    rows, ctx_cache = [], {}
    for run_id, rd in runs:
        run = json.loads((rd / "run.json").read_text())
        cid = run_id.split("/")[-1]
        cdir = contexts_root / cid
        if not (cdir / "contexts.jsonl.gz").exists():
            continue
        if cid not in ctx_cache:
            ctx_cache[cid] = {x["question_number"]: x for x in jl(cdir / "contexts.jsonl.gz")}
        ctx = ctx_cache[cid]
        for ln in jl(rd / "answers.jsonl"):
            q = ln["question_number"]
            if q not in qids or ln["status"] == "skipped" or q not in ctx or not ctx[q]["items"]:
                continue
            answered = ln["status"] == "ok" and not ln.get("abstained")
            for r in sc.answer(q, ctx[q], (ln.get("cited_chunk_ids") or []) if answered else []):
                rows.append({"run_id": run_id, "llm": run["llm"]["name"], "context_id": cid, "question_number": q,
                             "answered": answered, **r})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ linkage and utilisation (first-eval §3.1, §4.3)

def utilisation(ans: pd.DataFrame, ctx: pd.DataFrame, nt: pd.DataFrame) -> pd.DataFrame:
    """Per run and nugget importance: what the context holds (judge on the context) against what the answer
    states. Utilisation = P(answer support | context support); leakage = P(answer support | context
    not_support), and the share of the answer's ``support`` labels the context does not support."""
    m = ans.merge(ctx[["context_id", "nugget_id", "label"]].rename(columns={"label": "ctx_label"}),
                  on=["context_id", "nugget_id"]).merge(nt[["nugget_id", "importance"]], on="nugget_id")
    out = []
    for key, g in m.groupby(["llm", "context_id"]):
        for imp, h in [("all", g), ("vital", g[g.importance == "vital"])]:
            s, c = h.label == "support", h.ctx_label
            out.append({"llm": key[0], "context_id": key[1], "nuggets": imp, "n": len(h),
                        "ctx_support": (c == "support").mean(), "ctx_partial": (c == "partial_support").mean(),
                        "answer_support": s.mean(),
                        "utilisation": s[c == "support"].mean(), "use_of_partial": s[c == "partial_support"].mean(),
                        "leakage": s[c == "not_support"].mean(),
                        "support_not_in_context": (c[s] == "not_support").mean(),
                        "answer_contradicts_given_ctx_support": (h.label[c == "support"] == "contradicts").mean()})
    return pd.DataFrame(out)


def linkage(pq: pd.DataFrame, cq: pd.DataFrame, cit: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Answer V_strict against what the context holds: (1) per run, by the context's article recall and by its
    nugget support; (2) the paired S2 − S1 answer difference against the context differences."""
    art = cit[cit.level == "article"][["run_id", "question_number", "context_recall"]]
    m = pq.merge(art, on=["run_id", "question_number"], how="left").merge(
        cq[["context_id", "question_number", "V_strict"]].rename(columns={"V_strict": "ctx_V_strict"}),
        on=["context_id", "question_number"], how="left")
    rows = []
    for (g, c), h in m.groupby(["llm", "context_id"]):
        r = {"llm": g, "context_id": c, "n": len(h)}
        for name, b in [("art_none", h.context_recall == 0), ("art_part", (h.context_recall > 0) & (h.context_recall < 1)),
                        ("art_all", h.context_recall == 1)]:
            r[f"V_strict_{name}"], r[f"n_{name}"] = h.V_strict[b].mean(), int(b.sum())
        for name, b in [("ctx0", h.ctx_V_strict == 0), ("ctx_mid", (h.ctx_V_strict > 0) & (h.ctx_V_strict < 1)),
                        ("ctx1", h.ctx_V_strict == 1)]:
            r[f"V_strict_{name}"], r[f"n_{name}"] = h.V_strict[b].mean(), int(b.sum())
        ok = h.ctx_V_strict.notna() & h.V_strict.notna()
        r["spearman_answer_ctx"] = h.V_strict[ok].corr(h.ctx_V_strict[ok], method="spearman") if ok.sum() > 2 else np.nan
        rows.append(r)
    diff = []
    for g, h in m.groupby("llm"):
        a = h[h.context_id == "S1_budget4000"].set_index("question_number")
        b = h[h.context_id == "S2_budget4000"].set_index("question_number")
        common = a.index.intersection(b.index)
        if not len(common):
            continue
        d = pd.DataFrame({"answer": b.loc[common, "V_strict"] - a.loc[common, "V_strict"],
                          "ctx": b.loc[common, "ctx_V_strict"] - a.loc[common, "ctx_V_strict"],
                          "art": b.loc[common, "context_recall"] - a.loc[common, "context_recall"]}).dropna()
        slope = np.polyfit(d.ctx, d.answer, 1)[0] if len(d) > 2 else np.nan
        for name, bb in [("ctx_better", d.ctx > 0), ("ctx_same", d.ctx == 0), ("ctx_worse", d.ctx < 0)]:
            diff.append({"llm": g, "group": name, "n": int(bb.sum()), "answer_diff": d.answer[bb].mean(),
                         "ctx_diff": d.ctx[bb].mean(), "art_recall_diff": d.art[bb].mean()})
        diff.append({"llm": g, "group": "all", "n": len(d), "answer_diff": d.answer.mean(), "ctx_diff": d.ctx.mean(),
                     "art_recall_diff": d.art.mean(), "slope_answer_on_ctx": slope,
                     "spearman_answer_ctx": d.answer.corr(d.ctx, method="spearman"),
                     "answer_diff_ctx_same": d.answer[d.ctx == 0].mean()})
    return pd.DataFrame(rows), pd.DataFrame(diff)


# ------------------------------------------------------------------ robustness (plan v2 §5.6)

def _paired(a: str, b: str, pq: pd.DataFrame, n_resamples: int) -> pd.DataFrame:
    return scoring.compare(pq, a, b, ["llm"], n_resamples)


def slice_comparisons(lab: pd.DataFrame, nt: pd.DataFrame, pairs: list[tuple[str, str]],
                      n_resamples: int) -> pd.DataFrame:
    """The paired comparisons on nugget subsets (PGD vs the rest, temporal vs the rest, conditions, nuggets all
    three families produced, nuggets no auditor flagged)."""
    subsets = {"no_pgd": ~nt.pgd, "pgd": nt.pgd, "temporal": nt.temporal, "not_temporal": ~nt.temporal,
               "condicao": nt.category == "condicao", "stable_3of3": nt.stability == 3,
               "not_audit_flagged": ~nt.audit_flagged}
    out = []
    for name, mask in subsets.items():
        ids = set(nt.nugget_id[mask])
        pq = per_question_long(lab[lab.nugget_id.isin(ids)], nt, ["llm", "context_id"])
        for a, b in pairs:
            if {a, b} <= set(pq.context_id):
                c = _paired(a, b, pq, n_resamples)
                out.append(c[c.metric.isin(["V_strict", "A_strict"])].assign(subset=name))
    return pd.concat(out, ignore_index=True)


def run_means_by_subset(lab: pd.DataFrame, nt: pd.DataFrame) -> pd.DataFrame:
    """Per run, V_strict / A_strict on PGD and on the other nuggets: how much of the ceiling PGD content sets."""
    out = []
    for name, ids in [("pgd", set(nt.nugget_id[nt.pgd])), ("no_pgd", set(nt.nugget_id[~nt.pgd]))]:
        pq = per_question_long(lab[lab.nugget_id.isin(ids)], nt, ["llm", "context_id"])
        out.append(pq.groupby(["llm", "context_id"])[["V_strict", "A_strict"]].mean().add_suffix(f"_{name}"))
    return pd.concat(out, axis=1).reset_index()


def chapter_diffs(pq: pd.DataFrame, chapters: dict, a: str = "S1_budget4000", b: str = "S2_budget4000") -> pd.DataFrame:
    out = []
    for g, h in pq.groupby("llm"):
        x = h[h.context_id == a].set_index("question_number").V_strict
        y = h[h.context_id == b].set_index("question_number").V_strict
        d = (y - x).dropna()
        for ch, dd in d.groupby(d.index.map(chapters)):
            out.append({"llm": g, "chapter": ch, "n": len(dd), "diff": dd.mean()})
    return pd.DataFrame(out)


def perturbation(lab: pd.DataFrame, nt: pd.DataFrame, a: str, b: str, reps: int = 1000, seed: int = 13,
                 metric: str = "V_strict") -> pd.DataFrame:
    """Re-score the labels of two runs after damaging the nugget set (plan v2 §5.6): random deletion, vital ↔ okay
    flips, targeted deletion of ``condicao`` nuggets, deletion of auditor-flagged nuggets, stable-only. Per
    setting: the share of replicates in which b − a keeps its sign and stays significant (paired t, p < 0.05)."""
    rng = np.random.default_rng(seed)
    meta = nt.set_index("nugget_id")
    out = []
    for g, h in lab[lab.context_id.isin([a, b])].groupby("llm"):
        w = h.pivot_table(index="nugget_id", columns="context_id", values="label", aggfunc="first")
        if a not in w or b not in w:
            continue
        w = w.dropna()
        w = w.join(meta[["question_number", "importance", "category", "stability", "audit_flagged"]]) \
            .sort_values("question_number")
        sa = w[a].map(STRICT).to_numpy() if metric.endswith("strict") else w[a].map(CREDIT).to_numpy()
        sb = w[b].map(STRICT).to_numpy() if metric.endswith("strict") else w[b].map(CREDIT).to_numpy()
        vital = (w.importance == "vital").to_numpy()
        qn = w.question_number.to_numpy()
        starts = np.flatnonzero(np.r_[True, qn[1:] != qn[:-1]])
        n = len(w)

        def score(keep, vit):
            sel = keep & vit if metric.startswith("V") else keep
            den = np.add.reduceat(sel.astype(float), starts, axis=1)
            with np.errstate(invalid="ignore", divide="ignore"):
                va = np.add.reduceat(sel * sa, starts, axis=1) / den
                vb = np.add.reduceat(sel * sb, starts, axis=1) / den
            d = vb - va
            ok = ~np.isnan(d)
            cnt = ok.sum(1)
            d0 = np.where(ok, d, 0.0)
            mean = d0.sum(1) / cnt
            sd = np.sqrt(((np.where(ok, d - mean[:, None], 0.0)) ** 2).sum(1) / (cnt - 1))
            z = mean / (sd / np.sqrt(cnt))
            return mean, np.abs(z) > 1.96

        base_mean, base_sig = score(np.ones((1, n), bool), vital[None, :])
        sign = np.sign(base_mean[0])
        cond = (w.category == "condicao").to_numpy()
        settings = [("baseline", 0.0, np.ones((1, n), bool), vital[None, :])]
        for p in (0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50):
            settings.append(("delete", p, rng.random((reps, n)) >= p, np.broadcast_to(vital, (reps, n))))
        for p in (0.10, 0.20, 0.30):
            flip = rng.random((reps, n)) < p
            settings.append(("flip_vital_okay", p, np.ones((reps, n), bool), vital ^ flip))
        for p in (0.5, 1.0):
            settings.append(("delete_condicao", p, ~(cond & (rng.random((reps, n)) < p)), np.broadcast_to(vital, (reps, n))))
        settings.append(("delete_audit_flagged", 1.0, ~w.audit_flagged.to_numpy()[None, :], vital[None, :]))
        settings.append(("stable_3of3_only", 1.0, (w.stability == 3).to_numpy()[None, :], vital[None, :]))
        for name, p, keep, vit in settings:
            mean, sig = score(keep, np.asarray(vit))
            out.append({"llm": g, "a": a, "b": b, "metric": metric, "setting": name, "rate": p, "reps": len(mean),
                        "base_diff": float(base_mean[0]), "base_significant": bool(base_sig[0]),
                        "mean_diff": float(np.nanmean(mean)), "sign_kept": float(np.mean(np.sign(mean) == sign)),
                        "significant_same_sign": float(np.mean(sig & (np.sign(mean) == sign)))})
    return pd.DataFrame(out)


def kendall_tau(x: list[float], y: list[float]) -> float:
    from scipy.stats import kendalltau
    return float(kendalltau(x, y).statistic)


def judge_agreement(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """Two judges' labels on the same (run, nugget): agreement, Cohen's κ on the four labels and on support vs
    the rest, per run and pooled."""
    m = a.merge(b[["run_id", "nugget_id", "label"]], on=["run_id", "nugget_id"], suffixes=("_a", "_b"))
    m = m[m.source == "judge"]

    def kappa(x, y):
        cats = sorted(set(x) | set(y))
        po = float(np.mean(x.to_numpy() == y.to_numpy()))
        pe = sum(float(np.mean(x == c)) * float(np.mean(y == c)) for c in cats)
        return (po - pe) / (1 - pe) if pe < 1 else np.nan

    rows = []
    for key, g in [(("all", "all"), m), *m.groupby(["llm", "context_id"])]:
        rows.append({"llm": key[0], "context_id": key[1], "n": len(g),
                     "agree_4": float(np.mean(g.label_a.to_numpy() == g.label_b.to_numpy())),
                     "kappa_4": kappa(g.label_a, g.label_b),
                     "kappa_support": kappa(g.label_a == "support", g.label_b == "support"),
                     "support_a": float((g.label_a == "support").mean()), "support_b": float((g.label_b == "support").mean()),
                     "contradicts_a": float((g.label_a == "contradicts").mean()),
                     "contradicts_b": float((g.label_b == "contradicts").mean())})
    conf = pd.crosstab(m.label_a, m.label_b)
    return pd.DataFrame(rows), conf
