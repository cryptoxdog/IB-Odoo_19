"""Stub mode for buyer matcher only (ICP ``plasticos.matching_engine.stubbed``)."""

from __future__ import annotations

_ICP_STUBBED = "plasticos.matching_engine.stubbed"
_TRUTHY = frozenset({"true", "1", "yes", "on"})


def matching_engine_is_stubbed(env) -> bool:
    """When True, matcher returns deterministic empty results (no live graph)."""
    icp = env["ir.config_parameter"].sudo()
    raw = (icp.get_param(_ICP_STUBBED, "True") or "True").strip().lower()
    return raw in _TRUTHY
