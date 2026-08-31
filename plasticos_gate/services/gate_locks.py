"""PostgreSQL advisory locks for single-writer background workers.

A scheduler or drain worker must not run twice concurrently: two workers would
claim the same records and duplicate outbound work. Odoo has no cross-worker
mutex, so serialisation uses PostgreSQL session-level advisory locks, which
survive the per-record commits these workers rely on.

This is worker serialisation only. It is not a repository-write lock and it
grants no authority over anything but the named worker.
"""

from __future__ import annotations

import hashlib
import logging
from contextlib import contextmanager

_logger = logging.getLogger(__name__)

#: Namespace shared by every PlasticOS worker lock, so keys cannot collide with
#: advisory locks taken by Odoo core or another addon.
LOCK_CLASS_ID = 0x504C4153  # "PLAS"

_INT32_SPAN = 2**32
_INT32_MAX = 2**31


def lock_key(name: str) -> int:
    """Return a stable signed 32-bit advisory-lock key for ``name``."""
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    value = int.from_bytes(digest[:4], "big") % _INT32_SPAN
    return value - _INT32_SPAN if value >= _INT32_MAX else value


@contextmanager
def worker_lock(cr, name: str):
    """Hold the named worker lock for the block; yield False if already held.

    Session-scoped (``pg_advisory_lock``) rather than transaction-scoped, because
    these workers commit after every record and a transaction lock would be
    released by the first commit.
    """
    key = lock_key(name)
    cr.execute("SELECT pg_try_advisory_lock(%s, %s)", (LOCK_CLASS_ID, key))
    acquired = bool(cr.fetchone()[0])
    if not acquired:
        _logger.info("Worker lock %s already held; skipping this run.", name)
        yield False
        return
    try:
        yield True
    finally:
        try:
            cr.execute("SELECT pg_advisory_unlock(%s, %s)", (LOCK_CLASS_ID, key))
            cr.fetchone()
        except Exception:  # pragma: no cover — never mask the worker's own error
            _logger.exception("Failed to release worker lock %s", name)
