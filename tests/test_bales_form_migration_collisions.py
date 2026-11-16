"""``plasticos_material_profile`` 19.0.5.11.14 post-migrate never duplicates a profile identity.

Clearing the Bales form must not produce a second row for the unique key
``(owner, polymer_id, form_id, material_grade_id)`` (NULLS NOT DISTINCT), where the
owner is ``partner_id`` or, for a partner-less row, ``facility_profile_id``.
A colliding Bales profile keeps its form and is reported; the upgrade never aborts.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "plasticos_material_profile/migrations/19.0.5.11.14/post-migrate.py"


def _load():
    spec = importlib.util.spec_from_file_location("material_profile_post_migrate_5_11_14", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIG = _load()


def test_no_collision_moves_every_bales_profile():
    bales = [(1, 10, None, 100, None), (2, 10, None, 101, None), (3, 11, None, 100, 7)]
    formless = [(9, 10, None, 100, 7)]  # same owner and polymer, different grade
    safe, collisions = MIG.partition_bales_profiles(bales, formless)
    assert safe == [1, 2, 3]
    assert collisions == {}


def test_collision_with_existing_formless_row_keeps_the_form():
    bales = [(1, 10, None, 100, None), (2, 10, None, 101, None)]
    formless = [(9, 10, None, 100, None)]
    safe, collisions = MIG.partition_bales_profiles(bales, formless)
    assert safe == [2]
    assert collisions == {1: [9]}


def test_grade_is_part_of_the_key_and_null_grade_matches_null_grade():
    bales = [(1, 10, None, 100, 0), (2, 10, None, 100, 5)]
    formless = [(9, 10, None, 100, None)]
    safe, collisions = MIG.partition_bales_profiles(bales, formless)
    assert safe == [2]
    assert collisions == {1: [9]}


def test_two_bales_rows_with_the_same_target_both_stay():
    bales = [(1, 10, None, 100, None), (2, 10, None, 100, None), (3, 12, None, 100, None)]
    safe, collisions = MIG.partition_bales_profiles(bales, [])
    assert safe == [3]
    assert collisions == {1: [2], 2: [1]}


def test_rows_of_different_owners_do_not_collide():
    bales = [(1, 10, None, 100, None), (2, 11, None, 100, None), (3, None, 50, 100, None)]
    formless = [(9, 12, None, 100, None), (8, None, 51, 100, None)]
    safe, collisions = MIG.partition_bales_profiles(bales, formless)
    assert safe == [1, 2, 3]
    assert collisions == {}


def test_partner_owner_takes_precedence_over_facility_profile():
    # A row with a partner falls under the partner index only, whatever its facility profile.
    bales = [(1, 10, 50, 100, None), (2, None, 50, 100, None)]
    formless = [(9, None, 50, 100, None)]
    safe, collisions = MIG.partition_bales_profiles(bales, formless)
    assert safe == [1]
    assert collisions == {2: [9]}


def test_unowned_rows_never_collide():
    bales = [(1, None, None, 100, None), (2, None, None, 100, None)]
    formless = [(9, None, None, 100, None)]
    safe, collisions = MIG.partition_bales_profiles(bales, formless)
    assert safe == [1, 2]
    assert collisions == {}


# ── migrate() over a fake cursor and environment ─────────────────────────


class FakeRecordset:
    def __init__(self, store, ids):
        self.store = store
        self.ids = list(ids)

    def filtered(self, predicate):
        return FakeRecordset(self.store, [i for i in self.ids if predicate(SimpleNamespace(**self.store.rows[i]))])

    def write(self, vals):
        self.store.writes.append((tuple(self.ids), dict(vals)))
        for row_id in self.ids:
            self.store.rows[row_id].update(vals)
        return True

    def __bool__(self):
        return bool(self.ids)

    def __len__(self):
        return len(self.ids)


class FakeModel:
    def __init__(self, store):
        self.store = store

    def with_context(self, **_kw):
        return self

    def browse(self, ids):
        return FakeRecordset(self.store, ids)


class FakeStore:
    FORM = 77
    PACKAGING = 88

    def __init__(self, rows, *, has_facility=True):
        self.rows = {row["id"]: dict(row) for row in rows}
        self.has_facility = has_facility
        self.writes = []
        self._result = []

    # cursor
    def execute(self, sql, params=None):
        if "information_schema.columns" in sql:
            self._result = [(1,)] if self.has_facility else []
            return
        assert params == (self.FORM,)
        assert "%s" in sql  # parameterized, never formatted
        assert ("facility_profile_id," in sql) == self.has_facility
        self._result = [
            (
                r["id"],
                r["partner_id"],
                r["facility_profile_id"] if self.has_facility else None,
                r["polymer_id"],
                r["material_grade_id"],
                r["form_id"],
            )
            for r in self.rows.values()
            if r["form_id"] in (self.FORM, None)
        ]

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)


def _row(row_id, partner_id, polymer_id, form_id, *, grade=None, facility=None, packaging=None):
    return {
        "id": row_id,
        "partner_id": partner_id,
        "facility_profile_id": facility,
        "polymer_id": polymer_id,
        "material_grade_id": grade,
        "form_id": form_id,
        "packaging_type_id": packaging,
    }


def _run(store, monkeypatch):
    refs = {MIG.FORM_BALE: SimpleNamespace(id=store.FORM), MIG.PACKAGING_BALES: SimpleNamespace(id=store.PACKAGING)}
    model = FakeModel(store)

    class Env(dict):
        def ref(self, xmlid, raise_if_not_found=True):
            return refs[xmlid]

    env = Env({"plasticos.material.profile": model})
    fake_odoo = SimpleNamespace(SUPERUSER_ID=1, api=SimpleNamespace(Environment=lambda cr, uid, ctx: env))
    monkeypatch.setitem(sys.modules, "odoo", fake_odoo)
    MIG.migrate(store, "19.0.5.11.13")


def test_migrate_keeps_colliding_rows_and_warns(monkeypatch, caplog):
    store = FakeStore(
        [
            _row(1, 10, 100, FakeStore.FORM),  # collides with 9
            _row(2, 10, 101, FakeStore.FORM, packaging=5),  # safe, keeps its packaging
            _row(3, 11, 100, FakeStore.FORM),  # collides with 4 (same batch)
            _row(4, 11, 100, FakeStore.FORM),
            _row(9, 10, 100, None),
        ]
    )
    with caplog.at_level(logging.WARNING):
        _run(store, monkeypatch)
    assert store.rows[2]["form_id"] is False
    for kept in (1, 3, 4):
        assert store.rows[kept]["form_id"] == FakeStore.FORM
        assert store.rows[kept]["packaging_type_id"] == FakeStore.PACKAGING
    assert store.rows[2]["packaging_type_id"] == 5
    assert store.rows[9]["form_id"] is None
    form_writes = [ids for ids, vals in store.writes if "form_id" in vals]
    assert form_writes == [(2,)]
    text = caplog.text
    assert "material profile 1" in text and "[9]" in text
    assert "material profile 3" in text and "[4]" in text
    assert "material profile 4" in text and "[3]" in text


def test_migrate_is_idempotent(monkeypatch):
    store = FakeStore([_row(1, 10, 100, FakeStore.FORM), _row(9, 10, 100, None), _row(2, 10, 101, FakeStore.FORM)])
    _run(store, monkeypatch)
    first = {k: dict(v) for k, v in store.rows.items()}
    store.writes.clear()
    _run(store, monkeypatch)
    assert store.rows == first
    assert all("form_id" not in vals for _ids, vals in store.writes)


def test_migrate_without_crm_bridge_column(monkeypatch):
    store = FakeStore([_row(1, 10, 100, FakeStore.FORM), _row(2, 10, 100, None)], has_facility=False)
    _run(store, monkeypatch)
    assert store.rows[1]["form_id"] == FakeStore.FORM
