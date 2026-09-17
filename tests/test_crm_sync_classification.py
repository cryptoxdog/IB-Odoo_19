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


class _Cr:
    def commit(self):
        pass

    def rollback(self):
        pass


class _Env(dict):
    def __init__(self, lead_model, ref_model):
        super().__init__()
        self["crm.lead"] = lead_model
        self["plasticos.crm.external.ref"] = ref_model
        self.cr = _Cr()


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
    return CanonicalLead(provider="vanillasoft", external_id=external_id, company="Co", first_name="A", last_name="L", email=email)


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
    deleted = CanonicalLead(provider="vanillasoft", external_id="arch", company="Co", first_name="A", last_name="L", email="a@example.com", deleted=True)
    orch._upsert_lead(connection, deleted)
    assert outcomes["updated"] == 1
    assert record.active is False
    assert record.vanillasoft_sync_archived is True
