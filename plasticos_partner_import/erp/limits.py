"""Worksheet limit for diagnostic and test-database ERP imports.

``ERP_LIMIT`` accepts a count (``"100"``: the newest 100 worksheets) or a whole
percentage (``"25%"``: the newest quarter). Test databases use the percentage
form so an import proves the pipeline on a bounded, recent slice of the source
instead of the full history.

A fraction becomes a worksheet count in exactly one place,
``erp.native_orders.selected_worksheets``, against the worksheet count of the
source being imported. Everything upstream only validates and carries it.

An unset limit means a full import. Any other value that is not a valid limit
raises ``ValueError``: a typo must never widen a bounded run into an
unrestricted one. Odoo-free.
"""

from __future__ import annotations

import math
import re

__all__ = ["parse_limit", "resolve_limit", "validate_limit"]

_COUNT = re.compile(r"\d+")
_PERCENT = re.compile(r"(\d+)\s*%")
_HINT = "a positive worksheet count (e.g. 100) or a whole percentage from 1% to 100% (e.g. 25%)"


def parse_limit(raw: str | None) -> int | float | None:
    """``"100"`` → 100 worksheets; ``"25%"`` → ``0.25``; unset → ``None`` (full import).

    Raises ``ValueError`` for anything else, including ``0``, ``0%``, ``101%``,
    ``12.5%``, negative numbers, and text.
    """
    text = (raw or "").strip()
    if not text:
        return None
    if _COUNT.fullmatch(text) and int(text) >= 1:
        return int(text)
    percent = _PERCENT.fullmatch(text)
    if percent and 1 <= int(percent.group(1)) <= 100:
        return int(percent.group(1)) / 100
    raise ValueError(f"ERP_LIMIT must be {_HINT}; got {raw!r}")


def validate_limit(limit: int | float | None) -> int | float | None:
    """Accept ``None``, an ``int`` of at least 1, or a fraction in ``(0, 1]``; refuse anything else."""
    if limit is None:
        return None
    if not isinstance(limit, bool):
        if isinstance(limit, int) and limit >= 1:
            return limit
        if isinstance(limit, float) and 0 < limit <= 1:
            return limit
    raise ValueError(f"worksheet limit must be {_HINT}; got {limit!r}")


def resolve_limit(limit: int | float | None, total: int) -> int | None:
    """The worksheet count a limit selects out of ``total`` worksheets; ``None`` means no limit.

    A fraction rounds up so a small source still imports at least one worksheet.
    """
    limit = validate_limit(limit)
    if isinstance(limit, float):
        return min(total, math.ceil(total * limit))
    return limit
