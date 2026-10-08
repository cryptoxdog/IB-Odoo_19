# Slice A — Runtime Relationship Correctness

## Objective

Eliminate scoped per-record relationship rediscovery in transaction, purchase-order, and load flows **without changing relationship semantics**.

## Entry binding

Before modifying code:

1. record exact current `origin/Staging` SHA;
2. inspect the exact current versions of the files named below;
3. compare them with this playbook;
4. if the relevant semantics materially changed, STOP and emit a delta report instead of forcing this plan onto new architecture.

## Primary owners

Expected existing files only:

- `plasticos_transaction/models/transaction.py`
- `plasticos_transaction/models/purchase_inherit.py`
- `plasticos_logistics/models/load.py`
- `plasticos_logistics/models/transaction_inherit.py`
- affected addon `__manifest__.py` files
- existing appropriate tests where possible

No new runtime model field is authorized.

---

## A1 — Transaction profile computations

### Preserve concepts

Do not merge or rename:

- `supplier_profile_id`
- `buyer_profile_id`
- `buyer_facility_id`
- `supplier_material_id`

### Buyer facility

Current semantic predicate:

`sale_order_id.partner_id -> facility profile for that partner`

Because facility profile already has one-per-partner DB uniqueness, this is a strong candidate to consume `partner.facility_profile_ids` with recordset prefetch instead of per-transaction search.

Harden the dependency graph so a facility-profile relationship change causes the stored transaction field to become correct.

### Supplier material from PO

Preserve the existing predicate:

`first purchase order partner -> material profile by partner`

Do not silently add polymer/form criteria in this slice.

Batch the required lookup across all relevant transactions/partners. If multiple material profiles qualify under the current weak predicate, preserve deterministic current-compatible selection and document it as separate domain-model debt rather than redesigning semantics here.

### Polymer profile refs

`_compute_profile_refs()` matches partner + product polymer. This is same-root latent debt. It may be repaired in this slice because it is the same authoritative compute family, but do not broaden beyond this family.

Batch by the finite set of `(partner_id, polymer_id)` keys and preserve current first-match semantics.

### Proof

Tests must demonstrate multi-record computation and correct recomputation after profile relationship mutation where the new dependency design claims that behavior.

---

## A2 — Purchase-order delivery term

### Mandatory semantic lock

Use only the M2M relation:

`plasticos.transaction.purchase_order_ids`

Do not substitute `origin` or sale-order traversal.

### Implementation shape

One batched search for all POs in `self`, then map each PO to the qualifying transaction and assign `delivery_term`.

### Ambiguity

If more than one transaction can legally contain the same PO, do not invent a winner. Determine whether the model already prevents this. If not, preserve current selection behavior or STOP if deterministic preservation cannot be proven.

---

## A3 — Load relationship cardinality proof

Before replacing any reverse search with `load.transaction_id`, establish whether one load may be linked from more than one transaction.

### Required data census

On the current target DB intended for validation, determine whether any non-null `plasticos.transaction.load_id` appears on multiple transactions.

### Decision

#### If cardinality is one-to-one by business law

Implement the smallest database-level invariant on transaction `load_id` that makes duplicate non-null assignment impossible.

Before constraint installation:

- prove current data is clean;
- if dirty, STOP and report the conflicting records for explicit remediation.

Then prove `load.transaction_id` is a faithful inverse.

#### If cardinality is not one-to-one

Do not add uniqueness.

Do not use `load.transaction_id` as singular authority.

Batch the existing transaction lookup across the load recordset while preserving current behavior.

---

## A4 — Load create

Current behavior links a newly created load to a transaction using `sale_order_id` and only when transaction supplier and buyer are complete and transaction has no load yet.

Optimization must preserve every guard.

Preferred path if semantics prove equivalent:

- exploit already-owned sale-order transaction relation in batch;
- otherwise one batch transaction query keyed by sale-order IDs.

No per-load transaction query.

---

## A5 — Load close chatter

Current behavior posts `"Logistics closed."` to the linked transaction when a load closes.

After A3 cardinality resolution:

- if one-to-one is enforced, consume the faithful inverse relation;
- otherwise batch-resolve transactions using the preserved old predicate.

Prove exactly one expected chatter post per scoped transaction/load event.

---

## A6 — Delivery-term override compute

Same rule as A5.

Do not use `load.transaction_id` merely because it exists. Use it only if A3 proves it authoritative.

---

## A7 — Runtime propagation

Any changed runtime addon must bump its manifest version in the same change set.

Expected candidates:

- `plasticos_transaction`
- `plasticos_logistics`

Do not bump unaffected modules.

If a new DB constraint on `transaction.load_id` requires migration behavior for an installed environment, follow the repo-native version/migration contract and use a new versioned migration path.

---

## Slice A stop conditions

STOP instead of improvising if:

- PO M2M semantics cannot be preserved;
- load cardinality remains ambiguous;
- current data violates a proposed new load invariant;
- a new model field appears necessary;
- current Staging has materially changed these relationship contracts.

## Slice A completion evidence

Report:

- starting Staging SHA;
- changed files;
- addon version bumps;
- load-cardinality evidence and decision;
- multi-record behavior tests;
- recomputation tests;
- query-shape evidence showing scoped per-record lookups removed;
- any newly discovered but out-of-scope issues.
