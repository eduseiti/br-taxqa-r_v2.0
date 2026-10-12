"""Providers ``openai`` (Responses API), ``gemini`` (REST generateContent) and ``openai_compat``
(Chat Completions, e.g. Alibaba Model Studio for Qwen), a disk cache and a cost ledger."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import httpx
import yaml

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_ledger_lock = threading.Lock()


class LLMError(RuntimeError):
    pass


class BudgetExceeded(LLMError):
    pass


class BatchDeferred(LLMError):
    """Batch mode: the request was not in the cache and was queued for a batch job instead of called."""


class QuotaExhausted(LLMError):
    """A per-day provider quota (e.g. Gemini 3.1 Pro: 250 requests per model per day on our tier).
    Not retried: waiting minutes does not help."""


BATCH_TAG = "batch:"     # ledger rows of batch results: tag prefix; billed at BATCH_DISCOUNT off
BATCH_DISCOUNT = 0.5     # OpenAI and Gemini Batch APIs (registry batch_discount; checked at submit)


def ledger_total(ledger: Path) -> float:
    """Billed USD so far: ``usd_standard`` is always the synchronous price; batch rows count at half."""
    if not Path(ledger).exists():
        return 0.0
    with open(ledger, newline="") as f:
        return sum(float(r["usd_standard"]) * ((1 - BATCH_DISCOUNT) if r["tag"].startswith(BATCH_TAG) else 1)
                   for r in csv.DictReader(f))


# ---------------------------------------------------------------- request bodies and response parsing
# Shared by the synchronous calls and the batch jobs (batch.py), so both send and read the same thing.
def openai_body(model_id: str, params: dict, system: str, user: str, schema: dict, schema_name: str) -> dict:
    return {"model": model_id, "instructions": system, "input": user,
            "reasoning": {"effort": params["reasoning_effort"]},
            "text": {"format": {"type": "json_schema", "name": schema_name, "schema": schema, "strict": True}},
            "max_output_tokens": params.get("max_output_tokens", 32000)}


def parse_openai(d: dict):
    """Responses API object (dict) → (text, usage, served model, meta)."""
    text = "".join(c.get("text", "") for o in d.get("output") or [] if o.get("type") == "message"
                   for c in o.get("content") or [] if c.get("type") == "output_text")
    u = d.get("usage") or {}
    usage = Usage(u.get("input_tokens", 0), (u.get("input_tokens_details") or {}).get("cached_tokens") or 0,
                  u.get("output_tokens", 0), (u.get("output_tokens_details") or {}).get("reasoning_tokens") or 0)
    st = d.get("status")
    return text, usage, d.get("model"), {"finish": st, "truncated": st != "completed"}


def gemini_body(params: dict, system: str, user: str, schema: dict) -> dict:
    return {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema,
                                 "thinkingConfig": {"thinkingLevel": params["thinking_level"]},
                                 "maxOutputTokens": params.get("max_output_tokens", 32768)}}


def parse_gemini(d: dict, model_id: str = ""):
    """GenerateContentResponse (dict) → (text, usage, served model, meta)."""
    cand = (d.get("candidates") or [{}])[0]
    text = "".join(pt.get("text", "") for pt in cand.get("content", {}).get("parts", []) if not pt.get("thought"))
    m = d.get("usageMetadata", {})
    thoughts = m.get("thoughtsTokenCount", 0)
    usage = Usage(m.get("promptTokenCount", 0), m.get("cachedContentTokenCount", 0),
                  m.get("candidatesTokenCount", 0) + thoughts, thoughts)
    fin = cand.get("finishReason")
    return text, usage, d.get("modelVersion", model_id), {"finish": fin, "truncated": fin != "STOP"}


@dataclass
class Usage:
    input: int = 0          # all prompt tokens, cached ones included
    cached_input: int = 0
    output: int = 0         # billed output, reasoning included
    reasoning: int = 0

    def cost(self, price: dict, batch: bool = False) -> float:
        pin = price["usd_per_million_input"]
        pcache = price.get("usd_per_million_cached_input", pin)
        usd = ((self.input - self.cached_input) * pin + self.cached_input * pcache
               + self.output * price["usd_per_million_output"]) / 1e6
        return usd * (1 - price.get("batch_discount", 0)) if batch else usd


@dataclass
class Result:
    data: dict
    text: str
    usage: Usage
    cost_usd: float
    model_served: str
    from_cache: bool
    cache_key: str
    latency_s: float = 0.0
    attempts: int = 1
    meta: dict = field(default_factory=dict)


def load_registry(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text())["models"]


class LLM:
    def __init__(self, name: str, cfg: dict, cache_dir: Path, ledger: Path | None = None,
                 budget_usd: float | None = None):
        """``budget_usd``: refuse any API call once the ledger total reaches it. Checked before each
        call, so concurrent workers can overshoot by at most one call each."""
        self.name, self.cfg = name, cfg
        self.budget_usd = budget_usd
        self.batch = None        # a batch.BatchRecorder: cache misses are queued instead of called
        self.provider = cfg["provider"]
        self.model_id = cfg["model_id"]
        self.params = cfg.get("params", {})
        self.price = cfg["price"]
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = ledger
        key = os.environ.get(cfg["api_key_env"])
        if not key:
            raise LLMError(f"{cfg['api_key_env']} is not set")
        self._key = key
        if self.provider in ("openai", "openai_compat"):
            from openai import OpenAI
            self._oa = OpenAI(api_key=key, base_url=cfg.get("base_url"), timeout=600, max_retries=0)

    # ------------------------------------------------------------------ public
    def complete_json(self, system: str, user: str, schema: dict, schema_name: str,
                      validate=None, tag: str = "", max_attempts: int = 3, replicate: int = 0) -> Result:
        """Return the parsed JSON. ``validate(data)`` may raise to reject a reply; rejected or
        truncated replies are retried (not cached) up to ``max_attempts`` times. ``replicate`` > 0
        enters only the cache key, so an identical request gets a fresh sample (same-model noise)."""
        req = {"provider": self.provider, "model": self.model_id, "params": self.params,
               "system": system, "user": user, "schema": schema}
        if replicate:
            req["replicate"] = replicate
        ck = hashlib.sha256(json.dumps(req, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        cpath = self.cache_dir / f"{ck}.json"
        if cpath.exists():
            rec = json.loads(cpath.read_text())
            u = Usage(**rec["usage"])
            try:
                data = json.loads(rec["text"])
                if validate:
                    validate(data)
                return Result(data, rec["text"], u, u.cost(self.price), rec["model_served"], True, ck,
                              rec.get("latency_s", 0.0), rec.get("attempts", 1), rec.get("meta", {}))
            except Exception:  # noqa: BLE001
                # a batch result is cached before the command's own validation, which may reject it:
                # call again (the synchronous retry loop below). A synchronous record never fails here.
                if not rec.get("batch"):
                    raise
        if self.batch is not None and self.provider in ("openai", "gemini"):
            self.batch.add(self, ck, req, self.body(system, user, schema, schema_name), tag)
            raise BatchDeferred(tag)
        last = None
        spent = Usage()
        for attempt in range(1, max_attempts + 1):
            if self.budget_usd is not None and self.ledger:
                with _ledger_lock:
                    total = ledger_total(self.ledger)
                if total >= self.budget_usd:
                    raise BudgetExceeded(f"ledger {self.ledger} at ${total:.4f} >= budget ${self.budget_usd:.2f}")
            t0 = time.time()
            raw, text, u, served, meta = self._call(system, user, schema, schema_name)
            dt = time.time() - t0
            for f in ("input", "cached_input", "output", "reasoning"):
                setattr(spent, f, getattr(spent, f) + getattr(u, f))
            self._log(tag, attempt, u, served, dt, meta.get("finish"))
            try:
                if meta.get("truncated"):
                    raise LLMError(f"truncated response ({meta.get('finish')})")
                data = json.loads(text)
                if validate:
                    validate(data)
            except Exception as e:  # noqa: BLE001 - any rejection triggers a retry
                last = e
                continue
            rec = {"request": req, "response": raw, "text": text, "usage": asdict(u),
                   "usage_all_attempts": asdict(spent), "model_served": served, "latency_s": dt,
                   "attempts": attempt, "meta": meta, "ts": datetime.now().isoformat(timespec="seconds")}
            cpath.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
            return Result(data, text, u, u.cost(self.price), served, False, ck, dt, attempt, meta)
        raise LLMError(f"{self.name} {tag}: no valid reply after {max_attempts} attempts: {last}")

    # --------------------------------------------------------------- providers
    def _call(self, system, user, schema, schema_name):
        for wait in (5, 15, 45, 90, None):
            try:
                return getattr(self, f"_call_{self.provider}")(system, user, schema, schema_name)
            except Exception as e:  # noqa: BLE001
                status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
                if status == 429 and "PerDay" in str(e):
                    raise QuotaExhausted(str(e)) from e
                if wait is None or status not in (408, 429, 500, 502, 503, 504, None):
                    raise
                time.sleep(wait)

    def body(self, system, user, schema, schema_name) -> dict:
        """The provider request body (batch jobs send exactly this)."""
        if self.provider == "openai":
            return openai_body(self.model_id, self.params, system, user, schema, schema_name)
        if self.provider == "gemini":
            return gemini_body(self.params, system, user, schema)
        raise LLMError(f"no batch body for provider {self.provider}")

    def _call_openai(self, system, user, schema, schema_name):
        r = self._oa.responses.create(**openai_body(self.model_id, self.params, system, user, schema, schema_name))
        d = r.model_dump()
        text, usage, served, meta = parse_openai(d)
        return d, text, usage, served, meta

    def _call_gemini(self, system, user, schema, schema_name):
        body = gemini_body(self.params, system, user, schema)
        h = httpx.post(GEMINI_URL.format(model=self.model_id), headers={"x-goog-api-key": self._key},
                       json=body, timeout=600)
        if h.status_code != 200:
            err = LLMError(f"gemini HTTP {h.status_code}: {h.text[:300]}"
                           + (" [GenerateRequestsPerDayPerProjectPerModel]" if "PerDay" in h.text else ""))
            err.status_code = h.status_code
            raise err
        d = h.json()
        text, usage, served, meta = parse_gemini(d, self.model_id)
        return d, text, usage, served, meta

    def _call_openai_compat(self, system, user, schema, schema_name):
        p = dict(self.params)
        extra = {}
        if p.get("enable_thinking"):
            extra = {"enable_thinking": True, "thinking_budget": p.get("thinking_budget", 2048)}
        r = self._oa.chat.completions.create(
            model=self.model_id, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": p.get("response_format", "json_object")},
            max_tokens=p.get("max_tokens", 16000), extra_body=extra)
        u = r.usage
        det = u.completion_tokens_details
        cached = (u.prompt_tokens_details.cached_tokens or 0) if u.prompt_tokens_details else 0
        usage = Usage(u.prompt_tokens, cached, u.completion_tokens, (det.reasoning_tokens or 0) if det else 0)
        fin = r.choices[0].finish_reason
        return r.model_dump(), r.choices[0].message.content or "", usage, r.model, \
            {"finish": fin, "truncated": fin != "stop"}

    # ------------------------------------------------------------------ ledger
    def _log(self, tag, attempt, u: Usage, served, dt, finish):
        """One ledger row. ``usd_standard`` is the synchronous price; batch rows carry the ``batch:`` tag."""
        if not self.ledger:
            return
        row = {"ts": datetime.now().isoformat(timespec="seconds"), "model": self.name, "served": served,
               "tag": tag, "attempt": attempt, "finish": finish, "input": u.input, "cached_input": u.cached_input,
               "output": u.output, "reasoning": u.reasoning, "usd_standard": round(u.cost(self.price), 6),
               "latency_s": round(dt, 1)}
        with _ledger_lock:
            new = not Path(self.ledger).exists()
            with open(self.ledger, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(row))
                if new:
                    w.writeheader()
                w.writerow(row)
