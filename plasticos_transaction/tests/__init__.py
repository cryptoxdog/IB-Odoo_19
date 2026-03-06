# plasticos_transaction/tests/__init__.py

from . import test_account_move_inherit
from . import test_audit_cron
from . import test_close_race
from . import test_commission_rule
from . import test_commission_rules
from . import test_commission_service
from . import test_compliance_failure
from . import test_concurrency
from . import test_deterministic_replay
from . import test_domain_isolation
from . import test_financial_audit
from . import test_full_replay
from . import test_intake_bridge
from . import test_integrity_enforcement

# test_legacy_migration: deferred - models plasticos.legacy.staging/migration.service not yet implemented
from . import test_load_inherit
from . import test_match_result_bridge
from . import test_migration
from . import test_migration_safety
from . import test_module_install
from . import test_multi_currency
from . import test_offer_bridge
from . import test_partner_bridge
from . import test_performance_scale
from . import test_purchase_inherit
from . import test_res_users_inherit
from . import test_rpc_abuse
from . import test_sale_inherit
from . import test_security_permissions
from . import test_sequence_concurrency
from . import test_sequence_race
from . import test_transaction
from . import test_transaction_bridge
from . import test_transaction_computes
from . import test_transaction_constraints
from . import test_transaction_crud
from . import test_transaction_import_service
from . import test_transaction_lifecycle
from . import test_transaction_line
from . import test_transaction_states
from . import test_weight_reconciliation

from . import test_constraints_transaction
from . import test_depends_plasticos_transaction
from . import test_depends_transaction_computes
from . import test_statemachine_transaction
from . import test_wizard_transaction_import
from . import test_wizard_transaction_bulk_assign
from . import test_wizard_transaction_bulk_update
