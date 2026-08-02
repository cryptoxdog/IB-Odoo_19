# Contract tests package. Imports are optional so pure-Python parity tests can
# collect without an Odoo runtime (CI / local harness).

from __future__ import annotations

import importlib

_MODULES = [
    "test_intake_contracts",
    "test_transaction_contracts",
    "test_partner_contracts",
    "test_crm_lead_contracts",
    "test_selection_contracts",
    "test_bridge_wiring_contracts",
    "test_api_signature_contracts",
    "test_computed_field_deps",
]


def _try_import(name: str) -> None:
    try:
        importlib.import_module(f".{name}", __name__)
    except (ImportError, ModuleNotFoundError, NameError, AttributeError):
        return


for _mod in _MODULES:
    _try_import(_mod)
