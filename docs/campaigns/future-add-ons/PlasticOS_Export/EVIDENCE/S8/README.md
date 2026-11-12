# S8: coverage witnesses and the double-allocation guard

Contract `PLASTICOS-EXPORT-C08-S8-COVERAGE-AND-ALLOCATION-GUARD`. It was issued at sha256 `b85f2ef4…` on base `ff42df2d`, re-bound to base `6218a7d2` (`f07415c5…`, coordinator:C08-STACK-BIND), and re-frozen as SCOPE-2, sha256 `c4e129b15f2c1005d7f34066d71e4b74884924cf3049a1ac5a7fdc498cd73111`, branch `feat/plasticos-export-s8-coverage`, `plasticos_export` 19.0.1.1.1 → 19.0.1.1.2 on the branch, then 19.0.1.1.3 after merging S7 (which also took 19.0.1.1.2).

This note maps each rule S8 closes to its witness test method. These rules were `DEFERRED_COVERAGE_DEBT` in `../S6/S6_PRIMARY_RULE_WITNESSES.md`. The machine-readable form is `S8_RULE_WITNESSES.csv`. Runtime receipts are listed under "Runtime".

## Native fixture

`plasticos_export/tests/native_fixture.py::NativeExportFixtureMixin` builds every record through its native owner on the pinned Enterprise fixture:

- a storable product sold as whole loads (1 Unit = 1 load);
- a confirmed 30-load customer SO, and two confirmed 4-load supplier POs from different suppliers;
- weekly receipts that leave native backorders, and a partial SO delivery;
- a posted customer invoice;
- a verified `plasticos.document` on a Logistics load.

Export slots come from an accepted revision, and cargo is committed only through `action_commit_cargo`.

## Rules closed

| Rule | Case | Witness |
| --- | --- | --- |
| BRS-EXP-01-R002 (negative) | AC-EXP-01-002 | `plasticos_export/tests/test_native_coverage.py::TestNativeCoverage::test_single_fact_owner_export_stores_no_second_fact` |
| BRS-EXP-01-R004 | AC-EXP-01-004 | `plasticos_export/tests/test_native_coverage.py::TestNativeCoverage::test_acceptance_writes_no_order_stock_or_load` |
| BRS-EXP-02-R006 (negative) | AC-EXP-02-006 | `plasticos_export/tests/test_native_coverage.py::TestNativeCoverage::test_export_never_writes_an_order_incoterm` |
| BRS-EXP-06-R001 | AC-EXP-06-001 | `plasticos_export/tests/test_native_coverage.py::TestNativeCoverage::test_company_and_audience_isolation_on_native_sources` |
| BRS-EXP-06-R003 | AC-EXP-06-003 | `plasticos_export/tests/test_native_coverage.py::TestNativeCoverage::test_order_shipment_and_invoice_states_stay_scoped` |
| BRS-EXP-07-R006 (negative) | AC-EXP-07-006 | `plasticos_export/tests/test_native_coverage.py::TestNativeCoverage::test_slot_carries_no_payload_or_vgm` |
| BRS-EXP-08-R002 | AC-EXP-08-002 | `plasticos_export/tests/test_native_coverage.py::TestNativeCoverage::test_one_customer_commitment_with_smaller_supplier_orders` |
| BRS-EXP-08-R003 | AC-EXP-08-003 | `plasticos_export/tests/test_native_coverage.py::TestNativeCoverage::test_partial_purchase_fulfilment_through_native_backorders` |
| BRS-EXP-08-R004 | AC-EXP-08-004 | `plasticos_export/tests/test_native_coverage.py::TestNativeCoverage::test_partial_sale_fulfilment_and_unvalidated_booking_association` |
| BRS-EXP-08-R006 (positive) | AC-EXP-08-006 | `plasticos_export/tests/test_allocation_guard.py::TestAllocationGuard::test_four_executed_loads_traced_to_four_bookings` |
| BRS-EXP-08-R006 (no double allocation) | AC-EXP-08-006 | `plasticos_export/tests/test_allocation_guard.py::TestAllocationGuard::test_received_load_cannot_be_allocated_twice` |
| BRS-EXP-08-R006 (replaced link frees its source; partial indexes) | AC-EXP-08-006 | `plasticos_export/tests/test_allocation_guard.py::TestAllocationGuard::test_replaced_link_frees_its_source` |
| BRS-EXP-08-R006 (concurrent quantity bound, review B3) | AC-EXP-08-006 | `plasticos_export/tests/test_allocation_guard.py::TestAllocationGuard::test_commits_on_one_order_line_serialize_on_one_claim_row` |
| BRS-EXP-08-R006 (cross-booking correction, review N4) | AC-EXP-08-006 | `plasticos_export/tests/test_allocation_guard.py::TestAllocationGuard::test_correction_across_bookings_checks_the_other_booking` |
| BRS-EXP-01-R004 / 02-R006 (witness self-test, review B1) | AC-EXP-01-004 | `plasticos_export/tests/test_native_coverage.py::TestNativeCoverage::test_stamps_detect_any_stored_field_write` |
| BRS-EXP-08-R006 (no over-allocation) | AC-EXP-08-006 | `plasticos_export/tests/test_allocation_guard.py::TestAllocationGuard::test_planned_quantity_never_exceeds_the_order_line` |
| BRS-EXP-08-R006 (attributed corrections and splits) | AC-EXP-08-006 | `plasticos_export/tests/test_allocation_guard.py::TestAllocationGuard::test_correction_and_split_are_attributed` |
| BRS-EXP-08-R006 (concurrency) | AC-EXP-08-006 | `plasticos_export/tests/test_allocation_guard.py::TestAllocationGuard::test_double_commit_past_the_command_is_refused` |
| BRS-EXP-09-R007 (negative) | AC-EXP-09-007 | `plasticos_export/tests/test_native_coverage.py::TestNativeCoverage::test_no_direct_state_write_on_load_or_transaction` |
| BRS-EXP-11-R010 | AC-EXP-11-010 | `plasticos_export/tests/test_native_coverage.py::TestNativeCoverage::test_shipment_guard_and_native_po_remaining_balance` |

