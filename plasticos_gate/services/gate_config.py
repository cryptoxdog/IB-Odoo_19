"""Gate ICP helpers and integration exceptions — no UserError on fallback path."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from constellation_node_sdk import GateClientConfig


class GateIntegrationError(Exception):
    """Raised when Gate transport fails; matcher catches and falls back locally."""


def gate_matching_enabled(env) -> bool:
    """Return True when Gate matching should be attempted (never raises)."""
    icp = env["ir.config_parameter"].sudo()
    url = (icp.get_param("plasticos.gate.url") or "").strip()
    if not url.startswith(("http://", "https://")):
        return False
    if (icp.get_param("plasticos.gate.matching_enabled", "1") or "").strip() in {"0", "false", "False"}:
        return False
    try:
        import constellation_node_sdk  # noqa: F401
    except ImportError:
        return False
    return True


def get_matching_action(env) -> str:
    icp = env["ir.config_parameter"].sudo()
    return (icp.get_param("plasticos.gate.matching_action") or "match").strip().lower()


def build_gate_client_config(env) -> GateClientConfig:
    """Build SDK config — call only after gate_matching_enabled() passes."""
    from constellation_node_sdk import GateClientConfig

    icp = env["ir.config_parameter"].sudo()
    return GateClientConfig(
        gate_url=(icp.get_param("plasticos.gate.url") or "").strip(),
        local_node=(icp.get_param("plasticos.gate.local_node") or "odoo").strip().lower(),
        timeout_seconds=float(icp.get_param("plasticos.gate.timeout_seconds") or "30"),
        allowed_gate_destination="gate",
    )


def resolve_tenant(env) -> str:
    icp = env["ir.config_parameter"].sudo()
    org_id = (icp.get_param("plasticos.gate.org_id") or "").strip()
    return org_id or env.cr.dbname
