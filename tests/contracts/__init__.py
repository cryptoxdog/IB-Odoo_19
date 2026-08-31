# Contract tests package. Imports are optional so pure-Python parity tests can
# collect without an Odoo runtime (CI / local harness).
#
# Discovery is by filesystem scan rather than a hardcoded list: the previous
# _MODULES list omitted every pure-Python contract module added since it was
# written (test_no_local_intelligence, test_external_intelligence_authority,
# test_external_intelligence_contract_parity, test_field_family_cutover_contract,
# test_odoo_dual_write_contract).

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
