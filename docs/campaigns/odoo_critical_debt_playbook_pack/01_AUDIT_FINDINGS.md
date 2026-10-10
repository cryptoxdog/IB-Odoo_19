# GAR Architecture Audit Findings

## Audit subject

Repository: `cryptoxdog/IB-Odoo_19`

Historical observation used to form this pack: `Staging@73b27e6c902468cb76ee4d1ec4db89432ab9d939`.

**Execution-time rule:** this SHA is evidence provenance only. Do not require it to still be current. Bind the then-current `origin/Staging` before each slice.

## Scope

Original supplied finding set:

- 8 `N_PLUS_ONE_QUERY`
- 2 `SENSITIVE_DATA_LOGGED`

The recursive audit found that these symptoms collapse into five root causes.

---

## GAR-PROD-001 — PO delivery-term optimization can silently change semantics

### Current semantics

`purchase.order._compute_delivery_term_from_transaction()` derives the transaction through:

`plasticos.transaction.purchase_order_ids` Many2many membership.

### Dangerous proposal rejected

Do **not** switch that compute to:

`purchase.order.origin -> sale.order -> transaction_id`

That path exists elsewhere as a workflow helper, but it is not the current semantic owner of this compute.

### Required correction

Preserve the exact M2M predicate and batch it across the recordset.

Expected shape:

```text
all PO ids in self
      ↓
one transaction search where purchase_order_ids IN self.ids
      ↓
construct PO -> transaction mapping
      ↓
assign delivery_term per PO
```

No origin substitution.

---

## GAR-PROD-002 — `load.transaction_id` is not proven authoritative

### Current topology

`plasticos.transaction.load_id` is persisted.

`plasticos.load.transaction_id` is a stored computed reverse lookup.

### Hidden assumption

The compute creates a map keyed by `load_id`, which assumes one transaction per load. The current schema did not show an explicit uniqueness constraint enforcing that cardinality.

### Risk

If multiple transactions reference one load:

- the computed map selects one according to record iteration;
- `search(..., limit=1)` may select another;
- replacing the search with `rec.transaction_id` can change behavior.

### Required correction

Prove the business invariant first:

> Is one load allowed to belong to exactly one transaction?

If YES:

1. census existing data for duplicate non-null transaction `load_id` assignments;
2. reconcile conflicts if any;
3. enforce one-to-one at the database boundary;
4. preserve friendly validation if needed;
5. prove inverse recomputation;
6. then consume `load.transaction_id` everywhere in the scoped paths.

If NO:

- do not add a uniqueness constraint;
- do not promote `load.transaction_id` to authoritative;
- batch the existing reverse lookup while preserving the old selection semantics.

This is a blocking design fact for Slice A.

---

## GAR-PROD-003 — transaction profile N+1 is also stored-compute correctness debt

### Current behavior

Stored transaction profile fields use `search()` inside compute methods, while `@api.depends` references transaction-side fields but not the profile relationships being searched.

### Risk

Odoo cannot infer that later changes to facility/material profile relationships should invalidate a stored transaction cache when those relationships are hidden inside arbitrary searches.

### Consequence

This is not only performance debt. It can become stale-data correctness debt.

### Required correction

Where semantics allow, compute through declared relational dependencies and Odoo prefetch. Where selection predicates are more complex, preserve the existing predicate but explicitly close the recomputation contract.

Do not conflate:

- `supplier_profile_id` / `buyer_profile_id` polymer-based profile matching;
- `supplier_material_id` PO-partner material profile matching;
- `buyer_facility_id` sale-order partner facility profile matching.

They are currently different concepts.

---

## GAR-PROD-004 — material-profile selection is not inherently single-valued

Current material-profile uniqueness is approximately:

`unique(partner_id, polymer_id, form_id)`

A partner may legally have multiple material profiles.

Therefore this shortcut is invalid:

`partner.material_profile_ids -> take first`

### Required correction

For this campaign:

- preserve the existing predicate of each compute;
- batch it;
- make selection deterministic;
- do not redesign material-profile semantics;
- do not merge or rename existing cached fields.

A broader domain-model consolidation belongs to a separate architecture campaign.

---

## GAR-PROD-005 — facility uniqueness precheck is not batch-correct

