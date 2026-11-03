# Copy this message to Cursor with the ZIP attached

Activate the installed L9 Coding Agent and load `00_START_HERE.md` in the attached PlasticOS Domestic Multi-Load pack. Then follow `01_CURSOR_CODING_CONTRACT.md` as the **single** execution contract; `02_EXECUTION_CONTRACT.yaml` is its structured mirror.

Do not start implementation until the preceding Documents single-verification-writer plus exact-association PR is **merged into `Staging`**. Rebind to the actual post-merge `Staging` SHA; create ONE fresh feature branch and preserve unrelated work.

Implement 0..N actual physical loads for one PlasticOS transaction, with at most one source-proven owning transaction per load, no nondeterministic first-load shortcuts. Preserve historical one-load compatibility, exact Documents verification/association semantics, claims, immutable freight history, financial data, delivery and dispatch controls, company boundaries, and native PO-only Stock receiving without invented orders/transactions/loads.

Refresh the source and consumer census. Implement the schema and lossless, idempotent, reversible historical migration. Correct all mechanically affected consumers, including claim load attribution, Documents load lookups, dashboard SQL, freight context, Logistics UX and existing tests. Do not change global ACLs, admitted invariants, frozen BRS, financial formulas, Export, warehouse/shop-floor, AI or external mailing.

Add and run ALL required positive/negative tests in `05_REQUIRED_ACCEPTANCE_MATRIX.json` on real Odoo 19 Enterprise. Perform both fresh-install and upgrade/replay/rollback verification on protected EE clones. Reconcile the old links against an authorized real-pattern historical dataset, not synthetic fixtures alone, and prove no financial, claim, documentary, freight or dispatch facts were changed or lost. Do not claim PASS for unrun cases.

Work autonomously on in-scope defects, then rerun the final tree's tests, repository checks, `make install-smoke`, `make test-odoo`, `make pr-check` and pre-commit. If any required proof is UNKNOWN/FAILED, stop as BLOCKED with a traceable recovery action, keep lawful local progress, and do NOT publish an unverified PR.

Only after complete validation, commit the scoped final tree and invoke **`make pr`** to publish exactly ONE independent PR against Staging. No raw push, second PR, merge, Production deployment, or scope expansion. Return PR URL/head SHA, actual test logs, before/after migration and historical data reconciliation, per-probe acceptance results, and the final execution receipt.
