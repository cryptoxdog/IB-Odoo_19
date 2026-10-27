# PR #303: Cursor handoff and evidence index

**PR:** [cryptoxdog/IB-Odoo_19#303](https://github.com/cryptoxdog/IB-Odoo_19/pull/303). It moves the orphaned Odoo runtime tests into their owning addons and fixes the defects that running them exposed.
**Frozen implementation baseline:** `702ebaf77d987dc844e2758bd354b2ecef4f26cd`. This documentation directory is the only change after it.
**Status:** frozen by the operator. Cursor owns Enterprise verification. The operator alone may authorize remediation.
**Date of evidence:** 2026-10-24 to 2026-10-25.

## Evidence classes used in these documents

| Label | Meaning |
|---|---|
| **OBSERVED (CE runtime)** | Observed by the agent in a local **Odoo 19.0 Community** runtime (PostgreSQL 16, every installable `plasticos_*` addon installed, `--test-enable --test-tags … --stop-after-init`). **This is not Enterprise proof.** |
| **OBSERVED (static)** | Read by the agent from the source at `702ebaf` (file:line citations). Not executed. |
| **HYPOTHESIS** | An inference that is not verified. It needs the Enterprise run or operator confirmation. |
| **OPERATOR DECISION** | Accepted by the operator. Binding on future work, but it authorizes no implementation by itself. |

The local CE template excluded three groups of addons:
- `plasticos_documents_native`, which requires Enterprise `documents`.
- `plasticos_semantic_kernel`, which stays uninstalled by policy.
- The non-installable addons.

The Docker Enterprise install-smoke was **not** run. The PR was published with `make pr-nosmoke`, because the cloud container has no `odoo-enterprise` checkout.

## Documents

| File | Content |
|---|---|
| [`enterprise-validation.md`](enterprise-validation.md) | The 7 failing tests and 1 CE environment error with exact paths, CE run results, the PR scope inventory, open risks, and what the Enterprise validation must establish |
| [`claims-recovery-brief.md`](claims-recovery-brief.md) | Brief A: claim chargebacks and lightweight penalties |
| [`offer-acceptance-brief.md`](offer-acceptance-brief.md) | Brief B: whether offer acceptance creates a transaction |
| [`security-acl-brief.md`](security-acl-brief.md) | Brief C: blanket ACL grants and the effective-permission exposure |

## Operator decisions (accepted 2026-10-25)

These decisions settle intended behaviour or scope. **None of them authorizes code, test, documentation-outside-this-directory, permission or environment changes.**

- **A. Claim chargebacks and lightweight penalties.**
  - Claim recovery recognition remains **unresolved**. A resolved claim does not establish that a carrier or supplier credit was received, booked or recognized.
  - Do not change margin calculations, convert the fields to computed values, backfill or recalculate historical or closed transactions, or automate claim-to-margin.
  - Preserve existing manually entered values. Archiving a claim must not erase a previously recognized recovery.
  - The two failing tests are classified **BUSINESS_SEMANTICS_UNRESOLVED**. That is not permission to change accounting behaviour.
- **B. Offer acceptance.**
  - The native workflow is the baseline. Accepting an offer **changes its acceptance state only**; it creates neither a transaction nor a sale order.
  - Transactions are created through the existing **sale-order confirmation** workflow. No other transaction-creation mechanism is introduced.
  - The two failing tests encode an obsolete assumption. **They remain unchanged** until the operator authorizes a correction, which must validate the accepted behaviour rather than add functionality.
  - `offer.transaction_id` and its UI stay unchanged. No writer is invented, the field is not removed, and no new relationship is added.
- **C. Security permissions.**
  - The blanket ACL grants are a significant security concern requiring a **separately approved business-role policy** and a dedicated, tightly scoped remediation.
  - Ordinary internal-user membership should not grant unrestricted modification or deletion of claims, transaction lines or historical financial data.
  - Before implementation, explicit role permissions must be defined, legitimate document-upload and operational workflows preserved, and effective ORM permissions tested independently.
  - No blanket `sudo()`, no casual row removal, no refactor across 13 addons.
  - The broader `ir.model.data` and `product.template` exposures are recorded as **separate high-priority findings**. They are not authorization for a repository-wide security rewrite.
- **D. PR #303 scope.**
  - The direction is to separate test discovery from production behaviour changes.
  - The **logistics** changes belong outside this CRM/ERP import test campaign.
  - The **document-compliance** gate changes and the **match-exclusion** exception fix are production changes that need their own explicit scope and approval.
  - These are **earmarked for future scope separation and not yet authorized for modification**: no split, revert, cherry-pick or rewrite of #303.
  - No change affecting accounting-document posting or transaction closing is approved merely because tests exposed it.
- **E. Enterprise validation and PR #301.**
  - Cursor tests **#301 and #303 independently**, each at its exact SHA, using the existing admitted Enterprise fixture and owned disposable clones. The branches are not combined.
  - Establish whether `TestErpWorksheetImport` passes with the seeded accounting records present, **without modifying or reseeding the Enterprise template**.
  - The `plasticos_transaction` version collision (both PRs set `19.0.2.3.40`) is resolved **only during approved integration**. The resulting version must advance beyond the previously installed one, and the combined code plus module upgrade must actually be verified.

## Unresolved checks (must stay visible)

1. **Seven known Community test failures remain visible.** They are not fixed, skipped or weakened; see `enterprise-validation.md` §1. OBSERVED (CE runtime).
2. **`TestErpWorksheetImport` accounting-seed error is unverified on Enterprise.** The CE-only explanation is a HYPOTHESIS; see `enterprise-validation.md` §2.
3. **`TestTransactionACL.test_base_user_cannot_unlink` passes unexpectedly.** `access_transaction_all` grants delete to `base.group_user`, yet the test observed an `AccessError`. The mechanism is unidentified; see `security-acl-brief.md` §3 and `enterprise-validation.md` §4.
4. **Document-compliance enforcement may interact with automatic invoice posting.**
   - `plasticos_transaction/models/transaction.py:852-877` (`_compute_compliance`, which uses the **unscoped** `is_compliant`) calls `_auto_post_pending_invoices` (`:879-898`) when a transaction goes from `missing` to `compliant`.
   - That auto-post runs `account.move.action_post()`, whose compliance gate PR #303 now enforces with `purpose="invoice"`.
   - PR #303 also makes `action_close` enforce `required_for_close` rules (seeded: verified scale ticket).
   - The interaction is not analysed or approved.
5. **PR #301 and #303 are independent branches with overlapping module changes.**
   - Both bump `plasticos_transaction/__manifest__.py` to `19.0.2.3.40`.
   - #301 also edits `plasticos_transaction/tests/test_erp_worksheet_import.py`.
6. **The final cohesive-system run requires separate operator authorization.**

## Provenance

- The briefs were produced by read-only investigation of the source at `702ebaf` and reviewed by the session agent. The CE runtime results come from the session agent's local runs.
- The full CE logs are not committed. They lived in the ephemeral session container.
- The test counts and failing test IDs below are transcribed from those logs (`odoo.tests.result` summary lines and `FAIL:` / `ERROR:` records).
