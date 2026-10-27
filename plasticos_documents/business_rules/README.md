# PlasticOS Documents | Native-first Business Rules Specification

**Canonical module-local location:** `plasticos_documents/business_rules/`
**Source:** `PlasticOS_Native_First_BRS_v1.0.0_2026-10-25.zip`, frozen against Primary Documents campaign Rev008.
**Admission:** proposed until the dedicated BRS-only PR is approved and merged. Installing these files does not amend accepted ADRs by itself.

## Read first

1. `REGISTRY.json` and `EFFECTIVE_RULES.md` for the 44 local rule IDs, their statuses and exact normative text.
2. The three original chapters `BRS-POS-02`, `BRS-POS-03`, `BRS-POS-09`, copied verbatim.
3. `OWNERSHIP_AND_INTEROP.md`, `NATIVE_ODOO19_CAPABILITIES.md`, and `OPEN_DECISIONS_AND_PROOFS.md` for Odoo and other-module boundaries.
4. `ACCEPTANCE.json`, `CROSS_DOMAIN_ACCEPTANCE.json`, `ACCEPTANCE.md` for both success and falsifying counterexamples.
5. `ALL_170_RULES_SCOPE.csv`: 44 local normative records, relevant external dependencies by ID, and out-of-scope owners. **It never admits the other 126 rules as Documents-owned.**
6. `SUPERSESSION.md` for effective interpretation and amendment discipline; applicable accepted `docs/adr/` always applies.

## Ownership and reuse

`plasticos_documents` owns business evidence, validation, compliance and consumer policy. `plasticos_documents_native` binds native `documents.document` original file lifecycle and its configured Enterprise capabilities. Both modules consume this **one** BRS directory. They do not own Linda's external correspondence, Odoo stock, Sales/Purchase commercial releases, or posted Accounting/cash.

Internal native Documents Requests and Activities are not external share/request links. External document requests use authorized Linda via native Odoo Mail and one sender per obligation. An ordinary email attachment must not itself satisfy verification or post invoices.

## Mandatory implementation use

Every Documents code PR must cite affected `BRS-POS-XX-RNNN` IDs and paired positive/negative cases, examine current accepted ADRs, prove installed Odoo 19 Enterprise behavior, and identify the component's single writer. An unresolved requirement remains `UNKNOWN`, never silently interpreted as a default. A BRS install PR is **documentation only**, with no model, XML, manifest, data, migration, test runtime or cron changes.

## Adoption boundary

No silent migration from the older `Documents_Build_Pack_v1.0.0`. It is historical only. This package uses the *new* `BRS-POS` IDs and exact rule statements; supersession requires operator acceptance and a dated recorded change. Runtime tests and integration remain **NOT_RUN**. The 2026-10-27 reconciliation makes every non-documentation blob match #316 head `53b18fd90046696e946a0d8e1e60e88595a5e143` and leaves this BRS a candidate. It does not admit the rules, prove Enterprise Documents or AI, or activate mail, cron, or finance.
