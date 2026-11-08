"""`SyncOrchestrator._history_links` — which record owns one call or custom-table row.

A VanillaSoft contact bound to an ERP person keeps its history on that
`res.partner`; a contact that is still only a lead keeps it on the lead. A
person ref whose `res_id` no longer names a partner is unbound: `res_id` is a
plain integer and `partner_id` is a foreign key, so writing it would fail the
row. These tests drive the real method against a two-model fake env.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_crm_sync.services.orchestrator import SyncOrchestrator  # noqa: E402


class _Record:
    def __init__(self, rec_id: int, present: bool = True):
        self.id = rec_id
        self._present = present

    def __bool__(self):
        return bool(self.id)

    def exists(self):
        return self if self._present else _Record(0)


class _Ref:
    def __init__(self, res_id):
        self.id = 1
        self.res_id = res_id

    def __bool__(self):
        return True


class _Partners:
    def __init__(self, ids: set[int]):
        self._ids = ids

    def browse(self, rec_id):
        return _Record(rec_id, present=rec_id in self._ids)


def _orchestrator(partner_ids: set[int]) -> SyncOrchestrator:
    return SyncOrchestrator({"res.partner": _Partners(partner_ids)})


LEAD = _Record(7)
NO_LEAD = _Record(0)
NO_REF = _Record(0)


def test_lead_only_history_stays_on_the_lead():
    assert _orchestrator(set())._history_links(NO_REF, LEAD) == (7, False)


def test_bound_person_owns_the_history_and_clears_the_lead():
    assert _orchestrator({42})._history_links(_Ref(42), LEAD) == (False, 42)


def test_stale_person_ref_falls_back_to_the_lead():
    assert _orchestrator(set())._history_links(_Ref(42), LEAD) == (7, False)


def test_stale_person_ref_without_a_lead_links_nothing():
    assert _orchestrator(set())._history_links(_Ref(42), NO_LEAD) == (False, False)


def test_person_ref_without_res_id_is_unbound():
    assert _orchestrator({42})._history_links(_Ref(False), LEAD) == (7, False)
