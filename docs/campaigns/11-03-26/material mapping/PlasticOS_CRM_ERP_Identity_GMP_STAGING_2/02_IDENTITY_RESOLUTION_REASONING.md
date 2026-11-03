# Why this cross-source contact resolution is the right correction

**Purpose:** evidence and reasoning for the frozen matching rules. This document is explanatory, not an alternative execution authority or permission to edit code.

## Business problem

The ERP importer and VanillaSoft importer both track valid source identities, but they do not yet recognize when one ERP person and one VanillaSoft ContactID describe the same human. The ERP importer creates `res.partner` records keyed by `Contact.CT_ID` external XMLIDs; VanillaSoft currently upserts `crm.lead` keyed by its provider source ID. A naïve VanillaSoft full import can therefore create a redundant lead or duplicate contact even though the ERP person already exists.

The import objective is not "deduplicate by matching strings." It is **bind the operator-confirmed source identities to one existing Odoo person, keep ERP data authoritative, and retain all CRM history**.

## Evidence supporting the choice

1. **Human-reviewed pairs are the approved identity input.** The operator confirmed **763** VS source IDs and rejected **18** suggested links. Within the approved set there are 541 STRONG, 173 LIKELY and 49 REVIEW-tier rows. All 763 are accepted, so lowering their status due to heuristic mismatches would countermand the operator's decisions. The prior derived **366 static holds are withdrawn**.
2. **Ranked candidates are not independent people.** The source sheet includes **457** lower-ranked candidate rows beyond the selected 763 pairs. Example: Todd Byrum (`572648103`) selects ERP CT_ID `2350001`, not candidate `2200001`. Eugene Niuh (`576094121`) selects `95700001`; other ranked possibilities are excluded. Creating a record per candidate would fabricate duplicates.
3. **Many-to-one mapping is intentional.** There are **716** distinct ERP selected targets. **45** targets account for **92** VanillaSoft source IDs. Multiple provider IDs may legitimately refer to a single already-grouped ERP person. A person name difference inside such a group is informative but cannot silently repeal a confirmed operator decision. Live database contradictions are handled separately and fail closed.
4. **Company casing is transport noise.** Legacy ERP labels are often uppercase while VanillaSoft uses title/mixed case and different suffixes. Treating case or common legal suffix differences as nonmatches inflated review counts with no improvement in identity fidelity.
5. **The ERP email column contains lists.** Comparing `scott@example.com; team@example.com` with `scott@example.com` as *whole strings* falsely says they differ. Individual casefolded full-address tokens give a meaningful positive signal. An arbitrary substring does **not**: `ann@example.com` must not match `joann@example.com`. An email signal supports screening but never replaces the approved source-ID crosswalk.
6. **Data disagreements are not permission to overwrite.** Scott Fidler (`1082805107` -> `192650001`) was explicitly confirmed with differing CRM/ERP email values. ERP wins the person field; the CRM email should remain available as tagged external-source evidence.
7. **A refusal is local to a suggested pair.** The 18 NO decisions reject those ERP targets. They do not prove the VanillaSoft person is wholly new, nor require exclusion from legitimate CRM activity. Similarly the 4,095 unreviewed source IDs are not authorized ERP matches just because they exist in the same report.

## Why pin source identities, not mutable attributes?

An email can be reassigned, a contact can change jobs, phone numbers can be shared, and uppercase formatting can change on the next extract. ERP `CT_ID` and VanillaSoft `ContactID` are the identifiers that can safely be replayed. Once a reviewed crosswalk pair is admitted to the actual Odoo source-reference table, the importer should resolve future syncs from that association. The CSV is the initial operator-approved bridge, **not a new canonical person key**.

The ERP importer already groups multiple source CT_ID aliases into one `res.partner` using `ir.model.data`. Resolving the chosen CT_ID's existing XMLID therefore preserves its own grouping decision. Guessing an Odoo `res.partner.id` from workbook numbers would be incorrect because database record IDs are installation-specific.

## Why contact-first requires more than a two-column join

At inspected `Staging` commit `4ac9bfa59bb3b1c595f2105d3a23326c72f0fb1e`:

- `plasticos_partner_import/models/erp_import_service.py`: `_import_person` upserts source XMLID aliases and `_merge_person_channels` rewrites ERP-owned person channels, including `comment` when populated.
- `plasticos_crm_sync/models/crm_external_ref.py`: `(provider,external_id,res_model,res_id)` can refer to a person, but uniqueness is only `(provider, external_id, res_model)`, so a provider ContactID can have a person mapping and a lead mapping unless the importer protects that conflict.
- `plasticos_crm_sync/services/orchestrator.py`: `_upsert_lead` and `_find_lead` search specifically for `crm.lead` references; `_sync_tables_for_lead` and `_upsert_calls` also route dependent data through a lead, buffering some unmatched rows as orphans.
- `plasticos_crm_sync/models/crm_call_event.py` and `crm_external_table_row.py`: provider-native call and row IDs exist; the current `lead_id` linkage alone does not provide the desired person-based presentation path.

Therefore skipping lead creation without re-routing calls, custom rows, notes and materials would cause **data loss by deferral**. The existing external-reference and provider-record concepts are the preferred starting point, not a new CRM importer or a new shadow contact model. Source-side uniqueness, pre-existing lead reconciliation, historical provider IDs, and repeat-sync behavior all require executable proof.

## Why the import CSV does not violate the source-transport boundary

ADR-021 requires ERP business data from direct SQL and VanillaSoft contacts/calls from its API. This CSV carries **only reviewed identity associations**, not ERP business rows or VanillaSoft contact payloads. The existing API/SQL pipelines remain authoritative; the CSV is controlled reconciliation input. It must be validated before use and must not be implemented as a manual full-contact CSV wizard, production seed dataset, or independent ETL service.

