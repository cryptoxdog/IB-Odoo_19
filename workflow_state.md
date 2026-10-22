# Workflow State — PlasticOS (IB-Odoo_19)

Hand-edited operational state, as of 2026-10-21. No script writes this file.

This page names the open campaigns. Code findings stay in `docs/campaigns/odoo_tech_debt/00_README.md`, which remains the debt tracker. That register lands with PR #270. `memory-bank/` is retired. Session resume is [l9-graphiti-memory](https://github.com/Quantum-L9/l9-graphiti-memory).

## Now

ERP historical import is `make import-erp`. The contract is [ADR-021](docs/adr/ADR-021-erp-sql-crm-api-import.md) and `plasticos_partner_import` (`erp/mapping.py`, `erp/mapping_status.py`, `erp/reader.py`).

Two import campaigns are open. Each campaign's own contract is the task. Both packs land with PR #269.

| Campaign | Pack | Scope |
|---|---|---|
| Daytime contacts, then crosswalk | `docs/campaigns/PlasticOS_ERP_Contacts_Then_VanillaSoft_Crosswalk_Daytime_2026-10-21/README.md` | Active ERP contacts, then the 763 crosswalk IDs. Commercial documents stay out. |
| Full ERP, then full VanillaSoft | `docs/campaigns/PlasticOS_ERP_Then_Full_VanillaSoft_Cursor_Delegation_v2_2026-10-21/README.md` | Partners, commercial documents, then all 4,876 VanillaSoft IDs. Delegation and inputs only. No Docker import has been executed. |

Held apart from those packs: [Mack PR #197](docs/campaigns/Mack_PR197_Source_Bound_Execution_v1/README.md). That pull request stays unmerged.