## The BRS-EXP-08-R006 guard

The guard lives in `plasticos_export/models/booking_allocation.py`. Its rules:

- **One live link per physical source.** A Logistics load or a stock move line sits on at most one live cargo link. Every state except `released` counts as live.
- **No over-allocation.** The known planned quantities on one PO or SO line, converted to that line's unit, never exceed the line's own quantity. A unit that does not convert is refused.
- **Concurrency.** The command row-locks the cargo sources before it checks.
- **Backstops.** `create` and a model constraint repeat the check, so any guarded write gets the same refusal. Two partial unique indexes (`_one_live_link_per_load`, `_one_live_link_per_move_line`) refuse a second transaction that bypassed the ORM.
- **Corrections and splits.** These pass `replaces_link_id` and `correction_reason` in `source_refs`. The replaced link is released, never edited. Each new part records `replaces_link_id`. The booking chatter names the user and the reason.
- **Public shape.** No public command, field or model was added, renamed or removed.

How refusals reach the caller:

- **Through the command:** the command returns the frozen `blocked` result with the reason.
- **Through any other path:** `create`, or the model constraint on a write, raises `ValidationError`, which is a `UserError`.

## Seventh registry model (C08 SCOPE-2, OP8-E03)

`plasticos_export` now defines `plasticos.export.source.line.claim`. It is an internal row, one per PO or SO line that cargo plans quantity on, and it exists only to serialize concurrent commits for the BRS-EXP-08-R006 quantity bound.

- It stores no quantity. Planned quantities stay on the cargo links, and the order quantity stays on the native line.
- It has no view, menu, action or command. Only `action_commit_cargo` writes it, through one upsert in `booking_allocation.py`.
- Logistics and Operations Manager have read-only ACL rows; Sales Reps have none.
- The public shapes of TECHNICAL_CONTRACT_v2.7 are unchanged: E1–E4, J1–J2 and the twelve commands. The coordinator confirmed on 2026-11-12 that OP8-E03 governs this model.
- `test_install.py` (`MODELS` and the `DECLARED` ir.model.access ids) and `test_export_owner_handoff.py` (the model inventory) pin the module's inventory. Each changed only by this model and its two ACL ids.

## Review fixes (#483 at `3fda2e04`, coordinator:C08-SCOPE-2)

- **B1:** `stamps()` now compares each native row's `ctid`. Inside one test transaction `write_date` is constant, so it could not see a write; `ctid` changes on any UPDATE. The self-test `test_stamps_detect_any_stored_field_write` proves that a write to a non-state field is detected. The 01-R004 and 02-R006 witnesses now watch orders, order lines, pickings, moves, move lines, the transaction and the load.
- **B2:**
  - 08-R003 commits cargo through `action_commit_cargo` on each weekly receipt. It asserts that no PO, PO line or receipt row changed and that no PO or PO line was created, and that no Export field stores a receipt counter.
  - 08-R004 commits a move line from an assigned picking that is not done. It asserts that the picking state, the reservation and `qty_delivered` are unchanged. The tautological assertion is removed.
- **B3:** the claim row described above.
- **N1:** the supplier price is now 987.65, and every rounding of it is checked absent from the booking sheet and the PO display. A Logistics reader cannot read a native Documents original or a supplier bill.
- **N3:** the dozen-unit check is unconditional.
- **N4:** the cross-booking correction is locked and checked for currentness.
- **N6:** the two constants are distinct by name: `SOURCE_CLAIM_LINK_STATES` (proposed, committed, held; the allocation guard) and `PHYSICAL_HOLD_LINK_STATES` (committed, held; physical instructions).
- **Recorded, no code:**
  - N2: the field scan covers only Export's own models.
  - N5: indexes build through `post_constraint`. Any future database that installs S5–S7 alone before S8 needs a duplicate census.
  - N7: move-line quantity is not bounded by contract.
  - N8: superseded by B3.
  - N9: 06-R003 has no gate receipt.
