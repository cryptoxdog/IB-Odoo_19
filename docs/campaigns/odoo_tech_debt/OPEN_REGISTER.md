# Open tech-debt register

Subject: `cryptoxdog/IB-Odoo_19` `origin/Staging` `e78af874604890f8adb6b049694f93c48311eab4`.
Census date: 2026-10-22.

Machine contract: [`OPEN_REGISTER.json`](OPEN_REGISTER.json). This page is the same census in reading order. If they differ, the JSON wins.

An agent should load the JSON, keep rows with `remediate` true, and take one `recommended_batch` at a time.

## Also on the radar

[Proposed ADR backlog, 2026-08](../../adr/PROPOSED-ADR-BACKLOG-2026-08-architecture-convergence.md) is the session pack that became ADR-010 through ADR-019. Those ten files are Accepted. This register does not queue the backlog as code debt. Read the Accepted ADRs. The draft sections in the backlog still repeat the pre-acceptance notes.

Open campaigns are [`workflow_state.md`](../../../workflow_state.md). This register does not copy those campaigns. It remains the debt tracker.

## Counts

| Measure | Value |
|---|---:|
| live_n_plus_one | 77 |
| n_plus_one_new | 0 |
| n_plus_one_stale_baseline | 2 |
| extended_baseline_entries | 78 |
| weak_tests | 27 |
| unbounded_search | 22 |
| unjustified_sudo | 1 |
| state_bypass | 0 |
| sensitive_logged | 0 |
| field_not_found | 101 |
| invalid_constraint | 1 |
| schema_new | 0 |
| schema_stale | 0 |
| schema_baseline_entries | 88 |
| illegal_field_parameter | 2 |
| items | 250 |
| remediate_true | 115 |

| Classification | Items |
|---|---:|
| accepted_bounded_debt | 90 |
| baseline_housekeeping | 2 |
| documentation_misalignment | 1 |
| evidence_gap | 1 |
| false_positive | 113 |
| policy_deferred | 4 |
| real_debt | 32 |
| scanner_misalignment | 7 |

## Sealed work (do not reopen)

| ID | Result | Where |
|---|---|---|
| GAR-PROD-001 | closed | PR #234 purchase delivery term stays M2M and is batched |
| GAR-PROD-002 | closed | PR #234 unique load_id |
| GAR-PROD-003 | closed | PR #234 transaction profile batch and recompute |
| GAR-PROD-004 | closed | material-profile selection was not collapsed |
| GAR-PROD-005 | closed | PR #234 facility uniqueness batch and DB constraint |
| GAR-PROD-006 | closed | PR #234 commission partial unique index |
| GAR-PROD-007 | closed | PR #234 AST N+1 scanner; browse() is not a query |
| GAR-PROD-008 | closed | PR #234 AST sensitive-log scanner; live count 0 |
| GMP-NC-A | closed_owner | PR #235 one weak-test owner; assertion-free tests remain as TD-WEAK |
| GMP-NC-B | closed_elevations | PR #236; later TD-SUDO-001 and TD-DEF rows are the residue |
| GMP-NC-C | quiet | PR #237 both checkers silent; TD-OWN-001 records the duplicate |
| GMP-NC-D | closed_genuine_overfetch | PR #240 validation domains and negative batch_limit; scanner residue is TD-UB |
| GMP-NC-E | closed_findings | live XPath scan empty; TD-XPATH-001 is leftover fix text |
| GMP-NC-F | replaced | this register is the reconciliation |

## Rules

- Filter remediate=true. Rows with remediate=false are evidence or accepted residue.
- One recommended_batch per change. Do not clear the register in one branch.
- Do not add limit=1 to an UNBOUNDED_SEARCH row.
- Do not add a parent-model field for a FIELD_NOT_FOUND row.
- A rewritten N+1 line must remove its fingerprint from ci/baselines/extended_audit_baseline.json in the same change.
- Do not special-case a file inside performance_audit.py or security_audit.py.
- Do not inherit mail.thread on plasticos.freight.estimate or plasticos.freight.quote to silence tracking. Remove tracking=True. TD-TRACK-001 and TD-TRACK-002.
- Publication of a fix is make pr.

## N_PLUS_ONE_QUERY

