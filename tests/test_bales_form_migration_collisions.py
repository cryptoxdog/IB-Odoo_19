"""Bales retirement never duplicates a profile identity and never aborts the upgrade.

``plasticos_material_profile.bales_retirement`` moves a Bales-form profile whose
form-less key is free, merges a duplicate into the existing form-less profile
(fill empty fields, repoint references, delete the duplicate), and logs every
pair it cannot resolve. The planner and the orchestrator are pure; the Odoo
adapter (``OdooOps``) runs only inside Odoo and is not exercised here.
"""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "plasticos_material_profile" / "bales_retirement.py"
BALES = 88  # packaging Bales id
GAYLORDS = 89


def _load():
    spec = importlib.util.spec_from_file_location("bales_retirement_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BR = _load()


def _row(row_id, partner=None, polymer=100, grade=None, packaging=None, facility=None, **extra):
    return {
        "id": row_id,
        "partner_id": partner,
        "facility_profile_id": facility,
        "polymer_id": polymer,
        "material_grade_id": grade,
        "packaging_type_id": packaging,
        **extra,
    }


# ── plan ────────────────────────────────────────────────────────────────


def test_plan_moves_bales_rows_with_a_free_key():
    bales = [_row(1, partner=10), _row(2, partner=10, polymer=101), _row(3, partner=11, grade=7)]
    formless = [_row(9, partner=10, grade=7)]  # same owner and polymer, other grade
    assert BR.plan(bales, formless, BALES) == [("move", 1), ("move", 2), ("move", 3)]


def test_plan_merges_into_the_existing_formless_row():
    assert BR.plan([_row(1, partner=10)], [_row(9, partner=10)], BALES) == [("merge", 1, 9)]


def test_plan_intra_batch_moves_the_lowest_id_and_merges_the_rest():
    bales = [_row(4, partner=10), _row(2, partner=10), _row(3, partner=12)]
    assert BR.plan(bales, [], BALES) == [("move", 2), ("merge", 4, 2), ("move", 3)]


def test_plan_packaging_conflict_is_unresolved():
    actions = BR.plan([_row(1, partner=10)], [_row(9, partner=10, packaging=GAYLORDS)], BALES)
    assert [action[:3] for action in actions] == [("unresolved", 1, 9)]


def test_plan_same_packaging_or_empty_survivor_packaging_merges():
    assert BR.plan([_row(1, partner=10)], [_row(9, partner=10, packaging=BALES)], BALES) == [("merge", 1, 9)]
    assert BR.plan([_row(1, partner=10, packaging=GAYLORDS)], [_row(9, partner=10)], BALES) == [("merge", 1, 9)]


def test_plan_owners_grades_and_facility_profiles_are_part_of_the_key():
    bales = [_row(1, partner=10), _row(2, partner=11), _row(3, facility=50), _row(4, partner=10, grade=5)]
    formless = [_row(9, partner=12), _row(8, facility=51), _row(7, partner=10, grade=6)]
    assert BR.plan(bales, formless, BALES) == [("move", 1), ("move", 2), ("move", 3), ("move", 4)]


def test_plan_partner_owner_wins_over_facility_profile():
    bales = [_row(1, partner=10, facility=50), _row(2, facility=50)]
    assert BR.plan(bales, [_row(9, facility=50)], BALES) == [("move", 1), ("merge", 2, 9)]


def test_plan_ownerless_rows_always_move():
    assert BR.plan([_row(1), _row(2)], [_row(9)], BALES) == [("move", 1), ("move", 2)]


def test_fill_values_fills_only_empty_survivor_fields():
    names = ["notes", "color_id", "packaging_type_id", "origin"]
    survivor = {"notes": "kept", "color_id": False, "packaging_type_id": None, "origin": ""}
    bales = {"notes": "lost", "color_id": 4, "packaging_type_id": BALES, "origin": False}
    assert BR.fill_values(names, survivor, bales) == {"color_id": 4, "packaging_type_id": BALES}


# ── retire over in-memory operations ────────────────────────────────────


class ConstraintError(Exception):
    pass


class FakeOps:
    """Profiles plus a reference table ``(model, field) -> {record_id: profile_id}``."""

    FORM = 77

    def __init__(self, profiles, references=None, unique_reference_fields=()):
        self.profiles = {row["id"]: dict(row) for row in profiles}
        self.references = references or {}
        self.unique = set(unique_reference_fields)
        self.rollbacks = 0

    @contextlib.contextmanager
    def savepoint(self):
        snapshot = copy.deepcopy((self.profiles, self.references))
        try:
            yield
        except Exception:
            self.profiles, self.references = snapshot
            self.rollbacks += 1
            raise

    def after_rollback(self):
        pass

    def rows(self):
        bales = [dict(r) for r in self.profiles.values() if r.get("form_id") == self.FORM]
        formless = [dict(r) for r in self.profiles.values() if not r.get("form_id")]
        return bales, formless

    def move(self, profile_id, packaging_id):
        row = self.profiles[profile_id]
        row["form_id"] = None
        row["packaging_type_id"] = row["packaging_type_id"] or packaging_id

    def merge(self, bales_id, survivor_id, packaging_id):
        bales, survivor = self.profiles[bales_id], self.profiles[survivor_id]
        bales_vals = dict(bales, packaging_type_id=bales["packaging_type_id"] or packaging_id)
        filled = BR.fill_values(["notes", "color_id", "packaging_type_id"], survivor, bales_vals)
        survivor.update(filled)
        repointed = 0
        for key, links in self.references.items():
            for record_id, profile_id in list(links.items()):
                if profile_id != bales_id:
                    continue
                if key in self.unique and survivor_id in links.values():
                    raise ConstraintError(f"{key} already links profile {survivor_id}")
                links[record_id] = survivor_id
                repointed += 1
        del self.profiles[bales_id]
        return filled, repointed


def test_retire_no_collision_moves(caplog):
    ops = FakeOps([_row(1, partner=10, form_id=77), _row(2, partner=11, form_id=77, packaging=GAYLORDS)])
    with caplog.at_level(logging.INFO):
        counts = BR.retire(ops, BALES)
    assert counts == BR.Counts(moved=2, merged=0, unresolved=0)
    assert ops.profiles[1]["form_id"] is None and ops.profiles[1]["packaging_type_id"] == BALES
    assert ops.profiles[2]["packaging_type_id"] == GAYLORDS
    assert "2 moved, 0 merged, 0 unresolved" in caplog.text


def test_retire_merge_fills_empty_fields_and_repoints(caplog):
    ops = FakeOps(
        [
            _row(1, partner=10, form_id=77, notes="bales note", color_id=4),
            _row(9, partner=10, notes="survivor note", color_id=None),
        ],
        references={("plasticos.transaction", "supplier_profile_id"): {501: 1, 502: 9}},
    )
    with caplog.at_level(logging.INFO):
        counts = BR.retire(ops, BALES)
    assert counts == BR.Counts(moved=0, merged=1, unresolved=0)
    assert 1 not in ops.profiles
    survivor = ops.profiles[9]
    assert survivor["notes"] == "survivor note"  # set value never overwritten
    assert survivor["color_id"] == 4
    assert survivor["packaging_type_id"] == BALES
    assert ops.references[("plasticos.transaction", "supplier_profile_id")] == {501: 9, 502: 9}
    assert "took color_id=4 from profile 1" in caplog.text
    assert "merged material profile 1 into 9 (1 references repointed) and deleted 1" in caplog.text


def test_retire_packaging_conflict_leaves_both_rows(caplog):
    ops = FakeOps([_row(1, partner=10, form_id=77), _row(9, partner=10, packaging=GAYLORDS)])
    before = copy.deepcopy(ops.profiles)
    with caplog.at_level(logging.WARNING):
        counts = BR.retire(ops, BALES)
    assert counts == BR.Counts(moved=0, merged=0, unresolved=1)
    assert ops.profiles == before
    assert "left material profile 1 on the Bales form; it duplicates profile 9" in caplog.text


def test_retire_repoint_constraint_failure_rolls_the_pair_back(caplog):
    key = ("plasticos.match.result", "profile_id")
    ops = FakeOps(
        [_row(1, partner=10, form_id=77, color_id=4), _row(9, partner=10), _row(3, partner=11, form_id=77)],
        references={key: {701: 1, 702: 9}},
        unique_reference_fields=[key],
    )
    before = copy.deepcopy(ops.profiles)
    with caplog.at_level(logging.WARNING):
        counts = BR.retire(ops, BALES)
    assert counts == BR.Counts(moved=1, merged=0, unresolved=1)
    assert ops.rollbacks == 1
    assert ops.profiles[1] == before[1] and ops.profiles[9] == before[9]  # fill rolled back too
    assert ops.references[key] == {701: 1, 702: 9}
    assert ops.profiles[3]["form_id"] is None  # the upgrade carried on
    assert "rolled back the merge of material profile 1 into 9" in caplog.text


def test_retire_intra_batch_collision_merges_into_the_lowest_id():
    ops = FakeOps([_row(5, partner=10, form_id=77, notes="five"), _row(2, partner=10, form_id=77)])
    counts = BR.retire(ops, BALES)
    assert counts == BR.Counts(moved=1, merged=1, unresolved=0)
    assert list(ops.profiles) == [2]
    assert ops.profiles[2]["form_id"] is None
    assert ops.profiles[2]["packaging_type_id"] == BALES
    assert ops.profiles[2]["notes"] == "five"


def test_retire_is_idempotent():
    ops = FakeOps([_row(1, partner=10, form_id=77), _row(9, partner=10), _row(2, partner=11, form_id=77)])
    BR.retire(ops, BALES)
    after = copy.deepcopy(ops.profiles)
    assert BR.retire(ops, BALES) == BR.Counts(moved=0, merged=0, unresolved=0)
    assert ops.profiles == after


def test_migrations_call_the_shared_retirement():
    for version in ("19.0.5.11.14", "19.0.5.13.5"):
        text = (ROOT / "plasticos_material_profile" / "migrations" / version / "post-migrate.py").read_text()
        assert "bales_retirement.retire_bales_form(" in text, version
