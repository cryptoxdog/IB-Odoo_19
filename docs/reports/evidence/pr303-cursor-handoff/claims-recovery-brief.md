# Brief A: Claim chargebacks and lightweight penalties

**Baseline:** `702ebaf77d987dc844e2758bd354b2ecef4f26cd`.

**Evidence class:**
- **OBSERVED (static):** read-only source reading with file:line citations.
- **OBSERVED (CE runtime):** only the failing assertions, which come from the local Community run.
- **HYPOTHESIS:** statements marked as inference.

**Operator decision (2026-10-25):** BUSINESS_SEMANTICS_UNRESOLVED.
- Do not convert the fields to computed values, change margin calculations, backfill or automate claim-to-margin.
- Preserve manual values. Archiving must not erase a recognized recovery.
- Rationale: a resolved claim does not establish that a credit was received, booked or recognized, and auto-recognition risks unrealized or double-counted recoveries.

## Failing tests — OBSERVED (CE runtime)

| Test | Assertion | Expected | Actual |
|---|---|---|---|
| `plasticos_claims/tests/test_depends_transaction_claims_bridge.py::TestTransactionClaimsBridgeDepends.test_freight_chargeback_recovery_flows_to_transaction` | line 75 | 125.0 | 0.0 |
| `plasticos_claims/tests/test_depends_transaction_claims_bridge.py::TestTransactionClaimsBridgeDepends.test_lightweight_penalty_recovery_flows_to_transaction` | line 84 | 75.0 | 0.0 |

The test at `:86-89` passes only because the value is always 0.

These tests never ran before this PR:
- They were moved by commit `7fb71df` from the root `tests/` tree (never collected by Odoo) into `plasticos_claims/tests/`.
- The PR did not edit them.

## 1. Intended behaviour (as stated in code)

**Facts:**
- The fallback method's docstring says that with claims installed, the override "uses @api.depends(...) for automatic updates when claims are resolved" (`plasticos_transaction/models/transaction.py:833-842`).
- The override's docstrings say the same, labelled "Issue 4 fix" (`plasticos_claims/models/transaction_claims.py:3-5`, `51-62`).
- `action_resolve` deliberately does not push the values itself. Its docstring relies on that recompute (`plasticos_claims/models/claim.py:286-293`) and mentions `_update_transaction_recoveries()`, which exists nowhere in the repo.
- The test file pins the same contract in its docstring (`test_depends_transaction_claims_bridge.py:13-15`).
- `plasticos_security_base/tests/test_bridge_contracts.py:589-602` treats `case_type` and `recovery_amount` as inputs to this compute.
- The field help text describes carrier and supplier credits (`transaction.py:333-340`). The `gross_margin` help says "Revenue - costs + chargebacks + penalties" (`transaction.py:406`).

**Docs:** no ADR, business rule, README, `INVARIANTS.md` or `ARCHITECTURE.md` describes the behaviour.
- `ARCHITECTURE.md:81`, `AGENTS.md:210` and ADR-006:34 only say "claims, chargebacks".
- `plasticos_transaction/README.md:85` gives an outdated `gross_margin` formula without recoveries.
- The only statements of intent are the docstrings above.

**Inference (HYPOTHESIS):** the code's authors intended recoveries to come from resolved claims, with the plain fields in the base module only a placeholder for when `plasticos_claims` isn't installed.

The operator has explicitly **not** accepted this as business intent (Decision A).

## 2. Current implementation (why it fails)

- Both fields are plain `fields.Float` with no `compute=` (`transaction.py:333-340`). The same holds at the oldest commit in the clone (`f53d3cd`, lines 323-330).
- No field names `compute="_compute_chargebacks_penalties"`, and `git log -S` finds no commit that ever added it. So both the fallback (`transaction.py:832`) and the override (`transaction_claims.py:45-70`) are dead code; an `@api.depends` on a method no field uses never fires.
- The override sums claims on the transaction with `state == "resolved"` only:
  - `freight_chargebacks` takes their `recovery_amount` where `case_type == "freight_chargeback"`.
  - `lightweight_penalties` takes it where `case_type == "lightweight_penalty"`.
- Claim fields involved:
  - `case_type` (`claim.py:46-59`).
  - `state`: pending, in_progress, escalated, resolved, archived (`claim.py:73-86`).
  - `recovery_amount`, a plain Float (`claim.py:129-132`).
- Precedent: `has_quality_claim` is a plain field in the base module (`transaction.py:310-316`), re-declared with `compute=..., store=True` in claims (`transaction_claims.py:24-28`). Its test (`:58-66`) in the same file passes.

## 3. Every writer and reader

**Writers:**
- The only real writer is a person editing the transaction form. The fields are editable at `plasticos_transaction/views/transaction_views.xml:168` and `:173`; the claims view extension does not make them read-only.
- No ERP import, script, migration, data XML or cron writes them:
  - `sale_inherit.py:95-107` writes only `freight_actual`, `other_expenses` and the commission lock.
  - `transaction_import_service.py:148-264` writes the transaction header and lines only.
  - `plasticos_partner_import` never writes `plasticos.transaction` (its `README.md:28`).
  - The ERP's own chargebacks arrive as signed vendor or customer credit notes and as `other_expenses` (`native_document_import.py:810-877`, `925-1000`; `_signed_move_total` at `transaction.py:17-23`).
  - The "FEES & CHARGEBACKS" rows in `ERP.WksDetail.csv` become historical lines only. Worksheet 58699 (`native_orders.py:449-451`) is a selection pin, not a field write.
