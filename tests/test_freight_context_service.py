"""Pure-Python regression tests for the Linda freight-context contract."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

SERVICE_PATH = Path(__file__).parents[1] / "plasticos_logistics" / "services" / "freight_context.py"
SPEC = importlib.util.spec_from_file_location("freight_context_service", SERVICE_PATH)
freight_context = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = freight_context
SPEC.loader.exec_module(freight_context)


def _partner(identifier: int, street: str):
    return SimpleNamespace(
        id=identifier,
        contact_address_complete=street,
        city="Houston",
        country_id=SimpleNamespace(id=233),
        state_id=SimpleNamespace(id=48),
        street=street,
        street2=False,
        zip="77001",
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
