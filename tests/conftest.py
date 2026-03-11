# conftest.py - pytest configuration for tests/
#
# This file configures pytest to skip Odoo-specific tests when running
# outside of the Odoo environment (e.g., in CI without Odoo runtime).

import sys

# Odoo-specific test modules that require the Odoo framework
# These are run via `odoo --test-enable`, not pytest
_ODOO_TEST_MODULES = [
    "test_action_methods.py",
    "test_bridge_contracts.py",
    "test_bridge_models.py",
    "test_constraint_validation.py",
    "test_constraints_material_profile.py",
    "test_constraints_onchanges.py",
    "test_cron_batch_normalize.py",
    "test_cron_plasticos_base.py",
    "test_cron_runtime.py",
    "test_depends_transaction_claims_bridge.py",
    "test_error_handling.py",
    "test_golden_flows.py",
    "test_integration_flows.py",
    "test_onchange_purchase_order_line_plasticos.py",
    "test_onchange_sale_order_line_plasticos.py",
    "test_performance.py",
    "test_security_acl.py",
    "test_state_machines.py",
]

# Skip Odoo-specific tests if odoo is not available
if "odoo" not in sys.modules:
    collect_ignore = _ODOO_TEST_MODULES
    # Also ignore subdirectories that contain Odoo-specific tests
    collect_ignore_glob = [
        "integration/*",
        "contracts/*",
    ]
