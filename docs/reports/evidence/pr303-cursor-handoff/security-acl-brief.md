# Brief C: Blanket ACL grants and effective-permission exposure

**Baseline:** `702ebaf77d987dc844e2758bd354b2ecef4f26cd`.

**Evidence class:**
- **OBSERVED (static):** read-only source reading, including the Odoo 19 CE source, with file:line citations.
- **OBSERVED (CE runtime):** only the test outcomes, from the local Community run.
- **HYPOTHESIS:** statements marked as inference or prediction.

**Operator decision (2026-10-25):** a significant security concern requiring a **separately approved business-role policy** and a dedicated, tightly scoped remediation.
- Ordinary internal-user membership should not grant unrestricted modification or deletion of claims, transaction lines or historical financial data.
- Before implementation, define explicit role permissions, preserve legitimate document-upload and operational workflows, and test effective ORM permissions independently.
- No blanket `sudo()`, no casual ACL row removal, no refactor across 13 addons.
- `ir.model.data` and `product.template` exposures are separate high-priority findings, not authorization for a repository-wide rewrite.
- The passing `test_base_user_cannot_unlink` remains diagnostically unresolved.

## Summary

All three failing tests fail for the same reason:
- A blanket row gives every internal user (`base.group_user`) full CRUD.
- Odoo ACLs are additive, so that row overrides the narrower group rows.
- No record rule or code guard compensates on these models.

For `plasticos.claim`, nothing short of deleting the blanket row passes both claim tests. Deleting it alone would break real workflows, because no regular user is assigned a claims group.

## 0. How Odoo 19 combines access — OBSERVED (static, `odoo-19.0` CE source)

- **ACLs add up.**
  - `odoo/addons/base/models/ir_model.py:2157-2175` (`_get_allowed_models`) allows a model if any active row with that permission has `group_id IS NULL` or a group the user holds.
  - `check()` at `:2178-2191` tests membership in that set.
  - Implied groups count: `_get_group_ids` returns `all_group_ids` (`res_users.py:1099-1104`).
  - There is no "deny" row.
- **Record rules.**
  - `ir_rule.py:113-133` selects rules that are global or tied to one of the user's groups, for the requested mode only.
  - `:141-173` ANDs global rules and ORs group rules.
  - A user in none of a rule's groups is not restricted by it. A rule with `perm_unlink=False` is ignored for deletes.
- **Stored computed fields** run as superuser by default (`compute_sudo = store`, `fields.py:448`).
- **Automations** run their server actions as sudo (`base_automation.py:824`, `ir_actions.py:1175-1179`).

## 1. Inventory of blanket rows — OBSERVED (static)

- No row has an empty group.
- **32 rows named `*_all`** across **13 addons**: base, claims, documents, documents_native, enrichment, facility_profile, intake, intake_normalizer, material_profile, offer, partner_import, product, transaction.
- **43 full-CRUD rows granted to `base.group_user`** across **15 addons**.
  - These add logistics (2 wizard rows) and web_leads (1 wizard row).
  - They also include non-`_all` rows such as `access_plasticos_material_profile`, `access_plasticos_facility_profile` and `documents_native:4` (`documents.tag`).
- **18 addons** give `base.group_user` some write, create or delete right. The extras are create/write-only rows in crm_sync, semantic_kernel, matching, intake, logistics and facility_profile.

The two models behind the failing tests:

| Row | Model | Perms (r,w,c,u) | Other rows on the same model |
|---|---|---|---|
| `plasticos_claims/security/ir.model.access.csv:5` `access_claim_all` | plasticos.claim | 1,1,1,1 | `:2` group_claims_user 1,1,1,0 · `:3` group_claims_manager 1,1,1,1 |
| `plasticos_transaction/security/ir.model.access.csv:11` `access_transaction_line_all` | plasticos.transaction.line | 1,1,1,1 | `:4` base.group_user 1,0,0,0 · `:5` group_plasticos_manager 1,1,1,1 · `plasticos_security_base/security/ir.model.access.csv:8-10` sales_rep R, logistics RWC, accounting R |

- Every row in `plasticos_transaction/security/ir.model.access.csv` now has a duplicate: lines 2/10, 4/11 and 6/12 each pair a read-only row with an `_all` CRUD row for the same group.
- `.cursor/rules/71-plasticos-security-model.mdc:67` forbids that.

## 2. Effective permissions — OBSERVED (static)

**`plasticos.claim`**

| User | ACL result | Record rules | Effective |
|---|---|---|---|
| (a) internal user only, which includes every seed sales rep, logistics, accounting and QC manager user | CRUD from `:5` | none apply (both rules are group-scoped, `claims_security.xml:26-46`) | **full CRUD on every claim** |
| (b) group_claims_user | union of `:2` and `:5` = CRUD | `claim_rule_user_read` is 1=1 and skipped for deletes | **can delete** |
| (c) group_claims_manager | CRUD | 1=1 | CRUD |

