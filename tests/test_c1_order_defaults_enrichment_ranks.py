"""C1 lane C: last-used delivery address default and rank-based enrichment entity type.

Pure-python: the delivery selection lives in an Odoo-free module loaded by path,
and the enrichment helper is compiled from its AST, so no registry is needed.
The override wiring itself is checked structurally.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PY = ROOT / "plasticos_logistics/models/delivery_address_default.py"
SO_PY = ROOT / "plasticos_logistics/models/sale_order_inherit.py"
LOGISTICS_INIT = ROOT / "plasticos_logistics/models/__init__.py"
ENRICH_PY = ROOT / "plasticos_enrichment/models/enrichment_service.py"


def _load_default_module():
    spec = importlib.util.spec_from_file_location("c1_delivery_address_default", DEFAULT_PY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dad = _load_default_module()

CUSTOMER = 10
OTHER_CUSTOMER = 20
COMPANY = 1
OTHER_COMPANY = 2


def _row(customer=CUSTOMER, shipping=101, active=True, shipping_customer=None, company=None):
    return dad.HistoryRow(
        commercial_partner_id=customer,
        shipping_id=shipping,
        shipping_active=active,
        shipping_commercial_partner_id=CUSTOMER if shipping_customer is None else shipping_customer,
        shipping_company_id=company,
    )


def _pick(rows, customer=CUSTOMER, company=COMPANY):
    latest = dad.latest_row_per_customer(rows, [customer])
    return dad.last_used_delivery(customer, company, latest)


# ── Task 1: delivery address default ───────────────────────────


def test_last_used_found_is_used():
    assert _pick([_row(shipping=101), _row(shipping=102)]) == 101


def test_only_most_recent_order_counts():
    # The newest order's address is archived: fall back, do not reach for an older one.
    assert _pick([_row(shipping=101, active=False), _row(shipping=102)]) is None


def test_archived_last_used_falls_back():
    assert _pick([_row(active=False)]) is None


def test_last_used_of_another_commercial_partner_falls_back():
    assert _pick([_row(shipping_customer=OTHER_CUSTOMER)]) is None


def test_last_used_of_another_company_falls_back():
    assert _pick([_row(company=OTHER_COMPANY)], company=COMPANY) is None


def test_shared_address_without_company_is_used():
    assert _pick([_row(company=None)], company=COMPANY) == 101


def test_no_history_falls_back():
    assert _pick([]) is None


def test_history_of_other_customers_only_falls_back():
    assert _pick([_row(customer=OTHER_CUSTOMER, shipping_customer=OTHER_CUSTOMER)]) is None


def test_batch_keeps_newest_per_customer_and_stops_early():
    consumed = []

    def rows():
        for row in (
            _row(customer=CUSTOMER, shipping=101),
            _row(customer=OTHER_CUSTOMER, shipping=201, shipping_customer=OTHER_CUSTOMER),
            _row(customer=CUSTOMER, shipping=102),
        ):
            consumed.append(row.shipping_id)
            yield row

    latest = dad.latest_row_per_customer(rows(), [CUSTOMER, OTHER_CUSTOMER])
    assert latest[CUSTOMER].shipping_id == 101
    assert latest[OTHER_CUSTOMER].shipping_id == 201
    assert consumed == [101, 201]


def _compute_fn():
    tree = ast.parse(SO_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_compute_partner_shipping_id":
            return node
    raise AssertionError("_compute_partner_shipping_id override missing")


def test_override_depends_only_on_customer_so_explicit_value_is_preserved():
    # A value given at create or chosen by the user is not recomputed: the
    # override keeps the native single trigger (partner_id) and adds none.
    fn = _compute_fn()
    depends = [d for d in fn.decorator_list if isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "depends"]
    assert len(depends) == 1
    assert [a.value for a in depends[0].args] == ["partner_id"]


def test_override_calls_super_first_and_searches_once_outside_the_loop():
    fn = _compute_fn()
    first = (
        fn.body[1] if isinstance(fn.body[0], ast.Expr) and isinstance(fn.body[0].value, ast.Constant) else fn.body[0]
    )
    assert "super()._compute_partner_shipping_id" in ast.unparse(first)
    searches = [
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") in {"search", "search_fetch", "search_read"}
    ]
    assert len(searches) == 1
    for loop in (n for n in ast.walk(fn) if isinstance(n, ast.For)):
        assert not any(
            isinstance(n, ast.Call) and getattr(n.func, "attr", "") in {"search", "search_fetch", "search_read"}
            for n in ast.walk(loop)
        )
    src = ast.unparse(fn)
    assert "'state', '!=', ORDER_CANCEL" in src
    assert "date_order desc, id desc" in src


def test_helper_module_is_wired_and_odoo_free():
    assert "from . import delivery_address_default" in LOGISTICS_INIT.read_text(encoding="utf-8")
    tree = ast.parse(DEFAULT_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("odoo")
        if isinstance(node, ast.Import):
            assert not any(alias.name.startswith("odoo") for alias in node.names)


# ── Task 2: enrichment entity type from native ranks ───────────


def _entity_type_fn():
    tree = ast.parse(ENRICH_PY.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_entity_type_from_ranks")
    namespace: dict = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(ENRICH_PY), "exec"), namespace)  # noqa: S102
    return namespace["_entity_type_from_ranks"]


def _partner(customer_rank=0, supplier_rank=0):
    commercial = SimpleNamespace(customer_rank=customer_rank, supplier_rank=supplier_rank)
    return SimpleNamespace(commercial_partner_id=commercial)


@pytest.mark.parametrize(
    ("customer_rank", "supplier_rank", "expected"),
    [(1, 0, "buyer"), (0, 3, "supplier"), (2, 5, "buyer"), (0, 0, "supplier")],
)
def test_entity_type_from_ranks(customer_rank, supplier_rank, expected):
    assert _entity_type_fn()(_partner(customer_rank, supplier_rank)) == expected


def test_entity_type_without_partner_is_supplier():
    assert _entity_type_fn()(None) == "supplier"


def test_inference_reads_ranks_not_tag_names():
    src = ENRICH_PY.read_text(encoding="utf-8")
    body = src.split("def run_inference_on_profile")[1].split("\n    def ")[0]
    assert "_entity_type_from_ranks(profile.partner_id)" in body
    assert "category_id" not in body
    assert '"Buyer"' not in body
