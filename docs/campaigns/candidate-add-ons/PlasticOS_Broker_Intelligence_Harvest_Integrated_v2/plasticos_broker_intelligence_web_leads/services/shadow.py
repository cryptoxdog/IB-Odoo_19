"""Keep live routing exactly on the existing web-lead pipeline."""


def can_inject(configured_mode, qualification_mode):
    return configured_mode == "shadow_only" and qualification_mode == "shadow"


def context_from_advice(advice):
    """Minimum provider-visible advice; no source facts, proprietary documents or bogus evidence IDs."""
    return {
        "schema": "broker-advice-shadow/v1",
        "advisory_only": True,
        "missing_evidence_questions": list(advice.get("next_human_actions") or [])[:5],
        "allowed_to_change_routing": False,
        "seller_evidence_refs": [],
        "interpretation": "Questions are not source evidence or approval",
    }
