# ERP, QuickBooks and bank opening evidence, repeatable reopen, cutover acceptance

**Governing decision:** [ADR-022](https://github.com/cryptoxdog/IB-Odoo_19/blob/d6cc3c8ba04041da1844d7d0be396f4fad907be7/docs/adr/ADR-022-erp-historical-closure-and-accounting-opening-balances.md). **Status:** operational and financial source cutoff unprovided; implementation/run not claimed. Financial writer change is a **separate approval** from Production code readiness.

## Exact source-of-truth partition

| Source | What it controls | Boundary |
|---|---|---|
| Legacy ERP | Historical transactions, AP open-item ledger, AR open-item ledger, invoice/bill/credit residuals and applied partials, source inventory quantity and valuation evidence | Do not infer opening GL from closed/open transaction state or gross invoice totals |
| Bank statements | Opening bank account balance, actual statement items and outstanding deposit/check timing at signed cutoff | No fabricated payments or bank movements |
| QuickBooks | Signed Trial Balance, AR/AP control balances/aging, all other GL balances and approved chart mappings | One and only one opening ledger source; QB AR/AP controls mapped via clearing, not posted again directly to native AR/AP |
| Explicit source-backed operational exceptions | Which historical closed trades have *actual remaining fulfillment/physical obligations* | Manager operational reopen is not financial open-item posting |

**Cutoff manifest:** company and entity; timezone and last legacy-owned accounting date/time; currency/FX rate rules; raw report version/hash; source extraction owner; approval; post-extract delta register; partner/account mapping; bank statement end date. Missing or mismatched inputs are blocked, never guessed.

## A. Operational reopening, repeatable Make contract

Existing `plasticos.transaction.action_reopen_historical(reason)` changes one Closed historical trade to Active for an authorized Manager and logs the reason. **It does not create or post an account.move**. An AR/AP balance alone does not authorize activating logistics.

Requested command **to implement**: `make reopen-erp-transactions`, routed through the canonical transaction owner with the same discipline as `make import-erp` and `make import-vanillasoft`:

- Default **dry run** and report-only. Requires immutable signed source/exception register and SHA, known cutoff, exact destination DB/company, Manager authority and explicit bounded Production permit for actual writes.
- Select only approved operational exception entries with unique source worksheet identity, company, remaining action/quantity, reason and owner. Source report review and approval are **inputs**, never inferred from AR/AP invoice age.
- Reopen each selected Closed imported transaction once through existing owner method (or a single narrow shared service if batching requires it). Support transaction-safe batch checkpoints, partial failure ledger and deterministic restart.
- Re-run same approved manifest, expecting zero new reopen events and no demotion on ERP import replay. Unselected trades remain Closed. Deny bad role, missing signature, wrong company, nonhistorical row, stale cutoff, ambiguous identity, missing reason and unauthorized Production.
- The Make command does **not** post archival gross invoices, create opening AR/AP entries, activate mail/stock/commission, or silently launch payment automation.

## B. Financial opening, independent from a transaction's operational state

Use ADR-022's native Odoo accounting writer, not the transaction-reopen wizard. A safely named *future* Make target such as `make reconcile-opening-balances` may provide one reproducible **dry-run and reconciliation** interface; production posting remains a separate explicit accountant/operator action and is **not silently piggybacked** onto `make reopen-erp-transactions`.

1. **AR/AP:** full historical imported invoice/bill/credit remains Draft archival evidence. From ERP as-of **residual** reports, create distinct current opening native `out_invoice`, `in_invoice`, `out_refund`, `in_refund` documents for unpaid remainder only with exact partner, currency, source ref and provenance; skip zero residual. No duplicate taxes/revenue/expense/history.
2. **QuickBooks:** signed QB TB into native opening journal at same cutoff; QB AR/AP control lines into **separate AR Clearing/AP Clearing**, not native control accounts. When approved native opening invoices/bills are posted, the clearing accounts should return to exactly zero by entity/currency.
3. **Bank:** actual bank statements establish opening bank balance. Reconcile with QB cash account and outstanding timing items. A bank opening is not derived from ERP trade/payment guesses.
4. **Inventory:** ERP reports supply quantity/lot/warehouse/ownership/valuation source; physical review and QB control resolve differences. Any stock adjustment or valuation entry needs separately approved native owner action; do not fabricate pickings to match a worksheet count.
5. **Tie-out:** QB debits == credits; net ERP AR/AP including credits/refunds == QB AR/AP controls, matched per company/currency; native opening AR/AP schedules == those residuals; AR and AP clearing = 0; bank and inventory positions tie with independently signed adjustments. Quarantine source mismatches, unknown FX and duplicate keys.
6. **Idempotency:** cutoff ID + signed report SHA + company + source document type/key + currency; same report replay creates zero new records; changed report after posting needs attributable reversal/adjustment, not edits of posted rows.
7. **Run on isolated Odoo 19 Enterprise clone first**, with posted-opening rehearsal and safe restore. Record before/after TB, aging, clearing, account moves, partner residuals, bank reconcile and inventory. No Production financial posting, legacy writer shutdown or commission permission until exact signed cutover authority is supplied.

## Cross-domain acceptance cases not to forget

- One operationally unfinished historical trade with fully paid invoices and one financially unpaid but operationally completed trade: only the independently approved operational exception reopens.
- Partial payments, partial credits, refunds, wrong-sign vendor credit, negative/zero residual, reopened trade with unrelated bills and multi-currency FX cutoffs.
- A statement date not identical to accounting cutoff; one uncashed check; a cross-company partner collision; one inventory unit valuation conflict and out-of-scope vendor invoice.
- Fail between two opening items and rerun; clone restore then replay; immutable original gross lines and source identity survive.

**Hard separation:** production CRM/ERP import completeness, source reports, financial rehearsal, approved Production posting and Odoo financial system-of-record transfer are five different states. None is inferred from a dashboard or GitHub merge.
