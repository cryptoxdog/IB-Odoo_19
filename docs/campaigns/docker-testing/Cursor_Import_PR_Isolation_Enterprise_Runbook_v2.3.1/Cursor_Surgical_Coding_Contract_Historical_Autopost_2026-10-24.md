```yaml
repository_access:
  writable:
    - https://github.com/cryptoxdog/IB-Odoo_19
  read_only: []
  unlisted_repositories: no_access
```

# Cursor surgical coding contract | Protect imported historical accounting drafts

**Contract ID:** ODOO-303-HISTORICAL-AUTOPOST-GUARD-001  
**Authority:** Operator's explicit approval in this chat (2026-10-24): exclude historical ERP documents from compliance-triggered automatic posting; preserve normal operational posting and explicit manual accounting actions; production modification limited to `plasticos_transaction/models/transaction.py`, with focused tests and no unrelated remediation.  
**Delivery:** Local bounded patch/commit, exact diff and implementation/test report. **No push, new PR, updates to #303, merge or deploy without separate authorization.**

## Frozen target and source evidence

- **Repository:** `https://github.com/cryptoxdog/IB-Odoo_19`; integration branch `Staging`.
- **Implementation base:** frozen PR #303 GitHub head `190c497bdea1362cad87e231c713efdcd25240d4`; create a separate clean, isolated working branch/worktree from this exact commit. Do not modify or advance PR #303 itself.
- **Adjacent PR #301, read-only comparison:** `cc3f8cbb90d7f57c58de75af9d893d8ac2ed4c79`. Do not cherry-pick, merge, rebase, or change it.
- **Evidence:** uploaded premerge Enterprise pack's `SURGICAL_REMEDIATION_MAP.md` and `surgical/probe1-output.txt`, `probe2-output.txt`, `probe3-setup-output.txt`, `probe3-fail-output.txt`, `probe3-retry-output.txt`. Existing Enterprise template `odoo_test_tpl_ee_c9e8a81f52f23680`; preserve its recorded fingerprint. No fixture rebuilding or reseeding.
- **Source seam:** `plasticos_transaction/models/transaction.py::_auto_post_pending_invoices()` collects `customer_invoice_id`, `vendor_bill_ids` and `freight_bill_ids` when draft, then calls `account.move.action_post()`. `_compute_compliance()` triggers it on `missing -> compliant`.

## Required execution-contract fields

**objective:** Prevent a transaction's document-compliance transition from automatically posting **historical ERP-imported** `account.move` drafts, while continuing to auto-post eligible **operational** drafts and leaving direct manual `action_post()` unchanged.

**target:** Exact repository and head above; implement only in a new local isolated branch/worktree rooted at #303 head. Verify the SHA and clean worktree before editing; on drift, STOP and report.

**authority_refs:** This operator authorization; `SURGICAL_REMEDIATION_MAP.md` sections 1–6; exact frozen source definitions named above. No authority to revise wider accounting policy.

**in_scope / modification_scope:**
1. **Only production file:** `plasticos_transaction/models/transaction.py`, within `_auto_post_pending_invoices()` (and minimal immediately local helper only if truly necessary). No edits to `_compute_compliance()` semantics.
2. **Existing test files only, as needed:** `plasticos_documents/tests/test_account_move_transaction_link.py` and/or an existing relevant test file under `plasticos_transaction/tests/`. Add focused ORM assertions; do not rewrite or suppress existing failures. Avoid new files.
3. An evidence-only local implementation report may be generated outside the product diff for handoff; do not commit unrelated reports.

**locked_invariants:**
- ERP importer-created `account.move` documents stay draft until an **explicitly authorized** accounting action posts them. Compliance alone is not such authorization.
- Identify historical `account.move` provenance with existing `ir.model.data` identity records where **all** match: `module == 'plasticos_transaction'`, `model == 'account.move'`, `res_id == candidate_move.id`, and name starts with exactly one of `legacy_erp_outinv_`, `legacy_erp_ininv_`, `legacy_erp_ledger_`. A matching record is sufficient to exclude from **automatic** posting. Do not infer from `invoice_origin`, `ref`, `create_uid`, transaction state, sale-line links, or the invoice-line `is_imported` flag alone.
- Preserve `customer_invoice_id`, `vendor_bill_ids`, and `freight_bill_ids` selection behavior for unmarked draft moves. Use a **bounded batched provenance lookup** over candidate move IDs; do not add unnecessary per-move searches or new fields.
- Filter the collected draft recordset **before** `action_post()`. If no eligible moves remain, do not invoke `action_post()`. A mixed historical + operational set must still post eligible operational drafts.
- Leave `_compute_compliance()` and compliance rule purposes, operational posting checks, explicit `account.move.action_post()` (including core bill-date validation), error propagation, rollback semantics, transaction state, and all imported record data unchanged.
- Do not introduce `sudo()` overrides, new context bypasses, or provenance-metadata mutations.

