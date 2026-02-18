# plasticos_dev_tools — Development-only utilities
# installable: False — NOT for production deployment
#
# This module contains:
#   tools/       — Read-only audit, integrity checks, seed validators
#   migrations/  — Version-scoped migration scripts
#   tests/       — Integration test scripts (Odoo shell)
#   forbidden/   — Archived scripts that violate production safety rules
#                  (state mutation, scoring, AI matching, raw SQL)
#
# HARD RULES:
#   - No runtime production mutation
#   - No state rewriting
#   - No posted invoice mutation
#   - No margin recalculation override
#   - No raw SQL without ORM validation
