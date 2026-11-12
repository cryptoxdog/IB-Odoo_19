# S7 evidence: operator decisions of 2026-11-12

Contract `PLASTICOS-EXPORT-C07-S7-OPERATOR-DECISIONS` (digest `sha256:061c7174d375f327aaa29dbd1e27bb612c9ccf2d722ea5e2a22f86269b187c7a`), base `ff42df2deaa85ce6354740dda1df00db8413a2ea` (accepted S6 head, PR #480). Part of the PlasticOS Export campaign; plan: `docs/campaigns/future-add-ons/PlasticOS_Export/STRATEGIC_EXECUTION_PLAN_v2.8.md`.

`EVIDENCE/S6/` is unchanged. This note supersedes only the S6 witness rows named below.

## A. Sales Rep allocation visibility

Business rule change recorded in `plasticos_export/business_rules/SUPERSESSION.md` (section "Operator decision 2026-11-12"). `rule_export_cargo_link_sales_own` keeps its XML id and is read only for every link of the user's companies; the global company rule still applies. No rule on `plasticos.load`, `sale.order` or `purchase.order` changed.

### Witness rows updated

| Case | Rule | S6 witness replaced | S7 witnesses |
| --- | --- | --- | --- |
| AC-EXP-14-012 | BRS-EXP-14-R012 | `plasticos_export/tests/test_multicompany_permissions.py::TestMulticompanyPermissions::test_sales_rep_reads_only_cargo_on_their_own_sale_orders` (removed: recorded business-rule change) | `plasticos_export/tests/test_multicompany_permissions.py::TestMulticompanyPermissions::test_sales_rep_reads_every_allocation_of_their_companies`; `plasticos_export/tests/test_multicompany_permissions.py::TestMulticompanyPermissions::test_sales_rep_cannot_change_or_command_allocations`; `plasticos_export/tests/test_multicompany_permissions.py::TestMulticompanyPermissions::test_sales_rep_cannot_read_another_reps_load`; `plasticos_export/tests/test_multicompany_permissions.py::TestMulticompanyPermissions::test_sales_rep_exports_the_allocation_list`; the other S6 witnesses of this row are kept |
| AC-EXP-14-017 | BRS-EXP-14-R017 | none replaced | adds `plasticos_export/tests/test_multicompany_permissions.py::TestMulticompanyPermissions::test_source_references_open_only_for_logistics`; `plasticos_export/tests/test_multicompany_permissions.py::TestMulticompanyPermissions::test_sales_rep_web_reads_another_reps_link_with_display_names` |
| AC-EXP-14-022 | BRS-EXP-14-R022 | none replaced | adds `plasticos_export/tests/test_multicompany_permissions.py::TestMulticompanyPermissions::test_container_manifest_renders_for_a_sales_rep` |
| AC-EXP-06-001 | BRS-EXP-06-R001 | partial witness `plasticos_export/tests/test_multicompany_permissions.py::TestMulticompanyPermissions::test_sales_rep_reads_only_cargo_on_their_own_sale_orders` removed | stays DEFERRED_COVERAGE_DEBT; no economics column was added (the link exposes names only) |

Also documented: `plasticos_export/tests/test_multicompany_permissions.py::TestMulticompanyPermissions::test_sales_rep_and_logistics_user_sees_the_operations_view` (group rules are OR'ed).

## B. Bales as packaging (enrichment)

`plasticos_enrichment/models/enrichment_service.py`: `bale`, `bales`, `baled` map to `plasticos.packaging.type` code `bales` (`packaging_type_id` with provenance); BALE and BALES are no longer form codes. `enrichment_run.py`: a packaging-only material gets no form and never the OTHER fallback. Witnesses: `plasticos_enrichment/tests/test_bales_packaging.py` (real `normalize_material` path, nothing patched).

Web leads (contract effect OP7-E09, coordinator ruling option a): `plasticos_web_leads/models/web_lead.py` no longer maps bale words to the retired BALES form. A bale word sets the intake's `packaging_type_id` to Bales and the form stays at the OTHER fallback; a stored analysis naming BALES is read the same way. Witnesses: `plasticos_web_leads/tests/test_web_lead_bales_packaging.py`. Recorded for the final audit, not changed here: `plasticos.intake.form_id` is `required=True` (`plasticos_intake/models/intake.py`), so a web-lead intake cannot reach the no-form end state that enrichment profiles reach.

## Recorded, out of scope

- `plasticos_material_profile/models/material_normalizer.py` single-word table and `form_codes.py` still name bale forms (final audit).
- Gaylords (`GAY`) still maps to form OTHER in enrichment (final audit).
- `plasticos.load` has no Logistics-wide record rule, so a user in both Sales Rep and Logistics gets the openable load reference but the Sales Rep load rule still governs reading another rep's load (`plasticos_security_base`, not changed here).

## Runtime proof

Not run in this coding session: `add_repo Quantum-L9/odoo-enterprise` was refused, so `make runtime-bootstrap`, install-smoke and `make runtime-test` were not run here. The coordinator runs them on the pushed head.
