"""Parity check: served embeddings vs the model card's reference implementation (plan §5.4).

- sample: 64 corpus texts (the 5 longest + a spread over ``Tipo`` × length) and 16 queries,
  fixed in ``parity_sample.json`` (model-independent: ids are ``texto_sha256`` / question numbers);
- reference: sentence-transformers in bf16 (``SentenceTransformer(model, revision, model_kwargs dtype)``),
  pooled output cast to float32 and L2-normalized there, ``prompt=""`` (templates are applied before both paths);
- metrics: per-text cosine served↔reference (min, p1, median) and, for the 16 queries over the
  64 texts, top-1 agreement and Kendall tau of the full ranking.
"""

from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd

log = logging.getLogger("embedding")

N_TEXTS, N_LONGEST, N_QUERIES = 64, 5, 16


# ------------------------------------------------------------------------------------------------
# Sample
# ------------------------------------------------------------------------------------------------

def make_sample(rows: pd.DataFrame, queries: pd.DataFrame, len_col: str = "n_tokens") -> dict:
    """Deterministic (no RNG): the N_LONGEST longest unique texts, then round-robin over ``Tipo``
    taking the text at increasing length quantiles, then evenly spaced queries."""
    u = (rows.assign(_len=rows[len_col].astype(int))
         .drop_duplicates("texto_sha256")[["texto_sha256", "Tipo", "_len"]]
         .sort_values(["_len", "texto_sha256"], ascending=[False, True]))
    chosen = u["texto_sha256"].head(N_LONGEST).tolist()
    rest = u[~u["texto_sha256"].isin(chosen)]
    by_tipo = {t: g.sort_values(["_len", "texto_sha256"])["texto_sha256"].tolist()
               for t, g in rest.groupby("Tipo")}
    tipos = sorted(by_tipo)
    need = N_TEXTS - N_LONGEST
    rounds = -(-need // len(tipos))
    k = 0
    while len(chosen) < N_TEXTS:
        tipo = tipos[k % len(tipos)]
        r = k // len(tipos)
        pool = [x for x in by_tipo[tipo] if x not in chosen]
        if pool:
            q = (r + 0.5) / rounds
            chosen.append(pool[min(len(pool) - 1, int(q * len(pool)))])
        k += 1
        if k > 100 * N_TEXTS:
            raise RuntimeError("not enough texts for the parity sample")
    qids = queries["query_id"].tolist()
    step = len(qids) / N_QUERIES
    qsel = [qids[int(i * step)] for i in range(N_QUERIES)]
    return {"text_ids": chosen, "query_ids": qsel,
            "rule": f"{N_LONGEST} longest by {len_col}, then round-robin over Tipo at length "
                    f"quantiles; {N_QUERIES} evenly spaced queries"}


# ------------------------------------------------------------------------------------------------
# Reference
# ------------------------------------------------------------------------------------------------

def reference_vectors(model_id: str, revision: str | None, texts: list[str], dtype: str = "bfloat16",
                      device: str = "cpu", trust_remote_code: bool = False, max_seq_length: int = 8192,
                      batch_size: int = 1) -> tuple[np.ndarray, dict]:
    try:
        import sentence_transformers
        import torch
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise ImportError("the parity reference needs `pip install -r scripts/embedding/requirements-parity.txt`") from e
    t0 = time.monotonic()
    model = SentenceTransformer(model_id, revision=revision, device=device, trust_remote_code=trust_remote_code,
                                model_kwargs={"dtype": getattr(torch, dtype)})
    model.max_seq_length = max_seq_length
    order = np.argsort([len(t) for t in texts])          # short first: early progress, one long batch last
    dim_of = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
    out = np.empty((len(texts), dim_of()), dtype=np.float32)
    with torch.inference_mode():
        vecs = model.encode([texts[i] for i in order], prompt="", batch_size=batch_size,
                            normalize_embeddings=False, convert_to_tensor=True, show_progress_bar=True)
    vecs = vecs.float().cpu().numpy()                    # normalize in float32, not in bf16
    out[order] = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
    info = {"library": f"sentence-transformers {sentence_transformers.__version__}",
            "torch": torch.__version__, "dtype": dtype, "loaded_dtype": str(next(model.parameters()).dtype),
            "device": device, "model_id": model_id,
            "revision": revision, "wall_s": round(time.monotonic() - t0, 1)}
    return out, info


# ------------------------------------------------------------------------------------------------
# Metrics
# ------------------------------------------------------------------------------------------------

def kendall_tau(a: np.ndarray, b: np.ndarray) -> float:
    i, j = np.triu_indices(len(a), 1)
    return float((np.sign(a[i] - a[j]) * np.sign(b[i] - b[j])).mean())


def compare(served: np.ndarray, ref: np.ndarray, n_texts: int, thresholds: dict) -> dict:
    """Rows ``[:n_texts]`` are corpus texts, the rest queries (both arrays L2-normalized)."""
    cos = np.sum(served * ref, axis=1)
    ds, dr = served[:n_texts], ref[:n_texts]
    qs, qr = served[n_texts:], ref[n_texts:]
    ss, sr = qs @ ds.T, qr @ dr.T
    top1 = (ss.argmax(1) == sr.argmax(1))
    taus = [kendall_tau(ss[q], sr[q]) for q in range(len(qs))]
    m = {"cos_min": float(cos.min()), "cos_p1": float(np.percentile(cos, 1)),
         "cos_median": float(np.median(cos)), "cos_min_texts": float(cos[:n_texts].min()),
         "cos_min_queries": float(cos[n_texts:].min()) if len(qs) else None,
         "top1_agree": int(top1.sum()), "n_queries": int(len(qs)),
         "kendall_tau_min": float(min(taus)) if taus else None,
         "kendall_tau_median": float(np.median(taus)) if taus else None}
    checks = {"cos_median": m["cos_median"] >= thresholds["median_cos"],
              "cos_min": m["cos_min"] >= thresholds["min_cos"],
              "top1": (not thresholds.get("top1_all", True)) or m["top1_agree"] == m["n_queries"]}
    return {"metrics": m, "checks": checks, "passed": all(checks.values()),
            "per_item_cos": [round(float(c), 6) for c in cos]}