**out_of_scope / forbidden_actions:**
- No changes to `account_move_inherit.py`, `plasticos_documents` production code, historical importer, sale confirmation, document rules, security ACLs, Odoo models/schema, manifests, module versions, Odoo.sh, infrastructure, or data.
- Do not solve the #301/#303 `19.0.2.3.40` manifest collision in this slice; it remains an explicit final-integration gate.
- Do not remediate #303's seven known claim/offer/ACL failures, unverified ACL unlink PASS, Linda logistics, match exclusion, invoice due-date anomaly, or historical payment/posting policy beyond this automatic-post guard.
- No source import or VanillaSoft replay, merger of the two PRs, mutation of admitted Enterprise template, live financial record posting, or broad test campaign.

## Exact acceptance and regression obligations

1. **Historical-only:** On an owned disposable Enterprise clone, attach a marked historical `out_invoice` and a marked historical `in_invoice` (including an undated bill) to a transaction; drive `missing -> compliant` via verified document. Assert compliance becomes `compliant`, both moves remain `draft`, and no `action_post()` is called for those moves. Repeated document changes do not post them.
2. **Historical adjustments:** Verify the `legacy_erp_ledger_` provenance is also excluded if its `account.move` is in the actual auto-post candidate set. If the current relational fields cannot naturally hold a ledger adjustment, prove classification at the method level without inventing a business relationship.
3. **Operational and mixed:** A regular sale-origin operational invoice with **no qualifying historical marker** still auto-posts when compliance becomes satisfied. In a mixed set, operational moves post and historical moves remain draft. An unrelated XMLID, wrong namespace, wrong model, or similar-looking origin must **not** suppress normal posting.
4. **Manual accounting:** A direct, authorized `action_post()` on a valid historical draft remains routed through normal Odoo logic, and an undated bill still fails core date validation. Do not bypass existing invoice-purpose compliance or cancellation restrictions.
5. **Rollback/retry preservation:** A purely operational set containing an undated vendor bill must retain existing uncaught-error rollback behavior. After date correction in the disposable scenario, the normal compliance transition can retry and post eligible operational moves.
6. **Regression discrimination:** Where feasible, demonstrate at least the historical-only test fails against frozen #303 and passes after the change. Run the smallest relevant real Odoo ORM tests on a disposable admitted Enterprise clone, recording actual test IDs, commands, exit codes, totals, log paths, SHA, and fixture fingerprint. Do not count pytest mocks as Enterprise runtime proof. Never alter tests merely to force green.

**acceptance_criteria:** All above cases verified where runnable; product diff touches the one allowed production method and focused existing test files only; no changes to #301/#303; unrelated seven failures neither hidden nor reclassified; clean/dirty state and all limitations reported. If any acceptance case is NOT_RUN, report it as such, not PASS.

**validation_obligations:** First inspect the exact current test runner and available Enterprise fixture before invoking commands; use repository-supported commands verified from source. Avoid Odoo Community substitution, fixture re-creation, privileged changes, and blanket test reruns. Record before/after observations and independently review the final diff against this contract. Distinguish implementation tests from independent validator acceptance.

**delivery_mode:** Local implementation diff/commit and a concise execution report only. Include exact parent SHA, changed-path list, diff summary, test outcomes and any unverified conditions. **STOP before push, PR publication, merge or deployment.** The operator will separately decide publication and final integration/version bump.

**failure rule:** If existing markers cannot safely identify historical `account.move` records, or correctness requires edits outside the authorized method/tests, STOP and report a minimal evidence-based decision request. Do not widen scope, invent a marker, or bypass the issue.

## Required Cursor handoff

Return (1) proposed-and-implemented diff, (2) implementation report mapping each requirement above to file/line/test evidence, and (3) an independent-verification checklist with **PASS / FAIL / NOT_RUN** per assertion. No blanket "all green" claim. No unsolicited edits or next remediation loop.
