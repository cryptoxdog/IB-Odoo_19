"""The historical document import fabricates no lifecycle event (pure-Python tier).

The ORM proof is ``plasticos_transaction/tests/test_erp_worksheet_import.py``;
it needs an Odoo runtime that ``ci.yml`` does not start. This guard reads the
importer's syntax tree, so a call that would confirm a purchase order, ship,
post, or pay is caught on every push.
"""

from __future__ import annotations

import ast
from pathlib import Path

IMPORTER = Path(__file__).resolve().parent.parent / "plasticos_transaction" / "models" / "native_document_import.py"

# Methods that move a historical document past draft or create a stock or cash event.
FORBIDDEN_CALLS = {
    "button_confirm",  # purchase.order -> purchase, receipt picking
    "button_approve",
    "action_post",  # account.move draft -> posted
    "_post",
    "button_validate",  # stock.picking done
    "_action_done",
    "_action_confirm",
    "action_assign",
    "action_register_payment",
}
FORBIDDEN_MODELS = {"account.payment", "stock.picking", "stock.move", "stock.move.line", "stock.quant"}


def _tree():
    return ast.parse(IMPORTER.read_text(encoding="utf-8"))


def test_importer_calls_no_confirm_post_ship_or_pay_method():
    called = {
        node.func.attr
        for node in ast.walk(_tree())
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not called & FORBIDDEN_CALLS, f"importer calls {sorted(called & FORBIDDEN_CALLS)}"


def test_importer_opens_no_stock_or_payment_model():
    literals = {node.value for node in ast.walk(_tree()) if isinstance(node, ast.Constant)}
    assert not literals & FORBIDDEN_MODELS, f"importer names {sorted(literals & FORBIDDEN_MODELS)}"


def test_sale_confirmation_launches_no_procurement():
    """Confirming a historical sale order must not create a delivery picking (sale_stock)."""
    function = next(
        node for node in ast.walk(_tree()) if isinstance(node, ast.FunctionDef) and node.name == "_confirm_context"
    )
    keys = {
        key.value: value.value
        for node in ast.walk(function)
        if isinstance(node, ast.Dict)
        for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant) and isinstance(value, ast.Constant)
    }
    assert keys.get("skip_procurement") is True