## Safety and evidence limits

The workbook proves the **operator's selected source pairs**, not that all 763 XMLIDs currently exist in a particular Odoo database. A disposable Odoo 19 Enterprise test clone must validate the target identities, existing conflicting leads/refs, and repeat import. Any live contradiction blocks the affected row with an explicit reason; it does not automatically revoke the operator's approval or re-open the old name/email review heuristics.

The target's accepted ADR-021 still describes full ERP document import as unimplemented while code paths now implement native commercial documents. That adjacent source contradiction is not a license to widen this CRM identity task. Inspect applicable authority for CRM import, preserve the contradiction separately, and do not edit the ERP ADR opportunistically.

## Decision and alternatives

| Alternative | Disposition | Why |
|---|---|---|
| Operator-approved source-ID mapping + existing external references | **Select** | Reproducible, replay-safe, honors business decisions and Odoo person identity |
| Require exact whole-cell email equality | Reject | ERP email cells contain multiple addresses |
| Fuzzy auto-merge on name/company alone | Reject | Changes of employer and shared company contact details cause false merges |
| Create `crm.lead` for each source candidate | Reject | Wrong granularity and duplicates ranked alternatives |
| Create a parallel CRM/ERP importer or a custom person-identity subsystem | Reject | Existing canonical importers and source-reference owner already exist |
| Drop calls or table rows on matched people without a lead | Reject | Silent data loss and broken replay |
| Overwrite ERP primary fields with CRM values | Reject | Contradicts operator precedence and ERP source replay ownership |

## Current source links (read-only observations)

- ERP source contact identity: https://github.com/cryptoxdog/IB-Odoo_19/blob/4ac9bfa59bb3b1c595f2105d3a23326c72f0fb1e/plasticos_partner_import/models/erp_import_service.py
- CRM source ref: https://github.com/cryptoxdog/IB-Odoo_19/blob/4ac9bfa59bb3b1c595f2105d3a23326c72f0fb1e/plasticos_crm_sync/models/crm_external_ref.py
- CRM orchestration: https://github.com/cryptoxdog/IB-Odoo_19/blob/4ac9bfa59bb3b1c595f2105d3a23326c72f0fb1e/plasticos_crm_sync/services/orchestrator.py
- CRM call model: https://github.com/cryptoxdog/IB-Odoo_19/blob/4ac9bfa59bb3b1c595f2105d3a23326c72f0fb1e/plasticos_crm_sync/models/crm_call_event.py
- CRM custom-row model: https://github.com/cryptoxdog/IB-Odoo_19/blob/4ac9bfa59bb3b1c595f2105d3a23326c72f0fb1e/plasticos_crm_sync/models/crm_external_table_row.py
- Governing CRM API/ERP SQL boundary: https://github.com/cryptoxdog/IB-Odoo_19/blob/4ac9bfa59bb3b1c595f2105d3a23326c72f0fb1e/docs/adr/ADR-021-erp-sql-crm-api-import.md
- GMP specialist (read-only current owner): https://github.com/Quantum-L9/Cursor-Governance/blob/8e38ce5debb9f8b3028b0f017c360663bf98f87c/skills/l9-gmp-protocol/SKILL.md

## Staging-code Docker execution rationale (operator clarification, 2026-10-16)

The mandatory target is **Odoo.sh Staging parity**, not Production parity. The current repository's `docker-compose.yml` maps the **working tree** to `/mnt/extra-addons`, so changes at a Staging-based candidate HEAD are the files loaded into the Odoo container; Odoo Enterprise comes from the read-only `/mnt/enterprise` volume. The `scripts/test_env.sh` database template has preinstalled Odoo modules, US accounting/localization and testable admission metadata, and serves as a fast source of disposable databases. It does not replace the working-tree code. The current-content fingerprint ensures database module installations remain consistent with the code under test; unchanged inputs reuse a previous admitted installation.

The original PR #230 proved live Community templates in one sandbox, explicitly **not Enterprise-parity operation**. The Enterprise source must exist on the actual operator's Docker host, and a current Staging-installed-module census has not been independently observed here. The declared 43 Enterprise/core-localization module list came from an older Production snapshot and is not definitive Staging parity. `docker-compose.yml` uses `postgres:15` while `AGENTS.md` lists PostgreSQL 16; the actual remote Staging version remains unverified, with engine changes out of this CRM mission's scope. These are evidence gaps, not authority to create a second environment.

There is a direct control gap: `make test-module` already uses `test_env.sh run` to protect owned clones, but `make import-vanillasoft` does not. The existing test-env command whitelist accepts `make import-erp`, not CRM import. For the end-to-end API integration acceptance, extend that existing safety seam surgically if still needed on current HEAD; forbid raw CRM import against an ambiguous database. This preserves the operator's one-substrate testing intent without creating a parallel importer or duplicate data.

Source coordinates (all inspected at `Staging@4ac9bfa59bb3b1c595f2105d3a23326c72f0fb1e`):

- https://github.com/cryptoxdog/IB-Odoo_19/blob/4ac9bfa59bb3b1c595f2105d3a23326c72f0fb1e/docker-compose.yml
- https://github.com/cryptoxdog/IB-Odoo_19/blob/4ac9bfa59bb3b1c595f2105d3a23326c72f0fb1e/scripts/test_env.sh
- https://github.com/cryptoxdog/IB-Odoo_19/blob/4ac9bfa59bb3b1c595f2105d3a23326c72f0fb1e/Makefile
- https://github.com/cryptoxdog/IB-Odoo_19/blob/4ac9bfa59bb3b1c595f2105d3a23326c72f0fb1e/config/odoo_module_order.yaml
- https://github.com/cryptoxdog/IB-Odoo_19/pull/230
