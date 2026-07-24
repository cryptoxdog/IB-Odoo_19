"""Gate ICP helpers and integration exceptions — no UserError on fallback path."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from constellation_node_sdk import GateClientConfig


class GateIntegrationError(Exception):
    """Raised when Gate transport fails; matcher catches and falls back locally."""


_TRUTHY = {"1", "true", "True", "yes", "on"}


def _gate_url_usable(icp) -> bool:
    """Return True when the configured Gate URL is present and uses an accepted scheme.

    TLS (``https``) is required by default. The cleartext scheme is accepted only
    when the deployment explicitly opts in via ``plasticos.gate.allow_insecure_http=1``
    (intended for local development against a loopback Gate only).
    """
    url = (icp.get_param("plasticos.gate.url") or "").strip()
    scheme = urlsplit(url).scheme.lower()
    if scheme == "https":
        return True
    insecure_ok = (icp.get_param("plasticos.gate.allow_insecure_http") or "").strip() in _TRUTHY
    return insecure_ok and scheme == "http"  # NOSONAR(S5332) explicit local-dev opt-in, off by default


def gate_matching_enabled(env) -> bool:
    """Return True when Gate matching should be attempted (never raises)."""
    icp = env["ir.config_parameter"].sudo()
    if not _gate_url_usable(icp):
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


def gate_enrichment_enabled(env) -> bool:
    """Return True when Gate enrichment (converge) should be attempted (never raises).

    Live by default: enabled whenever a Gate URL is configured and the SDK is present
    (seeded ``plasticos.gate.enrichment_enabled=1``). Set it to ``0`` to disable.
    """
    icp = env["ir.config_parameter"].sudo()
    if not _gate_url_usable(icp):
        return False
    if (icp.get_param("plasticos.gate.enrichment_enabled", "1") or "").strip() not in _TRUTHY:
        return False
    try:
        import constellation_node_sdk  # noqa: F401
    except ImportError:
        return False
    return True


def gate_auto_writeback_enabled(env) -> bool:
    """Return True when converge results should be applied live to the partner.

    ON by default: allowlisted fields are backfilled (merge-not-overwrite) with
    provenance. Set ``plasticos.gate.auto_writeback=0`` to fall back to review-only
    (proposal stored, state='review', no partner writes).
    """
    icp = env["ir.config_parameter"].sudo()
    return (icp.get_param("plasticos.gate.auto_writeback", "1") or "").strip() in _TRUTHY


def get_enrichment_action(env) -> str:
    icp = env["ir.config_parameter"].sudo()
    return (icp.get_param("plasticos.gate.enrichment_action") or "converge").strip().lower()


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
