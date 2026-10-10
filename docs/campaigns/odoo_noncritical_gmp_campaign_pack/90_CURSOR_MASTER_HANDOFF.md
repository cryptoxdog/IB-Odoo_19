# Cursor Master Handoff

You are executing a bounded, multi-GMP non-critical debt campaign in `cryptoxdog/IB-Odoo_19`.

## Operator intent

We are not patching individual files to make scanners quiet. We are curing the upstream cause of each finding family.

## How to use this pack

1. Read `00_README.md`, `01_CAMPAIGN_MAP.md`, and `02_AUDIT_BASIS.md` once.
2. Execute **one GMP contract at a time** from `contracts/`.
3. At the start of each GMP, bind the current repository state. The repo is actively developing.
4. Follow that GMP's Phase 0–6 flow.
5. Before mutation, establish the modification lock.
6. Do not reopen earlier completed GMPs unless a proven contradiction blocks the current contract.
7. Emit the evidence report using `80_FINAL_REPORT_TEMPLATE.md`.
8. Stop at contract completion. Do not automatically begin the next GMP unless explicitly instructed.

## Global prohibitions

- no symptom patching;
- no blanket baselining;
- no fake assertions;
- no helper-name prefix counted as an assertion;
- no blind `limit=1`;
- no comment added only to silence `UNJUSTIFIED_SUDO`;
- no positional XPath repair, and no positional form left on the safe-pattern whitelist;
- no global sudo abstraction;
- no deletion of `STATE_BYPASS` without a containment proof;
- `UNKNOWN` blocks closure and does not authorize a silencing patch;
- no duplicate state-audit framework;
- no new file for convenience;
- no unrelated cleanup;
- no alternate publication command if current `make pr` is unavailable or semantically wrong;
- no claim of success from a green scanner when behavior/evidence is unresolved.

## Success definition

A GMP succeeds when its root cause is closed at the highest valid owner, behavior is preserved or intentionally strengthened, the before/after finding delta is explained, and the stage emits independently checkable evidence.
