# Workflow State — PlasticOS (IB-Odoo_19)

Hand-edited operational state, as of 2026-11-08. No script writes this file.

Open items only. `memory-bank/` is retired. Session resume is [l9-graphiti-memory](https://github.com/Quantum-L9/l9-graphiti-memory).

## Import campaigns

ERP historical import is `make import-erp`. The contract is [ADR-021](docs/adr/ADR-021-erp-sql-crm-api-import.md) and `plasticos_partner_import` (`erp/mapping.py`, `erp/mapping_status.py`, `erp/reader.py`). The write target is one owned disposable clone. Odoo.sh is not that target.

The importer still refuses a database that already contains business partners, and the database check still fails when any of these modules are missing: `l10n_us`, `l10n_us_account`, `l10n_us_1099`, `l10n_us_reports`, `l10n_us_check_printing`, `l10n_us_payment_nacha`.

| Campaign | Still open |
|---|---|
| [Daytime contacts, then crosswalk](docs/campaigns/future-add-ons/PlasticOS_ERP_Contacts_Then_VanillaSoft_Crosswalk_Daytime_2026-10-21/README.md) | The 763 crosswalk IDs on a new clone of `config/test_env_fixture.conf`. Commercial documents stay out. No receipt is in `docs/reports/evidence/`. The 2026-10-21 partners-only contact shell is not that receipt. |
| [Full ERP, then full VanillaSoft](docs/campaigns/future-add-ons/PlasticOS_ERP_Then_Full_VanillaSoft_Cursor_Delegation_v2_2026-10-21/README.md) | Partners, commercial documents, then all 4,876 VanillaSoft IDs. No Docker import has been executed. |

## Odoo.sh Staging

Live Connect values are `.env.local` (`ODOO_SH_STAGING_SSH`, `ODOO_SH_STAGING_URL`). Build ids rotate. Build `36099032`, still in the snapshot table in `.cursor/rules/98-odoo-sh-staging.mdc`, must not be used. **Allow my IP** lasts one hour and is not a standing firewall entry.

A census or later read stays `BEGIN READ ONLY` … `ROLLBACK`. `make import-erp` stays off Odoo.sh until a separate authorization.
