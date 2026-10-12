"""Batch API jobs (OpenAI Responses, Gemini generateContent) that fill the same disk cache.

Flow (plan v2 §7: "the rest of the pipeline reads only the cache"):

1. A command runs with a ``BatchRecorder`` on its ``LLM`` objects. Cache hits are served as usual; a
   miss is queued (``LLM.complete_json`` raises ``BatchDeferred``) instead of called. Providers without
   a batch API here (``openai_compat``: Qwen in Singapore) are still called synchronously.
2. ``submit()`` writes one JSONL per model under ``<out>/batches/``, uploads it and creates the job. A
   job record ``<out>/batches/<job>.json`` keeps the request of every key, so results can be cached
   with the same record a synchronous call writes.
3. ``collect()`` polls the jobs; for a finished one it downloads the results and writes one cache file
   per successful request, and one ledger row per result (tag ``batch:<tag>``, billed at half price).
4. Rerunning the command without batch mode reads everything from the cache. A batch result that the
   command's own validation rejects is called again synchronously (``complete_json``).

Both APIs bill 50 % of the synchronous price; a job finishes within 24 h (Gemini: expires after 48 h).
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import httpx

from .client import BATCH_DISCOUNT, BATCH_TAG, BudgetExceeded, LLMError, ledger_total, parse_gemini, parse_openai

GEMINI = "https://generativelanguage.googleapis.com"
OPENAI_DONE = {"completed", "failed", "expired", "cancelled"}
GEMINI_DONE = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED",
               "BATCH_STATE_SUCCEEDED", "BATCH_STATE_FAILED", "BATCH_STATE_CANCELLED", "BATCH_STATE_EXPIRED"}


class BatchRecorder:
    def __init__(self, out: Path):
        self.dir = Path(out) / "batches"
        self.pending: dict[str, dict] = {}         # model name -> {"llm", "items": {key: (req, body, tag)}}
        self._lock = threading.Lock()

    def add(self, llm, key, req, body, tag):
        with self._lock:
            g = self.pending.setdefault(llm.name, {"llm": llm, "items": {}})
            g["items"][key] = (req, body, tag)

    def __len__(self):
        return sum(len(g["items"]) for g in self.pending.values())

    # ------------------------------------------------------------------ submit
    def submit(self, budget_usd: float | None, ledger: Path, note: str = "") -> list[dict]:
        """Create one job per model. Refuses (BudgetExceeded) when the ledger plus the estimated cost of
        the jobs would pass the budget: a submitted job is billed whole, the cap cannot stop it midway."""
        est = {m: _estimate(g["llm"], g["items"], ledger) for m, g in self.pending.items()}
        total = ledger_total(ledger) if ledger else 0.0
        if budget_usd is not None and total + sum(est.values()) > budget_usd:
            raise BudgetExceeded(f"batch of {len(self)} requests: estimated ${sum(est.values()):.2f} "
                                 f"(+ ledger ${total:.2f}) > budget ${budget_usd:.2f}; nothing submitted")
        self.dir.mkdir(parents=True, exist_ok=True)
        jobs = []
        for m, g in self.pending.items():
            llm = g["llm"]
            if abs(llm.price.get("batch_discount", 0) - BATCH_DISCOUNT) > 1e-9:
                raise LLMError(f"{m}: registry batch_discount {llm.price.get('batch_discount')} != {BATCH_DISCOUNT}")
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            local = self.dir / f"{m}_{stamp}.input.jsonl"
            with open(local, "w") as f:
                for key, (_, body, _) in g["items"].items():
                    line = ({"custom_id": key, "method": "POST", "url": "/v1/responses", "body": body}
                            if llm.provider == "openai" else {"key": key, "request": body})
                    f.write(json.dumps(line, ensure_ascii=False) + "\n")
            job_id = _submit_openai(llm, local) if llm.provider == "openai" else _submit_gemini(llm, local, m)
            reqs = self.dir / f"{_safe(job_id)}.requests.jsonl"     # the cache records need the request
            with open(reqs, "w") as f:
                for k, (req, _, t) in g["items"].items():
                    f.write(json.dumps({"key": k, "tag": t, "request": req}, ensure_ascii=False) + "\n")
            rec = {"job": job_id, "provider": llm.provider, "model": m, "model_id": llm.model_id,
                   "created": datetime.now().isoformat(timespec="seconds"), "n_requests": len(g["items"]),
                   "estimated_usd_billed": round(est[m], 4), "note": note, "state": "submitted",
                   "input_file": local.name, "requests_file": reqs.name,
                   "tags": sorted({t.split(":")[0] for _, _, t in g["items"].values()})}
            path = self.dir / f"{_safe(job_id)}.json"
            path.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
            jobs.append({k: rec[k] for k in ("job", "model", "n_requests", "estimated_usd_billed")} | {"record": str(path)})
        return jobs


def _safe(job_id: str) -> str:
    return job_id.replace("/", "_")


def _estimate(llm, items, ledger) -> float:
    """Billed USD of a job: the mean synchronous cost of the same role and model in the ledger, else
    ≈ 4 characters per input token and 2,000 output tokens per request; times the batch discount."""
    import csv
    roles = {t.split(":")[0] for _, _, t in items.values()}
    hist = []
    if ledger and Path(ledger).exists():
        with open(ledger, newline="") as f:
            for r in csv.DictReader(f):
                tag = r["tag"].removeprefix(BATCH_TAG)
                if r["model"] == llm.name and tag.split(":")[0] in roles:
                    hist.append(float(r["usd_standard"]))
    if len(hist) >= 5:
        per = sum(hist) / len(hist)
    else:
        p = llm.price
        per = sum((len(req["system"]) + len(req["user"])) / 4 * p["usd_per_million_input"] / 1e6
                  + 2000 * p["usd_per_million_output"] / 1e6 for req, _, _ in items.values()) / max(len(items), 1)
    return per * len(items) * (1 - BATCH_DISCOUNT)


# ------------------------------------------------------------------ providers: submit
def _submit_openai(llm, local: Path) -> str:
    f = llm._oa.files.create(file=open(local, "rb"), purpose="batch")
    b = llm._oa.batches.create(input_file_id=f.id, endpoint="/v1/responses", completion_window="24h")
    return b.id


def _gemini_headers(llm):
    return {"x-goog-api-key": llm._key}


def _submit_gemini(llm, local: Path, display: str) -> str:
    data = local.read_bytes()
    start = httpx.post(f"{GEMINI}/upload/v1beta/files", headers={
        **_gemini_headers(llm), "X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(len(data)),
        "X-Goog-Upload-Header-Content-Type": "application/jsonl", "Content-Type": "application/json"},
        json={"file": {"display_name": local.name}}, timeout=120)
    start.raise_for_status()
    url = start.headers["x-goog-upload-url"]
    up = httpx.post(url, headers={"Content-Length": str(len(data)), "X-Goog-Upload-Offset": "0",
                                  "X-Goog-Upload-Command": "upload, finalize"}, content=data, timeout=600)
    up.raise_for_status()
    fname = up.json()["file"]["name"]
    r = httpx.post(f"{GEMINI}/v1beta/models/{llm.model_id}:batchGenerateContent", headers=_gemini_headers(llm),
                   json={"batch": {"display_name": display, "input_config": {"file_name": fname}}}, timeout=120)
    if r.status_code != 200:
        raise LLMError(f"gemini batch create HTTP {r.status_code}: {r.text[:500]}")
    return r.json()["name"]


# ------------------------------------------------------------------ poll and collect
def _find(d, *paths):
    """First value found at one of the dotted ``paths`` (the Gemini docs disagree on where things are)."""
    for p in paths:
        cur = d
        for k in p.split("."):
            cur = cur.get(k) if isinstance(cur, dict) else None
            if cur is None:
                break
        if cur is not None:
            return cur
    return None


def poll(llm, rec) -> tuple[str, bool, dict]:
    """(state, done, raw status)."""
    if rec["provider"] == "openai":
        b = llm._oa.batches.retrieve(rec["job"]).model_dump()
        return b["status"], b["status"] in OPENAI_DONE, b
    r = httpx.get(f"{GEMINI}/v1beta/{rec['job']}", headers=_gemini_headers(llm), timeout=120)
    r.raise_for_status()
    d = r.json()
    state = _find(d, "metadata.state", "state") or "?"
    return state, bool(d.get("done")) or state in GEMINI_DONE, d


def _results(llm, rec, status) -> list[tuple[str, dict | None, str | None]]:
    """[(key, response body or None, error)]"""
    out = []
    if rec["provider"] == "openai":
        for fid, is_err in ((status.get("output_file_id"), False), (status.get("error_file_id"), True)):
            if not fid:
                continue
            for line in llm._oa.files.content(fid).text.splitlines():
                if not line.strip():
                    continue
                x = json.loads(line)
                resp = x.get("response") or {}
                ok = not is_err and resp.get("status_code") == 200
                out.append((x["custom_id"], resp.get("body") if ok else None,
                            None if ok else json.dumps(x.get("error") or resp.get("body"))[:300]))
        return out
    fname = _find(status, "response.responsesFile", "dest.fileName", "metadata.output.responsesFile",
                  "response.dest.fileName")
    if fname:
        r = httpx.get(f"{GEMINI}/download/v1beta/{fname}:download", params={"alt": "media"},
                      headers=_gemini_headers(llm), timeout=600)
        r.raise_for_status()
        for line in r.text.splitlines():
            if line.strip():
                x = json.loads(line)
                out.append((x.get("key"), x.get("response"), None if "response" in x else json.dumps(x.get("error"))[:300]))
        return out
    inl = _find(status, "response.inlinedResponses.inlinedResponses", "dest.inlinedResponses.inlinedResponses",
                "response.inlinedResponses")
    for x in inl or []:
        out.append(((x.get("metadata") or {}).get("key"), x.get("response"),
                    None if "response" in x else json.dumps(x.get("error"))[:300]))
    return out


def _final(state: str) -> str:
    """Provider terminal state → collected / failed / expired / cancelled."""
    s = state.lower()
    if s == "completed" or s.endswith("succeeded"):
        return "collected"
    for k in ("expired", "cancelled", "failed"):
        if k in s:
            return k
    return "failed"


def collect(out: Path, llms: dict, log_fn=print) -> list[dict]:
    """Poll every job record of ``<out>/batches``; cache and ledger the results of finished ones.
    ``llms``: model name -> LLM (for keys, prices, cache and ledger)."""
    summary = []
    for path in sorted((Path(out) / "batches").glob("*.json")):
        if path.name.endswith((".input.jsonl", ".requests.jsonl")):
            continue
        rec = json.loads(path.read_text())
        if rec["state"] in ("collected", "failed", "expired", "cancelled"):
            summary.append({k: rec.get(k) for k in ("job", "model", "state", "n_requests", "n_cached", "n_failed")})
            continue
        llm = llms[rec["model"]]
        state, done, status = poll(llm, rec)
        rec["last_poll"] = {"ts": datetime.now().isoformat(timespec="seconds"), "state": state}
        if done:
            ok = bad = 0
            errors = {}
            requests = {}
            for line in open(path.parent / rec["requests_file"]):
                x = json.loads(line)
                requests[x["key"]] = x
            for key, body, err in _results(llm, rec, status):
                meta_req = requests.get(key)
                if meta_req is None:
                    continue
                if body is None:
                    bad += 1
                    errors[key] = err
                    continue
                parse = parse_openai if rec["provider"] == "openai" else parse_gemini
                text, u, served, meta = parse(body)
                llm._log(BATCH_TAG + meta_req["tag"], 1, u, served, 0.0, meta.get("finish"))
                try:
                    if meta.get("truncated"):
                        raise LLMError(f"truncated ({meta.get('finish')})")
                    json.loads(text)
                except Exception as e:  # noqa: BLE001 - left uncached; the synchronous rerun calls it again
                    bad += 1
                    errors[key] = str(e)[:300]
                    continue
                crec = {"request": meta_req["request"], "response": body, "text": text, "usage": asdict(u),
                        "usage_all_attempts": asdict(u), "model_served": served, "latency_s": 0.0, "attempts": 1,
                        "meta": {**meta, "batch_job": rec["job"]}, "batch": True,
                        "ts": datetime.now().isoformat(timespec="seconds")}
                (llm.cache_dir / f"{key}.json").write_text(json.dumps(crec, ensure_ascii=False, indent=1))
                ok += 1
            missing = len(requests) - ok - bad
            rec.update(state=_final(state),
                       provider_state=state, n_cached=ok, n_failed=bad + missing, errors=errors,
                       collected=datetime.now().isoformat(timespec="seconds"))
            log_fn(f"{rec['model']} {rec['job']}: {state}; {ok} cached, {bad} failed, {missing} without a result")
        else:
            log_fn(f"{rec['model']} {rec['job']}: {state}")
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        summary.append({k: rec.get(k) for k in ("job", "model", "state", "n_requests", "n_cached", "n_failed")})
    return summary


def wait(out: Path, llms: dict, every_s: int = 120, max_h: float = 26, log_fn=print):
    """Collect until no job is open (or ``max_h`` hours)."""
    t0 = time.time()
    while True:
        s = collect(out, llms, log_fn)
        if all(x["state"] in ("collected", "failed", "expired", "cancelled") for x in s):
            return s
        if time.time() - t0 > max_h * 3600:
            return s
        time.sleep(every_s)
