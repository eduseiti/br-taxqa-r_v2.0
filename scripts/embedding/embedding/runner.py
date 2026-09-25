"""Request packing, concurrent embedding into the shard store, per-batch validation (plan §5.6).

The provider does the real batching (TEI batches on the GPU by tokens); the client only keeps
``concurrency`` requests in flight.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

import numpy as np

from .manifest import now_iso
from .providers.base import Provider, ProviderError
from .store import ShardStore

log = logging.getLogger("embedding")

NORM_TOL = 1e-3


def pack(n_tokens: list[int], max_inputs: int, max_tokens: int) -> list[list[int]]:
    """Greedy batches of consecutive indices under both limits (a single text over
    ``max_tokens`` still gets its own batch; the length guard has already bounded it)."""
    batches, cur, cur_tok = [], [], 0
    for i, n in enumerate(n_tokens):
        if cur and (len(cur) >= max_inputs or cur_tok + n > max_tokens):
            batches.append(cur)
            cur, cur_tok = [], 0
        cur.append(i)
        cur_tok += n
    if cur:
        batches.append(cur)
    return batches


def validate(vecs: np.ndarray, n: int, dim: int, counters: dict) -> np.ndarray:
    if vecs.shape != (n, dim):
        raise ProviderError(f"expected shape ({n}, {dim}), got {vecs.shape}: wrong model or dimension?")
    if not np.isfinite(vecs).all():
        raise ProviderError("non-finite values in the response (fp16 overflow?)")
    norms = np.linalg.norm(vecs, axis=1)
    if (norms == 0).any():
        raise ProviderError("all-zero vector in the response")
    off = np.abs(norms - 1) > NORM_TOL
    if off.any():
        counters["renormalized"] += int(off.sum())
        log.warning("%d vectors with norm off by > %g: renormalized", int(off.sum()), NORM_TOL)
    return (vecs / norms[:, None]).astype(np.float32)


def run(provider: Provider, store: ShardStore, ids: list[str], texts: list[str], n_tokens: list[int],
        dim: int, max_inputs: int, max_tokens: int, concurrency: int, progress: bool = True) -> dict:
    """Embed every id not yet in the store. Returns the session record (also saved in the store)."""
    done = store.done_ids()
    todo = [k for k, i in enumerate(ids) if i not in done]
    session = {"start": now_iso(), "n_skipped": len(ids) - len(todo), "n_texts": 0, "n_tokens": 0,
               "renormalized": 0, "status": "running"}
    log.info("%d of %d texts already embedded; %d to go", len(ids) - len(todo), len(ids), len(todo))
    batches = [[todo[j] for j in b] for b in pack([n_tokens[k] for k in todo], max_inputs, max_tokens)]
    total_tok = sum(n_tokens[k] for k in todo)
    stats0 = dict(provider.stats)
    t0 = time.monotonic()
    bar = None
    if progress and batches:
        from tqdm import tqdm
        bar = tqdm(total=total_tok, unit="tok", unit_scale=True, smoothing=0.05, desc="embedding")

    def work(batch: list[int]):
        vecs = provider.embed([texts[k] for k in batch])
        return batch, vecs

    it = iter(batches)
    try:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            pending = set()
            for b in it:
                pending.add(pool.submit(work, b))
                if len(pending) >= concurrency:
                    break
            while pending:
                finished, pending = wait(pending, return_when=FIRST_COMPLETED)
                for f in finished:
                    batch, vecs = f.result()          # re-raises a provider failure
                    vecs = validate(vecs, len(batch), dim, session)
                    store.write([ids[k] for k in batch], vecs)
                    ntok = sum(n_tokens[k] for k in batch)
                    session["n_texts"] += len(batch)
                    session["n_tokens"] += ntok
                    if bar:
                        bar.update(ntok)
                        bar.set_postfix(texts=session["n_texts"], refresh=False)
                    nxt = next(it, None)
                    if nxt is not None:
                        pending.add(pool.submit(work, nxt))
        session["status"] = "complete"
    except BaseException as e:
        session["status"] = f"failed: {type(e).__name__}: {str(e)[:300]}"
        raise
    finally:
        if bar:
            bar.close()
        wall = time.monotonic() - t0
        session.update(end=now_iso(), wall_s=round(wall, 1),
                       tokens_per_s=round(session["n_tokens"] / wall, 1) if wall > 0 else None,
                       **{k: provider.stats[k] - stats0.get(k, 0) for k in provider.stats})
        store.add_session(session)
        log.info("session %s: %d texts, %d tokens in %.0fs (%s tok/s), requests=%s retries=%s",
                 session["status"], session["n_texts"], session["n_tokens"], wall,
                 session["tokens_per_s"], session.get("requests"), session.get("retries"))
    return session
