# Central test pack for cross-module integration tests
#
# NOTE: Imports are wrapped in try/except to allow pure Python tests
# to run without Odoo installed (e.g., in CI without Odoo runtime).

import importlib
import sys

# List of test modules - only imported if odoo is available
_ODOO_TEST_MODULES = [
    "test_action_methods",
    "test_bridge_contracts",
    "test_bridge_models",
    "test_constraint_validation",
    "test_constraints_material_profile",
    "test_constraints_onchanges",
    "test_cron_batch_normalize",
    "test_cron_plasticos_base",
    "test_cron_runtime",
    "test_depends_transaction_claims_bridge",
    "test_error_handling",
    "test_golden_flows",
    "test_integration_flows",
    "test_onchange_purchase_order_line_plasticos",
    "test_onchange_sale_order_line_plasticos",
    "test_performance",
    "test_security_acl",
    "test_state_machines",
]

# Pure Python tests (no Odoo dependency)
_PURE_PYTHON_MODULES = [
    "test_cron_invariants",
    "test_cypher_schema_alignment",
    "test_odoo19_compat",
    "test_odoo_test_setup_validity",
    "test_phantom_enum_values",
    "test_process_enum_alignment",
    "test_repo_dependency_integrity",
]


def _try_import(module_name: str) -> bool:
    """Try to import a module, return True if successful."""
    try:
        importlib.import_module(f".{module_name}", __name__)
        return True
    except ImportError:
        return False


# Always import pure Python tests
for _mod in _PURE_PYTHON_MODULES:
    _try_import(_mod)

# Only import Odoo tests if odoo is available
if "odoo" in sys.modules or _try_import("test_action_methods"):
    for _mod in _ODOO_TEST_MODULES[1:]:  # Skip first, already tried
        _try_import(_mod)
    # Import subpackages
    _try_import("contracts")
    _try_import("integration")
