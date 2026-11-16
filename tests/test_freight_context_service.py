"""Pure-Python regression tests for the Linda freight-context contract."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

SERVICE_PATH = Path(__file__).parents[1] / "plasticos_logistics" / "services" / "freight_context.py"
SPEC = importlib.util.spec_from_file_location("freight_context_service", SERVICE_PATH)
assert SPEC and SPEC.loader
freight_context = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = freight_context
SPEC.loader.exec_module(freight_context)


def _partner(identifier: int, street: str, latitude=29.7604, longitude=-95.3698):
    return SimpleNamespace(
        id=identifier,
        city="Houston",
        country_id=SimpleNamespace(id=233),
        state_id=SimpleNamespace(id=48),
        street=street,
        street2=False,
        zip="77001",
        partner_latitude=latitude,
        partner_longitude=longitude,
    )


def _load(origin_street="100 Origin Way", destination_street="200 Destination Lane", weight=40000.0):
    return SimpleNamespace(
        company_id=SimpleNamespace(id=1),
        delivery_partner_id=_partner(22, destination_street),
        pickup_partner_id=_partner(11, origin_street),
        reference_weight=weight,
        transaction_id=SimpleNamespace(intake_id=SimpleNamespace(id=73)),
    )


def test_context_is_stable_for_semantically_identical_inputs():
    assert (
        freight_context.build_freight_context(_load()).fingerprint
        == freight_context.build_freight_context(_load()).fingerprint
    )


def test_context_changes_when_physical_origin_changes():
    assert (
        freight_context.build_freight_context(_load()).fingerprint
        != freight_context.build_freight_context(_load(origin_street="101 Origin Way")).fingerprint
    )


def test_context_changes_when_physical_destination_changes():
    assert (
        freight_context.build_freight_context(_load()).fingerprint
        != freight_context.build_freight_context(_load(destination_street="201 Destination Lane")).fingerprint
    )


def test_context_changes_when_weight_changes():
    assert (
        freight_context.build_freight_context(_load()).fingerprint
        != freight_context.build_freight_context(_load(weight=41000.0)).fingerprint
    )


def test_context_changes_when_physical_geocode_changes():
    baseline = _load()
    corrected = _load()
    corrected.pickup_partner_id.partner_latitude = 29.7605
    assert (
        freight_context.build_freight_context(baseline).fingerprint
        != freight_context.build_freight_context(corrected).fingerprint
    )


def test_context_does_not_require_a_presentation_only_partner_address_field():
    baseline = _load()
    changed_presentation = _load()
    changed_presentation.pickup_partner_id.contact_address_complete = "Different presentation only"
    assert (
        freight_context.build_freight_context(baseline).fingerprint
        == freight_context.build_freight_context(changed_presentation).fingerprint
    )


def test_context_requires_positive_weight_and_repeat_stream():
    assert freight_context.build_freight_context(_load(weight=0.0)) is None
    no_intake = _load()
    no_intake.transaction_id = SimpleNamespace(intake_id=None)
    assert freight_context.build_freight_context(no_intake) is None


def test_location_fingerprints_are_sha256_digests():
    context = freight_context.build_freight_context(_load())
    assert len(context.location_fingerprint_origin) == 64
    assert len(context.location_fingerprint_destination) == 64
    assert len(context.fingerprint) == 64


# ── Manual / buyerless context (RP-01-E004, RP-01-E005, BRS-EXP-10-R006) ──

# freight_context_v3 digest of _load() at base 08504e12. Unchanged legacy contexts
# must keep these exact bytes so accepted fingerprints are never rehashed.
V3_GOLDEN_FINGERPRINT = "8679ff6d1be7a0ae5850190acf9cd77a49ce4e990631b22ad1d1092a1d3a1dc3"


def _buyerless_load(**overrides):
    load = _load()
    load.transaction_id = None
    for name, value in overrides.items():
        setattr(load, name, value)
    return load


def test_legacy_v3_context_bytes_are_unchanged():
    context = freight_context.build_freight_context(_load())
    assert context.fingerprint == V3_GOLDEN_FINGERPRINT
    assert context.version == freight_context.FREIGHT_CONTEXT_VERSION
    assert '"repeat_stream":{"id":73,"kind":"intake"}' in context.serialized


def test_manual_context_needs_no_intake_and_has_no_repeat_stream():
    context = freight_context.build_manual_freight_context(_buyerless_load())
    assert context is not None
    assert context.version == freight_context.FREIGHT_CONTEXT_MANUAL_VERSION
    assert context.repeat_stream_id is None
    assert "repeat_stream" not in context.serialized
    assert context.fingerprint != V3_GOLDEN_FINGERPRINT


def test_manual_context_records_unknown_equipment_explicitly():
    context = freight_context.build_manual_freight_context(_buyerless_load())
    assert '"equipment_class":"unknown"' in context.serialized
    assert '"equipment_class":null' not in context.serialized


def test_manual_context_still_requires_company_lane_and_weight():
    assert freight_context.build_manual_freight_context(_buyerless_load(company_id=None)) is None
    assert freight_context.build_manual_freight_context(_buyerless_load(reference_weight=0.0)) is None
    assert freight_context.build_manual_freight_context(_buyerless_load(pickup_partner_id=None)) is None


def test_manual_context_changes_with_the_physical_lane():
    baseline = freight_context.build_manual_freight_context(_buyerless_load())
    moved = freight_context.build_manual_freight_context(
        _buyerless_load(delivery_partner_id=_partner(22, "201 Destination Lane"))
    )
    assert baseline.fingerprint != moved.fingerprint


def test_manual_rate_selection_keeps_v3_for_an_intake_backed_load():
    assert freight_context.select_manual_rate_context(_load()).fingerprint == V3_GOLDEN_FINGERPRINT
    manual = freight_context.select_manual_rate_context(_buyerless_load())
    assert manual.version == freight_context.FREIGHT_CONTEXT_MANUAL_VERSION


def test_recorded_version_selects_its_own_validator():
    load = _load()
    v3 = freight_context.build_freight_context_for_version(load, freight_context.FREIGHT_CONTEXT_VERSION)
    manual = freight_context.build_freight_context_for_version(load, freight_context.FREIGHT_CONTEXT_MANUAL_VERSION)
    assert v3.fingerprint == V3_GOLDEN_FINGERPRINT
    assert manual.fingerprint != v3.fingerprint
    assert freight_context.build_freight_context_for_version(load, "freight_context_v2") is None


def _sal_resolver():
    """Load sal_resolver beside this freight_context, with a minimal odoo.fields stub when needed."""
    import types
    from datetime import UTC, datetime

    if "odoo" not in sys.modules and importlib.util.find_spec("odoo") is None:
        odoo_mod = types.ModuleType("odoo")
        fields_mod = types.ModuleType("odoo.fields")
        fields_mod.Datetime = type("Datetime", (), {"now": staticmethod(lambda: datetime.now(UTC))})
        odoo_mod.fields = fields_mod
        sys.modules["odoo"] = odoo_mod
        sys.modules["odoo.fields"] = fields_mod
    package = types.ModuleType("plasticos_logistics_fc_tests")
    services = types.ModuleType("plasticos_logistics_fc_tests.services")
    services.__path__ = [str(SERVICE_PATH.parent)]
    sys.modules["plasticos_logistics_fc_tests"] = package
    sys.modules["plasticos_logistics_fc_tests.services"] = services
    for name in ("freight_context", "sal_resolver"):
        spec = importlib.util.spec_from_file_location(
            f"plasticos_logistics_fc_tests.services.{name}", SERVICE_PATH.parent / f"{name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return sys.modules["plasticos_logistics_fc_tests.services.sal_resolver"]


class _NoSearch:
    def search(self, *args, **kwargs):
        raise AssertionError("SAL must abstain before any history lookup")


def test_sal_abstains_before_searching_for_a_load_without_intake():
    sal_resolver = _sal_resolver()
    load = _buyerless_load(
        state="ready_confirmed",
        rate_amount=0.0,
        carrier_id=None,
        sale_order_id=None,
        env={"plasticos.load": _NoSearch()},
    )
    decision = sal_resolver.resolve_sal(load)
    assert (decision.decision, decision.reason) == ("not_eligible", "missing_lane_identity")
    assert decision.source_load_id is None
