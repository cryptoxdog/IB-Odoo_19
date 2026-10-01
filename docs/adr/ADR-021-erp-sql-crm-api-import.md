# ADR-021: ERP Data Imports from SQL, CRM Data Imports from the API

**Status:** Accepted
**Date:** 2026-10-01
**Deciders:** Igor Beylin
**Scope:** ERP partner and transaction import; VanillaSoft CRM import
**Supersedes:** The CSV transport in [ADR-003](ADR-003-contact-import-configuration.md). The partner hierarchy in ADR-003 stays.

## Context

Two inbound streams were documented as CSV wizards: ERP counterparties, and VanillaSoft leads. The ERP extract queries live in `plasticos_partner_import/erp_extracted_data/`. The row files checked in beside them are CSV grids copied out of SSMS. `docs/erp_import_mapping.md` then treated those grids as the authoritative payload. That split is how the import architecture drifted back to CSV.

CSV wizards are the retired path. New ERP work must not add another spreadsheet mapping. New CRM work must not add another lead CSV.

## Decision

1. **ERP data enters through SQL.** Partners, facilities, contacts, and historical transactions from the ERP are imported from SQL (`INSERT` statements or an equivalent statement payload). The scripts in `plasticos_partner_import/erp_extracted_data/` are the query definitions for that extract. They are not a CSV specification.
2. **CRM data enters through the API.** VanillaSoft leads and calls load only through `plasticos_crm_sync`. The Settings action is **Run VanillaSoft API Sync**.
3. **CSV import is legacy.** `plasticos_partner_import` CSV wizards, the CRM lead CSV wizard, and `plasticos_partner_import/erp_extracted_data/bulk/*.csv` are frozen. Do not extend them, do not add columns to them, and do not document them as the current architecture. `make import-erp` may still read the frozen grids until a SQL payload replaces that call. That compatibility is not permission to build the next import on CSV.
4. **Identity stays on source keys.** ERP upserts key on the ERP id (`CpID` and the related table keys), not on company name. CRM upserts key on the VanillaSoft id. ADR-003's company → facility → contact shape still applies when those SQL rows are loaded.
5. **One sentence for agents.** ERP import means SQL. CRM import means the VanillaSoft API. A CSV path is legacy.

## Consequences

- Partner import that unblocks VanillaSoft material profiles reads CounterParty, Address, and Contact from SQL, not from `bulk/CounterParty.csv`.
- `reader.load_payload()` already prefers `INSERT` statements over the grid extract. The SQL payload is the form that preference is for.
- Docs that call `bulk/` the authoritative payload are wrong as of this ADR. Point them here instead of restating a CSV architecture.

## Compliance

- Do not reintroduce a CSV wizard as the operator path for ERP or CRM.
- ADR-003 remains the hierarchy and rank/tag mapping. Its corporate-CSV / facility-CSV procedure does not.
