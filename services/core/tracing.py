"""
Hafif tracing ve alarm servisi.
Dagitik tracing benzeri: trace_id + workflow metrikleri + esik alarmi.
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any

_EVENTS: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=8000))
_ALARM_LAST_AT: dict[str, datetime] = {}


def new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


def record_trace_event(
    workflow: str,
    *,
    ok: bool,
    duration_ms: int,
    trace_id: str | None = None,
    tenant_id: int | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    wf = (workflow or "unknown").strip().lower()
    _EVENTS[wf].append(
        {
            "ts": datetime.utcnow(),
            "ok": bool(ok),
            "duration_ms": int(duration_ms),
            "trace_id": trace_id or "",
            "tenant_id": int(tenant_id or 0),
            "meta": meta or {},
        }
    )


def get_trace_snapshot(workflow: str, minutes: int = 30) -> dict[str, Any]:
    wf = (workflow or "unknown").strip().lower()
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=max(1, int(minutes or 30)))
    events = [e for e in _EVENTS[wf] if e["ts"] >= cutoff]
    total = len(events)
    if total == 0:
        return {
            "workflow": wf,
            "window_minutes": int(minutes or 30),
            "total": 0,
            "error_rate_pct": 0.0,
            "avg_ms": 0,
            "p95_ms": 0,
        }
    errors = len([e for e in events if not e["ok"]])
    durations = sorted(int(e["duration_ms"] or 0) for e in events)
    avg_ms = int(sum(durations) / total)
    p95_ms = durations[min(total - 1, int(total * 0.95))]
    return {
        "workflow": wf,
        "window_minutes": int(minutes or 30),
        "total": total,
        "error_rate_pct": round((errors / total) * 100, 2),
        "avg_ms": avg_ms,
        "p95_ms": p95_ms,
    }


def check_trace_alarm(workflow: str, *, err_rate_threshold: float = 20.0, p95_threshold_ms: int = 2500) -> dict[str, Any] | None:
    """
    Alarm kosulu varsa dict dondurur, yoksa None.
    Cooldown: 10 dk.
    """
    snap = get_trace_snapshot(workflow, minutes=10)
    if snap["total"] < 20:
        return None
    is_alarm = bool(snap["error_rate_pct"] >= err_rate_threshold or snap["p95_ms"] >= p95_threshold_ms)
    if not is_alarm:
        return None
    now = datetime.utcnow()
    key = f"alarm:{snap['workflow']}"
    last = _ALARM_LAST_AT.get(key)
    if last and (now - last) < timedelta(minutes=10):
        return None
    _ALARM_LAST_AT[key] = now
    return snap
