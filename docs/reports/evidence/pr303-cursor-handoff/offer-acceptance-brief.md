# Brief B: Does accepting an offer create a transaction?

**Baseline:** `702ebaf77d987dc844e2758bd354b2ecef4f26cd`.

**Evidence class:**
- **OBSERVED (static):** read-only source reading with file:line citations.
- **OBSERVED (CE runtime):** only the failing assertions, which come from the local Community run.
- **HYPOTHESIS:** statements marked as inference.

**Operator decision (2026-10-25):** the native workflow is the baseline.
- Accepting an offer changes its acceptance state only. It creates neither a transaction nor a sale order.
- Transactions are created through sale-order confirmation. No other creation mechanism is to be introduced.
- The two failing tests encode an obsolete assumption and **remain unchanged** until a correction is authorized. That correction must validate the accepted behaviour, not add functionality.
- `offer.transaction_id` and its UI stay unchanged. No writer is invented, the field is not removed, and no new relationship is added.
- This decision does not authorize test or documentation edits outside this directory.

## Answer

In the current code, no. Accepting a `plasticos.offer` does not create or link a `plasticos.transaction`, and nothing outside tests writes `offer.transaction_id`.

The claims that it does live only in prose (READMEs, the field's help text, one diagram line) and in tests that had never run before this PR. The only binding rule found says transactions are compiled when a sale order is confirmed. No ADR covers what happens to an offer after acceptance.

## Failing tests — OBSERVED (CE runtime)

| Test | Assertion |
|---|---|
| `plasticos_claims/tests/test_bridge_models.py::TestOfferBridge.test_offer_accept_creates_transaction` | `:51-58` `assertTrue(offer.transaction_id)` after send and accept. Actual: `plasticos.transaction()` (empty) |
| `plasticos_security_base/tests/test_action_methods.py::TestOfferActions.test_action_accept_creates_transaction` | `:341-346` same assertion, same result |

Neither ran before `7fb71df` (2026-10-24), which moved the orphaned root-level tests into the addons. Commit `a2e71df` labelled them "Left failing (product defects): … offer accept never links a transaction". That label was the agent's judgment in a commit message, not ADR-backed. Decision B supersedes it: the tests encode an obsolete assumption.

Some neighbouring tests pass only because the expected thing is missing:
- `test_bridge_models.py:60-68` checks `hasattr(tx, "offer_id")`, which is false, so it asserts nothing.
- `plasticos_commission/tests/test_golden_flows.py:100-107` falls back to creating a transaction by hand when acceptance does not produce one. It was updated in `01194a0` and already accepts current behaviour.

## Current contract — OBSERVED (static)

**What acceptance does:**
- `plasticos_offer/models/offer.py:382-394` `action_accept` checks the state is `sent` or `responded`, then writes `state`, `accepted_by` and `accepted_date` and logs a line. That is all.
- Its docstring, "Accept this offer — ready for transaction creation", makes acceptance a **precondition** for a transaction, not its creator.
- No mail is sent beyond the automatic tracking entry. `plasticos_automation` never mentions offers.
- The bulk wizard (`plasticos_offer/wizards/offer_bulk_action_wizard.py:92-106`) just calls `action_accept`.
- There is no offer → `sale.order` path outside tests.
- The README says acceptance sets the intake to `won`. It does not.

**Write guard:**
- `offer.py:284-293` refuses any write to an accepted, rejected, expired or cancelled offer unless the write includes `state`.
- After acceptance, writing `{"transaction_id": tx}` alone raises `UserError`.

**Every code path that creates a `plasticos.transaction`:**

| # | Path | Location | Links an offer? |
|---|---|---|---|
| 1 | Live sale-order confirmation. Creates the transaction only if `order.transaction_id` is empty, names it after `origin` when set, then activates it | `plasticos_transaction/models/sale_inherit.py:27-50` | No |
| 2 | ERP-import sale-order confirmation. One transaction per worksheet in `origin`, via `native_document_import._confirm_sales` (:1152) and `_confirm_and_compile` (:1229) | `sale_inherit.py:52-76` | No |
| 3 | Intake "Make PO (Won)". Sets intake, supplier and quantity; finds the buyer by partner-name search on the selected match line; creates no PO or SO; leaves the transaction draft; sets the intake to `won` | `plasticos_intake/models/intake.py:957-1002`; button `intake_views.xml:212-218` | No |
| 4 | Legacy CSV import wizard (menu active) | `plasticos_transaction/wizards/transaction_import_wizard.py:217`; menu `views/transaction_import_wizard_views.xml:93` | No |
| 5 | Legacy CSV import service, from a script | `transaction_import_service.py:160-165`, `scripts/run_transaction_import.py:37` | No |
| 6 | Test helper only | `plasticos_base/test_common.py:106` | No |

Gate and matching code never creates transactions.

**Writers of `offer.transaction_id`:**
- None outside tests. The only write is `plasticos_security_base/tests/test_action_methods.py:382`, on a draft offer.
- The field is defined at `plasticos_transaction/models/offer_bridge.py:9-16`, help "Transaction created when this offer was accepted."
- The smart button (`views/offer_bridge_views.xml:10-14`) is hidden while the field is empty, so in practice it never shows.

**Related facts:**
- `plasticos.transaction` has no `offer_id` field. `test_bridge_contracts.py:261-270` says so: "The transaction itself carries no offer_id."
- `intake_id` on the transaction comes from `transaction_bridge.py:10`.
- Nothing in the database enforces one transaction per sale order. Only the `not order.transaction_id` filter at `sale_inherit.py:40` does. Transaction names are unique (`transaction.py:502`).
- Layers: `plasticos_offer/__manifest__.py` does not depend on `plasticos_transaction`, which is correct (Commercial = layer 3, Transaction = layer 5; CLAUDE.md). Any accept-to-transaction logic would have to live in `plasticos_transaction`.

## Architecture sources

- **CLAUDE.md:** "Material profile → intake → match → offer → transaction". This orders the stages; it names no trigger.
- **CLAUDE.md ERP Historical Import Law and ADR-021 amendment (2026-10-24):** the importer "confirms the sale orders it realizes, and that confirmation compiles the transaction". This is the only binding statement about how transactions are created, and it is scoped to the ERP import.
- **ADR-018 (lines 17-31, 39):** the human checkpoints stop at "Human Send Offer". Nothing after acceptance.
- **ADR-002:18:** "Odoo must remain the ERP spine: intake, offers, transactions."
- **No ADR** (002-021, 120-128, or the proposed backlog) defines what follows offer acceptance. ADR-015 does not mention offers or transactions.
- **ARCHITECTURE.md:362-376:** the offer phase does "Acceptance tracking", then the transaction phase does "Transaction record creation", with no trigger named.
- **ARCHITECTURE.md:161** says `plasticos_offer` depends on `plasticos_transaction`. That is wrong: the manifest does not, and it would break the layer rule.

## Where sources conflict

| Source | Claim | Reality |
|---|---|---|
| `plasticos_offer/README.md:42, 51, 88` | `action_create_transaction()` creates the transaction on acceptance | The method has never existed. It was a proposed fix ("GAP-1") in `reports/GAP_ANALYSIS_AND_CONSOLIDATION.md` (2026-02-19), deleted in commit `033f6d5`. That report recorded that `action_accept()` "does not create a transaction, sale order, or purchase order" |
| `plasticos_transaction/README.md:74, 137` | Transaction has `offer_id`; created from `offer.action_create_transaction()` | Neither exists |
| `plasticos_intake/README.md:30` | "Offer accepted → Transaction created" | False |
| `offer_bridge.py:5, 15` | Link set when the offer is accepted | Nothing sets it; the write guard blocks setting it afterwards |
| `plasticos_offer/tests/test_offer_state_machine.py:4`, `action_accept` docstring | Acceptance is "the gateway to" / "ready for" transaction creation | Consistent with the code: a precondition |
| `tests/README.md:181` | "Offer ↔ Transaction: Many2one ↔ One2many" | No One2many on the transaction side |

**Git history:**
- The clone is shallow (`.git/shallow` has 7 graft points; the oldest visible commit is `f53d3cd`, 2026-09-24).
- Within that window, `offer.py` and `offer_bridge.py` changed only in `f53d3cd`, and `sale_inherit.py` in `f365e69` and `f53d3cd`.

## Candidate resolutions (analysis; Decision B selects the native-workflow baseline)

**(a) Acceptance creates the transaction** (override of `action_accept` in `plasticos_transaction`).
- **Duplicate transaction:** confirming the deal's sale order later sees an empty `so.transaction_id` (`sale_inherit.py:40-47`) and creates a second one. "Make PO (Won)" can create a third.
- **Missing data:** SO-derived fields (`transaction.py:605-632`) and `product_id` (from the SO line, `sale_inherit.py:85`) stay empty.
- **Write guard:** the link would have to go in the same write as `state`.
- **Variant, acceptance creates a draft SO:** needs an offer → product mapping and an SO → offer link. That is a new field (requires operator approval) or an unsafe `origin` reuse, since `origin` is read as worksheet numbers and names the transaction. A new feature.
- **Rejected by Decision B.**

**(b) Acceptance creates nothing; the link is written when a transaction is compiled from the offer's SO.**
- No key from SO to offer exists today.
- It needs a new field or the unsafe `origin` reuse, plus a narrow write-guard exception.
- **Not adopted.** Decision B: no new relationship, and the field stays unchanged.

**(c) The prose and tests are stale; correct them to the real contract.**
- No schema change, no duplicate risk.
- `offer.transaction_id` remains writer-less. Its future is deferred by Decision B.

## Consequence of doing nothing

- The two tests stay red: visible, classified as encoding an obsolete assumption.
- The READMEs keep documenting a non-existent method, and the offer's Transaction button never appears.
- No data is corrupted, because no code depends on the link.

## Open items (not authorized)

1. Correcting the two tests to assert the accepted behaviour: acceptance sets the state, and `search_count` of transactions is unchanged.
2. Correcting stale prose:
   - `offer_bridge.py:5, 15` help and docstring
   - `plasticos_offer/README.md` (42, 49, 51, 88)
   - `plasticos_transaction/README.md` (74, 137)
   - `plasticos_intake/README.md:30`
   - `ARCHITECTURE.md:161`
   - `tests/README.md:181`
3. The future ownership of `offer.transaction_id`: who writes it, whether it is exempted from the write guard, or whether it is retired.
4. Recording the acceptance → sale-order → transaction step in an ADR or an ADR-018 amendment.
