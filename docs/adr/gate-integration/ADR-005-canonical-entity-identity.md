# ADR-005: Canonical Odoo entity identity is `entity.id`

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

Cross-service consumers need one stable way to name the Odoo record an
enrichment is about. An Odoo-private key (`_odoo_entity_id`) had been carried
on the entity without the canonical `entity.id` that other consumers read,
which made Odoo's identity legible only to code that already knew Odoo.

## Options Considered

### Option A: Canonical `entity.id` = `"res.partner:<database-id>"` (chosen)
- Pros: stable, explicit, globally interpretable in the application domain,
  independent of mutable CRM field contents; matches the `<model>:<id>` entity
  reference form already used for match candidates.
- Cons: exposes the Odoo database id across the service boundary.

### Option B: Keep `_odoo_entity_id` as the identity
- Pros: no change required.
- Cons: an underscore-prefixed private key is not a contract; consumers reading
  `entity.id` see nothing.

### Option C: Derive identity from a natural key (name/email/domain)
- Pros: meaningful without Odoo; survives database reloads.
- Cons: derived from mutable CRM contents — the identity changes when a user
  edits a field, which breaks replay and audit. **Rejected.**

## Decision

Canonical Odoo identity is:

```
entity.id = "res.partner:<database-id>"
```

```json
{
  "entity": {
    "id": "res.partner:123",
    "_odoo_entity_id": "res.partner:123"
  }
}
```

`_odoo_entity_id` may remain temporarily as compatibility metadata carrying the
same value. It is not the canonical identity and must not replace `entity.id`.

## Consequences

- Identity must never be derived from `name`, `email`, `phone`, a payload hash,
  a record serialization, or volatile enrichment state.
- Consumers migrate to `entity.id`; `_odoo_entity_id` may be retired once no
  consumer reads it.
