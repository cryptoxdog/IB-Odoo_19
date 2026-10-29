# Repository evidence register and authority classification

Current source: `cryptoxdog/IB-Odoo_19` Staging `2dc516aa29718b4545faf67e79ca225589ac6d7f`, verified by read-only GitHub connector on 2026-10-29. `EVIDENCE/REPOSITORY_REVISION_AND_BLOBS.json` binds all observed exact Odoo file hashes, and `EVIDENCE/REPO_MANIFEST_SNAPSHOT_CURRENT.json` binds 30 current active addon dependency lists and manifest blob SHA. `EVIDENCE/REPO_SOURCE_LOCK_CURRENT.json` rebinds the preserved planning kernel's source authority closure to the verified branch. The old kernel's source lock remains historically pinned at 677d; do not mistake it for this case.

## High-value current source pointers

| Source | Meaning |
|---|---|
| `plasticos_enrichment/models/enrichment_run.py` | Live Gate/manual `action_execute`, review-only default, bulk Inject, legacy local material injector, failure transaction behavior, run state guard |
| `plasticos_enrichment/models/enrichment_provenance.py` | Applied-field audit, not source admission/review state |
| `plasticos_enrichment/models/enrichment_service.py` | Retired local crawler/extractor/inference, legacy normalization helpers |
| `plasticos_enrichment/security/ir.model.access.csv` | Base internal user broad CRUD for all enrichment evidence models |
| `plasticos_enrichment/hooks.py` | Cron user enrollment in enrichment-manager group on post-init |
| `plasticos_enrichment/data/cron.xml` | Old cron active False and noupdate True; installed state unknown |
| `plasticos_gate/services/gate_mappers.py` | Completed-only response mapping; 8-field partner suggestion filter, no guaranteed field-level source |
| `plasticos_gate/services/gate_allowlists.py` | Eight current allowed partner fields |
| `plasticos_gate/services/gate_config.py` and data seed | Two OFF automatic writeback switches; no automatic CRM writes enabled by mere Gate transport |
| `docs/adr/ADR-012-crm-writeback-allowlist-provenance.md` | Accepted old single-switch default conflicts with current source |
| `docs/adr/ADR-003`, `ADR-009`, `ADR-010`, `ADR-013`, `ADR-017` | Gate authority, ranking ownership, consumer/manual triggers, fail-closed transport and external feedback contract |
| `plasticos_enrichment/tests/test_gate_enrichment_fallback.py` | Current Odoo runtime tests include auto-live and Inject old expectations |
| `plasticos_security_base/tests/test_action_methods.py` | External internal consumer test assumes one-click Inject |
| `docs/campaigns/odoo_tech_debt/OPEN_REGISTER.md` | Existing known audit debt and performance fingerprints on enrichment run loops |

## Limits

Repository source/content verification is NOT a live installed Enterprise, Odoo.sh database, signed EIE packet, tenant authorization, cross-project conformance or independent reviewer receipt. Current JSON lock `tree_sha=NOT_OBSERVED_IN_CONNECTOR` is intentionally honest; no tree SHA was fabricated. The source digest and blob evidence are sufficient for bounded *planning* validation, not for deployment or merge.
