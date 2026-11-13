# S10 evidence: Export displays and inputs, and the final coverage recount

Contract `PLASTICOS-EXPORT-C11-S10-EXPORT-FEATURES`.

- Contract digest: `sha256:2f2ec6c497d3ed1c2ad9e3d977103b1dce3ace0a6c9ad0d0b542ed7edde9aad2` (C11-STACK-BIND and C11-RULINGS-2026-11-12). Earlier freezes: `a09dcbf9…` (original), `a1675277…` (C11-SCOPE-2), `b85ee104…` (C11-SCOPE-3).
- Base: `fb1391d48f1ac4077946fec1fa739ebfe0f24a1e`, the accepted S9 head (`feat/plasticos-export-s9-logistics-features`, PR #489), merged into this branch with a merge commit. The slice is judged on `fb1391d4..head`.
- Part of the PlasticOS Export campaign; plan: `docs/campaigns/future-add-ons/PlasticOS_Export/STRATEGIC_EXECUTION_PLAN_v2.8.md`.

The S6, S7, S8 and S9 evidence folders are unchanged. This folder adds the S10 witnesses and the final recount.

## Files

| File | Contents |
| --- | --- |
| `S10_RULE_WITNESSES.csv` | Every S10 witness method, by case, rule and aspect. The C11-SCOPE-2 and C11-SCOPE-3 screen and see-all witnesses are included. |
| `FINAL_COVERAGE_RECOUNT.csv` | All 120 cases. Phase 1 cases are `cited` with the slices that witness them, or `NOT_RUN` with their blocker. Phase 2 cases are out of scope. |

## What S10 adds

All facts are read from their owners as the acting user and are never stored by Export. A fact the user may not read shows a restricted marker, never a blank or a zero.

- **BRS-EXP-01-R002** (positive and negative). The cargo link shows:
  - the Documents verdict for each Export obligation;
  - the Logistics load status;
  - the native stock move line and its package;
  - posted customer invoices and vendor bills.
- **BRS-EXP-07-R006**. The slot shows native Stock package totals and the package type nominal weight (Stock `base_weight`, summed per package; not a tare measurement), labelled as not a certified VGM, and the Documents VGM verdict. It also shows the container tare and VGM weight that Logistics records on the bound journey (`plasticos.iso.journey.fact`, S9).
- **BRS-EXP-02-R006**. The cargo link stores the quoted FOB, FAS or CNF trade label and its wording. It is edited in its own dialog and audited on the booking. The order Incoterms are shown and never written.
- **BRS-EXP-09-R001**, manual fallback. Record Booking Candidate hands typed terms to `record_booking_revision_candidate` with every command guard. Native Documents AI is not activated.
- **BRS-EXP-14-R011**. A read-only projection lays out the 43 legacy headings, grouped by booking, with an explicit Missing, Unknown, Not recorded, Not mapped, Phase 2 or Restricted marker in every cell.
  - The synthetic workbook `plasticos_export/tests/data/synthetic_booking_report.xlsx` is written byte-stably by `generate_synthetic_booking_report.py` in the same folder. Every value is invented there: `SYN-`/`SYNU` numbers, `Synthetic` parties, `Port Alpha`/`Port Beta`, 2030 dates. The private original workbook was never opened.
  - The heading names were read once from `EXPORT_BRS/SOURCES/LEGACY_REPORT_43_COLUMN_MAPPING.csv`. No test reads `docs/campaigns`.
- **BRS-EXP-08-R007**, Export side. A buyer assigned to a container already afloat is a new cargo link that replaces the buyerless one, through S8's `replaces_link_id` on the Commit Cargo screen. The slot's shipment history shows the unchanged Logistics gate-in, departure and filing parties, then every allocation, oldest first. The booking revision and the journey facts do not move.
- **C11-SCOPE-2 (OP10-E05)**. The Commit Cargo, Release Cargo and Bind Container screens are Logistics-only. Each calls its existing command as the acting user, stores nothing, and applies a double click once.
- **C11-SCOPE-3 (OP10-E06)**:
  - Booking search by container and seal goes through the slot's sudo-related fields.
  - Only users who can read the container journey get an openable journey and the Open Container Journey button: Logistics, Operations Manager (which implies Logistics) and System.
  - The Export dialog offers a user outside Logistics no cargo-link source link. A user who cannot read the journey is not offered the slot's journey either.

## Final recount (103 Phase 1 cases, 18 S6 primary rules)

| Set | Cited | NOT_RUN | Out of scope |
| --- | --- | --- | --- |
| Phase 1 cases (103) | 100 | 3 | — |
| Phase 2 cases (17) | — | — | 17 |
| S6 primary rules (18) | 15 | 3 | — |

All 16 cases that S6 recorded as DEFERRED_COVERAGE_DEBT now have witnesses:

| Slice | Cases it closes |
| --- | --- |
| S8 | 01-004, 06-001, 06-003, 08-002, 08-003, 08-004, 08-006, and the negatives of 01-002, 02-006 and 07-006 |
| S9 | 07-002, 08-007, 09-007, 11-010, and the 07-006 owner facts |
| S10 | the positives of 01-002, 02-006 and 07-006, the Export side of 08-007, 09-001 (manual fallback) and 14-011 |

What remains NOT_RUN:

- **AC-EXP-09-001, native Documents AI path.** The manual fallback is cited. The native AI activation is held for a separate operator decision, because it calls an external AI service.
- **AC-EXP-06-004** and **AC-EXP-06-005.** These are governance and process rules, proven by PR and evidence review.
- **AC-EXP-01-005.** This is not a process rule. There is no Community Edition environment, and the runtime is the pinned Enterprise fixture only. That S6 blocker is unchanged and is reported here as it stands.

## Runtime

All runs use the pinned Enterprise fixture `odoo_test_tpl_ee_c9e8a81f52f23680`, cloned to `odoo_test_wd2a49b169c`. Receipts are written by `scripts/test_env.sh` to `.l9/runtime/test-env/` (gitignored).

| Run | Head | Receipt | Result |
| --- | --- | --- | --- |
| Contract runtime, `make runtime-test m=plasticos_export,plasticos_logistics,plasticos_documents,plasticos_transaction` | `f1e3255e44260d6b83e099cc9b483bfdec4f1fa1` | `dirty: false`; addon source digest `f238ea51240b6b41e34d77a64ccc8207fbfcca289b0cdf9c475cb8cf03d2a96f`; receipt sha256 `f8e5a6ba…` | 612 run, 0 failed, 0 errors |
| First publication of PR #494, `PR_SMOKE=1 PR_REMEDIATE=0 make pr` | `24dfde64e54d66d969cea0a0ff477241275f1a3a` | install-smoke PASSED; whole roster (`make test-odoo`) | 1668 run, 0 failed, 0 errors |

The review fixes after the first publication (B1, I1, I2, I3, N1 to N6) are covered by the contract runtime row. The republication's own `make pr` gate reruns install-smoke and the roster on the final head. The commit that adds this section changes documentation only, so the addon source digest above still holds.

On `f1e3255e`: `pytest tests/` gives 3076 passed, 49 skipped; `make audit-baseline` reports no new finding; pre-commit passes on every file changed against the S9 head.

## Who sees container facts

Container weights and identities stay with Logistics. A user who cannot read the Logistics journey facts (only Logistics, which Operations Manager implies, and System can after the S9 review) sees "Restricted" for the container tare, the VGM weight and the shipment-history container facts, and gets no journey link. Export adds no sudo to show them. The operator's see-all rule covers allocations, so a Sales Rep still sees every cargo allocation on every booking through the `*_ref` names and can plan without overbooking (coordinator ruling 2026-11-12).

On the slot form and the shipment list, `journey_id` is omitted for non-readers. This is stricter than no_open, because a Many2one renders its display name under sudo (coordinator-confirmed 2026-11-12).

## Recorded for the operator, not changed here

- `plasticos_partner_import/erp/native_orders.py:599-608` maps the recycler basis "fob"/"fas" onto the legal Incoterm. This is outside Export and is untouched (contract unresolved unknown).
- At S9 head `ad9d35e5`, `access_iso_journey_fact_user` gave every internal user read on `plasticos.iso.journey.fact`. S9 review B1 removes it. The S10 witnesses follow the owner ACL, so they hold on both heads.
