"""Worksheet limit for diagnostic and test-database ERP imports.

``ERP_LIMIT`` accepts a count (``"100"``: the newest 100 worksheets) or a
percentage (``"25%"``: the newest quarter). The percentage form is what test
databases use so an import proves the pipeline on a bounded, recent slice of
the source instead of the full history. Odoo-free: shared by the shell driver
and by the worksheet selection in the historical-import extension.
"""

from __future__ import annotations

import math

__all__ = ["parse_limit", "resolve_limit"]


def parse_limit(raw: str | None) -> int | float | None:
    """``"100"`` → 100 worksheets; ``"25%"`` → ``0.25``; anything else → no limit."""
    text = (raw or "").strip()
    if text.endswith("%") and text[:-1].strip().isdigit():
        percent = int(text[:-1].strip())
        return percent / 100 if 0 < percent < 100 else None
    return int(text) if text.isdigit() and int(text) > 0 else None


def resolve_limit(limit: int | float | None, total: int) -> int | None:
    """A fraction becomes a worksheet count against ``total``, rounded up so a tiny source still runs."""
    if not limit:
        return None
    if isinstance(limit, float):
        return max(1, math.ceil(total * limit))
    return int(limit)
