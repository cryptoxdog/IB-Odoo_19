# Slice B — Uniqueness Ownership

## Objective

Make facility-profile and commission-rule uniqueness correct under batch operations and concurrency.

## Expected owners

- `plasticos_facility_profile/models/facility_profile.py`
- `plasticos_commission/models/commission_rule.py`
- affected addon `__manifest__.py`
- a new versioned commission migration only if required by the chosen DB mechanism
- existing relevant test surfaces where possible

---

## B1 — Facility profile

### Existing authority

The DB already owns:

`unique(partner_id)`

Do not replace or weaken it.

### Repair the friendly guard

Create one reusable set-oriented validation path that reasons about the intended final partner assignments for the whole operation.

For create:

1. collect non-null partner IDs from `vals_list`;
2. reject duplicate IDs within the request;
3. one persisted-conflict search;
4. prefetch partner display names;
5. raise `ValidationError` before insertion.

For write:

1. derive each record's intended partner after applying `vals`;
2. detect collisions between records in `self`;
3. one persisted-conflict search excluding the records in `self`;
4. preserve the same user-facing business error.

DB uniqueness remains final concurrency protection.

### Do not

- query once per record;
- `browse()` solely to satisfy the old scanner;
- remove the DB constraint;
- relax one-profile-per-partner semantics.

---

## B2 — Commission rule

### Business invariant

At most one active rule per sales rep.

### Step 1: census before schema mutation

Before adding DB authority, prove whether current data contains any rep with more than one active commission rule.

If duplicates exist:

STOP and report exact conflicting rule IDs/reps. Do not auto-delete, deactivate, or choose a winner.

### Step 2: database authority

Implement a target-proven Odoo/PostgreSQL constraint that enforces uniqueness only for active rows.

The exact mechanism is intentionally not hard-coded here. Cursor must verify Odoo 19 and repo-native precedent on the current target before choosing the implementation.

### Step 3: friendly precheck

A reusable batch-aware precheck must evaluate the intended post-operation state and cover:

- create;
- `model_create_multi`;
- duplicate reps within the same create batch;
- write changing `sales_rep_id`;
- write changing `active` false -> true;
- simultaneous multi-record write;
- current-record exclusion.

The precheck is not the concurrency authority.

### Step 4: version/migration

Because the runtime model changes, bump `plasticos_commission`.

If a migration/index/constraint must be applied to an installed DB, create it at the new module version. Never edit a migration folder that may already have been consumed.

---

## Slice B required tests

### Facility

- duplicate existing partner rejected;
- duplicate partner IDs in one multi-create rejected;
- multi-record write converging onto one partner rejected;
- valid distinct partners succeed;
- database constraint still exists.

### Commission

- first active rule succeeds;
- second active rule same rep rejected;
- two same-rep active rules in one multi-create rejected;
- inactive rule for same rep remains legal if current semantics allow it;
- inactive -> active collision rejected;
- rep reassignment collision rejected;
- concurrent writers cannot persist two active rules.

The concurrency test must exercise the DB authority, not merely two sequential ORM calls.

## Slice B stop conditions

STOP if:

- existing data violates the proposed commission invariant;
- current business semantics actually allow multiple active rules per rep;
- the chosen DB mechanism cannot be proven on target Odoo/PostgreSQL;
- satisfying the invariant appears to require new business fields.
