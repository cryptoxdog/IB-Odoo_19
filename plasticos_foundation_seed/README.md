# plasticos_foundation_seed

Deterministic XML-only seed module for Odoo 19.

## Seeded Data
- Payment Terms (account.payment.term)
- Incoterms (account.incoterms)
- Sales Reps (res.partner + res.users)
- Chart of Accounts (account.account)
- Material taxonomy values (stored as res.partner.category tags)

## Notes
- No runtime CSV loaders
- No Python bootstrap logic
- Stable external IDs
- `noupdate="1"` discipline
- Idempotent install behavior

Generated from `csv_schema_index.json`.
