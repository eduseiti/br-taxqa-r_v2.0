"""Cost ledger ``embeddings/costs.csv`` (plan §9): one row per billable activity, append-only.

Implemented for HF endpoints (replica-minutes × hourly price, from the ``endpoint.Meter``) and
manual rows (``costs add``). Token-priced providers and billing reconciliation (§9.2, §9.4) come
with the OpenAI / Gemini providers.
"""

from __future__ import annotations

import csv
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import ModelConfig
from .endpoint import round_minutes

COLUMNS = ["row_id", "timestamp_start", "timestamp_end", "model_slug", "activity", "run_id",
           "provider", "billing_unit", "quantity", "unit_price_usd", "price_checked", "usd",
           "source", "reconciles", "notes"]
ACTIVITIES = ("smoke", "parity", "parity_reference", "corpus", "queries", "idle", "other")


def _iso(ts: float | None) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds") if ts else ""


def append(ledger: Path, **row) -> dict:
    row = {c: row.get(c, "") for c in COLUMNS} | {"row_id": row.get("row_id") or uuid.uuid4().hex}
    ledger.parent.mkdir(parents=True, exist_ok=True)
    new = not ledger.exists()
    with open(ledger, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerow(row)
    return row


def endpoint_rows(ledger: Path, cfg: ModelConfig, activity: str, run_id: str, meter: dict,
                  idle_minutes: int = 0, notes: str = "") -> list[dict]:
    """Ledger rows for one metered session (+ the expected idle tail if left running)."""
    price = cfg.price.get("usd_per_hour")
    rows = []
    q = round_minutes(meter.get("replica_minutes", 0.0))
    if q:
        rows.append(append(ledger, timestamp_start=_iso(meter.get("start")), timestamp_end=_iso(meter.get("end")),
                           model_slug=cfg.slug, activity=activity, run_id=run_id, provider="hf_endpoint",
                           billing_unit="replica_minutes", quantity=q, unit_price_usd=price or "",
                           price_checked=cfg.price.get("checked", ""),
                           usd=round(q * price / 60, 4) if price else "", source="auto_estimate", notes=notes))
    if idle_minutes:
        rows.append(append(ledger, timestamp_start=_iso(meter.get("end")), model_slug=cfg.slug, activity="idle",
                           run_id=run_id, provider="hf_endpoint", billing_unit="replica_minutes",
                           quantity=idle_minutes, unit_price_usd=price or "",
                           price_checked=cfg.price.get("checked", ""),
                           usd=round(idle_minutes * price / 60, 4) if price else "", source="auto_estimate",
                           notes="endpoint left running: scale-to-zero timeout expected before billing stops"))
    return rows


def summary(ledger: Path, by: str = "model", markdown: bool = False) -> str:
    if not ledger.exists():
        return "no cost ledger yet"
    df = pd.read_csv(ledger, dtype={"usd": float, "quantity": float}, keep_default_na=False,
                     na_values={"usd": [""], "quantity": [""]})
    key = {"model": "model_slug", "activity": "activity", "provider": "provider"}[by]
    est = df[df["source"] == "auto_estimate"]
    act = df[df["source"].isin(["provider_reported", "invoice"])]
    out = pd.DataFrame({
        "est_usd": est.groupby(key)["usd"].sum(),
        "actual_usd": act.groupby(key)["usd"].sum(),
        "replica_minutes": df[df["billing_unit"] == "replica_minutes"].groupby(key)["quantity"].sum(),
        "tokens": df[df["billing_unit"] == "tokens"].groupby(key)["quantity"].sum(),
    }).fillna(0).round(4)
    if key != "activity":
        pivot = est.pivot_table(index=key, columns="activity", values="usd", aggfunc="sum").fillna(0).round(4)
        out = out.join(pivot.add_prefix("est_"), rsuffix="_")
    out.loc["TOTAL"] = out.sum(numeric_only=True)
    return to_markdown(out) if markdown else out.to_string()


def to_markdown(df: pd.DataFrame) -> str:
    """Minimal Markdown table (avoids the optional ``tabulate`` dependency)."""
    cols = [df.index.name or ""] + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for idx, row in df.iterrows():
        lines.append("| " + " | ".join([str(idx)] + [f"{v:g}" if isinstance(v, float) else str(v) for v in row]) + " |")
    return "\n".join(lines)
