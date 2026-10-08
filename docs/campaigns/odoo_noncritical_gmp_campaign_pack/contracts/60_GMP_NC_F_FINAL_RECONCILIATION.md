# GMP-NC-F — Final Non-Critical Register Reconciliation

## Contract

**ID:** GMP-NC-F  
**Tier:** Assurance / Campaign Closure  
**Objective:** Rebuild the non-critical register from current truth after upstream remediation and produce the final production-readiness debt view.  
**Predecessors:** consume completed evidence from GMP-NC-A through E, plus the earlier High/Critical production-debt campaign where relevant.  
**Expected runtime behavior change:** none.

## Locked scope

This is a reconciliation/evidence stage.

It does not authorize application fixes.
If a real remaining defect is discovered, record it as a new bounded candidate rather than patching it here.

## Phase 0 — Bind final subject

Record:

- current `Staging` SHA;
- predecessor PRs/HEADs/receipts actually present;
- any completed prior High/Critical remediation relevant to scanner truth.

If a declared predecessor is absent, mark it absent. Do not assume completion.

## Phase 1 — Generate fresh register

Run the exact-current audit surfaces needed to enumerate:

- Moderate extended-audit findings;
- Medium XPath findings;
- weak-test advisory findings;
- any other explicitly tracked non-critical register entries.

Do not reuse historical counts as current truth.

## Phase 2 — Classify every survivor

Every survivor must be exactly one of:

- `REAL_DEBT`
- `FALSE_POSITIVE`
- `ACCEPTED_BOUNDED_DEBT`
- `UNKNOWN`

No unclassified findings.

For accepted bounded debt record:

- owner;
- reason acceptance is safe;
- operational bound;
- trigger for re-evaluation.

`UNKNOWN` blocks a clean closure claim.

## Phase 3 — Compare campaign delta

Produce a before/after matrix for each original family:

```text
original count
scanner-noise removed
real debt repaired
accepted bounded debt retained
unknown
current count
```

Do not claim that count reduction alone proves improvement.

## Phase 4 — Ownership audit

Prove one owner per concern:

- weak-test semantics;
- Odoo runtime coverage claim surface;
- privilege-elevation policy;
- state-bypass policy;
- performance/query-boundedness semantics;
- XPath anchor policy.

Duplicate authority is a failure even if counts are low.

## Phase 5 — No-reopen check

Verify this campaign did not reopen or regress:

- High N+1 remediation;
- High sensitive-logging remediation;
- stored-profile correctness;
- load cardinality;
- facility/commission uniqueness;
- High baseline work.

If a regression exists, report it. Do not repair it in GMP-NC-F.

## Phase 6 — Final evidence report

Emit the final campaign report with:

- exact final SHA;
- current register;
- root-cause closures;
- unresolved real debt;
- accepted bounded debt;
- UNKNOWNs;
- production-readiness recommendation for this register only.

Publication, if needed, uses only the verified current repo-native ceremony.

## Acceptance

CLOSED only if:

- false claims and duplicate audit authority are eliminated;
- every survivor is classified;
- UNKNOWN = 0 for a clean closure verdict;
- no previous Critical/High remediation is reopened or regressed;
- the final register reflects real engineering risk rather than scanner exhaust.
