# Execution status audit — 2026-11-03

**Audited against:** local `Staging` working tree at `8b1483cb2c098ba6c0308508c3f2615f96d6ce73`
(`origin/Staging` `9ee917e7521d64d0e759afd2fdef8198d4c32b30`).
**Audit scope:** pack documents only were mutated. No codebase file was changed by this audit.

## Verdict

**SUPERSEDED — IMPLEMENTED UPSTREAM.** The campaign's mission (domestic 0..N
load-per-transaction cardinality with a single load-owned FK) was implemented and merged
into `Staging` on 2026-10-29 through the PR chain ending in
[PR #339](https://github.com/cryptoxdog/IB-Odoo_19/pull/339)
(`2dc516aa29718b4545faf67e79ca225589ac6d7f`,
"test(logistics): accept the lock-table names and the reviewed loop queries").
This pack was never activated: `08_EXECUTION_RECEIPT_TEMPLATE.json` is unfilled, and no
branch named `fix/domestic-multiload-foundation` exists. The work landed outside this
contract's ceremony but satisfies its architecture.

The pack's source census **was accurate at its baseline**. At
`04bd0594a7c9dcad53d9c45fc65276d76817c112` (2026-10-27), `transaction_inherit.py` carried
the stored singular `load_id` Many2one with the `UNIQUE (load_id)` constraint exactly as
`03_SOURCE_AND_CONSUMER_CENSUS.md` records. Every root defect and consumer hazard it
names has since been resolved.

## Per-claim disposition (verified 2026-11-03)

| Claim | Current state | Disposition |
|---|---|---|
| ML-ROOT-01 single-slot `transaction.load_id` + UNIQUE | Field removed entirely. `transaction_inherit.py` now defines `load_ids` One2many (inverse `transaction_id`) + `load_count`. | RESOLVED |
| ML-ROOT-02 create/write reverse recompute | Gone. No `_compute_transaction_id` recompute path remains. | RESOLVED |
| ML-ROOT-03 single-field guards / `action_view_load` | Replaced by `action_view_loads` (empty set stays empty; single opens form; many open list). | RESOLVED |
| ML-ROOT-04 stored computed reverse `load.transaction_id` | Now a plain stored Many2one, `ondelete="restrict"`, documented as the one canonical parent. | RESOLVED |
| ML-ROOT-05 `load.create` `setdefault` first-pick | Replaced by `_link_unique_sale_order_transaction`: zero candidates stay unlinked, >1 raises `ValidationError`, exactly one links after identity + milestone checks, with row locking against races. | RESOLVED |
| ML-CONS-01 state lock / delivery-term compute | Reparent protection via `_parent_link_is_protected` (dispatched or evidence-bearing loads cannot be moved or cleared). | RESOLVED |
| ML-CONS-02 cron/action `limit=1` tx search | `action_view_transaction` reads `self.transaction_id` directly; dispatch-ack cron searches loads, not transactions-by-load. | RESOLVED |
| ML-CONS-03 dashboard SQL old join | `load_dashboard.py` joins `plasticos_transaction t ON t.id = l.transaction_id`, probing `plasticos_load.transaction_id` for first-install fallback; one row per load. | RESOLVED |
| ML-CONS-04 claim `load_id` related field | Now a real optional Many2one with an `@api.constrains` requiring `load_id.transaction_id == transaction_id`; onchange clears mismatches. Generic transaction claims stay unallocated. | RESOLVED |
| ML-CONS-05 claim trigger `limit=1` | `document_inherit._check_claim_trigger` resolves the load's actual owner; load attribution travels on the claim values. | RESOLVED |
| ML-CONS-06 `_get_related_transactions` guessing | Resolves via `record.load_id.transaction_id`; no `search(..., limit=1)` by legacy FK. | RESOLVED |
| ML-CONS-07 scale-ticket cron single-load read | `transaction_docs.py` depends on `load_ids` and iterates per-load retry sets. | RESOLVED |
| ML-CONS-08 native bridge recency matching | `_auto_link_partner` short-circuits when `transaction_id` or `load_id` is already set; exact links preserved. | RESOLVED |
| ML-CONS-09 freight context per-load | Freight quote/governance/context remain load-scoped; provenance fields are create-protected. | RESOLVED |
| ML-CONS-10 financials double-count | No stored recompute from load count was introduced; economics unchanged. | RESOLVED |
| ML-CONS-11 SO→tx ambiguity | `_eligible_transactions` requires supplier+buyer and same SO; ambiguity refuses, `_reconcile_unlinked_for_transactions` links late singles only. | RESOLVED |
| ML-CONS-12 single-`load_id` views | `transaction_load_views.xml` shows `load_ids` list + `load_count` statinfo. | RESOLVED |
| ML-CONS-13 migration | `plasticos_logistics/migrations/19.0.1.14.6/` pre+post migrate copy historical `transaction.load_id` → `load.transaction_id`, refusing on any disagreement (fail-closed, replay-safe). Module now at `19.0.1.14.10`. | RESOLVED |
| ML-CONS-14 cardinality tests | `test_load_cardinality.py` covers 25+ cases: two loads on one transaction, ambiguity refusal, cross-company refusal, protected-link immutability, milestone gating, migration conflict refusal, and three concurrency races. | RESOLVED |
| ML-CONS-15 bridge contract singleton assertions | `test_bridge_wiring_contracts.py` now asserts `load_id` is ABSENT and `load_ids` is the One2many inverse of `transaction_id`; `test_bridge_contracts.py` matches. | RESOLVED |
| ML-CONS-16 `load.company_id` SO derivation | Unchanged by design (`related="sale_order_id.company_id"`); cross-company joins are refused in `_parent_identity_error`. | CONFIRMED AS-DESIGNED |
| ML-CONS-17 state/dispatch guards | `_transition`, freight events and dispatch guards intact; `_FREIGHT_PROVENANCE_FIELDS` create-guard added. | RESOLVED |

## Residual notes

- The predecessor Documents PR dependency (§2 of the coding contract) is moot: the Documents
  exact-evidence representation this pack depends on is present in current `Staging`
  (`plasticos_documents/models/document.py` `ASSOCIATION_IDENTITY`, association-state model).
- `05_REQUIRED_ACCEPTANCE_MATRIX.json` (32 probes) was never executed through this pack's
  ceremony. Equivalent behavior is covered by the merged test suite above; anyone claiming
  THIS pack's acceptance must still run the matrix, but there is no remaining code mission.
- Do not execute this pack. It is retained as a historical contract record. Any future
  multi-load work (Export bookings, many-to-many assignment) requires a new contract.