- Code guards are partial:
  - `claim.py:255-263` blocks deleting only `resolved`/`archived` claims.
  - `claim.py:249-252` blocks editing archived claims, but any write that includes `state` skips the check.
- There is no company or ownership rule, and the model has no `company_id`.

**`plasticos.transaction.line`**

| User | Effective |
|---|---|
| (a) internal user only | **full CRUD** from `:11` |
| sales rep / accounting | full CRUD (security_base grants read-only, but `:11` wins) |
| logistics | full CRUD (RWC plus `:11`) |
| (c) group_plasticos_manager | CRUD |

- No record rules on lines. The sales-rep own-records rule exists only on the transaction header (`record_rules.xml:53-68`), so a rep can edit lines of transactions they cannot see.
- No write or unlink override (`transaction_line.py` is fields and computes only).
- Line edits ripple into stored `historical_sale_total` and `historical_purchase_total` (`transaction.py:768-773`).

## 3. Failing assertions (`plasticos_commission/tests/test_security_acl.py`)

**OBSERVED (CE runtime):**
- **`TestClaimACL.test_claim_user_cannot_unlink` (145-148):** the user has internal user + group_claims_user and expects `AccessError` on delete. The union with `:5` allows deleting a `pending` claim, so nothing is raised.
- **`TestClaimACL.test_no_group_cannot_read` (155-158):** the user has internal user only and expects `AccessError` on read. `:5` grants read. Any `base.group_user` row with read=1 fails this test; read-only or no-delete variants do not help.
- **`TestTransactionACL.test_base_user_cannot_write_tx_line` (59-63):** the user has internal user only and expects `AccessError` on write. `:11` grants write.

**Unexpected PASS (unresolved):** `TestTransactionACL.test_base_user_cannot_unlink` (54-57).
- **Static prediction (HYPOTHESIS):** this test should fail. `access_transaction_all` (`plasticos_transaction/security/ir.model.access.csv:10`) grants delete to `base.group_user`, and `transaction.py:990-996` blocks only closed transactions or ones linked to invoices or bills.
- **Observed:** the test started in the CE run and was not reported as failed, so it raised `AccessError`.
- **Mechanism not identified.** Candidates to inspect, not verified:
  - a record rule in `plasticos_transaction/security/security_hardening.xml`
  - a record rule in `plasticos_security_base/security/record_rules.xml`
- Per Decision C, Cursor must identify the actual mechanism, not assume the broad ACL is harmless.

**Fragile setup:** these tests live in `plasticos_commission`, whose manifest (`plasticos_commission/__manifest__.py:8-17`) does not depend on `plasticos_claims`. The setup code silently drops a group it cannot find.

## 4. Groups and how users are assigned — OBSERVED (static)

- **`plasticos_security_base` groups** (`security_groups.xml`): sales_rep, logistics, accounting, logistics_ops, qc_manager, accounting_ops, operations_manager, system_admin. All imply `base.group_user`, never the reverse.
- **Module groups:** `group_claims_user` and `group_claims_manager` (`claims_security.xml:14-23`); `group_plasticos_manager` (`security_hardening.xml:15-18`).
- **No security_base group implies a claims group.** `group_qc_manager` has no claim access of its own; the CRM bridge adds only `sales_team.group_sale_salesman` to it (`plasticos_crm_bridge/security/crm_group_imply.xml:23`).
- **Who gets which groups:**
  - Seed sales reps get internal user + sales_rep only (`plasticos_security_base/hooks.py:21-34`).
  - Admins and `user_system_cron` get claims manager and plasticos manager (`plasticos_base/hooks.py:130-176`, `plasticos_claims/hooks.py`).
  - So every non-admin reaches claims only through the blanket row.
- **No role-matrix document exists.** Stated intent conflicts with the blanket rows:
  - `ARCHITECTURE.md:620`: `plasticos.claim` "requires … Claims groups".
  - `:642`: "No ACLs relaxed".
  - `INVARIANTS.md:170-183`: group-based manager CRUD / user CRU / readonly R.
  - `.cursor/rules/71...mdc:57-65`: new rows use security_base groups.

## 5. Workflows that depend on the blanket rows — OBSERVED (static)

