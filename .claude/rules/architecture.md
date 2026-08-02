---
paths:
  - "plasticos_*/__manifest__.py"
  - "plasticos_*/models/**/*.py"
  - "config/**"
---
# PlasticOS Architecture — Path-Scoped Pointer

**Authority:** `ARCHITECTURE.md` (repo root) · `AGENTS.md` § Project Structure

## 5-Layer Model (lower → higher, never reverse deps)

| Layer | Modules |
|-------|---------|
| 1 Material | `plasticos_base`, `plasticos_security_base`, `plasticos_material_profile`, `plasticos_product` |
| 2 Capability | `plasticos_intake`, `plasticos_facility_profile`, `plasticos_buyer_match_engine`, … |
| 3 Commercial | `plasticos_offer`, `plasticos_commission`, `plasticos_automation`, … |
| 4 Compliance | `plasticos_documents`, `plasticos_documents_native` |
| 5 Transaction | `plasticos_transaction`, `plasticos_logistics`, `plasticos_claims` |

**Install order:** `config/odoo_module_order.yaml` · enforced by `tests/test_repo_dependency_integrity.py`

**Manifest:** every cross-module model ref → `depends` entry (`82-ci-module-wiring.mdc`)
