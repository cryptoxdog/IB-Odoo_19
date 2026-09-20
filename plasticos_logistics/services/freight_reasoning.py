"""Deterministic Linda explanations derived only from canonical Odoo freight facts."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FreightReasoning:
    observed_state: str
    decision: str
    violations: list[str]
    next_valid_actions: list[str]
    facts_used: list[str]
    unknowns: list[str]

    def as_dict(self) -> dict:
        return asdict(self)


def explain_load_freight(load) -> FreightReasoning:
    """Explain current freight readiness without creating authority or transitions."""
    facts = [f"load.state={load.state}"]
    violations: list[str] = []
    next_actions: list[str] = []
    unknowns: list[str] = []
    if load.state == "ready_confirmed" and not load.rate_resolution_method:
        violations.append("no_current_freight_resolution")
        next_actions.append("action_resolve_freight")
        return FreightReasoning(load.state, "blocked", violations, next_actions, facts, unknowns)
    if load.rate_resolution_method and not load.freight_context_fingerprint:
        violations.append("resolution_missing_context_provenance")
        return FreightReasoning(load.state, "blocked", violations, next_actions, facts, unknowns)
    if load.sal_decision in ("miss", "not_eligible"):
        facts.append(f"sal.decision={load.sal_decision}")
        unknowns.append("outbound_delivery_unavailable")
        next_actions.append("action_create_freight_quote_request")
    if load.state in ("dispatched", "picked_up", "delivered", "closed"):
        return FreightReasoning(load.state, "informational", violations, next_actions, facts, unknowns)
    return FreightReasoning(load.state, "allowed", violations, next_actions, facts, unknowns)
