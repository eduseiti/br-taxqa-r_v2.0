"""HF Inference Endpoint management and the replica meter (plan §3.6, §9.3).

HF bills the time a replica is up, per minute, and has no billing API; the ``Meter`` polls the
endpoint status every ``interval`` seconds and integrates the billed replicas over time. A replica
counts as billed while the endpoint is ``running`` (``readyReplica``) or starting
(``initializing`` / ``pending`` / ``updating``: ``targetReplica``); ``paused``, ``scaledToZero``
and ``failed`` count as zero.
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import ConfigError, ModelConfig

log = logging.getLogger("embedding")

STARTING = {"initializing", "pending", "updating"}


def get_endpoint(cfg: ModelConfig, required: bool = False):
    """The ``InferenceEndpoint`` named in the config, or None (with a warning) if unavailable."""
    import os

    from huggingface_hub import get_inference_endpoint

    if not cfg.endpoint_name:
        if required:
            raise ConfigError(f"{cfg.slug}: endpoint_name is not set in models.yaml")
        return None
    try:
        return get_inference_endpoint(cfg.endpoint_name, namespace=cfg.endpoint_namespace,
                                      token=os.environ.get("HF_TOKEN"))
    except Exception as e:  # noqa: BLE001 - token without 'Manage' permission, network, …
        if required:
            raise ConfigError(f"cannot read endpoint {cfg.endpoint_name!r}: {e} (the token needs "
                              "'Manage Inference Endpoints', plan §3.1)") from e
        log.warning("endpoint %s not readable (%s): no metering, no revision check", cfg.endpoint_name,
                    type(e).__name__)
        return None


def describe(ep) -> dict:
    """Endpoint configuration for the manifest (no secrets: the ``secrets`` block is dropped)."""
    raw = json.loads(json.dumps(ep.raw, default=str))
    raw.get("model", {}).pop("secrets", None)
    raw.pop("status", None)
    return {"name": ep.name, "namespace": ep.namespace, "repository": ep.repository,
            "revision": ep.revision, "config": raw}


def state(ep) -> dict:
    st = ep.raw.get("status", {})
    return {"state": st.get("state"), "ready": st.get("readyReplica", 0) or 0,
            "target": st.get("targetReplica", 0) or 0}


def billed_replicas(s: dict) -> int:
    if s["state"] == "running":
        return max(s["ready"], 1)
    if s["state"] in STARTING:
        return max(s["target"], 1)
    return 0


def replica_minutes(samples: list[dict], end_ts: float | None = None) -> float:
    """Integrate billed replicas over a step function of samples ``{ts, state, ready, target}``."""
    total = 0.0
    for a, b in zip(samples, samples[1:] + ([{"ts": end_ts}] if end_ts else [])):
        total += billed_replicas(a) * (b["ts"] - a["ts"]) / 60
    return total


def scale_to_zero_minutes(ep) -> int:
    return int(ep.raw.get("compute", {}).get("scaling", {}).get("scaleToZeroTimeout") or 0)


def ensure_running(ep, resume: bool, timeout: int = 1800) -> None:
    """Paused endpoints must be resumed explicitly; scaled-to-zero ones wake on the first request."""
    ep.fetch()
    s = state(ep)["state"]
    if s == "paused":
        if not resume:
            raise ConfigError(f"endpoint {ep.name} is paused: pass --resume, or run "
                              f"`embed.py endpoint --model … resume`")
        log.info("resuming endpoint %s …", ep.name)
        ep.resume()
        ep.wait(timeout=timeout)
        log.info("endpoint %s is running", ep.name)
    elif s == "failed":
        raise ConfigError(f"endpoint {ep.name} is in state 'failed': check its logs in the HF UI")


class Meter:
    """Background poller writing ``endpoint_meter.jsonl`` and integrating replica-minutes."""

    def __init__(self, ep, path: Path, run_id: str, interval: float = 60):
        self.ep, self.path, self.run_id, self.interval = ep, path, run_id, interval
        self.samples: list[dict] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _sample(self) -> None:
        try:
            self.ep.fetch()
            s = {"ts": time.time(), **state(self.ep)}
        except Exception as e:  # noqa: BLE001 - keep the previous state on a transient failure
            log.debug("meter poll failed: %s", e)
            if not self.samples:
                return
            s = {**self.samples[-1], "ts": time.time(), "poll_error": type(e).__name__}
        self.samples.append(s)
        rec = {"run_id": self.run_id, "time": datetime.fromtimestamp(s["ts"], timezone.utc).isoformat(timespec="seconds"),
               **{k: v for k, v in s.items() if k != "ts"}}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            self._sample()

    def start(self) -> "Meter":
        self._sample()
        self._thread.start()
        return self

    def stop(self) -> dict:
        """Stops polling; returns ``{start, end, replica_minutes, final_state}``."""
        self._stop.set()
        self._thread.join(timeout=5)
        self._sample()
        if not self.samples:
            return {"replica_minutes": 0.0, "final_state": None}
        return {"start": self.samples[0]["ts"], "end": self.samples[-1]["ts"],
                "replica_minutes": replica_minutes(self.samples),
                "final_state": self.samples[-1]["state"],
                "final_billed_replicas": billed_replicas(self.samples[-1])}


def round_minutes(x: float) -> int:
    return int(math.ceil(x - 1e-9)) if x > 0 else 0
