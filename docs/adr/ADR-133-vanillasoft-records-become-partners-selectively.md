# ADR-133: VanillaSoft records become partners selectively; cold records stay CRM leads

**Status:** Accepted (operator decisions D32 and D33 final; D29, D30 and D31 amended; 2026-11-16/17)
**Decision date:** 2026-11-17
**Applies to:** `plasticos_crm_sync` (VanillaSoft import), `plasticos_crm_bridge` (mapping and CRM tags)
**Decision owner:** Operator (campaign C1)
**Implementation owner:** `plasticos_crm_sync`, `plasticos_crm_bridge` (this PR)
**Related:** ADR-131 (sites and native classification), ADR-132 (where material profiles go)

## Context

- Gate matching and enrichment run only on `res.partner`, never on `crm.lead`.
- So a buyer or supplier that exists only as a VanillaSoft lead can never be matched, enriched or offered material.
- Importing every lead as a partner would flood partners with dead and cold records.

## Decision

1. A qualified record becomes a partner: the company, its people, its Company Type, and its materials, placed by ADR-132. The `crm.lead` stays the pipeline record, with `partner_id` set to that company.
2. The qualification bar is looser for buyers, because a buyer widens matching reach:
   - A record whose Buyer/Supplier field contains **Buyer** qualifies at every status except 2c COLD, 5 Dead Lead, 6 Wrong #, 7 Do Not Call and 8 Duplicate. This includes 1, 2, 2a, 2b, 3 and 4 Unqualified.
   - A **supplier-only or unspecified** record qualifies at 2a HOT, 2b WARM, 3 Resist, or when the contact is approved.
   - Everything else stays a CRM lead, with its Company Type on the lead's CRM tags.
3. Every partner creation first runs the duplicate match and reuses a match.
   - ERP partners are checked first.
   - Several matches are refused and reported, never guessed.
   - Ranks and Company Roles tags are raised, never lowered.
4. 7 Do Not Call on an existing partner sets the DNC status tag, and adds the record's emails and phones to the native mail and phone blacklists. Nothing is removed.
5. The trade role is shown as the Buyer and Supplier tags synced from the native ranks, with no Both or Broker label. Broker is a Company Type.

## Consequences

- No new field or model.
- Matching and enrichment reach these partners, so enrichment raises their value over time (the flywheel).
- Cold records stay out of partners until their status changes; a later run promotes them.
- The bar is tunable in one place, `plasticos_crm_sync/services/vanillasoft_partners.py`:
  - `partner_allowed()`
  - `BUYER_EXCLUDED_STATUSES`
  - `SUPPLIER_QUALIFIED_STATUSES`
- The duplicate match is `SyncOrchestrator._existing_company`. It matches a normalized company name (case, punctuation, "&"/"and" and legal suffixes ignored), ERP `legacy_erp_cp_*` companies first. A stricter matcher replaces that method only.
- `make import-vanillasoft` stays operator-run, on Production only (AGENTS.md 2026-11-10).
