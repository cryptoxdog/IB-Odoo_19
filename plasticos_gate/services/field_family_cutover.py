"""Opt-in field-family cutover controls (TASK-035 / ADR-127).

Gates read authority for one approved semantic family to Gate-mediated
path. Defaults OFF. Does not restore local matching/inference authority.
Actual production cutover remains an operator action outside this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

_TRUTHY = {"1", "true", "True", "yes", "on"}

ICP_CUTOVER_ENABLED = "plasticos.gate.field_family_cutover_enabled"
ICP_CUTOVER_FAMILY = "plasticos.gate.field_family_cutover_family"
ICP_OPERATOR_APPROVED = "plasticos.gate.field_family_cutover_operator_approved"

# Wave lock: only specification is eligible (TASK-031 / TASK-063 lineage).
APPROVED_FAMILY = "specification"
BLOCKED_FAMILIES = frozenset({"supply", "demand"})

# Must be defined before any enable — observation window entry criteria.
REQUIRED_OBSERVATION_METRICS: tuple[str, ...] = (
    "gate_path_success_rate",
    "gate_path_latency_p95_ms",
    "parity_mismatch_count",
    "local_authority_attempt_count",
)


@dataclass
class FieldFamilyCutoverDecision:
    enabled: bool
    operator_approved: bool
    family: str
    mode: str  # "off" | "blocked" | "armed"
    gate_authority: bool = True
    local_intelligence_authority: bool = False
    observation_metrics: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    observed_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _truthy(env, key: str, default: str = "0") -> bool:
    icp = env["ir.config_parameter"].sudo()
    return (icp.get_param(key, default) or "").strip() in _TRUTHY


def _family_param(env) -> str:
    icp = env["ir.config_parameter"].sudo()
    raw = (icp.get_param(ICP_CUTOVER_FAMILY, APPROVED_FAMILY) or APPROVED_FAMILY).strip()
    return raw or APPROVED_FAMILY


def cutover_enabled(env) -> bool:
    """Return True only when operators explicitly opt in (default OFF)."""
    return _truthy(env, ICP_CUTOVER_ENABLED, "0")


def operator_approved(env) -> bool:
    """Second gate: explicit operator approval flag (default OFF)."""
    return _truthy(env, ICP_OPERATOR_APPROVED, "0")


def observation_metrics_defined() -> list[str]:
    """Return the locked observation metric names required before enable."""
    return list(REQUIRED_OBSERVATION_METRICS)


def classify_cutover(env) -> FieldFamilyCutoverDecision:
    """Classify cutover posture. Gate remains sole intelligence authority."""
    enabled = cutover_enabled(env)
    approved = operator_approved(env)
    family = _family_param(env)
    reasons: list[str] = []
    metrics = observation_metrics_defined()

    if family in BLOCKED_FAMILIES:
        reasons.append(f"family={family} is BLOCKED_AUTOMATIC")
        mode = "blocked"
    elif family != APPROVED_FAMILY:
        reasons.append(f"family={family} is not the approved cutover family ({APPROVED_FAMILY})")
        mode = "blocked"
    elif not enabled:
        reasons.append(f"{ICP_CUTOVER_ENABLED} is off (default)")
        mode = "off"
    elif not approved:
        reasons.append(f"{ICP_OPERATOR_APPROVED} is off — config alone is insufficient")
        mode = "off"
    elif not metrics:
        reasons.append("observation metrics missing — refuse enable")
        mode = "blocked"
    else:
        reasons.append(
            f"armed for family={family}; Gate-mediated read authority eligible "
            "(production enable remains operator-owned)"
        )
        mode = "armed"

    return FieldFamilyCutoverDecision(
        enabled=enabled and approved and mode == "armed",
        operator_approved=approved,
        family=family,
        mode=mode,
        gate_authority=True,
        local_intelligence_authority=False,
        observation_metrics=metrics,
        reasons=reasons,
        observed_at=datetime.now(UTC).isoformat(),
    )


def field_family_uses_gate_authority(env, family: str) -> bool:
    """True when cutover is armed for the given family."""
    decision = classify_cutover(env)
    return decision.mode == "armed" and decision.family == family and family == APPROVED_FAMILY


def assert_no_local_intelligence_restoration(decision: FieldFamilyCutoverDecision) -> None:
    """Fail closed if cutover ever claims or restores local intelligence authority."""
    if decision.local_intelligence_authority:
        raise RuntimeError("local intelligence authority restoration is forbidden under ADR-127")
    if not decision.gate_authority:
        raise RuntimeError("Gate authority must remain true for field-family cutover")


def recovery_disable(env) -> FieldFamilyCutoverDecision:
    """Disable cutover flags; restore prior field authority without local matcher."""
    icp = env["ir.config_parameter"].sudo()
    icp.set_param(ICP_CUTOVER_ENABLED, "0")
    icp.set_param(ICP_OPERATOR_APPROVED, "0")
    decision = classify_cutover(env)
    assert_no_local_intelligence_restoration(decision)
    return decision
