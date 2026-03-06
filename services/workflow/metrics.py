"""
Pipeline temel metrikleri (in-memory).
Istek sayisi, hata orani, gecikme ve intent dagilimi.
"""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any

_EVENTS: dict[int, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=5000))
_CHAT_EVENTS: dict[int, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=5000))


def record_pipeline_event(
    tenant_id: int,
    *,
    ok: bool,
    latency_ms: int,
    intent: str,
    primary_module: str,
) -> None:
    _EVENTS[int(tenant_id or 1)].append(
        {
            "ts": datetime.utcnow(),
            "ok": bool(ok),
            "latency_ms": int(latency_ms),
            "intent": (intent or "unknown").strip().lower(),
            "primary_module": (primary_module or "ai").strip().lower(),
        }
    )


def get_pipeline_metrics_snapshot(tenant_id: int, hours: int = 24) -> dict[str, Any]:
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=max(1, int(hours or 24)))
    events = [e for e in _EVENTS[int(tenant_id or 1)] if e["ts"] >= cutoff]
    total = len(events)
    errors = len([e for e in events if not e.get("ok")])
    latencies = sorted(int(e.get("latency_ms") or 0) for e in events)
    avg_latency = int(sum(latencies) / total) if total else 0
    p95_latency = latencies[min(total - 1, int(total * 0.95))] if total else 0

    intent_counts: dict[str, int] = {}
    for e in events:
        k = e.get("intent") or "unknown"
        intent_counts[k] = intent_counts.get(k, 0) + 1
    top_intents = sorted(intent_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "window_hours": int(hours or 24),
        "total_requests": total,
        "error_count": errors,
        "error_rate_pct": round((errors / total) * 100, 2) if total else 0.0,
        "avg_latency_ms": avg_latency,
        "p95_latency_ms": int(p95_latency or 0),
        "top_intents": top_intents,
    }


def record_chat_response_event(
    tenant_id: int,
    *,
    ok: bool,
    latency_ms: int,
    channel: str,
) -> None:
    _CHAT_EVENTS[int(tenant_id or 1)].append(
        {
            "ts": datetime.utcnow(),
            "ok": bool(ok),
            "latency_ms": int(latency_ms),
            "channel": (channel or "unknown").strip().lower(),
        }
    )


def get_chat_response_metrics(tenant_id: int, hours: int = 24) -> dict[str, Any]:
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=max(1, int(hours or 24)))
    events = [e for e in _CHAT_EVENTS[int(tenant_id or 1)] if e["ts"] >= cutoff]
    total = len(events)
    errors = len([e for e in events if not e.get("ok")])
    latencies = sorted(int(e.get("latency_ms") or 0) for e in events)
    avg_latency = int(sum(latencies) / total) if total else 0
    p95_latency = latencies[min(total - 1, int(total * 0.95))] if total else 0
    return {
        "window_hours": int(hours or 24),
        "total": total,
        "error_count": errors,
        "avg_latency_ms": avg_latency,
        "p95_latency_ms": int(p95_latency or 0),
    }
