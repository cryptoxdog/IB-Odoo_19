# Integration tests package. Soft-import Odoo-backed modules so pure-Python
# harnesses (CI Tier 3 / make test) can collect non-Odoo tests in this tree
# (e.g. Gate live e2e) without requiring an Odoo runtime.

from __future__ import annotations

import importlib

_MODULES = [
    "test_account_move_transaction_link",
    "test_match_result_guards",
    "test_intake_onchange_cascade",
    "test_offer_state_machine",
    "test_write_unlink_guards",
    "test_graph_hooks_trigger",
    "test_sale_order_transaction_autocreate",
    "test_polymer_product_sync",
    "test_compliance_service",
    "test_cron_idempotency",
]


def _try_import(name: str) -> None:
    try:
        importlib.import_module(f".{name}", __name__)
    except (ImportError, ModuleNotFoundError, NameError, AttributeError):
        return


for _mod in _MODULES:
    _try_import(_mod)
