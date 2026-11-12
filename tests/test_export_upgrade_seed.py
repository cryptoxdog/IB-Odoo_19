"""scripts/export_upgrade_seed.py: the pure plan, guard and SQL contract (Export campaign S6, F7/F8).

The Odoo part runs inside ``odoo shell`` on an owned test clone; its observed counts
are recorded with the slice's runtime evidence, which this test never reads. These
tests need no Odoo: they pin the shapes the upgrade proof depends on.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "export_upgrade_seed.py"


def _load():
    spec = importlib.util.spec_from_file_location("export_upgrade_seed", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed = _load()


def test_import_does_not_run_the_odoo_part():
    assert not hasattr(seed, "env")


def test_default_plan_exceeds_the_linda_sweep_batch():
    plan = seed.build_plan()
    assert len(plan["lane_loads"]) > 200
    assert seed.expected_summary(plan)["dispatched_unacknowledged"] > 200


def test_default_plan_holds_every_legacy_shape():
    summary = seed.expected_summary(seed.build_plan())
    assert summary["null_company_loads"] >= 1
    assert summary["multi_load_transactions"] >= 1
    assert summary["legacy_parent_links"] == summary["transactions"]
    assert summary["accepted_documents"] >= 1
    assert summary["documents"] > summary["accepted_documents"]


def test_plan_is_deterministic():
    assert seed.build_plan() == seed.build_plan()


def test_every_null_company_load_has_one_source_through_its_parent():
    plan = seed.build_plan()
    for tx in plan["transactions"]:
        own = [load for load in tx["loads"] if load["own_sale_order"]]
        if tx["source"] == "sale_order":
            # The first load carries the sale order; the others reach it through the parent.
            assert len(own) == 1 and tx["loads"][0]["own_sale_order"]
        else:
            # A purchase-order-only parent: no load carries a sale order.
            assert tx["source"] == "purchase_order" and not own


def test_expected_summary_counts_null_company_loads_exactly():
    plan = seed.build_plan(multi_load_transactions=2, loads_per_transaction=4, po_only_transactions=3)
    summary = seed.expected_summary(plan)
    assert summary["null_company_loads"] == 2 * 3 + 3
    assert summary["loads"] == 2 * 4 + 3 + len(plan["lane_loads"])


def test_every_name_is_synthetic():
    plan = seed.build_plan()
    names = plan["partners"] + plan["lane_loads"] + plan["accepted_documents"] + plan["pending_documents"]
    names += [tx["name"] for tx in plan["transactions"]]
    names += [load["name"] for tx in plan["transactions"] for load in tx["loads"]]
    assert names and all(name.startswith(seed.NAME_PREFIX) for name in names)
    assert len(names) == len(set(names))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"lane_loads": 200},
        {"multi_load_transactions": 0},
        {"loads_per_transaction": 1},
        {"po_only_transactions": 0},
        {"accepted_documents": 0},
        {"pending_documents": -1},
        {"lane_loads": "240"},
    ],
)
def test_plan_refuses_a_shape_that_misses_a_proof_case(kwargs):
    with pytest.raises(ValueError):
        seed.build_plan(**kwargs)


@pytest.mark.parametrize("name", ["odoo_test_s6up", "odoo_test_w0123456789", "odoo_test_s6_restore"])
def test_guard_accepts_disposable_clones(name):
    assert seed.guard_database(name) == name


@pytest.mark.parametrize(
    "name",
    [
        "odoo",
        "plasticos",
        "odoo_test_tpl_ee_c9e8a81f52f23680",
        "odoo_test_bld_ee_0123456789abcdef",
        "odoo_test_prod_copy",
        "odoo_test_staging",
        "odoo_test_UPPER",
        "odoo_test_x; DROP DATABASE odoo",
        "",
        None,
    ],
)
def test_guard_refuses_everything_else(name):
    with pytest.raises(SystemExit):
        seed.guard_database(name)


def test_synthetic_checksum_is_odoo_attachment_sha1():
    content = seed.synthetic_bytes("S6-SYN-DOC-A-01")
    assert seed.synthetic_checksum("S6-SYN-DOC-A-01") == hashlib.sha1(content).hexdigest()  # noqa: S324
    assert b"S6-SYN" in content


def test_sql_statements_are_fixed_and_parameterized():
    statements = [
        seed.SQL_ADD_LEGACY_PARENT_COLUMN,
        seed.SQL_SET_LEGACY_PARENT,
        seed.SQL_LEGACY_PARENT_LINK,
        seed.SQL_LEGACY_DISPATCHED,
        seed.SQL_LEGACY_ACCEPTED_DOCUMENT,
    ]
    for sql in statements:
        assert "{" not in sql and "%(" not in sql
    assert seed.SQL_LEGACY_ACCEPTED_DOCUMENT.count("%s") == 11
    # The accepted digest and the source revision are bound to the same checksum
    # in seed(), so the 2.1.18 pre-migration's contradiction check does not refuse.
    assert re.search(r"source_revision = %s", seed.SQL_LEGACY_ACCEPTED_DOCUMENT)
    assert re.search(r"evidence_digest = %s", seed.SQL_LEGACY_ACCEPTED_DOCUMENT)


def test_seed_never_writes_outside_its_marker_and_synthetic_rows():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "DELETE" not in text and "DROP" not in text.replace("DROP DATABASE odoo", "")
    assert "sudo()" not in text or "# sudo:" in text
