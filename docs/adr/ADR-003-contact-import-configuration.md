# ADR-003: Contact Import Configuration

**Status:** Accepted
**Date:** 2026-03-13
**Deciders:** Igor Beylin
**Scope:** `plasticos_partner_import`, `plasticos_base`

## Context

PlasticOS imports counterparties from a legacy ERP system via two CSV files. The import must create a hierarchical partner structure that maps to Odoo's native `res.partner` model while preserving business relationships (corporate → facility → contact) and leveraging Odoo's built-in address selection for invoicing and delivery.

## Decision

### Import Order

The import runs in two sequential phases via the Import Partners wizard:

1. **Phase 1 — Corporate CSV** → top-level `res.partner` (companies)
2. **Phase 2 — Facility CSV** → child `res.partner` (addresses, locations, contacts)

Corporates must be imported first because facilities reference them by name via `partner_id`.

### Partner Hierarchy

```
ACME RECYCLING (company, type=contact)              ← corporate entity
├── ACME RECYCLING - Inv/Remit (person, type=invoice)  ← billing address
├── CHARLOTTE NC (company, type=contact)               ← physical facility
│   └── Doug Smith (person, type=delivery)             ← site contact
├── ATLANTA GA (company, type=contact)                 ← physical facility
│   └── Jane Doe (person, type=invoice)                ← AR/AP contact
└── Mike Johnson (person, type=contact)                ← corporate contact
```

### Odoo Field Mapping by Record Type

| Record Type | `is_company` | `type` | `parent_id` | Rationale |
|---|---|---|---|---|
| Corporate | `True` | `contact` | `False` | Standalone business entity |
| Inv/Remit address | `False` | `invoice` | Corporate ID | Odoo uses `type=invoice` for billing address selection on SO/PO |
| Physical facility | `True` | `contact` | Corporate ID | Independent operating location with own contacts |
| Person contact | `False` | `invoice`/`contact`/`delivery` | Facility or Corporate ID | AR/AP/delivery logic based on parent's supplier/customer rank |

### Corporate CSV Column Mapping

| CSV Column | Odoo Field | Notes |
|---|---|---|
| `ref` | `ref` | Legacy system ID |
| `role` | `supplier_rank`, `customer_rank`, `category_id` | Parsed into ranks + tags |
| `user_id` | `user_id` | Salesperson, looked up by name |
| `name` | `name` | Company name |
| `street` | `street` | |
| `street2` | `street2` | |
| `city` | `city` | |
| `state_id` | `state_id` | Looked up by state code |
| `zip` | `zip` | |
| `country` | `country_id` | Looked up by name or ISO code |

### Facility CSV Column Mapping

| CSV Column | Odoo Field | Notes |
|---|---|---|
| `partner_id` | Parent lookup | Matched to corporate by name |
| `Type` | Controls `is_company` and `type` | `Remit`/`Inv/Remit`/`Invoice`/`Primary` → invoice address; `Location` → facility |
| `Alias` | `name` | Used as facility name (if not "INVOICE") |
| `address` | `street` | |
| `adderess2` | `street2` | Typo preserved from source CSV |
| `city` | `city` | |
| `state` | `state_id` | |
| `zip` | `zip` | |
| `country` | `country_id` | |
| `Contact` | Child `res.partner` name | Creates person contact under facility |
| `Phone` | Child contact `phone` | |
| `Email` | Child contact `email` | Smart email matching when multiple addresses present |

### Role Parsing and Tag Assignment

The CSV `role` column supports comma-separated values (e.g., `"Customer,Supplier,Expense"`).

**Rank assignment** (controls Odoo's vendor/customer visibility):
- `Supplier` → `supplier_rank = 1`
- `Customer` → `customer_rank = 1`

**Tag assignment** (maps to `res.partner.category` defined in `plasticos_base/data/partner_tags.xml`):

| CSV Role | Tag XML ID | Tag Name |
|---|---|---|
| `Customer` | `plasticos_base.tag_buyer` | Buyer |
| `Supplier` | `plasticos_base.tag_supplier` | Supplier |
| `Expense` | `plasticos_base.tag_expense` | Expense |
| `Broker` | `plasticos_base.tag_broker` | Broker |
| `Carrier` | `plasticos_base.tag_carrier` | Carrier |
| `Processor` | `plasticos_base.tag_processor` | Processor |

Tags are inherited by child facilities from their corporate parent.

### Contact AR/AP Logic

When creating person contacts under facilities, the contact `type` is determined by the corporate parent's role:

- Supplier → `type=invoice` (AR contact — we pay them)
- Customer → `type=contact` (AP contact — they pay us)
- Both → `type=invoice` (AR takes priority)
- Location facility → `type=delivery` (shipping contact)

### Deduplication

- **Corporates**: Deduplicated by external ID derived from `ref` column
- **Facilities**: Deduplicated by external ID derived from `partner_name + alias + row_num`
- **Contacts**: Deduplicated by `(corporate_id, name, email)` tuple within a single import run

### Payment Terms

All imported corporates receive the default payment term (Net 30 from `plasticos_accounting.payment_term_net_30`) assigned to:
- `property_payment_term_id` if customer
- `property_supplier_payment_term_id` if supplier

## Consequences

### Positive

- Odoo's native address selection on sale orders and invoices works automatically
- Facility locations can carry their own contacts, equipment profiles, and material profiles
- Tags enable filtering contacts by role in list views and reports
- Idempotent upsert allows re-running imports safely

### Negative

- Corporate names must match exactly between the two CSV files (facility lookup is by name)
- The `adderess2` typo in the facility CSV must be preserved in the import code
- Contacts without a matching corporate parent are silently skipped