- So no other code path fills these fields. Making them computed would not overwrite imported values, but it **would overwrite hand-typed ones**.

**Readers:**
- `_compute_financials`: depends at `transaction.py:790-791`, used at `:814-818`.
- The form view (`:168`, `:173`).
- Source-level view tests (`tests/test_transaction_profit_snapshot.py:55,58`, `test_transaction_form_ui.py:90,93`), which check presence and order only.
- No SQL view, dashboard or report reads the two fields directly.

## 4. Downstream chain

```
claim.state / case_type / recovery_amount  (currently not connected)
  → freight_chargebacks, lightweight_penalties
  → gross_margin  (transaction.py:775-824, stored)
      → commission_amount  (transaction_commission.py:54-69 → commission_service.py:38-45; skipped if commission_locked)
      → net_margin  (transaction_commission.py:71-75, stored)
      → commission_payout.gross_margin_total  (commission_payout.py:109-114)
      → close guard "gross_margin < 0"  (transaction.py:1047)
      → audit cron negative-margin check  (audit_cron.py:26-32)
      → SQL: sales dashboard view  (sales_dashboard.py:167)
      → SQL: admin dashboard KPIs  (admin_dashboard.py:318-325, 669-670, 694-724)
```

## 5. Git history

- The clone is shallow (`git rev-parse --is-shallow-repository` → `true`; grafted at `f53d3cd`, `c73696a` and others).
- `git log -S freight_chargebacks` lists `96fab3d`, `3c9183e`, `fea99d5`, `cee14d3`, `75bdea0` and `f53d3cd`, mostly merges or view moves.
- The fields have no `compute=` in any visible commit. Whether one existed before the graft is unknown.

## 6. Consequence of doing nothing

- **If claims are the intended source (unresolved, per Decision A):**
  - These are understated by the recovery amount on every transaction with a resolved freight-chargeback or lightweight-penalty claim: `gross_margin`, `net_margin`, unlocked `commission_amount`, payout `gross_margin_total`, and the sales and admin dashboard sums.
  - A transaction can be blocked from closing, or flagged by the audit cron, as negative-margin.
- **Under the current manual-entry reality**, recoveries count only when someone types them into the form.
- The number of affected records is not determinable from the repository. It needs a database query comparing resolved claim recoveries to stored field values.
- The two tests stay red: visible, classified BUSINESS_SEMANTICS_UNRESOLVED.

## 7. Candidate corrections (none authorized)

**(a) Re-declare both fields as computed in `plasticos_claims` only** (`compute="_compute_chargebacks_penalties", store=True`), like `has_quality_claim`. One module and one version bump.
- **Existing data:** the column exists, so the upgrade does not recompute anything (Odoo only recomputes new columns: `odoo/orm/models.py:3227-3246`). Old values stay until a related claim changes. A backfill needs a post-migrate `env.add_to_compute(...)`; precedent: `plasticos_order_lines/migrations/19.0.1.0.1/post-migrate.py:13`.
- **Manual values:** the fields become read-only. With `readonly=False` they stay editable but are overwritten on the next related claim change.
- **Closed transactions:** stored recomputes bypass the transaction `write()` guards (`transaction.py:948-967`), so closed-deal margins can change. Locked commission stays frozen and `net_margin` moves.
- **Dashboards:** recompute updates `write_date` (`models.py:4540-4543`). Admin dashboard month-to-date and year-to-date buckets use `write_date`, so old deals appear in the current period.
- **Coverage:** includes the bulk status wizard (`claim_bulk_update_wizard.py:108-114`), reopen, archive and `recovery_amount` edits.

**(b) Keep plain fields and call the compute from `action_resolve`.**
- It misses the bulk wizard, `action_reopen` (`claim.py:309-317`), `action_archive` (`claim.py:304-307`), and edits after resolution.
- Handling those means `create`/`write` overrides, which rebuilds what `@api.depends` already does.
- It still overwrites manual values on each resolve.

**(c) Treat the fields as manual-only.** Delete the tests and the dead methods, and fix the docstrings.
- This contradicts every stated code intent; claim recoveries would never reach margin automatically.
- Deleting tests is not authorized.

## 8. Decisions the operator must make (recorded in Decision A as open)

1. **Source of truth:** are claim recoveries the source (read-only fields), or may staff type values?
   - The operator states that recognition requires a confirmed credit, not merely a resolved claim.
2. **Archived claims:** the compute counts `resolved` only, and archiving moves resolved to archived.
   - The operator requires that archiving not erase a recognized recovery.
   - `has_quality_claim` (`transaction_claims.py:41`) already treats both states as closed. This is untested either way.
3. **Backfill:** the operator decision is **no backfill or recalculation** of historical or closed transactions.
4. **Double counting (HYPOTHESIS):** a carrier credit may already be booked as a vendor or freight credit note, which lowers cost. If the same credit is also recorded as a claim recovery it counts twice.
   - A reconciliation rule naming which record holds a given credit is needed before any automation.