**Claims**
- **Would break:** uploading a document with a claim tag (`claim_pics`, `claim_photo`, `claim`). `plasticos_claims/models/document_inherit.py:13-15, 40-61` searches and creates the claim **as the uploading user, without sudo**. An `AccessError` there rolls back the document upload itself.
- **Would break:** the transaction "Claims" button (`transaction_claims_bridge.py:13-23`), and the Claims menu (`claim_menus.xml`, no groups) for non-claims users.
- **Still works:** `claim_count`, `has_quality_claim` and chargebacks/penalties (stored, compute_sudo).
- **Not affected:**
  - the SLA cron (its user is claims manager)
  - the midnight recompute
  - `workflow_automations.xml:70-170` (runs as sudo)
  - CRM sync and bridge, partner import, controllers and reports, which do not reference claims
- **Bulk wizard row (`:6`):** a transient model and low risk.

**Transaction lines**
- **Would break:** the CSV import wizard.
  - Its menu has no group (`transaction_import_wizard_views.xml:93-97`), and it creates lines as the current user (`transaction_import_wizard.py:189-243`).
  - Its `except Exception` (around 245-247) has no savepoint, so a user without create rights would save closed transaction headers with no lines and only see an error.
- **Still works:**
  - the read-only `line_ids` on the form (`transaction_views.xml:214`)
  - `transaction_import_service`, which runs from an `odoo shell` script as superuser
  - the database cascade when a transaction is deleted

## 6. Git history

- The clone is shallow (`.git/shallow`); the cut-off commit is `f53d3cd` (2026-09-24).
- The blanket rows predate it: `git log -S` and `-L` on the claim, transaction-line and `ir.model.data` rows stop at `f53d3cd`.
- No commit message, comment or ADR explains them. The real origin needs a full fetch.

## 7. Candidate minimal corrections for the two failing-test models (none authorized)

**Claim** (`plasticos_claims/security/ir.model.access.csv:5`):
- **C1:** delete the row, then grant access to the real roles.
  - Add claim rows for security_base roles in `plasticos_security_base`'s CSV, with `plasticos_claims` added to its `depends`. The reverse dependency would loop: security_base → plasticos_automation → plasticos_claims.
  - Make QC and operations managers imply the claims groups, using the `crm_group_imply.xml` pattern.
  - Give the photo auto-create (`document_inherit.py:50`) either create rights for uploader roles or a justified sudo.
- **C2:** delete the row only. Passes the claim tests but breaks claim access for every non-claims user, the photo upload and the Claims button.
- **C3:** change it to 1,1,1,0. Fixes only `test_claim_user_cannot_unlink`. Valid only if "all internal users can read claims" is intended, in which case `test_no_group_cannot_read` encodes the wrong contract.

**Transaction line** (`plasticos_transaction/security/ir.model.access.csv:11`):
- Delete it. A read-only variant would duplicate `:4`.
- Result: internal users and sales reps read; logistics RWC; managers CRUD.
- Breaks the CSV import for users who are neither logistics nor managers, with the partial-save problem. Mitigate by restricting the menu or adding a savepoint.
- `access_transaction_all` (`:10`) is outside this scope, but it relates to the unresolved PASS above.

Per Decision C: **no** wholesale removal, no blanket sudo, no multi-addon refactor. Any correction follows a separately approved role policy.

## 8. Consequence of doing nothing

- The three tests stay red: visible.
- Any internal user, including every seed sales rep, can create, edit, delete and resolve claims.
  - That includes `recovery_amount`, which feeds `gross_margin` (`transaction.py:813-818`) and commission (`commission_rule.py:210`).
  - So commission earners can change inputs to their own pay.
- Any internal user can rewrite or delete ERP historical lines on any transaction, changing stored historical totals.

## 9. Separate high-priority findings (recorded, not authorized)

- **`plasticos_base/security/ir.model.access.csv:5`:** internal users get read/write/create on **`ir.model.data`**, which core Odoo sets to 0,0,0,0 (`base/security/ir.model.access.csv:19`). Users can repoint XML IDs that code resolves with `env.ref(...)`.
- **`plasticos_product/security/ir.model.access.csv:4`:** full CRUD on core **`product.template`** for internal users.
- **Remaining blanket rows**, for a later inventory review:
  - Master and config data: material_profile `:4,19-26`, facility_profile `:2,7,8`, intake_normalizer `:4`, documents `:11-13`, documents_native `:3-4` (core `documents.tag`).
  - Business records: documents `:10`, enrichment `:14-17`, intake `:6-7`, offer `:5`, partner_import `:8-9`, transaction `:10,12`, base `:4`.
  - Transient wizards, low risk: logistics `:22-23`, offer `:4`, partner_import `:7`, transaction `:7-9`, web_leads `:7`, claims `:6`.

## Decisions required (open under Decision C)

1. Which business roles may read, write, create and delete claims? May commission earners edit `recovery_amount`?
2. Claim-photo upload: create rights for uploader roles, or a justified sudo?
3. Who may run the CSV transaction import?
4. Whether to fetch full history to establish the origin of the `_all` rows before any wider review.
