"""Opt-in Gate dual-write controls (TASK-032 / ADR-125).

Local projection/audit mirroring of Gate-mediated intelligence results.
Does not confer local matching or inference authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

_TRUTHY = {"1", "true", "True", "yes", "on"}
ICP_DUAL_WRITE = "plasticos.gate.dual_write_enabled"
ICP_DUAL_WRITE_AUDIT = "plasticos.gate.dual_write_audit"


@dataclass
class DualWriteDecision:
    enabled: bool
    mode: str  # "off" | "projection_audit"
    gate_authority: bool = True
    local_intelligence_authority: bool = False
    reasons: list[str] = field(default_factory=list)
    observed_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DualWriteAuditEntry:
    packet_id: str
    action: str
    projection_target: str
    status: str
    detail: str = ""
    observed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def dual_write_enabled(env) -> bool:
    """Return True only when operators explicitly opt in (default OFF)."""
    icp = env["ir.config_parameter"].sudo()
    return (icp.get_param(ICP_DUAL_WRITE, "0") or "").strip() in _TRUTHY


def classify_dual_write(env) -> DualWriteDecision:
    """Classify dual-write posture. Gate remains sole intelligence authority."""
    enabled = dual_write_enabled(env)
    reasons: list[str] = []
    if not enabled:
        reasons.append(f"{ICP_DUAL_WRITE} is off (default)")
        mode = "off"
    else:
        reasons.append("opt-in projection/audit mirror enabled")
        mode = "projection_audit"
    return DualWriteDecision(
        enabled=enabled,
        mode=mode,
        gate_authority=True,
        local_intelligence_authority=False,
        reasons=reasons,
        observed_at=datetime.now(UTC).isoformat(),
    )


def plan_projection_write(
    *,
    packet_id: str,
    action: str,
    gate_payload: dict[str, Any],
    projection_target: str = "plasticos.gate.projection_audit",
) -> DualWriteAuditEntry:
    """Build an audit entry for a Gate-authority result mirrored locally.

    Never invents local matcher/inference authority. Callers must only invoke
    this when ``dual_write_enabled(env)`` is True.
    """
    if not packet_id:
        raise ValueError("packet_id required for dual-write audit")
    if not isinstance(gate_payload, dict):
        raise TypeError("gate_payload must be a dict")
    return DualWriteAuditEntry(
        packet_id=str(packet_id),
        action=str(action or "unknown"),
        projection_target=projection_target,
        status="planned",
        detail=f"keys={sorted(gate_payload.keys())}",
    )


def assert_no_local_intelligence_authority(decision: DualWriteDecision) -> None:
    """Fail closed if a decision ever claims local intelligence authority."""
    if decision.local_intelligence_authority:
        raise RuntimeError("local intelligence authority is forbidden under ADR-125")
    if not decision.gate_authority:
        raise RuntimeError("Gate authority must remain true for dual-write")
