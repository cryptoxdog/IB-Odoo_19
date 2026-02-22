"""Metrics collector for Neo4j graph operations.

Provides timing and counter metrics for observability. Uses a singleton
pattern so all graph operations share the same collector instance.
"""

import logging
import time
from contextlib import contextmanager
from threading import Lock

_logger = logging.getLogger(__name__)

_metrics_instance = None
_metrics_lock = Lock()


class MetricsCollector:
    """Simple metrics collector for Neo4j operations.

    Tracks:
    - Operation counts (success, failure, by type)
    - Timing measurements (duration per operation)
    - Row counts returned from queries

    Thread-safe via internal locking.
    """

    def __init__(self):
        self._lock = Lock()
        self._counters = {}
        self._timings = {}

    def increment(self, name, value=1):
        """Increment a counter metric.

        :param name: Metric name (e.g., "neo4j.query.rows", "sync_facility.success")
        :param value: Amount to increment (default 1)
        """
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value
            _logger.debug("metrics.increment: %s += %d (total: %d)", name, value, self._counters[name])

    def get_counter(self, name):
        """Get current value of a counter."""
        with self._lock:
            return self._counters.get(name, 0)

    @contextmanager
    def measure(self, operation_name):
        """Context manager to measure operation duration.

        :param operation_name: Name of the operation being measured

        Usage:
            with metrics.measure("sync_facility"):
                # ... do work ...
        """
        start = time.perf_counter()
        try:
            yield
            self.increment(f"{operation_name}.success")
        except Exception:
            self.increment(f"{operation_name}.failure")
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            with self._lock:
                if operation_name not in self._timings:
                    self._timings[operation_name] = []
                self._timings[operation_name].append(elapsed_ms)
            _logger.debug("metrics.timing: %s = %.2fms", operation_name, elapsed_ms)

    def get_timing_stats(self, operation_name):
        """Get timing statistics for an operation.

        :return: dict with count, total_ms, avg_ms, min_ms, max_ms
        """
        with self._lock:
            timings = self._timings.get(operation_name, [])
            if not timings:
                return {"count": 0, "total_ms": 0, "avg_ms": 0, "min_ms": 0, "max_ms": 0}
            return {
                "count": len(timings),
                "total_ms": sum(timings),
                "avg_ms": sum(timings) / len(timings),
                "min_ms": min(timings),
                "max_ms": max(timings),
            }

    def get_all_counters(self):
        """Get snapshot of all counters."""
        with self._lock:
            return dict(self._counters)

    def reset(self):
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._counters.clear()
            self._timings.clear()


def get_metrics():
    """Get the singleton MetricsCollector instance.

    Thread-safe lazy initialization.
    """
    global _metrics_instance
    if _metrics_instance is None:
        with _metrics_lock:
            if _metrics_instance is None:
                _metrics_instance = MetricsCollector()
    return _metrics_instance
