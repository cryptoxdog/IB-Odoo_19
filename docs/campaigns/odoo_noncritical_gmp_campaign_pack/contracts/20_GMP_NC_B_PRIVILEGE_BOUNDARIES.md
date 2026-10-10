# GMP-NC-B — Privilege Boundary Convergence

## Contract

**ID:** GMP-NC-B  
**Tier:** Security / Runtime Ownership  
**Objective:** Convert `UNJUSTIFIED_SUDO` from comment noise into explicit domain-owned privilege boundaries, without removing legitimate authorization.  
**Predecessor:** GMP-NC-A recommended but not semantically required. Branch from current `Staging` unless stacking is necessary.  

## Locked scope

Owned finding family:

- `UNJUSTIFIED_SUDO`

Expected surfaces:

- modules containing current `sudo()` calls that survive the census;
- `scripts/audit/business_logic_audit.py` only as needed to align the scanner to existing repo law;
- existing security/runtime tests relevant to modified privilege boundaries.

## Non-goals

- No global `sudo_service`.
- No blanket removal of `sudo()`.
- No comments added merely to silence the scanner.
- No ACL/record-rule redesign unless required by a proven contradiction.
- Do not touch state-bypass ownership; GMP-NC-C owns that.

## Phase 0 — Bind current target

Record current `Staging` SHA and current security policy. Verify the repo still requires explicit same-boundary justification for `sudo()`.

## Phase 1 — Privilege census

Inventory every current `sudo()` call in runtime `plasticos_*` code and classify it into exactly one category:

1. system parameter/config access;
2. unattended cron/system maintenance;
3. server-owned evidence persistence;
4. user/workflow privileged mutation;
5. read-only dashboard/report elevation;
6. unnecessary elevation;
7. UNKNOWN.

For each call record:

- domain owner;
- caller identity before elevation;
- reason normal ACLs cannot be used;
- operation performed elevated;
- existing guard/authorization proof;
- whether multiple calls in the same module represent one repeated boundary.

No mutation until the census is complete.

## Phase 2 — Select upstream owner per category

Preferred shape:

```text
real caller/authority check
        -> module-owned boundary
        -> single justified elevation
        -> restricted privileged operation
```

Examples:

- repeated ICP access may converge behind an existing module-local config helper;
- server-owned evidence persistence must validate the real caller before elevation;
- cron/system maintenance must remain attributable to system execution;
- user-facing mutation must not use `sudo()` as an ACL escape hatch.

Do not generalize across domains merely for symmetry.

## Phase 3 — Implement only proven repairs

For each `sudo()`:

- remove it if unnecessary;
- centralize it only if the same module/domain already has an appropriate owner;
- preserve it with explicit same-boundary justification if it is legitimate;
- block on UNKNOWN rather than guessing authorization.

Runtime-affecting module changes must satisfy current module version/upgrade obligations.

## Phase 4 — Scanner alignment

After runtime ownership is correct, align the Moderate scanner with the repository's actual policy.

The scanner may verify that a legitimate elevation carries the explicit same-boundary justification repo law already requires. A comment on one of the preceding lines is not that justification. The suggested fix must not be "add a comment."

A justified elevation remains in the register as retained, not as open debt. `UNKNOWN` blocks a CLOSED verdict. It does not authorize a comment, a new abstraction, or an ACL change.

Do not introduce filename-specific exemptions.

## Phase 5 — Verification

For every modified privilege boundary prove:

- intended legitimate caller still succeeds;
- unauthorized caller does not gain new access;
- no record-rule/ACL bypass was silently broadened;
- privilege scope is no wider than before;
- before/after `UNJUSTIFIED_SUDO` count is explained.

Any newly discovered security concern outside this family is reported separately.

## Phase 6 — Evidence and publication

Report:

- census counts by category;
- every changed authorization boundary;
- any retained justified `sudo()`;
- any removed `sudo()`;
- all UNKNOWNs;
- module versions changed, if applicable;
- publication evidence.

Verify current publication semantics before using `make pr`; do not substitute another path.

## Acceptance

PASS only if:

- the scanner no longer treats a nearby comment as proof of authorization;
- a same-line justification required by repo law is recognized when the elevation is legitimate;
- unnecessary elevation found by the census is removed;
- a repeated boundary is centralized only when that module already has an owner for it;
- a legitimate elevation may remain, with explicit same-boundary justification;
- `UNKNOWN` blocks a CLOSED verdict and does not authorize a comment, a new abstraction, or an ACL change;
- no global privilege abstraction was introduced;
- no legitimate security boundary was weakened;
- scanner policy matches current repo law;
- previous Critical/High campaign remains sealed.
