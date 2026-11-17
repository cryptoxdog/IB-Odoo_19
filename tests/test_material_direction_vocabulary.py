"""Direction defaults, the extended key, and the ADR-134 vocabulary retirement.

Pure: the decision functions and the mapping sheet. No Odoo runtime.
"""

from __future__ import annotations

import ast
import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "plasticos_material_profile"
SHEET = PROFILE / "data" / "material_mapping.csv"
CATALOG = PROFILE / "data" / "ERP-Products.csv"
ALIASES = ("superacs", "supersacks", "super sacks", "super sacs", "supersac")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DIRECTION = _load(PROFILE / "direction.py", "_cmat_direction")
RETIREMENT = _load(PROFILE / "vocabulary_retirement.py", "_cmat_retirement")
NORMALIZER = _load(PROFILE / "models" / "material_normalizer.py", "_cmat_normalizer")


def _rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _profile(**values):
    row = {
        "id": 1,
        "partner_id": 10,
        "polymer_id": 20,
        "form_id": 30,
        "material_grade_id": 40,
        "direction": None,
    }
    row.update(values)
    return row


def test_direction_follows_ranks_when_the_site_type_is_not_one_side() -> None:
    assert (
        DIRECTION.direction_for(
            site=False,
            partner_type=None,
            source_label=None,
            company_role=None,
            supplier_rank=1,
            customer_rank=0,
        )
        == "out"
    )
    assert (
        DIRECTION.direction_for(
            site=True,
            partner_type="delivery",
            source_label=None,
            company_role=None,
            supplier_rank=0,
            customer_rank=1,
        )
        == "in"
    )
    assert (
        DIRECTION.direction_for(
            site=True,
            partner_type="delivery",
            source_label=None,
            company_role="supplier",
            supplier_rank=1,
            customer_rank=1,
        )
        is None
    )
    assert (
        DIRECTION.direction_for(
            site=False,
            partner_type="contact",
            source_label=None,
            company_role=None,
            supplier_rank=0,
            customer_rank=0,
        )
        is None
    )


def test_pickup_label_overrides_a_buyer_rank() -> None:
    assert (
        DIRECTION.direction_for(
            site=True,
            partner_type="delivery",
            source_label="HOUSTON TX - PICK UP",
            company_role="buyer",
            supplier_rank=0,
            customer_rank=1,
        )
        == "out"
    )
    assert (
        DIRECTION.direction_for(
            site=True,
            partner_type="invoice",
            source_label="PICK UP",
            company_role="supplier",
            supplier_rank=0,
            customer_rank=1,
        )
        == "in"
    )


def test_in_and_out_are_distinct_and_a_same_direction_collision_is_reported() -> None:
    outgoing = _profile(id=1, direction="out")
    incoming = _profile(id=2, direction="in")
    assert DIRECTION.collision_groups([outgoing, incoming]) == {}
    duplicate = _profile(id=3, direction="out")
    collisions = DIRECTION.collision_groups([outgoing, duplicate])
    assert list(collisions.values()) == [[1, 3]]
    assert DIRECTION.blank_direction_ids([_profile(id=4, direction=None), outgoing]) == [4]


def test_repro_becomes_pellets_only_when_the_text_says_pellets() -> None:
    rows = [_profile(id=1, form_id=7), _profile(id=2, form_id=7), _profile(id=3, form_id=8)]
    texts = {1: ("HDPE repro pellets",), 2: ("LDPE Repro",), 3: ("already pellets",)}
    pellets, review = RETIREMENT.plan_repro(rows, 7, texts)
    assert pellets == [1]
    assert review == [2]
    again, still = RETIREMENT.plan_repro([_profile(id=1, form_id=9), _profile(id=2, form_id=7)], 7, texts)
    assert again == []
    assert still == [2]


def test_loose_clears_until_the_key_is_taken_and_replay_is_a_no_op() -> None:
    loose = _profile(id=1, form_id=5, direction="out")
    taken = _profile(id=2, form_id=None, direction="out")
    other = _profile(id=3, form_id=5, polymer_id=99, direction="in")
    clear, blocked = RETIREMENT.plan_loose([loose, taken, other], 5)
    assert clear == [3]
    assert blocked == [1]
    replay_clear, replay_blocked = RETIREMENT.plan_loose(
        [_profile(id=3, form_id=None, polymer_id=99, direction="in")],
        5,
    )
    assert replay_clear == []
    assert replay_blocked == []


def test_sheet_retirement_is_idempotent_and_the_committed_sheet_emits_neither_form() -> None:
    sample = {
        "form": "REPRO",
        "source_value": "HDPE Repro Pellets",
        "match_key": "hdpe repro pellets",
        "attributes": "frac_melt",
        "packaging_type": "",
    }
    once = RETIREMENT.retire_sheet_row(dict(sample))
    twice = RETIREMENT.retire_sheet_row(dict(once))
    assert once == twice
    assert once["form"] == "PELLETS"
    assert once["attributes"] == "frac_melt repro"
    plain = RETIREMENT.retire_sheet_row(
        {"form": "REPRO", "source_value": "PP Repro", "match_key": "pp repro", "attributes": "", "packaging_type": ""}
    )
    assert plain["form"] == ""
    assert plain["attributes"] == "repro"
    loose = RETIREMENT.retire_sheet_row(
        {"form": "LOOSE", "source_value": "PP Loose", "match_key": "pp loose", "attributes": "", "packaging_type": ""}
    )
    assert loose["form"] == ""
    assert loose["packaging_type"] == "loose"
    assert RETIREMENT.retire_sheet_row(dict(loose)) == loose

    for path in (SHEET, CATALOG):
        retired = [row for row in _rows(path) if (row.get("form") or "").strip() in {"REPRO", "LOOSE"}]
        assert retired == [], path.name


def test_every_supersacs_alias_resolves_to_the_grade() -> None:
    phrases = NORMALIZER.phrase_table()
    for alias in ALIASES:
        spec = phrases[alias]
        assert spec.polymer == "PP", alias
        assert spec.material_grade == "SUPERACS", alias
        assert spec.form is None, alias


def test_normalizer_form_words_do_not_emit_retired_forms() -> None:
    words = NORMALIZER.form_words()
    assert "REPRO" not in words.values()
    assert "LOOSE" not in words.values()
    assert "repro" not in words
    assert "loose" not in words


def test_enrichment_form_maps_do_not_send_repro_to_regrind_or_loose_to_a_form() -> None:
    source = (ROOT / "plasticos_enrichment" / "models" / "enrichment_service.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {
                    "FORM_NORMALIZE",
                    "FORM_CODE_TO_MASTER",
                    "PACKAGING_NORMALIZE",
                }:
                    found[target.id] = ast.literal_eval(node.value)
    assert "repro" not in found["FORM_NORMALIZE"]
    assert "reprocessed" not in found["FORM_NORMALIZE"]
    assert "loose" not in found["FORM_NORMALIZE"]
    assert "REPRO" not in found["FORM_CODE_TO_MASTER"]
    assert "LOOSE" not in found["FORM_CODE_TO_MASTER"]
    assert found["FORM_CODE_TO_MASTER"].get("REPRO") is None
    assert found["PACKAGING_NORMALIZE"]["loose"] == "loose"
