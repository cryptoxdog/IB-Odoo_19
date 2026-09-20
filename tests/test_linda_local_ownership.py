"""Static regression guards for Linda's deterministic target-local boundary."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
LOGISTICS = ROOT / "plasticos_logistics"


def _sources():
    return "\n".join(path.read_text(encoding="utf-8") for path in LOGISTICS.rglob("*.py"))


def test_linda_manifest_has_no_external_intelligence_module_dependency():
    manifest = (LOGISTICS / "__manifest__.py").read_text(encoding="utf-8")
    assert "plasticos_gate" not in manifest
    assert "plasticos_matching" not in manifest
    assert "plasticos_enrichment" not in manifest


def test_linda_has_no_direct_external_intelligence_import_or_action_call():
    source = _sources()
    assert "odoo.addons.plasticos_gate" not in source
    assert "estimate_freight" not in source
    assert "interpret_freight_message" not in source
    assert "openai" not in source.lower()


def test_local_estimator_and_ranking_are_explicitly_versioned_services():
    estimator = (LOGISTICS / "services" / "freight_estimation.py").read_text(encoding="utf-8")
    ranking = (LOGISTICS / "services" / "freight_quote_ranking.py").read_text(encoding="utf-8")
    assert 'ESTIMATOR_MODEL_VERSION = "linda-haversine-curve-v1"' in estimator
    assert 'RANKING_POLICY_VERSION = "linda-quote-rank-v1"' in ranking


def test_canonical_freight_context_uses_only_declared_structured_location_facts():
    context = (LOGISTICS / "services" / "freight_context.py").read_text(encoding="utf-8")
    assert "contact_address_complete" not in context
    assert 'FREIGHT_CONTEXT_VERSION = "freight_context_v3"' in context


def test_immutable_freight_evidence_is_not_directly_creatable_by_internal_users():
    acl = (LOGISTICS / "security" / "ir.model.access.csv").read_text(encoding="utf-8")
    event_user = next(line for line in acl.splitlines() if line.startswith("access_freight_event_user,"))
    calibration_user = next(line for line in acl.splitlines() if line.startswith("access_freight_calibration_user,"))
    estimate_user = next(line for line in acl.splitlines() if line.startswith("access_freight_estimate_user,"))
    assert event_user.endswith(",1,0,0,0")
    assert calibration_user.endswith(",1,0,0,0")
    assert estimate_user.endswith(",1,0,0,0")
