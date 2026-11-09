"""Per-record classification contract for the CRM sync orchestrator.

Pure-python tier (no Odoo import): the REAL `_upsert_lead` classification
logic runs against an in-memory ORM (same seam pattern as
tests/test_crm_sync_full_import.py — only `_lead_vals_from_dto`, which imports
odoo.addons, is replaced). Every record must land in exactly one of
created | updated | unchanged | duplicate_rejected | failed, and unchanged
records must never be written.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_crm_sync.adapters.base import CanonicalLead  # noqa: E402
from plasticos_crm_sync.services.orchestrator import SyncOrchestrator  # noqa: E402


class _Missing:
    id = False

    def __bool__(self):
        return False


MISSING = _Missing()


class _Record:
    def __init__(self, rec_id: int, vals: dict):
        self.id = rec_id
        self.writes = 0
        self.__dict__.update(vals)

    def write(self, vals):
        self.writes += 1
        self.__dict__.update(vals)

    def __getattr__(self, name):
        return False


class _Model:
    def __init__(self, defaults: dict | None = None):
        self.rows: dict[int, _Record] = {}
        self._next = 1
        self._defaults = defaults or {}

    def with_context(self, **ctx):
        return self

    def browse(self, rec_id=None):
        if not rec_id:
            return MISSING
        return self.rows.get(rec_id, MISSING)

    def create(self, vals):
        rec_id = self._next
        self._next += 1
        merged = dict(self._defaults)
        merged.update(vals)
        record = _Record(rec_id, merged)
        self.rows[rec_id] = record
        return record

    def search(self, domain, limit=None, order=None):
        matches = [r for r in self.rows.values() if all(getattr(r, f, None) == v for f, op, v in domain)]
        if limit == 1:
            return matches[0] if matches else MISSING
        return matches


class _Savepoint:
    """In-memory stand-in for ``cr.savepoint()``.

    Snapshots the fake models on enter. An exception restores row identity and
    field values, then propagates. A clean exit keeps the writes.
    """

    def __init__(self, models):
        self._models = tuple(models)
        self._saved = None

    def __enter__(self):
        self._saved = [
            (
                model,
                model._next,
                {rec_id: dict(record.__dict__) for rec_id, record in model.rows.items()},
            )
            for model in self._models
        ]
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None or self._saved is None:
            return False
        for model, next_id, rows in self._saved:
            model._next = next_id
            for rec_id in list(model.rows):
                if rec_id not in rows:
                    del model.rows[rec_id]
            for rec_id, state in rows.items():
                record = model.rows.get(rec_id)
                if record is None:
                    record = _Record(rec_id, {})
                    model.rows[rec_id] = record
                record.__dict__.clear()
                record.__dict__.update(state)
        return False


class _Cr:
    def __init__(self, models):
        self._models = tuple(models)

    def commit(self):
        pass

    def rollback(self):
        pass

    def savepoint(self):
        return _Savepoint(self._models)


class _Env(dict):
    def __init__(self, lead_model, ref_model):
        super().__init__()
        self["crm.lead"] = lead_model
        self["plasticos.crm.external.ref"] = ref_model
        self.cr = _Cr((lead_model, ref_model))


class _Orchestrator(SyncOrchestrator):
    """Real classification logic; only the odoo.addons mapping seam replaced."""

    def __init__(self, env):
        super().__init__(env)
        self.outcomes = None
        self.error_rows = []

    def _lead_vals_from_dto(self, dto):
        return {
            "name": f"{dto.company} — {dto.first_name} {dto.last_name}".strip(),
            "type": "lead",
            "partner_name": dto.company or False,
            "email_from": dto.email or False,
            "vanillasoft_id": dto.external_id,
        }


def _lead(external_id: str, email: str = "a@example.com") -> CanonicalLead:
    return CanonicalLead(
        provider="vanillasoft", external_id=external_id, company="Co", first_name="A", last_name="L", email=email
    )


def _harness():
    leads = _Model()
    refs = _Model()
    env = _Env(leads, refs)
    orch = _Orchestrator(env)
    connection = type("C", (), {"id": 1})()
    return orch, connection, leads, refs


def _outcomes(orch):
    orch.outcomes = {
        "seen": 0,
        "table_rows": 0,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "duplicate_rejected": 0,
        "failed": 0,
    }
    return orch.outcomes


def test_first_upsert_is_created():
    orch, connection, leads, refs = _harness()
    outcomes = _outcomes(orch)
    record = orch._upsert_lead(connection, _lead("a1"))
    assert outcomes == {
        "seen": 0,
        "table_rows": 0,
        "created": 1,
        "updated": 0,
        "unchanged": 0,
        "duplicate_rejected": 0,
        "failed": 0,
    }
    assert refs.rows and list(refs.rows.values())[0].external_id == "a1"
    assert record.id == 1


def test_identical_repeat_is_unchanged_and_not_written():
    orch, connection, leads, refs = _harness()
    _outcomes(orch)
    first = orch._upsert_lead(connection, _lead("a2"))
    outcomes = _outcomes(orch)
    again = orch._upsert_lead(connection, _lead("a2"))
    assert again.id == first.id
    assert outcomes["unchanged"] == 1
    assert outcomes["created"] == 0 and outcomes["updated"] == 0
    assert first.writes == 0, "an unchanged record must never be written"


def test_changed_value_is_updated():
    orch, connection, leads, refs = _harness()
    _outcomes(orch)
    first = orch._upsert_lead(connection, _lead("a3", email="x@example.com"))
    outcomes = _outcomes(orch)
    again = orch._upsert_lead(connection, _lead("a3", email="y@example.com"))
    assert again.id == first.id
    assert outcomes["updated"] == 1
    assert again.email_from == "y@example.com"
    assert len(leads.rows) == 1


def test_duplicate_identity_is_rejected_not_repointed():
    orch, connection, leads, refs = _harness()
    outcomes = _outcomes(orch)
    # Two leads carry the same source id and no external ref exists: ambiguous.
    leads.create({"vanillasoft_id": "dup", "name": "First", "active": True})
    leads.create({"vanillasoft_id": "dup", "name": "Second", "active": True})
    result = orch._upsert_lead(connection, _lead("dup"))
    assert outcomes["duplicate_rejected"] == 1
    assert outcomes["created"] == outcomes["updated"] == outcomes["unchanged"] == 0
    assert len(orch.error_rows) == 1 and orch.error_rows[0]["record_ref"] == "dup"
    assert not refs.rows, "an ambiguous identity must not mint an external ref"
    assert result.id in leads.rows


def test_fake_savepoint_rolls_back_partial_identity():
    """An exception inside the fake savepoint leaves neither a new lead nor a dirty one."""
    orch, connection, leads, refs = _harness()
    outcomes = _outcomes(orch)
    original_create = refs.create

    def boom(_vals):
        raise RuntimeError("injected ref failure")

    refs.create = boom
    returned = orch._upsert_lead(connection, _lead("atomic"))
    assert outcomes["failed"] == 1 and outcomes["created"] == 0
    assert orch.last_lead_outcome == "failed"
    assert not returned
    assert not leads.rows and not refs.rows
    assert orch.error_rows[-1]["record_ref"] == "atomic"
    assert "injected ref failure" in orch.error_rows[-1]["message"]

    refs.create = original_create
    follow_outcomes = _outcomes(orch)
    follow = orch._upsert_lead(connection, _lead("after-atomic"))
    assert follow_outcomes["created"] == 1
    assert follow.id == 1
    assert list(refs.rows.values())[0].external_id == "after-atomic"

    orch, connection, leads, refs = _harness()
    outcomes = _outcomes(orch)
    seeded = leads.create(
        {
            "name": "Old",
            "type": "lead",
            "partner_name": "Old Co",
            "email_from": "old@example.com",
            "vanillasoft_id": "atomic-upd",
        }
    )

    def boom_update(_vals):
        raise RuntimeError("injected ref failure")

    refs.create = boom_update
    returned = orch._upsert_lead(connection, _lead("atomic-upd", email="new@example.com"))
    assert outcomes["failed"] == 1 and outcomes["updated"] == 0
    assert seeded.email_from == "old@example.com"
    assert seeded.name == "Old"
    assert seeded.partner_name == "Old Co"
    assert seeded.writes == 0
    assert not refs.rows
    assert returned.id == seeded.id


def test_write_failure_is_recorded_not_silent():
    orch, connection, leads, refs = _harness()
    outcomes = _outcomes(orch)

    def boom(vals):
        raise RuntimeError("column broken")

    record = leads.create({"vanillasoft_id": "fail"})
    record.write = boom
    orch._upsert_lead(connection, _lead("fail"))
    assert outcomes["failed"] == 1
    assert len(orch.error_rows) == 1 and "column broken" in orch.error_rows[0]["message"]


def test_deleted_dto_archives_with_classification():
    orch, connection, leads, refs = _harness()
    outcomes = _outcomes(orch)
    record = orch._upsert_lead(connection, _lead("arch"))
    deleted = CanonicalLead(
        provider="vanillasoft",
        external_id="arch",
        company="Co",
        first_name="A",
        last_name="L",
        email="a@example.com",
        deleted=True,
    )
    orch._upsert_lead(connection, deleted)
    assert outcomes["updated"] == 1
    assert record.active is False
    assert record.vanillasoft_sync_archived is True


# ── admission gate: dependent writes only after an admitted lead ─────────────
#
# `_upsert_lead` returns a recordset for admitted AND rejected outcomes (pinned
# contract), so the page loop must gate custom-table synchronization on the
# classification, never on the returned record: a duplicate_rejected or failed
# contact gets zero child-table side effects.


class _Connection:
    id = 1
    contact_watermark_utc = None

    def default_contact_modified_after(self):
        return "2026-01-01T00:00:00Z"


class _PageAdapter:
    """One contact page; custom-table rows are irrelevant because the sync is spied."""

    def __init__(self, leads):
        self._leads = leads

    def iter_contacts(self, *, modified_after, limit=200):
        yield self._leads, None, False

    def iter_table_rows(self, contact_external_id):
        return iter(())


class _TableSpyOrchestrator(_Orchestrator):
    def __init__(self, env):
        super().__init__(env)
        self.table_sync_for: list[str] = []

    def _sync_tables_for_lead(self, connection, adapter, contact_external_id, lead=None):
        self.table_sync_for.append(contact_external_id)


def test_multiple_fallback_matches_get_no_dependent_table_writes():
    leads = _Model()
    orch = _TableSpyOrchestrator(_Env(leads, _Model()))
    # Two leads carry the same source id and no external ref exists: ambiguous.
    leads.create({"vanillasoft_id": "dup", "name": "First", "active": True})
    leads.create({"vanillasoft_id": "dup", "name": "Second", "active": True})

    orch._sync_contacts(_Connection(), _PageAdapter([_lead("dup"), _lead("ok")]), None)

    assert orch._contact_outcomes["duplicate_rejected"] == 1
    assert orch._contact_outcomes["created"] == 1
    assert orch.table_sync_for == ["ok"], "table sync must run for the admitted contact only, never the rejected one"


def test_a_failed_lead_write_gets_no_dependent_table_writes():
    leads = _Model()
    orch = _TableSpyOrchestrator(_Env(leads, _Model()))
    record = leads.create({"vanillasoft_id": "boom"})

    def boom(vals):
        raise RuntimeError("column broken")

    record.write = boom
    orch._sync_contacts(_Connection(), _PageAdapter([_lead("boom")]), None)

    assert orch._contact_outcomes["failed"] == 1
    assert orch.table_sync_for == []


def test_upsert_lead_exposes_its_classification_beside_the_pinned_return():
    orch, connection, leads, refs = _harness()
    _outcomes(orch)
    orch._upsert_lead(connection, _lead("x1"))
    assert orch.last_lead_outcome == "created"

    leads.create({"vanillasoft_id": "dup2", "active": True})
    leads.create({"vanillasoft_id": "dup2", "active": True})
    result = orch._upsert_lead(connection, _lead("dup2"))
    assert result.id in leads.rows, "the pinned return contract still yields a recordset on rejection"
    assert orch.last_lead_outcome == "duplicate_rejected"


# ── standalone lead field fidelity: the REAL `_lead_vals_from_dto` ──────────
#
# Only the Odoo module seams are replaced: the stage / lead-source constant
# modules (installed into ``sys.modules`` for one test by ``monkeypatch``), the
# ORM lookups, and the unrelated material path. The lead write, the evidence
# appended to ``description`` and the replay run unmodified. All values are
# synthetic.

import types  # noqa: E402

import pytest  # noqa: E402

from plasticos_crm_sync.adapters.vanillasoft.adapter import contact_to_canonical  # noqa: E402
from plasticos_crm_sync.services.approved_identity import comment_blocks  # noqa: E402


class _Found(list):
    @property
    def id(self):
        return self[0].id if self else False

    def filtered(self, fn):
        return _Found(row for row in self if fn(row))


class _Lookup:
    """``search`` over plain rows; ``=ilike`` is exact and case-insensitive."""

    def __init__(self, rows):
        self.rows = rows

    def search(self, domain, limit=None):
        def hit(row):
            for name, op, value in domain:
                current = getattr(row, name)
                if op == "=ilike":
                    if str(current).casefold() != str(value).casefold():
                        return False
                elif current != value:
                    return False
            return True

        found = _Found(row for row in self.rows if hit(row))
        return _Found(found[:1]) if limit == 1 else found


class _User(types.SimpleNamespace):
    def has_group(self, xmlid):
        return True


class _SourceResolver:
    """Contract of ``plasticos.lead.source.utils.normalize_raw_source``: mapped name, else ``Other``."""

    def __init__(self, mapping, sources):
        self.mapping = mapping
        self.sources = sources

    def normalize_raw_source(self, raw):
        if not raw:
            return False
        return self.sources.search([("name", "=", self.mapping.get(raw.strip(), "Other"))], limit=1)


_SOURCE_MAP = {"Google": "Google"}
_US = types.SimpleNamespace(id=233, code="US", name="United States")
_COUNTRIES = [_US, types.SimpleNamespace(id=38, code="CA", name="Canada")]
_STATES = [
    types.SimpleNamespace(id=10, code="PA", name="Pennsylvania", country_id=233),
    types.SimpleNamespace(id=11, code="NY", name="New York", country_id=233),
]
_USERS = [
    _User(id=7, login="sa@scrapmanagement.com", active=True, share=False),
    _User(id=8, login="sales2@scrapmanagement.com", active=True, share=False),
]


class _LeadEnv(_Env):
    def __init__(self, lead_model, ref_model):
        super().__init__(lead_model, ref_model)
        sources = _Lookup([types.SimpleNamespace(id=1, name="Google"), types.SimpleNamespace(id=2, name="Other")])
        self["plasticos.lead.source.utils"] = _SourceResolver(_SOURCE_MAP, sources)
        self["res.country"] = _Lookup(_COUNTRIES)
        self["res.country.state"] = _Lookup(_STATES)
        self["res.users"] = _Lookup(_USERS)

    def ref(self, xmlid, raise_if_not_found=True):
        return types.SimpleNamespace(id=99) if xmlid == "plasticos_crm_bridge.stage_new" else None


class _RealValsOrchestrator(SyncOrchestrator):
    def __init__(self, env):
        super().__init__(env)
        self.error_rows = []

    def _apply_contact_materials(self, lead, *field_maps):
        """Material normalization is outside this contract and unchanged."""


@pytest.fixture
def lead_harness(monkeypatch):
    stage_mod = types.ModuleType("odoo.addons.plasticos_crm_bridge.models.crm_mapping")
    stage_mod.STAGE_MAPPING = {}
    source_mod = types.ModuleType("odoo.addons.plasticos_facility_profile.models.lead_source")
    source_mod.LEAD_SOURCE_MAPPING = _SOURCE_MAP
    monkeypatch.setitem(sys.modules, stage_mod.__name__, stage_mod)
    monkeypatch.setitem(sys.modules, source_mod.__name__, source_mod)
    leads, refs = _Model(), _Model()
    orch = _RealValsOrchestrator(_LeadEnv(leads, refs))
    return orch, type("C", (), {"id": 1})(), leads, refs


_FULL_PHONES = [
    {"name": "Direct", "number": "(215) 555-0101", "disabled": "false"},
    {"name": "Mobile 1", "number": "215-555-0102"},
    {"name": "Mobile 2", "number": "215.555.0103"},
    {"name": "Business", "number": "215-555-0104"},
    {"name": "Office", "number": "215-555-0105"},
    {"name": "Home", "number": "215-555-0106"},
    {"name": "Fax", "number": "215-555-0107"},
    {"name": "Other", "number": "215-555-0108", "disabled": True},
]


def _contact(**overrides):
    raw = {
        "contact_id": "vs-9001",
        "company": "Synthetic Plastics",
        "first_name": " Ada ",
        "last_name": "Byron",
        "email": "ada@example.test",
        "address": "1 Test Way",
        "address_2": "Unit 2",
        "city": "Testville",
        "state": "Pennsylvania",
        "zip": "19000",
        "country": "USA",
        "custom_fields": [
            {"name": "Lead Source", "value": "Google"},
            {"name": "Contact Owner", "value": "sa@scrapmanagement.com"},
            {"name": "Notes", "value": "called twice; wants film"},
            {"name": "Buyer/Supplier", "value": "Supplier"},
            {"name": "Company Type", "value": "Recycler"},
            {"name": "Location Type", "value": "Facility"},
        ],
        "phone_numbers": _FULL_PHONES,
    }
    raw.update(overrides)
    return contact_to_canonical(raw)


def _paragraphs(lead):
    return comment_blocks(lead.description)


def test_standalone_lead_fields_land_on_native_fields(lead_harness):
    orch, connection, _leads, _refs = lead_harness
    lead = orch._upsert_lead(connection, _contact())
    assert orch.last_lead_outcome == "created"
    assert lead.name == "Synthetic Plastics — Ada Byron"
    assert lead.partner_name == "Synthetic Plastics"
    assert lead.contact_name == "Ada Byron"
    assert lead.email_from == "ada@example.test"
    assert (lead.street, lead.street2, lead.city, lead.zip) == ("1 Test Way", "Unit 2", "Testville", "19000")
    assert lead.country_id == 233
    assert lead.state_id == 10, "an exact state name resolves within the resolved country"
    assert lead.user_id == 7, "Tiffany's source owner lands on sa@, never tw@"
    assert lead.source_id == 1
    assert lead.phone == "(215) 555-0101"
    assert lead.mobile == "215-555-0102"


def test_standalone_lead_keeps_every_other_number_and_note_in_the_description(lead_harness):
    orch, connection, _leads, _refs = lead_harness
    lead = orch._upsert_lead(connection, _contact())
    assert _paragraphs(lead) == (
        "VanillaSoft ContactID vs-9001 Notes: called twice; wants film",
        "VanillaSoft Buyer/Supplier: Supplier",
        "VanillaSoft Company Type: Recycler",
        "VanillaSoft Location Type: Facility",
        "VanillaSoft phone (Mobile 2): 215.555.0103",
        "VanillaSoft phone (Business): 215-555-0104",
        "VanillaSoft phone (Office): 215-555-0105",
        "VanillaSoft phone (Home): 215-555-0106",
        "VanillaSoft phone (Fax): 215-555-0107",
    )
    assert "215-555-0108" not in lead.description, "a disabled number is omitted"


def test_standalone_lead_replay_writes_nothing_and_repeats_no_note(lead_harness):
    orch, connection, _leads, _refs = lead_harness
    orch.outcomes = _new_counts()
    lead = orch._upsert_lead(connection, _contact())
    first = lead.description
    again = orch._upsert_lead(connection, _contact())
    assert again.id == lead.id
    assert orch.last_lead_outcome == "unchanged"
    assert lead.writes == 0 and lead.description == first


def test_standalone_lead_appends_new_notes_after_existing_ones(lead_harness):
    orch, connection, leads, _refs = lead_harness
    lead = orch._upsert_lead(connection, _contact())
    lead.description = "<p>written by a salesperson</p>" + lead.description
    custom = [{"name": "Notes", "value": "second note"}]
    orch._upsert_lead(connection, _contact(custom_fields=custom))
    paragraphs = _paragraphs(lead)
    assert paragraphs[0] == "written by a salesperson"
    assert "VanillaSoft ContactID vs-9001 Notes: called twice; wants film" in paragraphs
    assert paragraphs[-1] == "VanillaSoft ContactID vs-9001 Notes: second note"
    assert len(leads.rows) == 1


def test_mobile_two_fills_the_lead_mobile_when_no_primary_mobile_exists(lead_harness):
    orch, connection, _leads, _refs = lead_harness
    phones = [{"name": "Mobile 2", "number": "267-555-0110"}]
    lead = orch._upsert_lead(connection, _contact(phone_numbers=phones, custom_fields=[]))
    assert lead.mobile == "267-555-0110"
    assert not lead.description


def test_a_non_us_mobile_is_kept_and_explained_not_a_failed_contact(lead_harness):
    orch, connection, _leads, _refs = lead_harness
    phones = [{"name": "Mobile 1", "number": "+44 7700 900123"}]
    lead = orch._upsert_lead(connection, _contact(phone_numbers=phones, custom_fields=[]))
    assert orch.last_lead_outcome == "created"
    assert lead.mobile is False, "crm.lead.mobile accepts a 10-digit US number only"
    assert _paragraphs(lead) == ("VanillaSoft phone (Mobile 1): +44 7700 900123",)
    assert any("not a 10-digit US number" in row["message"] for row in orch.error_rows)


def test_unknown_source_falls_back_to_other_and_keeps_the_source_text(lead_harness):
    orch, connection, _leads, _refs = lead_harness
    custom = [{"name": "Lead Source", "value": "Trade Show 2019"}]
    lead = orch._upsert_lead(connection, _contact(custom_fields=custom, phone_numbers=[]))
    assert lead.source_id == 2
    assert _paragraphs(lead) == ("VanillaSoft Lead Source: Trade Show 2019",)
    blank = orch._upsert_lead(connection, _contact(contact_id="vs-9002", custom_fields=[], phone_numbers=[]))
    assert blank.source_id is False and not blank.description


def test_unresolved_state_and_country_are_reported_never_guessed(lead_harness):
    orch, connection, _leads, _refs = lead_harness
    lead = orch._upsert_lead(connection, _contact(state="Atlantis", custom_fields=[], phone_numbers=[]), adapter=None)
    assert lead.country_id == 233 and lead.state_id is False
    assert _paragraphs(lead) == ("VanillaSoft State (unresolved): Atlantis",)
    nowhere = orch._upsert_lead(
        connection,
        _contact(contact_id="vs-9003", country="Narnia", state="PA", custom_fields=[], phone_numbers=[]),
    )
    assert nowhere.country_id is False
    assert nowhere.state_id is False, "no country is inferred from a state value"
    assert _paragraphs(nowhere) == (
        "VanillaSoft Country (unresolved): Narnia",
        "VanillaSoft State (unresolved): PA",
    )
    messages = [row["message"] for row in orch.error_rows]
    assert sum("state did not resolve" in m for m in messages) == 2
    assert sum("country did not resolve" in m for m in messages) == 1


def _new_counts():
    return {
        "seen": 0,
        "table_rows": 0,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "duplicate_rejected": 0,
        "failed": 0,
    }


def test_a_valid_second_mobile_fills_the_lead_when_the_first_is_international(lead_harness):
    orch, connection, _leads, _refs = lead_harness
    phones = [
        {"name": "Mobile 1", "number": "+44 7700 900123"},
        {"name": "Mobile 2", "number": "267-555-0110"},
    ]
    lead = orch._upsert_lead(connection, _contact(phone_numbers=phones, custom_fields=[]))
    assert lead.mobile == "267-555-0110"
    assert _paragraphs(lead) == ("VanillaSoft phone (Mobile 1): +44 7700 900123",)
    assert any("primary mobile is not a 10-digit US number" in row["message"] for row in orch.error_rows)
    again = orch._upsert_lead(connection, _contact(phone_numbers=phones, custom_fields=[]))
    assert again.id == lead.id and lead.writes == 0


def test_a_same_number_fax_stays_visible_beside_the_lead_phone(lead_harness):
    orch, connection, _leads, _refs = lead_harness
    phones = [
        {"name": "Direct", "number": "215-555-0101"},
        {"name": "Fax", "number": "(215) 555-0101"},
        {"name": "Business", "number": "215-555-0101 ext. 7"},
    ]
    lead = orch._upsert_lead(connection, _contact(phone_numbers=phones, custom_fields=[]))
    assert lead.phone == "215-555-0101"
    assert _paragraphs(lead) == (
        "VanillaSoft phone (Fax): (215) 555-0101",
        "VanillaSoft phone (Business): 215-555-0101 ext. 7",
    )


def test_excluded_columns_stay_out_of_the_lead_while_notes_and_context_remain(lead_harness):
    orch, connection, _leads, _refs = lead_harness
    custom = [
        {"name": "Notes", "value": "operator wrote that the melt looked high"},
        {"name": "Buyer/Supplier", "value": "Supplier"},
        {"name": "Load Ready", "value": "EXCL-LOAD-READY"},
        {"name": "FOB/FAS (MRP)", "value": "EXCL-FOB-MRP"},
        {"name": "Equipment", "value": "EXCL-EQUIPMENT"},
    ]
    lead = orch._upsert_lead(connection, _contact(custom_fields=custom, phone_numbers=[]))
    text = lead.description or ""
    assert "operator wrote that the melt looked high" in text
    assert "VanillaSoft Buyer/Supplier: Supplier" in text
    assert "EXCL-LOAD-READY" not in text
    assert "EXCL-FOB-MRP" not in text
    assert "EXCL-EQUIPMENT" not in text
    again = orch._upsert_lead(connection, _contact(custom_fields=custom, phone_numbers=[]))
    assert again.id == lead.id
    assert (again.description or "").count("operator wrote that the melt looked high") == 1


def test_call_and_load_context_is_kept_as_labelled_notes_only_when_present(lead_harness):
    orch, connection, _leads, _refs = lead_harness
    custom = [
        {"name": "Last Result Code", "value": "LM"},
        {"name": "Last Call Date", "value": "2024-03-05 14:10"},
        {"name": "Load Ready", "value": "Yes - 2 loads"},
    ]
    lead = orch._upsert_lead(connection, _contact(custom_fields=custom, phone_numbers=[]))
    assert _paragraphs(lead) == (
        "VanillaSoft ContactID vs-9001 Last Result Code: LM",
        "VanillaSoft ContactID vs-9001 Last Call Date: 2024-03-05 14:10",
    )
    assert "Yes - 2 loads" not in (lead.description or "")
    assert "plasticos.crm.call.event" not in orch.env, "a note, never a synthesized call"
    blank = [{"name": "Last Result Code", "value": "  "}]
    other = orch._upsert_lead(connection, _contact(contact_id="vs-9010", custom_fields=blank, phone_numbers=[]))
    assert not other.description


def test_human_paragraph_equal_to_the_note_is_kept_and_still_labelled(lead_harness):
    orch, connection, _leads, _refs = lead_harness
    dto = _contact(
        custom_fields=[{"name": "Notes", "value": "called twice; wants film"}],
        phone_numbers=[],
    )
    lead = orch._upsert_lead(connection, dto)
    lead.description = "<p>called twice; wants film</p>"
    again = orch._upsert_lead(connection, dto)
    assert _paragraphs(again) == (
        "called twice; wants film",
        "VanillaSoft ContactID vs-9001 Notes: called twice; wants film",
    )
    stored = again.description
    third = orch._upsert_lead(connection, dto)
    assert third.id == lead.id and third.description == stored


def test_historic_unlabelled_note_is_not_copied_with_a_contact_id(lead_harness):
    orch, connection, _leads, _refs = lead_harness
    dto = _contact()
    lead = orch._upsert_lead(connection, dto)
    lead.description = (lead.description or "").replace(
        "VanillaSoft ContactID vs-9001 Notes: called twice; wants film",
        "VanillaSoft Notes: called twice; wants film",
    )
    before = _paragraphs(lead)
    again = orch._upsert_lead(connection, dto)
    assert again.id == lead.id
    assert _paragraphs(again) == before
    assert "VanillaSoft ContactID vs-9001 Notes:" not in (again.description or "")


def test_website_and_title_are_labelled_source_text_and_never_a_native_lead_field(lead_harness):
    orch, connection, leads, _refs = lead_harness
    leads._fields = {"website": object()}
    lead = orch._upsert_lead(
        connection,
        _contact(Website="https://example.test", title="Buyer", phone_numbers=[], custom_fields=[]),
    )
    assert not getattr(lead, "website", False)
    assert "VanillaSoft ContactID vs-9001 Website: https://example.test" in (lead.description or "")
    assert "VanillaSoft ContactID vs-9001 Title: Buyer" in (lead.description or "")


def test_website_and_title_are_recorded_once_across_replays(lead_harness):
    orch, connection, _leads, _refs = lead_harness
    contact = _contact(website="https://example.test", Title="Buyer", phone_numbers=[], custom_fields=[])
    orch._upsert_lead(connection, contact)
    again = orch._upsert_lead(connection, contact)
    assert (again.description or "").count("Website: https://example.test") == 1
    assert (again.description or "").count("Title: Buyer") == 1


def test_contact_section_notes_are_labelled_and_pps_notes_stay_off_the_contact(lead_harness):
    orch, connection, _leads, _refs = lead_harness
    custom = [
        {"name": "Notes (MRP)", "value": "mrp note"},
        {"name": "Notes (LDPE)", "value": "ldpe note"},
        {"name": "Notes (HDPE)", "value": "hdpe note"},
        {"name": "Notes (PP)", "value": "pp note"},
        {"name": "Notes (PPS)", "value": "PPS-PROFILE-ONLY"},
    ]
    dto = _contact(custom_fields=custom, phone_numbers=[])
    lead = orch._upsert_lead(connection, dto)
    assert _paragraphs(lead) == (
        "VanillaSoft ContactID vs-9001 Notes (MRP): mrp note",
        "VanillaSoft ContactID vs-9001 Notes (LDPE): ldpe note",
        "VanillaSoft ContactID vs-9001 Notes (HDPE): hdpe note",
        "VanillaSoft ContactID vs-9001 Notes (PP): pp note",
    )
    assert "PPS-PROFILE-ONLY" not in (lead.description or "")
    again = orch._upsert_lead(connection, dto)
    assert again.id == lead.id and _paragraphs(again) == _paragraphs(lead)
