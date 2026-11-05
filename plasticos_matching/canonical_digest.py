"""Deterministic digest for Gate match receipts.

Kept free of the Odoo registry so pure-Python tests can import it directly.
"""

from __future__ import annotations

import hashlib
import json


def _canonical_digest(value):
    """Return a deterministic SHA-256 digest of Gate request or response material."""
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
