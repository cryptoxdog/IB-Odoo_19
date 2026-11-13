# S13: single merge onto current Staging

**Contract:** PLASTICOS-EXPORT-C14-S13-STAGING-REFRESH (digest `0bef0053`).

**Branch:** `feat/plasticos-export-s13-staging-refresh`, cut from the accepted S12 head `12645284`. Two merges, neither rebased:

1. `ccd61653` merges #481 (`2caf6cf9`), which removes the private PO64014 originals.
2. `de557a50` merges Staging `3ad23289` (#484–#493).

This PR targets `Staging` and is the campaign's single merge point. Merging it lands S1–S12 and #481, and GitHub then marks #473–#499 and #481 merged.

## Rulings applied

| Ruling | Date | Effect |
|---|---|---|
| Staging's changes are outside the Export lane | 2026-11-12 | Staging wins every conflict, and the campaign's intent is re-applied on top. |
| A1: retire the attachment cleanup again | 2026-11-13 | Staging #485's `plasticos_base/models/ir_attachment.py` and `tests/test_attachment_orphan_cleanup.py` are removed. The retirement migration runs as `plasticos_base` 19.0.1.1.12 and also deletes the `plasticos_base.attachment_orphan_cleanup_cursor` parameter. #485's invoice-FK and Linda-recorder hardening are kept. |
| Material and facility profiles are outside Export | 2026-11-13 | `plasticos_material_profile` and `plasticos_facility_profile` are byte-identical to Staging. |
| Documents AI is outside the campaign | 2026-11-12 | Not touched. |

## Conflicts

The merge had 25 conflicted paths.

**Re-applied from the recorded dry-run resolution, then reviewed:** 21 content conflicts.

| Path | Resolution |
|---|---|
| Version-only manifest and README conflicts | Set above both sides. |
| `config/odoo_module_order.yaml` | Staging's roster, which now includes `plasticos_documents_native`, plus `plasticos_export` after it. |
| `plasticos_documents/models/document.py` `unlink()` | Staging's evidence guard first, then the campaign's guard for decided operation evidence. |
| `plasticos_documents/security/ir.model.access.csv` | Staging's least-privilege file. |
| `plasticos_documents/business_rules/SUPERSESSION.md` | Both sections. |
| `plasticos_logistics/models/linda_response.py` | Staging's recorder containment, with typed-source replies routed to the campaign's recorder. |
| `plasticos_logistics/tests/test_linda_inbound.py` | Both test blocks. |
| `plasticos_security_base/tests/test_action_methods.py` | Staging's assertions plus the campaign's. |
| `plasticos_claims/tests/__init__.py` | Both imports. |
| `plasticos_web_leads/models/web_lead.py` | Staging's file, byte for byte. |

**Resolved by hand:** the other 4 conflicts.

| Path | Resolution |
|---|---|
| `plasticos_transaction` manifest and README | Version set to 19.0.2.3.70. |
| `plasticos_base/models/ir_attachment.py` (modify/delete) | Deleted, per A1. |
| `plasticos_material_profile/tests/test_material_normalizer.py` | Staging's file. |

## Migration moves

These campaign migrations would be skipped on a database that is already on current Staging, so each moves above Staging's shipped version:

| Module | From | To | Notes |
|---|---|---|---|
| `plasticos_base` | 19.0.1.1.11 | 19.0.1.1.12 | |
| `plasticos_logistics` | 19.0.1.14.20 | 19.0.1.14.21 | Marker key unchanged. |
| `plasticos_security_base` | 19.0.1.2.25 | 19.0.1.2.28 | |
| `plasticos_documents` | 19.0.2.1.18 | 19.0.2.1.20 | Accepts 19.0.2.1.17 and 19.0.2.1.18; does nothing at 19.0.2.1.19, the campaign build. |

## Versions

Every module changed on both sides is set above both:

| Module | Version |
|---|---|
| automation | 19.0.2.1.12 |
| base | 19.0.1.1.12 |
| claims | 19.0.1.1.8 |
| crm_bridge | 19.0.3.6.4 |
| documents | 19.0.2.1.20 |
| documents_native | 19.0.1.3.1 |
| logistics | 19.0.1.14.25 |
| security_base | 19.0.1.2.28 |
| transaction | 19.0.2.3.70 |
| web_leads | 19.0.2.11.6 |

## Tests changed

- **`plasticos_web_leads/tests/test_web_lead_bales_packaging.py`** is rewritten to Staging's catalog contract. Bales still resolve to the Bales packaging type, from seller text, AI or photo, and the retired Bales form never reaches the intake.
- **`tests/test_test_env_safety.py`**: the excluded-module cases now use `plasticos_semantic_kernel`, because `plasticos_documents_native` is in the roster.
- **`plasticos_documents/tests/test_scoped_evidence.py`**, **`plasticos_logistics/tests/test_load_cardinality.py`** and **`plasticos_security_base/tests/test_bridge_contracts.py`** follow the moved migration paths.

## Validation

**Run:** pure-Python suite `pytest tests/`, 3257 passed, 49 skipped, 0 failed (at `7e1b4489`).

**Not run, by operator decision 2026-11-13 ("Just publish skip extra testing"):**
- the Enterprise runtime tests and install-smoke on this merged tree;
- the upgrade proof from a Staging database.

The pinned test template was built for the campaign base. Current Staging changed the module roster, so the template needs `make test-env-rebuild` first. Each slice, S1–S12, was runtime-tested on its own; the merged-with-Staging tree is not.
