# Source evidence / owner matrix / acceptance partition

## Exact sources examined (read-only, current turn)

- `https://github.com/cryptoxdog/IB-Odoo_19` Staging `42556d2e5e7434be43f2ff7f89e66b1c8ee6c15a` (observed). 2026-10-30: PR #345 OPEN head `76c7d0bf0e3b449be367ebd82de74273f303ad7b`, PR #346 OPEN head `26f97308885a638c45d957ef9767b5e1dd00ed4c`.
- `https://github.com/Quantum-L9/Cursor-Governance` main `f47c256b2c282b51a22b416f28466d60018e299f` observed, owner root `Makefile`, `ops/make/publish.mk` inspected before; **NOT** complete terminal publisher graph or canonical L9 compiler proof. `.github` main `3dcdeaae355b6de08562993f705084d7a3714bfd` observed; canonical projection not verified.
- Read target source: `Makefile` (`import-erp`, `import-vanillasoft`, `test-odoo`, `install-smoke`); `plasticos_partner_import/scripts/validate_partner_layer.py`, `import_erp_shell.py`, `run_erp_import.py`, `erp/reader.py`, `erp/mapping.py`, `erp/summary.py`, `models/erp_import_service.py`; `plasticos_transaction/models/native_document_import.py`; `plasticos_crm_sync/scripts/import_vanillasoft_shell.py`, `services/orchestrator.py`, `models/crm_connection.py`; `plasticos_logistics/models/sale_order_inherit.py`, `models/linda_request.py`; `config/odoo_module_order.yaml`; `docs/adr/ADR-021-erp-sql-crm-api-import.md`; the 2026-10-21 4,876-ID campaign contract and runner.
- Official Odoo 19 sources: https://www.odoo.com/documentation/19.0/administration/odoo_sh/getting_started/branches.html (Odoo.sh shell/SSH, sessions can terminate); https://www.odoo.com/documentation/19.0/administration/odoo_sh/advanced.html (Odoo CLI and cron time limits); https://www.odoo.sh/faq (no external long-lived daemons). These are platform capabilities, not evidence that this user's specific Production can access the ERP SQL source.

## Alignment to the existing working cutover plan

Read `PlasticOS_Plan_Graph_Overnight_Cutover_2026-10-30.zip`, especially 26 (operator decision) and 27 (operational graph). The one-PR source owners implement `PL-RELEASE-IMPORT-AUTH` / source bootstrap dependencies. `PL-RELEASE-DR`, `PL-RELEASE-BUSINESS-ACCEPT`, documents binary load and Production migration rehearsal are deferred by later operator decisions even though the older historical checkpoint 23 listed them as prerequisites. For the combined same-night event, obtain actual current ERP SQL/CRM live-source proof **before** starting code promotion. None of those operational cutover proofs is implied by a PR-ready code review.

## Evidence-bound root causes

| ID | Root owner | Verified at snapshot | Contract / response |
|---|---|---|---|
| F01 | `validate_partner_layer.py::check_database` | Production stage/`prod`-like DB denied | C01 default deny + per-run exact-target permit; no spoof |
| F02 | Odoo `Makefile` import recipes / ERP shell | Docker or local venv, not an Odoo.sh-native operator path | C02 existing service via verified Odoo shell, no new ETL |
| F03 | Odoo.sh actual env + `erp/reader.py` | Direct SQL source connectivity/driver CURRENTLY UNKNOWN | C00 READONLY host probe, C02 hosted enablement, cutover blocked if unavailable |
| F04 | `import_erp_shell.py` / `native_document_import.py` | Partner initial empty guard; commercial per-200 worksheet commits; `ERP_LIMIT` diagnostics | C01/C02 ordered first partner + commercial resume, immutable source; no truncation |
| F05 | `erp/mapping.py::contact_exclusion` | Explicit active-only selection already enforced | Preserve; do NOT reimplement |
| F06 | `erp/summary.py::run_exit_status` | Report `partial` does not automatically become nonzero process exit | C03 PR vs data completeness separation; named exceptions and correct fail-close |
| F07 | `native_document_import.py` / ADR-021 | `account.move` draft, no post/payment, native SO confirm/compile | C03 do not invent source accurate posted state; separate accounting acceptance decision |
| F08 | `docs/campaigns/.../import_4876.py` | Hardcoded local path; checkpoint marks all entries DONE without DB revalidation | C04 durable identity-aware resume and host-compatible input path |
| F09 | `plasticos_crm_sync` + historical API evidence | `make import-vanillasoft` modified-after lookback not complete history | C04 per exact ContactID through existing orchestrator, then separate live delta |
| F10 | import side effects | Historical `import_mode` and `skip_procurement`/Linda guards exist; complete negative runtime proof not established | C02/C05 side effect tests; disable competing CRM cron |
| F11 | Odoo.sh actual Production | Current installed addons, DB cleanliness, read-only ERP SQL link, real credentials UNVERIFIED | C00 proof request; not code PR blocker but cutover hard gate |
| F12 | Historical worksheet images/documents | Operator expressly deferred | FORBIDDEN FROM ALL CONTRACTS |

## Coding responsibility vs operational dependencies

**Coding PR can progress without**: direct access to Production, go-live ERP backup, live provider API, Odoo.sh Production write authority, historical-posted accounting status admission, or merge of existing unrelated PRs. Those are not converted into PASS; they affect the appropriate future gate. Code-only tests cannot fake a full live hosted proof.

**Import execution cannot progress without**: explicit operator permit, immutable current ERP SQL source accessible to the runner, current installed addon and source parity, clean target/approved replacement, valid CRM API and trusted crosswalk digest, real crash/replay evidence, no outbound side effects, and properly scoped accounting data acceptance. One omitted gate blocks only its affected part, not source-independent coding.

**Permission boundary:** one writable `IB-Odoo_19` worktree; `.github` and `Cursor-Governance` read-only; one governed PR to `Staging`; no merge, no deployment, no Production import, no destructive reset.

**Assurance boundary:** `08_VALIDATION.json` is only pack/schema-level assertion, not current code test, GAR compiler delegation, independent reviewer acceptance, live Odoo.sh proof or production readiness.