The authoritative invariant already exists as a DB constraint:

`unique(partner_id)`

The current create/write prechecks are friendly UX guards but execute per record.

They miss or poorly handle:

- duplicates within one `model_create_multi` request;
- multi-record writes converging onto one partner;
- efficient set-based conflict resolution.

### Required correction

Keep the DB constraint as final authority.

Replace the procedural guard with one set-oriented validation helper that:

1. derives intended partner assignments for the whole operation;
2. detects duplicates inside the request itself;
3. performs one query for persisted conflicts;
4. excludes the records being updated correctly;
5. prefetches display names for a friendly `ValidationError`.

Concurrent writers remain protected by the database constraint.

---

## GAR-PROD-006 — commission uniqueness lacks concurrency-safe authority

Business invariant:

> At most one active commission rule per sales representative.

Current code uses search-before-write logic only.

### Race

Two concurrent writers can both search, observe no active rule, then both persist.

### Required correction

Move the invariant to the database boundary using an Odoo-19-compatible conditional uniqueness mechanism proven against the target runtime.

Keep a batch-aware precheck only for friendly UX.

Must cover:

- single create;
- multi-create;
- duplicate reps within the same batch;
- write changing rep;
- inactive -> active;
- active rule moved to another rep;
- multi-record writes;
- concurrent writers.

Before adding the DB invariant, census existing active-rule duplicates. Do not impose the constraint over dirty data.

---

## GAR-PROD-007 — performance scanner is semantically unsound

Current detector relies heavily on source-line spelling such as literal `self.env` inside loop context.

### False negatives

It can miss:

- `self.search(...)`;
- `Profile.search(...)`;
- local model aliases.

### Category error

It treats `browse()` as if it were itself an SQL query. `browse()` primarily constructs a recordset; field access may later cause reads.

### Required correction

Move to AST-based detection and distinguish at least:

- query/read-in-loop;
- mutation-in-loop;
- recordset construction.

Recognize equivalent ORM call shapes without filename-specific exceptions.

### Sequencing correction

Do **not** repair this first. A truthful scanner may expose unrelated debt and accidentally widen the campaign.

Repair the scoped runtime causes first, then harden the scanner, then report unrelated newly visible findings separately.

---

## GAR-PROD-008 — security scanner detects vocabulary, not leakage

The current scanner flags any logging line containing words such as `api_key`, `token`, or `secret`.

The two scoped migration findings are static prose and do not emit secret values.

### Required correction

Analyze logging calls structurally.

Expected outcomes:

- constant prose containing `api_key` -> no finding;
- dynamic secret variable interpolation -> finding;
- f-string secret interpolation -> finding;
- logging format argument containing secret value -> finding.

Do not modify the harmless migration messages.

---

## GAR-PROD-009 — truthful scanners may expose same-root latent findings

For example, aliased `Profile.search()` inside `_compute_profile_refs()` is part of the same relationship/search pattern but can be invisible to the current scanner.

This does not authorize scope expansion.

Required behavior:

- close the scoped root causes;
- improve the scanner honestly;
- report unrelated/newly exposed findings as future work;
- do not baseline them merely to obtain green.

---

## GAR-PROD-010 — runtime module propagation is mandatory

Repo-native law requires manifest version advancement for runtime-affecting `plasticos_*` module changes.

Likely affected runtime modules in this campaign:

- `plasticos_transaction`
- `plasticos_logistics`
- `plasticos_facility_profile`
- `plasticos_commission`

Scanner-only changes do not require addon version bumps.

If a DB migration is required for commission uniqueness, it must be placed under a **new version** with matching manifest version. Do not edit an already-consumed migration version and expect it to rerun.

---

## GAR-PROD-011 — scanner silence is insufficient proof

Every runtime repair needs behavior proof. See `60_ACCEPTANCE_MATRIX.md`.

---

## GAR-PROD-012 — baseline cleanup is terminal, not causal

Correct order:

```text
runtime root cause fixed
      ↓
behavior proven
      ↓
scanner semantics fixed
      ↓
fresh audit
      ↓
old fingerprints become stale
      ↓
remove stale entries
```

No new suppression entries for repaired paths.
