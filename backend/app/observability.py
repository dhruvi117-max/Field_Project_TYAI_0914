"""Small dependency-free request tracing and operational metrics for the classroom prototype."""

from __future__ import annotations

import json
import logging
import time
from collections import Counter, defaultdict
from contextvars import ContextVar
from threading import Lock

trace_id: ContextVar[str] = ContextVar("trace_id", default="unknown")
LOGGER = logging.getLogger("retail_shelf_intelligence")
_LOCK = Lock()
_COUNTERS: Counter[str] = Counter()
_LATENCIES: defaultdict[str, list[float]] = defaultdict(list)
_MAX_SAMPLES = 200


def log_event(event: str, **details: object) -> None:
    """Emit searchable JSON-style application events without logging image/OCR contents."""
    LOGGER.info(json.dumps({"event": event, "trace_id": trace_id.get(), **details}, default=str))


def increment(metric: str, amount: int = 1) -> None:
    with _LOCK:
        _COUNTERS[metric] += amount


def observe_seconds(metric: str, seconds: float) -> None:
    with _LOCK:
        values = _LATENCIES[metric]
        values.append(max(0.0, seconds))
        if len(values) > _MAX_SAMPLES:
            del values[:-_MAX_SAMPLES]


def timed(metric: str):
    """Return a tiny context manager-like timer for an isolated pipeline stage."""

    class _Timer:
        def __enter__(self):
            self.started = time.perf_counter()
            return self

        def __exit__(self, *_: object) -> None:
            observe_seconds(metric, time.perf_counter() - self.started)

        @property
        def elapsed_ms(self) -> int:
            return round((time.perf_counter() - self.started) * 1000)

    return _Timer()


def prometheus_metrics() -> str:
    """Expose compact Prometheus-compatible text without adding a monitoring dependency."""
    with _LOCK:
        lines = [
            "# HELP shelf_requests_total Total HTTP requests handled by the prototype",
            "# TYPE shelf_requests_total counter",
            f"shelf_requests_total {_COUNTERS['http_requests_total']}",
            "# HELP shelf_audits_total Total completed or failed shelf audits",
            "# TYPE shelf_audits_total counter",
            f"shelf_audits_total {_COUNTERS['audits_total']}",
            "# HELP shelf_audit_failures_total Failed shelf audit requests",
            "# TYPE shelf_audit_failures_total counter",
            f"shelf_audit_failures_total {_COUNTERS['audit_failures_total']}",
        ]
        for metric, values in sorted(_LATENCIES.items()):
            if not values:
                continue
            mean = sum(values) / len(values)
            lines.extend(
                [
                    f"# TYPE shelf_{metric} gauge",
                    f"shelf_{metric}_seconds_mean {mean:.6f}",
                    f"shelf_{metric}_seconds_samples {len(values)}",
                ]
            )
    return "\n".join(lines) + "\n"
