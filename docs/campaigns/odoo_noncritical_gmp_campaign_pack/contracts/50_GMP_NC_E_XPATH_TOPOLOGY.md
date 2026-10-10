# GMP-NC-E — XPath Anchor Topology Convergence

## Contract

**ID:** GMP-NC-E  
**Tier:** UI / XML Architecture  
**Objective:** Eliminate Medium XPath instability by repairing anchor ownership, not by inserting positional selectors.  
**Predecessor:** none required; branch from current `Staging`.  

## Governing rule

Current repo law requires stable **named** XPath anchors and forbids positional selectors. The checker must follow this law.

## Locked scope

Owned findings:

- `UNSCOPED_NOTEBOOK`
- `UNSCOPED_SHEET_NOTEBOOK`
- `UNSCOPED_LIST_FIELD`
- other Medium XPath findings produced by the same anchor-stability checker, if present in the fresh census.

Expected owners:

- affected `plasticos_*/views/*.xml` files;
- PlasticOS-owned parent views where a named structural anchor is genuinely missing;
- `ci/check_xpath_stability.py` guidance/logic;
- existing XML/view tests.

## Non-goals

- No `[1]`, `[2]`, positional-group, or `@string` repairs.
- No modification of upstream Odoo core views.
- No gratuitous view redesign.
- No unrelated XML cleanup.
- Do not revisit Critical/High XPath issues unless newly introduced by this GMP.

## Phase 0 — Bind current target

Record current SHA, current XPath policy, current checker behavior, and current Medium finding set.

## Phase 1 — Group by inheritance topology

Do not treat findings as independent files.

Group them by:

```text
inherit_id
-> parent view
-> structural insertion point
-> downstream child views
```

For every group determine whether the parent is:

- PlasticOS-owned;
- Odoo-owned;
- UNKNOWN.

## Phase 2 — Select highest valid anchor owner

### PlasticOS-owned parent

Reuse an existing named structural node if possible.
Only if no lawful stable owner exists, add a named anchor to the owning parent view, then migrate children to consume it.

### Odoo-owned parent

Do not modify Odoo core. Target an existing stable named `field`, `page`, `group`, `div`, or other durable node and use `before`, `after`, or `inside`.

### Unknown parent semantics

Stop that finding group rather than inventing a positional selector.

### `UNSCOPED_LIST_FIELD`

This finding is a list-field scoping repair (`//list/field[@name=...]`). Do not invent a notebook anchor for it.

## Phase 3 — Implement topology repair

Repair the minimum set of authoritative anchors and dependent selectors.

Runtime XML module changes require current module version/upgrade obligations.

No new view file unless the invariant cannot be satisfied in an existing owner.

## Phase 4 — Align checker to canonical policy

The checker must no longer recommend forbidden fixes such as:

- `//notebook[1]`
- `//sheet/notebook[1]`

In the same change, delete the safe-pattern entries that treat those positional forms as already safe, including `//notebook[1]`. Leaving the whitelist in place blesses the repair this contract forbids.

Guidance must prefer stable named anchors consistent with repo law.

Do not weaken detection merely to make the report empty.

High class-based positional guidance stays sealed. Report it. Do not repair it in this GMP.

## Phase 5 — Runtime/view proof

Prove:

- affected inherited views compile/load;
- selectors resolve exactly where intended;
- no positional selector was introduced;
- no Odoo core file changed;
- before/after Medium counts are explained;
- no new High/Critical XPath issue was introduced.

## Phase 6 — Evidence and publication

Report by inheritance family, not only by file. Include parent owner, chosen anchor, child consumers, module version changes, and validation evidence.

Publish only through the verified current repo ceremony.

## Acceptance

PASS only if:

- positional repair count = 0;
- checker guidance matches canonical named-anchor law;
- positional notebook forms are absent from the safe-pattern whitelist;
- `UNSCOPED_LIST_FIELD` repairs scope to a named list field;
- all repaired view families have a clear authoritative anchor owner;
- affected views validate at runtime or through the strongest current faithful view proof;
- unrelated XML work is absent.