- **Runtime of the fixes:** the four-module run gave 548 run, 0 failed, 0 errors. The first run had 2 failures, the pinned model inventories, and 1 error, a self-test field name. Both were fixed as described above.

## Not in S8

- Native Documents AI stays `NOT_RUN` (operator decision pending).
- The rules S6 marked `NOT_RUN` with a real blocker (BRS-EXP-01-R005, BRS-EXP-06-R004/R005) are unchanged.

## Runtime

- Branch tree before the S7 merge (dirty source `b6c35f64…`, base `ff42df2d`): `make runtime-test m=plasticos_export` on a clone of `odoo_test_tpl_ee_c9e8a81f52f23680`. Result: 74 run, 0 failed, 0 errors. Receipt `.l9/runtime/test-env/odoo_test_w9f0caa25be.test-receipt.json`.
- Index build: the `-u plasticos_export` upgrade created both partial unique indexes on the fixture's seeded data with no constraint warning. `test_replaced_link_frees_its_source` reads them back from `pg_indexes`. `plasticos_export` ships no migration in this slice.
- Concurrency, layer by layer. This list supersedes the earlier claim, which review B3 of #483 at `3fda2e04` showed was too broad.
  - **Same load or same stock move line, two transactions:** the partial unique indexes `_one_live_link_per_load` and `_one_live_link_per_move_line` refuse the second live link at commit, whatever the snapshot. Witness: a raw second insert raises `UniqueViolation` (`test_double_commit_past_the_command_is_refused`).
  - **Same PO or SO line, quantity bound, two transactions (review B3):** each commit that plans a known quantity first upserts and bumps the line's one Export-owned row, `plasticos.export.source.line.claim`, with `INSERT … ON CONFLICT DO UPDATE`. Only then does it count the line's live links. At REPEATABLE READ, a second transaction whose snapshot predates the first commit blocks on that row. It then fails to serialize and is retried by Odoo, and the retry counts the first link. No native PO or SO row is written.
    - Witness `test_commits_on_one_order_line_serialize_on_one_claim_row`: two commits on one line bump one row, the second counts the first one's quantity, and the native rows' `ctid` is unchanged.
    - The serialization failure itself needs two committing transactions, so it is not run inside a TransactionCase. It follows from PostgreSQL's documented REPEATABLE READ upsert behaviour.
  - **The row locks taken before the check (`lock_for_update(allow_referencing=True)`, `SKIP LOCKED`):** they only refuse a commit while another transaction holds the same source in flight (`blocked: cargo_source_busy`). Alone they do not serialize the quantity bound. That is the claim row's job.
  - **Any guarded `create` or write:** the `create` backstop and `@api.constrains` raise `ValidationError`. This is a check within one transaction, not a concurrency control.
  - **A correction that replaces cargo on another booking (review N4):** that booking is locked, and `replaced_booking_revision_id` must name its current revision. Otherwise the result is `stale` and nothing is released (`test_correction_across_bookings_checks_the_other_booking`).

### Merged tree (S7 merged at `034f8b2d`)

- S7 (PR #482, head `6218a7d2`) was merged with a merge commit. `plasticos_export` is 19.0.1.1.3, because S7 took 19.0.1.1.2.
- First four-module run on the merge (`m=plasticos_export,plasticos_logistics,plasticos_documents,plasticos_transaction`): 545 run, **8 failed**, 0 errors. All 8 are S7 Sales Rep tests in `test_multicompany_permissions.py`, and all of them fail at the precondition of S7's `_shared_allocations` fixture. That fixture planned 40000 lb and 38000 lb against SO lines of 1 Unit, and 38000 lb against a 700 lb PO line. The S8 guard refuses this, as BRS-EXP-08-R006 requires.
- Classification: fixture defect from the S7/S8 interaction, not a product defect. Coordinator ruling: the guard stays as built.
- Fix in commit `020812b9`: data only. The fixture's SO lines are now 40000 lb and 38000 lb, and its PO line is 38000 lb. Every S7 assertion is byte-identical.
- Rerun at clean head `020812b9`: 545 run, **0 failed, 0 errors**. Receipt `.l9/runtime/test-env/odoo_test_w9f0caa25be.test-receipt.json` (source `10a8a4b1…`, dirty false).
- Static checks on the merged tree: `pytest tests/` 3076 passed, 49 skipped, 0 failed; `pre-commit run` on every file changed since `ff42df2d`: pass; `make audit-baseline`: no new finding.
- `test_allocation_guard.py::TestAllocationGuard::test_planned_quantity_never_exceeds_the_order_line` already witnesses the refusal of an allocation planned beyond its SO line or PO line.