77 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-N1-001 | yes | accepted_bounded_debt | `plasticos_automation/models/contract_renewal.py` | 40 | cron_contract_renewal_alert | existing_log = log_model.search_count( |
| TD-N1-002 | yes | accepted_bounded_debt | `plasticos_automation/models/contract_renewal.py` | 57 | cron_contract_renewal_alert | log_model.create( |
| TD-N1-003 | yes | accepted_bounded_debt | `plasticos_automation/models/load_automation.py` | 72 | cron_load_sla_check | log_model.create( |
| TD-N1-004 | yes | accepted_bounded_debt | `plasticos_automation/models/purchase_order_automation.py` | 56 | cron_supplier_followup | log_model.create( |
| TD-N1-005 | yes | accepted_bounded_debt | `plasticos_automation/models/sale_approval.py` | 50 | cron_flag_sale_approvals | log_model.create( |
| TD-N1-006 | yes | accepted_bounded_debt | `plasticos_automation/models/stock_picking_automation.py` | 84 | cron_trucker_followup | log_model.create( |
| TD-N1-007 | yes | accepted_bounded_debt | `plasticos_automation/models/stock_reorder_alert.py` | 40 | cron_stock_reorder_alert | already_logged = log_model.search_count( |
| TD-N1-008 | yes | accepted_bounded_debt | `plasticos_automation/models/stock_reorder_alert.py` | 56 | cron_stock_reorder_alert | log_model.create( |
| TD-N1-009 | yes | accepted_bounded_debt | `plasticos_claims/models/claim.py` | 237 | create | if name and name != "New" and self.search([("name", "=", name)], limit=1): |
| TD-N1-010 | yes | accepted_bounded_debt | `plasticos_claims/models/claim.py` | 246 | write | duplicate = self.search([("name", "=", name), ("id", "!=", record.id)], limit=1) |
| TD-N1-011 | yes | accepted_bounded_debt | `plasticos_claims/models/claim.py` | 415 | _cron_check_sla | existing_activity = self.env["mail.activity"].search_count( |
| TD-N1-012 | yes | accepted_bounded_debt | `plasticos_crm_bridge/models/crm_lead.py` | 117 | _compute_commercial_image_count | rec.commercial_image_count = Attachment.search_count( |
| TD-N1-013 | yes | accepted_bounded_debt | `plasticos_crm_bridge/models/material_profile.py` | 91 | _compute_tx_stats | txs = Transaction.search( |
| TD-N1-014 | yes | accepted_bounded_debt | `plasticos_documents/models/document.py` | 154 | _get_related_transactions | tx = tx_model.search([("load_id", "=", record.res_id)], limit=1) |
| TD-N1-015 | yes | accepted_bounded_debt | `plasticos_documents/models/document.py` | 160 | _get_related_transactions | tx = tx_model.search([("sale_order_id", "=", record.res_id)], limit=1) |
| TD-N1-016 | yes | accepted_bounded_debt | `plasticos_documents/models/transaction_docs.py` | 153 | cron_check_missing_docs | rules = self.env["plasticos.document.rule"].search( |
| TD-N1-017 | yes | accepted_bounded_debt | `plasticos_documents/models/transaction_docs.py` | 186 | cron_check_missing_docs | has_today_activity = self.env["mail.activity"].search_count( |
| TD-N1-018 | yes | accepted_bounded_debt | `plasticos_documents/models/transaction_docs.py` | 308 | cron_check_scale_tickets | has_scale_ticket = self.env["plasticos.document"].search_count( |
| TD-N1-019 | no | false_positive | `plasticos_documents_native/models/document_sync.py` | 165 | batch_sync_unlinked | batch = NativeDoc.search( |
| TD-N1-020 | yes | accepted_bounded_debt | `plasticos_enrichment/models/enrichment_run.py` | 301 | _apply_converge_writeback | self.env[PROVENANCE_MODEL].create( |
| TD-N1-021 | yes | accepted_bounded_debt | `plasticos_enrichment/models/enrichment_run.py` | 600 | action_inject | existing = MatProf.search(domain, limit=1) |
| TD-N1-022 | yes | accepted_bounded_debt | `plasticos_enrichment/models/enrichment_run.py` | 651 | action_inject | MatProf.create(create_vals) |
| TD-N1-023 | yes | accepted_bounded_debt | `plasticos_facility_profile/models/equipment_type.py` | 38 | create | if code and self.search([("code", "=", code)], limit=1): |
| TD-N1-024 | yes | accepted_bounded_debt | `plasticos_facility_profile/models/equipment_type.py` | 46 | write | duplicate = self.search([("code", "=", code), ("id", "!=", record.id)], limit=1) |
| TD-N1-025 | yes | accepted_bounded_debt | `plasticos_facility_profile/models/partner_type.py` | 37 | create | if code and self.search([("code", "=", code)], limit=1): |
| TD-N1-026 | yes | accepted_bounded_debt | `plasticos_facility_profile/models/partner_type.py` | 45 | write | duplicate = self.search([("code", "=", code), ("id", "!=", record.id)], limit=1) |
| TD-N1-027 | yes | accepted_bounded_debt | `plasticos_facility_profile/models/res_partner.py` | 371 | _inverse_mobile | phone_model.create(values) |
| TD-N1-028 | yes | accepted_bounded_debt | `plasticos_intake/models/intake.py` | 406 | _compute_image_count | rec.image_count = Attachment.search_count( |
| TD-N1-029 | yes | accepted_bounded_debt | `plasticos_intake/models/intake.py` | 460 | _compute_offer_count | rec.offer_count = self.env["plasticos.offer"].search_count([("intake_id", "=", rec.id)]) |
| TD-N1-030 | yes | accepted_bounded_debt | `plasticos_intake/models/intake.py` | 922 | action_send_offers | offer = Offer.create( |
| TD-N1-031 | yes | accepted_bounded_debt | `plasticos_intake/models/material_profile_intake.py` | 27 | _compute_intake_count | rec.intake_count = Intake.search_count([("material_profile_id", "=", rec.id)]) |
| TD-N1-032 | yes | accepted_bounded_debt | `plasticos_intake/models/res_partner_intake.py` | 27 | _compute_intake_count | rec.intake_count = Intake.search_count( |
| TD-N1-033 | yes | accepted_bounded_debt | `plasticos_logistics/models/freight_estimate.py` | 83 | create | duplicate = self.search( |
| TD-N1-034 | yes | accepted_bounded_debt | `plasticos_logistics/models/freight_governance.py` | 117 | create | if not prior_id and self.search([("load_id", "=", vals.get("load_id"))], limit=1): |
| TD-N1-035 | yes | accepted_bounded_debt | `plasticos_logistics/models/freight_quote.py` | 135 | create | if self.search([("idempotency_key", "=", idempotency_key)], limit=1): |
| TD-N1-036 | yes | accepted_bounded_debt | `plasticos_logistics/models/freight_quote.py` | 629 | _check_supersession_lineage | if self.search_count([("supersedes_quote_id", "=", prior.id), ("id", "!=", rec.id)]): |
| TD-N1-037 | yes | accepted_bounded_debt | `plasticos_logistics/models/load.py` | 316 | _compute_freight_evidence_counts | rec.freight_quote_request_count = request_model.search_count([("load_id", "=", rec.id)]) |
| TD-N1-038 | yes | accepted_bounded_debt | `plasticos_logistics/models/load.py` | 317 | _compute_freight_evidence_counts | rec.freight_estimate_count = estimate_model.search_count( |
| TD-N1-039 | yes | accepted_bounded_debt | `plasticos_logistics/models/load.py` | 492 | action_create_freight_quote_request | existing = request_model.search([("idempotency_key", "=", key)], limit=1) |
| TD-N1-040 | yes | accepted_bounded_debt | `plasticos_logistics/models/load.py` | 498 | action_create_freight_quote_request | request = request_model.create( |
| TD-N1-041 | yes | accepted_bounded_debt | `plasticos_logistics/models/load.py` | 606 | action_request_freight_estimate | existing = estimate_model.search( |
| TD-N1-042 | yes | accepted_bounded_debt | `plasticos_logistics/models/load.py` | 706 | action_record_actual_freight_cost | existing = calibration_model.search([("load_id", "=", rec.id)], limit=1) |
| TD-N1-043 | yes | accepted_bounded_debt | `plasticos_logistics/models/load.py` | 709 | action_record_actual_freight_cost | estimate = estimate_model.search( |
| TD-N1-044 | yes | accepted_bounded_debt | `plasticos_logistics/models/load.py` | 772 | action_correct_actual_freight_cost | prior = calibration_model.search([("load_id", "=", rec.id)], order="observed_at desc, id desc", limit=1) |
| TD-N1-045 | yes | accepted_bounded_debt | `plasticos_logistics/models/load.py` | 891 | _cancel_stale_freight_quote_requests | stale = request_model.search(domain) |
| TD-N1-046 | yes | accepted_bounded_debt | `plasticos_logistics/models/load.py` | 1212 | _cron_check_dispatch_acknowledgments | has_activity = self.env["mail.activity"].search_count( |
| TD-N1-047 | yes | accepted_bounded_debt | `plasticos_logistics/models/load.py` | 1224 | _cron_check_dispatch_acknowledgments | tx = self.env[PLASTICOS_TRANSACTION].search([("load_id", "=", load.id)], order="id asc", limit=1) |
| TD-N1-048 | yes | accepted_bounded_debt | `plasticos_logistics/models/rate_memory.py` | 75 | action_reconcile_to_canonical_history | reconciliation_model.create( |
| TD-N1-049 | yes | accepted_bounded_debt | `plasticos_material_profile/models/filler_type.py` | 25 | create | if code and self.search([("code", "=", code)], limit=1): |
| TD-N1-050 | yes | accepted_bounded_debt | `plasticos_material_profile/models/filler_type.py` | 33 | write | duplicate = self.search([("code", "=", code), ("id", "!=", record.id)], limit=1) |
| TD-N1-051 | yes | accepted_bounded_debt | `plasticos_material_profile/models/material_attribute.py` | 36 | create | if code and self.search([("code", "=", code)], limit=1): |
| TD-N1-052 | yes | accepted_bounded_debt | `plasticos_material_profile/models/material_attribute.py` | 44 | write | duplicate = self.search([("code", "=", code), ("id", "!=", record.id)], limit=1) |
| TD-N1-053 | yes | accepted_bounded_debt | `plasticos_material_profile/models/material_color.py` | 31 | create | if code and self.search([("code", "=", code)], limit=1): |
| TD-N1-054 | yes | accepted_bounded_debt | `plasticos_material_profile/models/material_color.py` | 39 | write | duplicate = self.search([("code", "=", code), ("id", "!=", record.id)], limit=1) |
| TD-N1-055 | yes | accepted_bounded_debt | `plasticos_material_profile/models/material_form.py` | 31 | create | if code and self.search([("code", "=", code)], limit=1): |
| TD-N1-056 | yes | accepted_bounded_debt | `plasticos_material_profile/models/material_form.py` | 39 | write | duplicate = self.search([("code", "=", code), ("id", "!=", record.id)], limit=1) |
| TD-N1-057 | yes | accepted_bounded_debt | `plasticos_material_profile/models/material_profile.py` | 347 | _compute_image_count | rec.image_count = Attachment.search_count( |
| TD-N1-058 | yes | accepted_bounded_debt | `plasticos_material_profile/models/material_profile.py` | 466 | _compute_po_line_count | rec.po_line_count = POLine.search_count([("material_profile_id", "=", rec.id)]) if has_field else 0 |
| TD-N1-059 | yes | accepted_bounded_debt | `plasticos_material_profile/models/material_profile.py` | 478 | _compute_so_line_count | rec.so_line_count = SOLine.search_count([("material_profile_id", "=", rec.id)]) if has_field else 0 |
| TD-N1-060 | yes | accepted_bounded_debt | `plasticos_material_profile/models/packaging_type.py` | 32 | create | if code and self.search([("code", "=", code)], limit=1): |
| TD-N1-061 | yes | accepted_bounded_debt | `plasticos_material_profile/models/packaging_type.py` | 40 | write | duplicate = self.search([("code", "=", code), ("id", "!=", record.id)], limit=1) |
| TD-N1-062 | yes | accepted_bounded_debt | `plasticos_material_profile/models/polymer.py` | 46 | create | if code and self.search([("code", "=", code)], limit=1): |
| TD-N1-063 | yes | accepted_bounded_debt | `plasticos_material_profile/models/polymer.py` | 54 | write | duplicate = self.search([("code", "=", code), ("id", "!=", record.id)], limit=1) |
| TD-N1-064 | yes | accepted_bounded_debt | `plasticos_material_profile/models/process_type.py` | 31 | create | if code and self.search([("code", "=", code)], limit=1): |
| TD-N1-065 | yes | accepted_bounded_debt | `plasticos_material_profile/models/process_type.py` | 39 | write | duplicate = self.search([("code", "=", code), ("id", "!=", record.id)], limit=1) |
| TD-N1-066 | yes | accepted_bounded_debt | `plasticos_material_profile/models/res_partner.py` | 51 | _compute_material_profile_count | rec.material_profile_count = Profile.search_count([("partner_id", "=", rec.id)]) |
| TD-N1-067 | yes | accepted_bounded_debt | `plasticos_material_profile/models/source_type.py` | 31 | create | if code and self.search([("code", "=", code)], limit=1): |
| TD-N1-068 | yes | accepted_bounded_debt | `plasticos_material_profile/models/source_type.py` | 39 | write | duplicate = self.search([("code", "=", code), ("id", "!=", record.id)], limit=1) |
| TD-N1-069 | yes | accepted_bounded_debt | `plasticos_offer/models/offer.py` | 195 | _compute_image_count | rec.image_count = Attachment.search_count( |
| TD-N1-070 | yes | accepted_bounded_debt | `plasticos_offer/models/offer_price_bridge.py` | 27 | create | match_line = self.env["plasticos.intake.match"].search( |
| TD-N1-071 | yes | accepted_bounded_debt | `plasticos_transaction/models/sale_inherit.py` | 46 | action_confirm | tx = transactions.create(order._transaction_vals(False, worksheet)) |
| TD-N1-072 | yes | accepted_bounded_debt | `plasticos_transaction/models/sale_inherit.py` | 65 | _compile_worksheet_transactions | if transactions.search([("name", "=", worksheet)], limit=1): |
| TD-N1-073 | yes | accepted_bounded_debt | `plasticos_transaction/models/transaction.py` | 906 | create | if name and name != "New" and self.search([("name", "=", name)], limit=1): |
| TD-N1-074 | yes | accepted_bounded_debt | `plasticos_transaction/models/transaction.py` | 914 | write | duplicate = self.search([("name", "=", name), ("id", "!=", record.id)], limit=1) |
| TD-N1-075 | yes | accepted_bounded_debt | `plasticos_transaction/models/transaction.py` | 975 | _validate_bill_uniqueness | other = self.search( |
| TD-N1-076 | yes | accepted_bounded_debt | `plasticos_transaction/models/transaction.py` | 983 | _validate_bill_uniqueness | other = self.search( |
| TD-N1-077 | yes | accepted_bounded_debt | `plasticos_transaction/models/transaction_import_service.py` | 185 | _create_transaction_lines | Line.create(line_vals) |

Actions:

- TD-N1-001 … TD-N1-076 (62 rows, same action): Lift the search out of the loop only when every iteration's domain can be expressed as one domain over the recordset. Keep selection order identical. Do not special-case this file inside scripts/audit/performance_audit.py. Do not add a new baseline row for a rewritten line; remove this fingerprint in the same change.
- TD-N1-002 … TD-N1-077 (14 rows, same action): Batch the create, write, or unlink for the whole recordset after proving each iteration does not depend on the previous write. Do not special-case this file inside scripts/audit/performance_audit.py. Do not add a new baseline row for a rewritten line; remove this fingerprint in the same change.
- TD-N1-019: Leave the loop. Removing it would load the whole unlinked set at once. Do not special-case this file inside scripts/audit/performance_audit.py. Do not add a new baseline row for a rewritten line; remove this fingerprint in the same change.

## STALE_BASELINE

2 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-BASE-39bbc2ad6a8906c4 | no | baseline_housekeeping | `plasticos_buyer_match_engine/models/intake_extension.py` | 70 |  | ORM .create() inside loop (N+1 query) |
| TD-BASE-4a48e73c9623fd94 | no | baseline_housekeeping | `plasticos_crm_bridge/models/crm_lead.py` | 198 |  | ORM .search() inside loop (query in loop) |

Actions:

- TD-BASE-39bbc2ad6a8906c4, TD-BASE-4a48e73c9623fd94: Delete this entry from ci/baselines/extended_audit_baseline.json when a baseline-only change is already in progress. Do not treat a stale row as a live defect. Do not fail a feature PR solely to prune it.

## WEAK_TEST

27 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-WEAK-001 | yes | real_debt | `tests/integration/test_cron_idempotency.py` | 61 | test_midnight_recompute_idempotent | def test_midnight_recompute_idempotent(self): |
| TD-WEAK-002 | yes | real_debt | `tests/integration/test_cron_idempotency.py` | 65 | test_batch_normalize_idempotent | def test_batch_normalize_idempotent(self): |
| TD-WEAK-003 | yes | real_debt | `tests/integration/test_cron_idempotency.py` | 69 | test_geo_backfill_idempotent | def test_geo_backfill_idempotent(self): |
| TD-WEAK-004 | yes | real_debt | `tests/integration/test_cron_idempotency.py` | 73 | test_expire_offers_idempotent | def test_expire_offers_idempotent(self): |
| TD-WEAK-005 | yes | real_debt | `tests/integration/test_cron_idempotency.py` | 77 | test_claim_cron_idempotent | def test_claim_cron_idempotent(self): |
| TD-WEAK-006 | yes | real_debt | `tests/integration/test_cron_idempotency.py` | 81 | test_logistics_cron_idempotent | def test_logistics_cron_idempotent(self): |
| TD-WEAK-007 | yes | real_debt | `tests/integration/test_cron_idempotency.py` | 85 | test_enrichment_cron_idempotent | def test_enrichment_cron_idempotent(self): |
| TD-WEAK-008 | yes | real_debt | `tests/integration/test_cron_idempotency.py` | 94 | test_audit_cron_idempotent | def test_audit_cron_idempotent(self): |
| TD-WEAK-009 | yes | real_debt | `tests/integration/test_cron_idempotency.py` | 98 | test_scale_ticket_cron_idempotent | def test_scale_ticket_cron_idempotent(self): |
| TD-WEAK-010 | yes | real_debt | `tests/integration/test_cron_idempotency.py` | 101 | test_missing_docs_cron_idempotent | def test_missing_docs_cron_idempotent(self): |
| TD-WEAK-011 | yes | real_debt | `tests/integration/test_cron_idempotency.py` | 105 | test_contract_renewal_cron_idempotent | def test_contract_renewal_cron_idempotent(self): |
| TD-WEAK-012 | yes | real_debt | `tests/integration/test_cron_idempotency.py` | 108 | test_invoice_reminder_cron_idempotent | def test_invoice_reminder_cron_idempotent(self): |
| TD-WEAK-013 | yes | real_debt | `tests/integration/test_cron_idempotency.py` | 111 | test_sale_approval_cron_idempotent | def test_sale_approval_cron_idempotent(self): |
| TD-WEAK-014 | yes | real_debt | `tests/test_cron_runtime.py` | 85 | test_load_sla_check_empty | def test_load_sla_check_empty(self): |
| TD-WEAK-015 | yes | real_debt | `tests/test_cron_runtime.py` | 89 | test_stock_alert_empty | def test_stock_alert_empty(self): |
| TD-WEAK-016 | yes | real_debt | `tests/test_cron_runtime.py` | 93 | test_enrichment_pending_empty | def test_enrichment_pending_empty(self): |
| TD-WEAK-017 | yes | real_debt | `tests/test_cron_runtime.py` | 101 | test_claim_escalation_empty | def test_claim_escalation_empty(self): |
| TD-WEAK-018 | yes | real_debt | `tests/test_cron_runtime.py` | 105 | test_transaction_audit_empty | def test_transaction_audit_empty(self): |
| TD-WEAK-019 | yes | real_debt | `tests/test_cron_runtime.py` | 109 | test_missing_docs_check_empty | def test_missing_docs_check_empty(self): |
| TD-WEAK-020 | yes | real_debt | `tests/test_cron_runtime.py` | 113 | test_geo_backfill_empty | def test_geo_backfill_empty(self): |
| TD-WEAK-021 | yes | real_debt | `tests/test_gate_sdk_invocation.py` | 238 | test_sdk_validates_the_adapter_packet_as_gate_bound | def test_sdk_validates_the_adapter_packet_as_gate_bound(gate): |
| TD-WEAK-022 | yes | real_debt | `tests/test_opportunity_protocol_split.py` | 41 | test_positive_supply_fixture | def test_positive_supply_fixture() -> None: |
| TD-WEAK-023 | yes | real_debt | `tests/test_opportunity_protocol_split.py` | 45 | test_positive_buyer_demand_fixture | def test_positive_buyer_demand_fixture() -> None: |
| TD-WEAK-024 | yes | real_debt | `tests/test_projection_outcome_schemas.py` | 45 | test_canonical_fixture | def test_canonical_fixture() -> None: |
| TD-WEAK-025 | yes | real_debt | `tests/test_projection_outcome_schemas.py` | 49 | test_sync_and_tombstone_fixtures | def test_sync_and_tombstone_fixtures() -> None: |
| TD-WEAK-026 | yes | real_debt | `tests/test_projection_outcome_schemas.py` | 54 | test_outcome_fixture | def test_outcome_fixture() -> None: |
| TD-WEAK-027 | yes | real_debt | `tests/test_semantic_gate_payloads.py` | 118 | test_example_fixtures_still_valid | def test_example_fixtures_still_valid() -> None: |

Actions:

- TD-WEAK-001 … TD-WEAK-027 (27 rows, same action): Add an assertion that fails if the contract under test is broken. Use the operations already in the test body. Do not add assert True, a tautology, or a helper whose name merely starts with check_, validate_, _run_, or _safe_.

## UNBOUNDED_SEARCH

22 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-UB-001 | no | accepted_bounded_debt | `plasticos_automation/models/penalty_rule.py` | 110 | calculate_penalty | rules = self.search([("active", "=", True)], order="sequence, id") |
| TD-UB-002 | no | false_positive | `plasticos_crm_bridge/models/facility_profile.py` | 255 | _rows_for_reference | return self.env[field.model_name].search([(field.name, "=", source.id)]) |
| TD-UB-003 | no | false_positive | `plasticos_crm_bridge/models/facility_profile.py` | 256 | _rows_for_reference | return self.env[field.model_name].search([(field.name, "in", source.ids)]) |
| TD-UB-004 | no | accepted_bounded_debt | `plasticos_documents/models/compliance_service.py` | 16 | get_missing_documents | rules = self.env["plasticos.document.rule"].search([("res_model", "=", res_model), ("active", "=", True)]) |
| TD-UB-005 | no | accepted_bounded_debt | `plasticos_documents/models/transaction_docs.py` | 153 | cron_check_missing_docs | rules = self.env["plasticos.document.rule"].search( |
| TD-UB-006 | no | false_positive | `plasticos_geolocalize/models/res_partner_geo.py` | 54 | cron_geo_backfill | partners = self.search( |
| TD-UB-007 | no | false_positive | `plasticos_intake_normalizer/models/intake_normalizer.py` | 188 | cron_batch_normalize | pending = self.search( |
| TD-UB-008 | no | accepted_bounded_debt | `plasticos_intake_normalizer/models/intake_normalizer.py` | 597 | _get_canonical_polymers | polymers = Polymer.search([("active", "=", True)]) |
| TD-UB-009 | no | false_positive | `plasticos_partner_import/models/erp_import_service.py` | 755 | _user_ids_by_name | users = self.env["res.users"].search([("name", "in", sorted(names))]) |
| TD-UB-010 | no | accepted_bounded_debt | `plasticos_partner_import/models/erp_import_service.py` | 832 | _address_catalog | data = self.env["ir.model.data"].search( |
| TD-UB-011 | no | accepted_bounded_debt | `plasticos_partner_import/models/erp_import_service.py` | 852 | _partners_by_prefix | data = self.env["ir.model.data"].search( |
| TD-UB-012 | no | false_positive | `plasticos_partner_import/models/validation.py` | 49 | validate_partner_graph | candidates = self.env["res.partner"].search( |
| TD-UB-013 | no | accepted_bounded_debt | `plasticos_partner_import/models/validation.py` | 95 | audit_import_integrity | old_data = IrModelData.search( |
| TD-UB-014 | no | false_positive | `plasticos_partner_import/models/validation.py` | 111 | audit_import_integrity | facilities = Partner.search( |
| TD-UB-015 | no | accepted_bounded_debt | `plasticos_partner_import/models/validation.py` | 121 | audit_import_integrity | contacts_no_parent = Partner.search( |
| TD-UB-016 | no | accepted_bounded_debt | `plasticos_partner_import/models/validation.py` | 130 | audit_import_integrity | new_module_data = IrModelData.search( |
| TD-UB-017 | no | accepted_bounded_debt | `plasticos_partner_import/models/validation.py` | 193 | repair_import_data | old_data = IrModelData.search( |
| TD-UB-018 | no | false_positive | `plasticos_transaction/models/account_move_inherit.py` | 56 | action_post | sale_orders = self.env["sale.order"].search([("name", "in", all_origins)]) |
| TD-UB-019 | no | false_positive | `plasticos_transaction/models/account_move_inherit.py` | 61 | action_post | purchase_orders = self.env["purchase.order"].search([("name", "in", missing_origins)]) |
| TD-UB-020 | no | false_positive | `plasticos_transaction/models/purchase_inherit.py` | 49 | button_confirm | sale_orders = self.env["sale.order"].search([("name", "in", origins)]) |
| TD-UB-021 | no | accepted_bounded_debt | `plasticos_transaction/models/sale_inherit.py` | 167 | _worksheet_document_vals | purchases = self.env["purchase.order"].search([("origin", "=", worksheet)]) |
| TD-UB-022 | no | accepted_bounded_debt | `plasticos_transaction/models/sale_inherit.py` | 168 | _worksheet_document_vals | found = moves.search( |

Actions:

- TD-UB-001 … TD-UB-022 (12 rows, same action): Leave the search complete. Re-open only if a caller is shown to filter most of the rows in Python. Do not add limit=1 to silence the scanner.
- TD-UB-002, TD-UB-003: Leave the search complete. A limit would drop referencing rows. Do not add limit=1 to silence the scanner.
- TD-UB-006: Leave the call. Do not add a second literal limit. Do not add limit=1 to silence the scanner.
- TD-UB-007: Leave the call. The positivity proof is plasticos_intake_normalizer/models/normalizer_config.py _check_batch_limit. Do not add limit=1 to silence the scanner.
- TD-UB-009, TD-UB-018, TD-UB-019, TD-UB-020: Leave the search. Do not add limit=1. Do not add limit=1 to silence the scanner.
- TD-UB-012, TD-UB-014: Leave the domain. Do not add limit=1. Do not add limit=1 to silence the scanner.

## UNJUSTIFIED_SUDO

1 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-SUDO-001 | yes | real_debt | `plasticos_crm_bridge/models/facility_profile.py` | 307 | _retarget_profile_bindings | .sudo() |

Actions:

- TD-SUDO-001: Move the existing chatter-ACL reason onto the .sudo() line as '# sudo: sync ACL cannot read chatter'. Re-read the method before changing the elevation itself. Do not remove the elevation unless mail.message is readable by the sync caller without it. Do not put TODO in the reason; the scanner rejects debt words.

## FIELD_NOT_FOUND

102 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-SCAN-001 | yes | scanner_misalignment | `scripts/audit/odoo_audit.py` | 189 | scan_view_field_refs | current_model = model_match.group(1) |
| TD-FIELD-001 | no | false_positive | `plasticos_automation/views/automation_config_views.xml` | 44 | target | [record_context_bleed] <field name="target">current</field> |
| TD-FIELD-002 | no | false_positive | `plasticos_claims/views/transaction_claims_bridge_views.xml` | 15 | claim_count | [cross_module_inherit] <field name="claim_count" nolabel="1"/> |
| TD-FIELD-003 | no | false_positive | `plasticos_commission/views/commission_payout_views.xml` | 88 | supplier_id | [nested_subview] <field name="supplier_id"              string="Supplier"/> |
| TD-FIELD-004 | no | false_positive | `plasticos_commission/views/commission_payout_views.xml` | 89 | buyer_id | [nested_subview] <field name="buyer_id"                 string="Buyer"/> |
| TD-FIELD-005 | no | false_positive | `plasticos_commission/views/commission_payout_views.xml` | 90 | gross_margin | [nested_subview] <field name="gross_margin"             string="Margin"     widget="monetary"/> |
| TD-FIELD-006 | no | false_positive | `plasticos_commission/views/commission_payout_views.xml` | 91 | commission_locked_amount | [nested_subview] <field name="commission_locked_amount" string="Commission" widget="monetary"/> |
| TD-FIELD-007 | no | false_positive | `plasticos_commission/views/transaction_commission_views.xml` | 20 | commission_rule_id | [cross_module_inherit] <field name="commission_rule_id"/> |
| TD-FIELD-008 | no | false_positive | `plasticos_commission/views/transaction_commission_views.xml` | 22 | commission_locked | [cross_module_inherit] <field name="commission_locked"/> |
| TD-FIELD-009 | no | false_positive | `plasticos_commission/views/transaction_commission_views.xml` | 23 | commission_locked_amount | [cross_module_inherit] <field name="commission_locked_amount" invisible="not commission_locked"/> |
| TD-FIELD-010 | no | false_positive | `plasticos_crm_bridge/views/crm_facility_ownership_views.xml` | 9 | crm_lead_id | [cross_module_inherit] <field name="crm_lead_id"/> |
| TD-FIELD-011 | no | false_positive | `plasticos_crm_bridge/views/crm_facility_ownership_views.xml` | 21 | facility_profile_id | [cross_module_inherit] <field name="facility_profile_id"/> |
| TD-FIELD-012 | no | false_positive | `plasticos_crm_bridge/views/crm_lead_views.xml` | 309 | crm_lead_id | [cross_module_inherit] <field name="crm_lead_id"/> |
| TD-FIELD-013 | no | false_positive | `plasticos_crm_bridge/views/crm_lead_views.xml` | 324 | crm_lead_id | [cross_module_inherit] <field name="crm_lead_id" optional="show"/> |
| TD-FIELD-014 | no | false_positive | `plasticos_crm_bridge/views/material_profile_views.xml` | 28 | match_count | [cross_module_inherit] <field name="match_count" nolabel="1"/> |
| TD-FIELD-015 | no | false_positive | `plasticos_crm_bridge/views/material_profile_views.xml` | 42 | best_match_score | [cross_module_inherit] <field name="best_match_score" nolabel="1" |
| TD-FIELD-016 | no | false_positive | `plasticos_crm_bridge/views/material_profile_views.xml` | 55 | transaction_count | [cross_module_inherit] <field name="transaction_count" |
| TD-FIELD-017 | no | false_positive | `plasticos_crm_bridge/views/material_profile_views.xml` | 71 | last_pickup_date | [cross_module_inherit] <field name="last_pickup_date" nolabel="1"/> |
| TD-FIELD-018 | no | false_positive | `plasticos_crm_bridge/views/material_profile_views.xml` | 83 | match_count | [cross_module_inherit] <field name="match_count"/> |
| TD-FIELD-019 | no | false_positive | `plasticos_crm_bridge/views/material_profile_views.xml` | 84 | best_match_score | [cross_module_inherit] <field name="best_match_score" |
| TD-FIELD-020 | no | false_positive | `plasticos_crm_bridge/views/material_profile_views.xml` | 88 | pending_match_count | [cross_module_inherit] <field name="pending_match_count"/> |
| TD-FIELD-021 | no | false_positive | `plasticos_crm_bridge/views/material_profile_views.xml` | 95 | transaction_count | [cross_module_inherit] <field name="transaction_count"/> |
| TD-FIELD-022 | no | false_positive | `plasticos_crm_bridge/views/material_profile_views.xml` | 96 | total_revenue | [cross_module_inherit] <field name="total_revenue"/> |
| TD-FIELD-023 | no | false_positive | `plasticos_crm_bridge/views/material_profile_views.xml` | 99 | last_pickup_date | [cross_module_inherit] <field name="last_pickup_date" |
| TD-FIELD-024 | no | false_positive | `plasticos_crm_bridge/views/material_profile_views.xml` | 122 | match_count | [cross_module_inherit] <field name="match_count" string="Matches" optional="show"/> |
| TD-FIELD-025 | no | false_positive | `plasticos_crm_bridge/views/material_profile_views.xml` | 123 | best_match_score | [cross_module_inherit] <field name="best_match_score" string="Best Match %" |
| TD-FIELD-026 | no | false_positive | `plasticos_crm_bridge/views/material_profile_views.xml` | 125 | transaction_count | [cross_module_inherit] <field name="transaction_count" string="Txns" optional="show"/> |
| TD-FIELD-027 | no | false_positive | `plasticos_crm_bridge/views/material_profile_views.xml` | 126 | total_revenue | [cross_module_inherit] <field name="total_revenue" string="Revenue" optional="hide" |
| TD-FIELD-028 | no | false_positive | `plasticos_crm_bridge/views/material_profile_views.xml` | 128 | last_pickup_date | [cross_module_inherit] <field name="last_pickup_date" string="Last Shipped" |
| TD-FIELD-029 | no | false_positive | `plasticos_documents/views/load_docs_bridge_views.xml` | 15 | document_count | [cross_module_inherit] <field name="document_count" nolabel="1"/> |
| TD-FIELD-030 | no | false_positive | `plasticos_documents/views/transaction_docs_bridge_views.xml` | 15 | document_count | [cross_module_inherit] <field name="document_count" nolabel="1"/> |
| TD-FIELD-031 | no | false_positive | `plasticos_documents/views/transaction_docs_views.xml` | 12 | missing_doc_status | [cross_module_inherit] <field name="missing_doc_status" readonly="1"/> |
| TD-FIELD-032 | no | false_positive | `plasticos_documents/views/transaction_docs_views.xml` | 13 | doc_reminder_count | [cross_module_inherit] <field name="doc_reminder_count" readonly="1"/> |
| TD-FIELD-033 | no | false_positive | `plasticos_documents/views/transaction_docs_views.xml` | 14 | last_doc_reminder_date | [cross_module_inherit] <field name="last_doc_reminder_date" readonly="1"/> |
| TD-FIELD-034 | no | false_positive | `plasticos_documents/views/transaction_docs_views.xml` | 17 | missing_supplier_docs | [cross_module_inherit] <field name="missing_supplier_docs" readonly="1"/> |
| TD-FIELD-035 | no | false_positive | `plasticos_documents/views/transaction_docs_views.xml` | 18 | missing_carrier_docs | [cross_module_inherit] <field name="missing_carrier_docs" readonly="1"/> |
| TD-FIELD-036 | no | false_positive | `plasticos_documents/views/transaction_docs_views.xml` | 19 | missing_buyer_docs | [cross_module_inherit] <field name="missing_buyer_docs" readonly="1"/> |
| TD-FIELD-037 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 60 | url | [nested_subview] <field name="url"/> |
| TD-FIELD-038 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 61 | source_type | [nested_subview] <field name="source_type"/> |
| TD-FIELD-039 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 62 | crawl_status | [nested_subview] <field name="crawl_status" widget="badge"/> |
| TD-FIELD-040 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 63 | last_crawled_at | [nested_subview] <field name="last_crawled_at"/> |
| TD-FIELD-041 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 64 | error_message | [nested_subview] <field name="error_message"/> |
| TD-FIELD-042 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 71 | source_id | [nested_subview] <field name="source_id"/> |
| TD-FIELD-043 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 72 | confidence | [nested_subview] <field name="confidence"/> |
| TD-FIELD-044 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 73 | governance_passed | [nested_subview] <field name="governance_passed"/> |
| TD-FIELD-045 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 74 | is_injectable | [nested_subview] <field name="is_injectable"/> |
| TD-FIELD-046 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 75 | extracted_at | [nested_subview] <field name="extracted_at"/> |
| TD-FIELD-047 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 82 | target_field | [nested_subview] <field name="target_field"/> |
| TD-FIELD-048 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 83 | value_written | [nested_subview] <field name="value_written"/> |
| TD-FIELD-049 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 84 | previous_value | [nested_subview] <field name="previous_value"/> |
| TD-FIELD-050 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 85 | status | [nested_subview] <field name="status" widget="badge"/> |
| TD-FIELD-051 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 86 | confidence | [nested_subview] <field name="confidence"/> |
| TD-FIELD-052 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 87 | inference_type | [nested_subview] <field name="inference_type"/> |
| TD-FIELD-053 | no | false_positive | `plasticos_enrichment/views/enrichment_run_views.xml` | 88 | source_sentence | [nested_subview] <field name="source_sentence"/> |
| TD-FIELD-054 | no | false_positive | `plasticos_intake/views/intake_views.xml` | 380 | selected | [nested_subview] <field name="selected" string="Select"/> |
| TD-FIELD-055 | no | false_positive | `plasticos_intake/views/intake_views.xml` | 381 | buyer_name | [nested_subview] <field name="buyer_name" string="Buyer"/> |
| TD-FIELD-056 | no | false_positive | `plasticos_intake/views/intake_views.xml` | 382 | buyer_city | [nested_subview] <field name="buyer_city"/> |
| TD-FIELD-057 | no | false_positive | `plasticos_intake/views/intake_views.xml` | 383 | buyer_state | [nested_subview] <field name="buyer_state"/> |
| TD-FIELD-058 | no | false_positive | `plasticos_intake/views/intake_views.xml` | 384 | match_reason | [nested_subview] <field name="match_reason" string="Why Matched"/> |
| TD-FIELD-059 | no | false_positive | `plasticos_intake/views/intake_views.xml` | 385 | match_score | [nested_subview] <field name="match_score" string="Match %"/> |
| TD-FIELD-060 | no | false_positive | `plasticos_intake/views/intake_views.xml` | 386 | typical_price | [nested_subview] <field name="typical_price" string="$/lb" optional="show"/> |
| TD-FIELD-061 | no | false_positive | `plasticos_intake/views/material_profile_intake_views.xml` | 28 | intake_count | [cross_module_inherit] <field name="intake_count" string="Intakes" widget="statinfo"/> |
| TD-FIELD-062 | no | false_positive | `plasticos_intake_normalizer/views/intake_normalizer_views.xml` | 29 | normalized | [cross_module_inherit] <field name="normalized" readonly="1"/> |
| TD-FIELD-063 | no | false_positive | `plasticos_intake_normalizer/views/intake_normalizer_views.xml` | 30 | normalization_ts | [cross_module_inherit] <field name="normalization_ts" readonly="1"/> |
| TD-FIELD-064 | no | false_positive | `plasticos_intake_normalizer/views/intake_normalizer_views.xml` | 33 | last_packet_id | [cross_module_inherit] <field name="last_packet_id" readonly="1"/> |
| TD-FIELD-065 | no | false_positive | `plasticos_intake_normalizer/views/intake_normalizer_views.xml` | 34 | last_packet_version | [cross_module_inherit] <field name="last_packet_version" readonly="1"/> |
| TD-FIELD-066 | no | false_positive | `plasticos_intake_normalizer/views/intake_normalizer_views.xml` | 35 | last_packet_ts | [cross_module_inherit] <field name="last_packet_ts" readonly="1"/> |
| TD-FIELD-067 | no | false_positive | `plasticos_intake_normalizer/views/intake_normalizer_views.xml` | 39 | normalization_errors | [cross_module_inherit] <field name="normalization_errors" widget="json" readonly="1"/> |
| TD-FIELD-068 | no | false_positive | `plasticos_intake_normalizer/views/intake_normalizer_views.xml` | 42 | normalization_warnings | [cross_module_inherit] <field name="normalization_warnings" widget="json" readonly="1"/> |
| TD-FIELD-069 | no | false_positive | `plasticos_intake_normalizer/views/intake_normalizer_views.xml` | 45 | last_packet_payload | [cross_module_inherit] <field name="last_packet_payload" widget="json" readonly="1"/> |
| TD-FIELD-070 | no | false_positive | `plasticos_intake_normalizer/views/normalizer_config_views.xml` | 53 | target | [record_context_bleed] <field name="target">current</field> |
| TD-FIELD-071 | no | false_positive | `plasticos_intake_normalizer/views/normalizer_config_views.xml` | 54 | res_id | [record_context_bleed] <field name="res_id" ref="normalizer_config_default"/> |
| TD-FIELD-072 | no | false_positive | `plasticos_logistics/views/load_views.xml` | 335 | message_follower_ids | [nested_subview] <field name="message_follower_ids"/> |
| TD-FIELD-073 | no | false_positive | `plasticos_logistics/views/load_views.xml` | 336 | message_ids | [nested_subview] <field name="message_ids"/> |
| TD-FIELD-074 | no | false_positive | `plasticos_logistics/views/transaction_load_views.xml` | 18 | load_id | [cross_module_inherit] <field name="load_id" |
| TD-FIELD-075 | no | false_positive | `plasticos_logistics/views/transaction_load_views.xml` | 66 | load_id | [cross_module_inherit] <field name="load_id" string="Load" optional="show"/> |
| TD-FIELD-076 | no | false_positive | `plasticos_logistics/views/transaction_load_views.xml` | 86 | load_id | [cross_module_inherit] <field name="load_id"/> |
| TD-FIELD-077 | no | false_positive | `plasticos_matching/views/match_exclusion_views.xml` | 95 | model_id | [record_context_bleed] <field name="model_id" ref="model_plasticos_match_exclusion" /> |
| TD-FIELD-078 | no | false_positive | `plasticos_matching/views/match_exclusion_views.xml` | 96 | state | [record_context_bleed] <field name="state">code</field> |
| TD-FIELD-079 | no | false_positive | `plasticos_matching/views/match_exclusion_views.xml` | 97 | code | [record_context_bleed] <field name="code">model._cron_expire_temporary_exclusions()</field> |
| TD-FIELD-080 | no | false_positive | `plasticos_matching/views/match_exclusion_views.xml` | 98 | interval_number | [record_context_bleed] <field name="interval_number">1</field> |
| TD-FIELD-081 | no | false_positive | `plasticos_matching/views/match_exclusion_views.xml` | 99 | interval_type | [record_context_bleed] <field name="interval_type">days</field> |
| TD-FIELD-082 | no | false_positive | `plasticos_matching/views/match_exclusion_views.xml` | 101 | user_id | [record_context_bleed] <field name="user_id" ref="plasticos_base.user_system_cron" /></record> |
| TD-FIELD-083 | no | false_positive | `plasticos_product/views/polymer_views.xml` | 14 | product_id | [cross_module_inherit] <field name="product_id" string="Product" optional="show"/> |
| TD-FIELD-084 | no | false_positive | `plasticos_product/views/polymer_views.xml` | 39 | product_id | [cross_module_inherit] <field name="product_id" readonly="1"/> |
| TD-FIELD-085 | no | false_positive | `plasticos_product/views/polymer_views.xml` | 48 | model_id | [record_context_bleed] <field name="model_id" ref="plasticos_material_profile.model_plasticos_polymer"/> |
| TD-FIELD-086 | no | false_positive | `plasticos_product/views/polymer_views.xml` | 49 | binding_model_id | [record_context_bleed] <field name="binding_model_id" ref="plasticos_material_profile.model_plasticos_polymer"/> |
| TD-FIELD-087 | no | false_positive | `plasticos_product/views/polymer_views.xml` | 50 | binding_view_types | [record_context_bleed] <field name="binding_view_types">list</field> |
| TD-FIELD-088 | no | false_positive | `plasticos_product/views/polymer_views.xml` | 51 | state | [record_context_bleed] <field name="state">code</field> |
| TD-FIELD-089 | no | false_positive | `plasticos_transaction/views/intake_bridge_views.xml` | 15 | transaction_count | [cross_module_inherit] <field name="transaction_count" nolabel="1"/> |
| TD-FIELD-090 | no | false_positive | `plasticos_transaction/views/transaction_views.xml` | 216 | detail_id | [nested_subview] <field name="detail_id"/> |
| TD-FIELD-091 | no | false_positive | `plasticos_transaction/views/transaction_views.xml` | 217 | grade_id | [nested_subview] <field name="grade_id"/> |
| TD-FIELD-092 | no | false_positive | `plasticos_transaction/views/transaction_views.xml` | 218 | description | [nested_subview] <field name="description"/> |
| TD-FIELD-093 | no | false_positive | `plasticos_transaction/views/transaction_views.xml` | 219 | sale_weight | [nested_subview] <field name="sale_weight"/> |
| TD-FIELD-094 | no | false_positive | `plasticos_transaction/views/transaction_views.xml` | 220 | weight_uom | [nested_subview] <field name="weight_uom"/> |
| TD-FIELD-095 | no | false_positive | `plasticos_transaction/views/transaction_views.xml` | 221 | sale_price | [nested_subview] <field name="sale_price"/> |
| TD-FIELD-096 | no | false_positive | `plasticos_transaction/views/transaction_views.xml` | 222 | sale_amount | [nested_subview] <field name="sale_amount" sum="Total Sale"/> |
| TD-FIELD-097 | no | false_positive | `plasticos_transaction/views/transaction_views.xml` | 223 | purchase_price | [nested_subview] <field name="purchase_price"/> |
| TD-FIELD-098 | no | false_positive | `plasticos_transaction/views/transaction_views.xml` | 224 | purchase_amount | [nested_subview] <field name="purchase_amount" sum="Total Purchase"/> |
| TD-FIELD-099 | no | false_positive | `plasticos_transaction/views/transaction_views.xml` | 225 | margin | [nested_subview] <field name="margin" sum="Total Margin"/> |
| TD-FIELD-100 | no | false_positive | `plasticos_web_leads/views/web_lead_config_views.xml` | 157 | target | [record_context_bleed] <field name="target">current</field> |
| TD-FIELD-101 | no | false_positive | `plasticos_web_leads/views/web_lead_config_views.xml` | 158 | res_id | [record_context_bleed] <field name="res_id" ref="web_lead_config_default"/> |

Actions:

- TD-SCAN-001: Teach scan_view_field_refs to enter a relational subview, to reset the model when a record ends, and to follow _inherit. Child TD-FIELD rows are the fixtures. Do not add these field names onto the model named in the message. Do not delete the view columns or the action records.
- TD-FIELD-001 … TD-FIELD-101 (101 rows, same action): No view edit. Use this row as a fixture for TD-SCAN-001. Do not declare this field on the parent model named in the message.

## INVALID_CONSTRAINT_FIELD

1 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-CONSTRAINT-001 | no | false_positive | `plasticos_transaction/models/transaction.py` | 507 | _check_override_pct_range | @api.constrains("commission_override_pct") |

Actions:

- TD-CONSTRAINT-001: Leave the stub. A scanner fix may follow _inherit across modules; that is separate work. Do not drop the decorator and do not redeclare the field on plasticos.transaction.

## AUTOMATION_LOG_PAYLOAD

1 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-DEF-D01 | yes | real_debt | `plasticos_intake_normalizer/models/intake_normalizer.py` | 619 | _log_normalization | AutoLog.create( |

Actions:

- TD-DEF-D01: Either map onto name, res_id, note, and an allowed action_type, or stop calling the log. Decide the shared schema before changing either model. Do not widen action_type with a normalize value only to silence the exception, and do not drop the try/except without a replacement record.

## PUBLIC_RPC

4 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-DEF-D02 | yes | policy_deferred | `plasticos_partner_import/models/partner_import_service.py` | 270 | run_csv_import | def run_csv_import(self, corporate_csv_path, facility_csv_path): |
| TD-DEF-D03 | yes | policy_deferred | `plasticos_geolocalize/models/res_partner_geo.py` | 38 | cron_geo_backfill | def cron_geo_backfill(self): |
| TD-DEF-D04 | yes | policy_deferred | `plasticos_crm_sync/models/crm_connection.py` | 121 | action_sync_now | def action_sync_now(self): |
| TD-DEF-D08 | yes | policy_deferred | `plasticos_matching/models/match_result_writer.py` | 24 | persist_match_lines | def persist_match_lines(self, intake, matches, *, match_run): |

Actions:

- TD-DEF-D02: If import stays an operator action, restrict the group or reject paths outside the configured import directory. If it is already server-only, prefix the methods with _ and update the one caller. Do not mark them private without updating every RPC and shell caller in the same change.
- TD-DEF-D03: Rename to _cron_geo_backfill and point the ir.cron code at the private name. Do not leave a public alias that calls the private method.
- TD-DEF-D04: Restrict action_sync_now to the group that is allowed to spend the VanillaSoft key, or require that group inside the method before building the adapter. Do not log the key. Do not remove the sudo on the ICP read unless the chosen group can already read system parameters.
- TD-DEF-D08: Rename to _persist_match_lines and update the orchestrator call if no UI action needs the public name. Do not weaken the receipt checks while renaming.

## SECRET_IN_QUERY

1 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-DEF-D05 | yes | real_debt | `plasticos_crm_sync/controllers/webhook.py` | 62 | _extract_token | q = req.httprequest.args.get("token") or "" |

Actions:

- TD-DEF-D05: Accept only X-Plasticos-Webhook-Token and Authorization: Bearer. Reject a query token. Do not log the token value while removing the query path.

## DOCSTRING_DRIFT

1 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-DEF-D06 | yes | documentation_misalignment | `plasticos_web_leads/controllers/web_lead_api.py` | 34 | WebLeadController | is safe because it happens only under sudo() after the token has been |

Actions:

- TD-DEF-D06: Rewrite the class note so it matches the pre-auth singleton read. Put '# sudo: public route reads config before auth' on line 171 if that elevation stays. Do not move get_config() to after auth as a drive-by. The pre-auth read is documented in the method itself at line 73.

## UNVERIFIED_ELEVATION

1 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-DEF-D07 | no | evidence_gap | `plasticos_commission/models/sales_dashboard.py` | 230 | _compute_doc_status | .sudo()  # sudo: read-only rep dashboard; document ACL is narrower |

Actions:

- TD-DEF-D07: On an Enterprise fixture, read documents.document as the dashboard group with and without sudo. Remove the sudo only if the read succeeds without it. Do not remove the sudo on a Community-only run. The model is absent there and the code falls back to plasticos.document.

## HOOK_SUDO

2 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-DEF-D10 | no | accepted_bounded_debt | `plasticos_automation/hooks.py` | 49 |  | .sudo() |
| TD-DEF-D10-WRITE | no | accepted_bounded_debt | `plasticos_automation/hooks.py` | 28 | _merge_automation_groups_into_settings | sys_group.sudo().write({"implied_ids": [(4, g.id) for g in missing]}) |

Actions:

- TD-DEF-D10: Leave them. A later hook cleanup can drop them in one mechanical change. Do not remove a single module's hooks sudo as part of an unrelated PR.
- TD-DEF-D10-WRITE: Leave the write. If the comment is moved, put it on this line. Do not drop the write. Settings would stop implying the automation groups.

## DUPLICATE_STATE_AUTHORITY

1 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-OWN-001 | no | scanner_misalignment | `scripts/audit/business_logic_audit.py` | 225 | check_state_machine_bypasses | def check_state_machine_bypasses(self): |

Actions:

- TD-OWN-001: Collapse them only when one predicate is shown to contain the other on a fixture pair. Until then leave both. Do not delete either checker while both are quiet. Do not add a third.

## XPATH_GUIDANCE

1 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-XPATH-001 | yes | scanner_misalignment | `ci/check_xpath_stability.py` | 51 | RISKY_PATTERNS | "Add [1] index: //div[@class='oe_title'][1]", |

Actions:

- TD-XPATH-001: Change that fix string to a named anchor. Do not add [1] to any view. Do not insert positional predicates into XML to satisfy this string.

## UNBOUNDED_SEARCH_LIMIT

4 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-SCAN-UB-001 | no | scanner_misalignment | `scripts/audit/performance_audit.py` | 310 | _search_verdict | A many-to-one equality (*_id = value) counts as an identity bound even when the field is categorical, for example country_id. |
| TD-SCAN-UB-002 | no | scanner_misalignment | `scripts/audit/performance_audit.py` | 310 | _search_verdict | A dynamic identity value is not proven non-null. False and None on an identity field are not a bound, but a name that might be null is st... |
| TD-SCAN-UB-003 | no | scanner_misalignment | `scripts/audit/performance_audit.py` | 310 | _search_verdict | A domain list passed into a helper that appends to it is not modelled. |
| TD-SCAN-UB-004 | no | scanner_misalignment | `scripts/audit/performance_audit.py` | 310 | _search_verdict | Aliasing (b = domain; b.append(...)) is not modelled. |

Actions:

- TD-SCAN-UB-001: Widen the identity rule only with a fixture where a categorical *_id equality currently suppresses a real full-table search. Do not weaken a current bounded verdict to chase this limit.
- TD-SCAN-UB-002: Leave the rule. A non-null proof needs a data model the scanner does not have. Do not weaken a current bounded verdict to chase this limit.
- TD-SCAN-UB-003: Leave the rule unless a real unbounded search is hiding behind a helper. Do not weaken a current bounded verdict to chase this limit.
- TD-SCAN-UB-004: Leave the rule unless a real unbounded search is hiding behind an alias. Do not weaken a current bounded verdict to chase this limit.

## ILLEGAL_FIELD_PARAMETER

2 item(s).

| ID | Remediate | Class | File | Line | Symbol | Code / message |
|---|---|---|---|---:|---|---|
| TD-TRACK-001 | yes | real_debt | `plasticos_logistics/models/freight_estimate.py` | 68 | status | tracking=True, |
| TD-TRACK-002 | yes | real_debt | `plasticos_logistics/models/freight_quote.py` | 541 | selected | selected = fields.Boolean(default=False, tracking=True) |

Actions:

- TD-TRACK-001: Delete tracking=True from status. Keep the column. The stored value and the load audit path stay. Do not add mail.thread to plasticos.freight.estimate. The model is immutable evidence and cannot post chatter.
- TD-TRACK-002: Delete tracking=True from selected. Keep the column. action_select remains the only writer. Do not add mail.thread to plasticos.freight.quote. Selection already writes the freight event on the load.
