"""Pure-Python contract tests for the Odoo side of the constellation seams.

Covers the three contracts this repository owns and can break on its own:

* canonical converge identity + deterministic idempotency (Odoo -> EIE),
* canonical Graph match direction + response direction key (Odoo <-> Graph),
* the authoritative Odoo -> Graph facility projection and its retry policy.

No Odoo runtime: these run in the ``pure-python-tests`` CI job.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_gate.services.gate_builders import (  # noqa: E402
    CONVERGE_PIPELINE_CONTRACT_VERSION,
    build_converge_idempotency_key,
    build_converge_request,
    build_entity_ref,
    build_match_request,
    converge_input_fingerprint,
)
from plasticos_gate.services.gate_contracts import (  # noqa: E402
    MATCH_DIRECTION_BUYER_TO_SUPPLY,
    MATCH_DIRECTION_SUPPLY_TO_BUYER,
    normalize_match_direction,
)
from plasticos_gate.services.gate_mappers import map_match_response  # noqa: E402
from plasticos_gate.services.gate_projection import (  # noqa: E402
    FACILITY_ENTITY_TYPE,
    POUNDS_PER_SHORT_TON,
    ProjectionContractError,
    build_facility_id,
    build_facility_projection_row,
    build_facility_sync_payload,
    projection_semantic_key,
    validate_projection_row,
)
from plasticos_gate.services.gate_retry import (  # noqa: E402
    MAX_ATTEMPTS,
    MAX_RETRIES,
    RETRY_BACKOFF_SECONDS,
    attempts_exhausted,
    next_retry_delay_seconds,
)


class _MockICP:
    def __init__(self, params: dict[str, str]):
        self._params = params

    def get_param(self, key: str, default=None):
        return self._params.get(key, default)


class _MockEnv:
    def __init__(self, params: dict[str, str] | None = None, dbname: str = "plasticos_prod"):
        self.cr = SimpleNamespace(dbname=dbname)
        self.company = SimpleNamespace(id=1)
        self.user = SimpleNamespace(id=2)
        self._icp = _MockICP(params or {})

    def __getitem__(self, key: str):
        if key == "ir.config_parameter":
            return self
        raise KeyError(key)

    def sudo(self):
        return self

    def get_param(self, key: str, default=None):
        return self._icp.get_param(key, default)


class _PartnerStub:
    _name = "res.partner"

    def __init__(self, *, partner_id=55, name="Acme Recycling", lat=35.22, lon=-80.84):
        self.id = partner_id
        self._fields = {"name", "website", "city", "zip", "street", "street2", "comment", "email", "phone"}
        self.name = name
        self.website = "https://acme.example"
        self.city = "Charlotte"
        self.zip = "28202"
        self.street = "1 Polymer Way"
        self.street2 = False
        self.comment = False
        self.email = "ops@acme.example"
        self.phone = "+1-704-555-0100"
        self.partner_latitude = lat
        self.partner_longitude = lon

    def __getitem__(self, key):
        return getattr(self, key)


class _SourceStub:
    def __init__(self, url):
        self.url = url


class _RunStub:
    _name = "plasticos.enrichment.run"

    def __init__(self, partner=None, sources=("https://acme.example/about",)):
        self.id = 7
        self.partner_id = partner or _PartnerStub()
        self.source_ids = [_SourceStub(url) for url in sources]


class _FacilityProfileStub:
    _name = "plasticos.facility.profile"

    def __init__(self, *, profile_id=31, capacity_lbs_month=1_600_000.0, food_grade=False):
        self.id = profile_id
        self.capacity_lbs_month = capacity_lbs_month
        self.food_grade_certified = food_grade


class _IntakeStub:
    _name = "plasticos.intake"

    def __init__(self):
        self.id = 42
        self._fields = {"polymer_id", "form_id", "color_id", "partner_id"}
        self.polymer_id = SimpleNamespace(code="HDPE", name="HDPE", id=10)
        self.form_id = SimpleNamespace(code="PELLET", name="Pellet", id=11)
        self.color_id = SimpleNamespace(code="NAT", name="Natural", id=12)
        self.partner_id = SimpleNamespace(id=99)

    def __getitem__(self, key):
        return getattr(self, key)


# ── Converge identity ────────────────────────────────────────────


def test_converge_request_carries_canonical_entity_id():
    """EIE resolves identity from entity["id"]; without it, traffic falls through."""
    request = build_converge_request(_MockEnv(), _RunStub())
    assert request.entity["id"] == "res.partner:55"


def test_converge_request_dual_populates_legacy_identity_key():
    """The legacy key stays for one migration window — removal needs telemetry."""
    request = build_converge_request(_MockEnv(), _RunStub())
    assert request.entity["_odoo_entity_id"] == "res.partner:55"
    assert request.to_dict()["entity"]["id"] == "res.partner:55"


def test_converge_request_sets_deterministic_idempotency_key():
    wire = build_converge_request(_MockEnv(), _RunStub()).to_dict()
    key = wire["idempotency_key"]
    assert key.startswith(f"odoo:plasticos_prod:res.partner:55:converge:{CONVERGE_PIPELINE_CONTRACT_VERSION}:")


def test_idempotency_key_is_stable_across_identical_attempts():
    """A retry of the same semantic work must reuse the cached computation."""
    first = build_converge_request(_MockEnv(), _RunStub()).idempotency_key
    second = build_converge_request(_MockEnv(), _RunStub()).idempotency_key
    assert first == second


def test_idempotency_key_changes_when_partner_snapshot_changes():
    base = build_converge_request(_MockEnv(), _RunStub()).idempotency_key
    changed_partner = _PartnerStub()
    changed_partner.city = "Raleigh"
    changed = build_converge_request(_MockEnv(), _RunStub(partner=changed_partner)).idempotency_key
    assert changed != base


def test_idempotency_key_ignores_source_url_ordering_and_duplicates():
    """Relation ordering noise must not invalidate a cached enrichment."""
    a = build_converge_request(_MockEnv(), _RunStub(sources=("https://a.example", "https://b.example")))
    b = build_converge_request(
        _MockEnv(), _RunStub(sources=("https://b.example", "https://a.example", "https://b.example"))
    )
    assert a.idempotency_key == b.idempotency_key


def test_idempotency_key_is_scoped_per_database():
    """Two databases may safely produce the same caller-side semantic inputs."""
    a = build_converge_request(_MockEnv(dbname="tenant_a"), _RunStub()).idempotency_key
    b = build_converge_request(_MockEnv(dbname="tenant_b"), _RunStub()).idempotency_key
    assert a != b


def test_fingerprint_excludes_run_and_attempt_identity():
    """Fingerprint material is semantic only — no run id, packet id, or clock."""
    snapshot = {"name": "Acme", "source_urls": ["https://a.example"]}
    kwargs = {"object_type": "plasticos", "objective": "obj", "max_variations": 5}
    assert converge_input_fingerprint(snapshot, **kwargs) == converge_input_fingerprint(snapshot, **kwargs)


def test_fingerprint_changes_with_pipeline_contract_version():
    """A deliberate pipeline bump must invalidate previously cached results."""
    snapshot = {"name": "Acme"}
    kwargs = {"object_type": "plasticos", "objective": "obj", "max_variations": 5}
    assert converge_input_fingerprint(snapshot, pipeline_version="v1", **kwargs) != converge_input_fingerprint(
        snapshot, pipeline_version="v2", **kwargs
    )


def test_idempotency_key_falls_back_to_unknown_db_without_fabricating():
    key = build_converge_idempotency_key(db_name=None, entity_ref="res.partner:1", fingerprint="abc")
    assert key == f"odoo:unknown:res.partner:1:converge:{CONVERGE_PIPELINE_CONTRACT_VERSION}:abc"


def test_build_entity_ref_shape():
    assert build_entity_ref("res.partner", 7) == "res.partner:7"


# ── Match direction ──────────────────────────────────────────────


def test_intake_match_request_uses_canonical_graph_direction():
    """Graph accepts only its two published directions; intake is the supply side."""
    request = build_match_request(_MockEnv(), intake=_IntakeStub())
    assert request.to_dict()["match_direction"] == MATCH_DIRECTION_SUPPLY_TO_BUYER


def test_legacy_odoo_direction_is_normalized_not_forwarded():
    assert normalize_match_direction("intake_to_buyer") == MATCH_DIRECTION_SUPPLY_TO_BUYER
    assert normalize_match_direction("buyer_to_intake") == MATCH_DIRECTION_BUYER_TO_SUPPLY


def test_unknown_direction_fails_closed_before_the_round_trip():
    with pytest.raises(ValueError, match="unknown match_direction"):
        normalize_match_direction("sideways")


def test_match_request_rejects_unknown_direction_on_the_wire():
    request = build_match_request(_MockEnv(), intake=_IntakeStub())
    request.match_direction = "nonsense"
    with pytest.raises(ValueError):
        request.to_dict()


def test_mapper_prefers_match_direction_over_legacy_direction_key():
    payload = {
        "match_direction": MATCH_DIRECTION_SUPPLY_TO_BUYER,
        "direction": "intake_to_buyer",
        "candidates": [],
    }
    assert map_match_response(payload).match_direction == MATCH_DIRECTION_SUPPLY_TO_BUYER


def test_mapper_still_reads_legacy_direction_key_during_migration():
    payload = {"direction": "intake_to_buyer", "candidates": []}
    assert map_match_response(payload).match_direction == "intake_to_buyer"


# ── Graph projection ─────────────────────────────────────────────


def test_facility_projection_row_is_built_from_committed_odoo_state():
    row = build_facility_projection_row(_PartnerStub(), _FacilityProfileStub())
    assert row["facility_id"] == "plasticos.facility.profile:31"
    assert row["entity_ref"] == "res.partner:55"
    assert row["name"] == "Acme Recycling"
    assert row["lat"] == pytest.approx(35.22)
    assert row["capacity_tons_month"] == pytest.approx(1_600_000.0 / POUNDS_PER_SHORT_TON)
    assert row["food_grade_certified"] is False


def test_projection_never_publishes_contact_data():
    """Partner email/phone exist on the stub; the projection must not carry them."""
    row = build_facility_projection_row(_PartnerStub(), _FacilityProfileStub())
    assert "email" not in row
    assert "phone" not in row


def test_partner_without_facility_profile_is_not_declared_a_facility():
    assert build_facility_projection_row(_PartnerStub(), None) is None


def test_ungeocoded_partner_publishes_no_coordinates():
    """0.0/0.0 is a real point in the Gulf of Guinea, not 'unknown'."""
    row = build_facility_projection_row(_PartnerStub(lat=0.0, lon=0.0), _FacilityProfileStub())
    assert "lat" not in row
    assert "lon" not in row


def test_undeclared_property_is_rejected_at_the_producer():
    with pytest.raises(ProjectionContractError, match="undeclared"):
        validate_projection_row(
            {
                "facility_id": "plasticos.facility.profile:1",
                "entity_ref": "res.partner:1",
                "name": "X",
                "internal_notes": "leak",
            }
        )


def test_prohibited_property_is_rejected_even_if_allowlisted_by_mistake():
    with pytest.raises(ProjectionContractError):
        validate_projection_row({"facility_id": "f:1", "entity_ref": "res.partner:1", "name": "X", "email": "a@b.c"})


def test_projection_row_requires_identity():
    with pytest.raises(ProjectionContractError, match="facility_id"):
        validate_projection_row({"entity_ref": "res.partner:1", "name": "X"})


def test_sync_payload_shape():
    row = build_facility_projection_row(_PartnerStub(), _FacilityProfileStub())
    payload = build_facility_sync_payload([row])
    assert payload["entity_type"] == FACILITY_ENTITY_TYPE
    assert payload["batch"] == [row]


def test_semantic_key_is_stable_for_an_unchanged_projection():
    """Replay-safe: resending identical state must not create duplicate work."""
    payload_a = build_facility_sync_payload([build_facility_projection_row(_PartnerStub(), _FacilityProfileStub())])
    payload_b = build_facility_sync_payload([build_facility_projection_row(_PartnerStub(), _FacilityProfileStub())])
    assert projection_semantic_key(payload_a) == projection_semantic_key(payload_b)


def test_semantic_key_changes_when_projected_state_changes():
    before = build_facility_sync_payload([build_facility_projection_row(_PartnerStub(), _FacilityProfileStub())])
    after = build_facility_sync_payload(
        [build_facility_projection_row(_PartnerStub(), _FacilityProfileStub(food_grade=True))]
    )
    assert projection_semantic_key(before) != projection_semantic_key(after)


def test_facility_id_uses_the_declared_stable_id_policy():
    assert build_facility_id(31) == "plasticos.facility.profile:31"


# ── Retry policy ─────────────────────────────────────────────────


def test_first_failure_waits_the_first_published_delay():
    """Callers pass failed-attempt counts, so 1 failure must map to 1 minute.

    Indexing the schedule by the raw attempt counter instead would make the
    published one-minute step unreachable and end the budget a retry early.
    """
    assert next_retry_delay_seconds(1, apply_jitter=False) == 60.0


def test_backoff_progresses_through_the_published_schedule():
    delays = [next_retry_delay_seconds(n, apply_jitter=False) for n in range(1, MAX_RETRIES + 1)]
    assert delays == [float(x) for x in RETRY_BACKOFF_SECONDS]


def test_backoff_is_exhausted_rather_than_infinite():
    assert next_retry_delay_seconds(MAX_RETRIES + 1, apply_jitter=False) is None
    assert attempts_exhausted(MAX_ATTEMPTS) is True
    assert attempts_exhausted(MAX_ATTEMPTS - 1) is False


def test_budget_is_the_initial_attempt_plus_every_retry():
    assert MAX_ATTEMPTS == MAX_RETRIES + 1


def test_jitter_stays_within_the_declared_band():
    base = RETRY_BACKOFF_SECONDS[0]
    for _ in range(50):
        delay = next_retry_delay_seconds(1)
        assert 0.8 * base <= delay <= 1.2 * base
