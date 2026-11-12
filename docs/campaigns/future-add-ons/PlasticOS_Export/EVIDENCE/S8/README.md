# S8: coverage witnesses and the double-allocation guard

Contract `PLASTICOS-EXPORT-C08-S8-COVERAGE-AND-ALLOCATION-GUARD` (sha256 `b85f2ef4143696dd3f3b860f8ff97b377ea3f3502c04e79981119a96f10ddaa0`), base `ff42df2deaa85ce6354740dda1df00db8413a2ea`, branch `feat/plasticos-export-s8-coverage`, `plasticos_export` 19.0.1.1.1 → 19.0.1.1.2 on the branch, then 19.0.1.1.3 after merging S7 (which also took 19.0.1.1.2).

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

## Not in S8

- Native Documents AI stays `NOT_RUN` (operator decision pending).
- The rules S6 marked `NOT_RUN` with a real blocker (BRS-EXP-01-R005, BRS-EXP-06-R004/R005) are unchanged.

## Runtime

- Branch tree before the S7 merge (dirty source `b6c35f64…`, base `ff42df2d`): `make runtime-test m=plasticos_export` on a clone of `odoo_test_tpl_ee_c9e8a81f52f23680`. Result: 74 run, 0 failed, 0 errors. Receipt `.l9/runtime/test-env/odoo_test_w9f0caa25be.test-receipt.json`.
- Index build: the `-u plasticos_export` upgrade created both partial unique indexes on the fixture's seeded data with no constraint warning. `test_replaced_link_frees_its_source` reads them back from `pg_indexes`. `plasticos_export` ships no migration in this slice.
- Concurrency: the test cursor cannot run two committing transactions at once. The race is therefore witnessed in three ways:
  - at the database: a raw second insert of a live move line raises `UniqueViolation`;
  - at the ORM: a guarded `create` raises `ValidationError`;
  - at the command: a second commit returns `blocked`.

  The command also row-locks the sources (`lock_for_update`, `SKIP LOCKED`), so a concurrent commit gets `blocked: cargo_source_busy`.

### Merged tree (S7 merged at `034f8b2d`)

- S7 (PR #482, head `6218a7d2`) was merged with a merge commit. `plasticos_export` is 19.0.1.1.3, because S7 took 19.0.1.1.2.
- First four-module run on the merge (`m=plasticos_export,plasticos_logistics,plasticos_documents,plasticos_transaction`): 545 run, **8 failed**, 0 errors. All 8 are S7 Sales Rep tests in `test_multicompany_permissions.py`, and all of them fail at the precondition of S7's `_shared_allocations` fixture. That fixture planned 40000 lb and 38000 lb against SO lines of 1 Unit, and 38000 lb against a 700 lb PO line. The S8 guard refuses this, as BRS-EXP-08-R006 requires.
- Classification: fixture defect from the S7/S8 interaction, not a product defect. Coordinator ruling: the guard stays as built.
- Fix in commit `020812b9`: data only. The fixture's SO lines are now 40000 lb and 38000 lb, and its PO line is 38000 lb. Every S7 assertion is byte-identical.
- Rerun at clean head `020812b9`: 545 run, **0 failed, 0 errors**. Receipt `.l9/runtime/test-env/odoo_test_w9f0caa25be.test-receipt.json` (source `10a8a4b1…`, dirty false).
- Static checks on the merged tree: `pytest tests/` 3076 passed, 49 skipped, 0 failed; `pre-commit run` on every file changed since `ff42df2d`: pass; `make audit-baseline`: no new finding.
- `test_allocation_guard.py::TestAllocationGuard::test_planned_quantity_never_exceeds_the_order_line` already witnesses the refusal of an allocation planned beyond its SO line or PO line.
