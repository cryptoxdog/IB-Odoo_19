# Integration tests package. Soft-import Odoo-backed modules so pure-Python
# harnesses (CI Tier 3 / make test) can collect non-Odoo tests in this tree
# (e.g. Gate live e2e) without requiring an Odoo runtime.
#
# Discovery is by filesystem scan rather than a hardcoded list: the previous
# _MODULES list still named test_graph_hooks_trigger (deleted — it targeted the
# M7-retired plasticos_buyer_match_engine) and omitted test_gate_external_authority_e2e.

from __future__ import annotations

import importlib
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _try_import(name: str) -> None:
    try:
        importlib.import_module(f".{name}", __name__)
    except (ImportError, ModuleNotFoundError, NameError, AttributeError):
        return


for _mod in sorted(n[:-3] for n in os.listdir(_HERE) if n.startswith("test_") and n.endswith(".py")):
    _try_import(_mod)
