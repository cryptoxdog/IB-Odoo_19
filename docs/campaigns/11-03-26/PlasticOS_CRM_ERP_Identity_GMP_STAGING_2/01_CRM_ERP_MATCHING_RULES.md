# CRM <-> ERP Contact Identity Matching Rules

**Decision owner:** PlasticOS operator, 2026-10-16. **Purpose:** prevent creation of duplicate Odoo people or duplicate CRM leads for the approved VanillaSoft contacts while retaining their CRM history. **State:** binding implementation requirements; not a completed Odoo runtime import.

## 1. Identity authority and input

- The accompanying `03_APPROVED_CONTACT_CROSSWALK.csv` is the **only approved cross-source link set in this pack**. Header is exactly `erp_ct_id,vanillasoft_contact_id`; each column is a source ID stored as a string, not an Odoo database ID. CSV SHA256: `f22c707a7b6fceba40a20fa393e0c8887e3f05a8d183865ca28f0ccfc16fede2`.
- It contains **763 pairs**, each with a distinct VanillaSoft ContactID, selecting **716 distinct ERP person identities**. Several VanillaSoft IDs intentionally point to one ERP person: **45 shared-target groups, 92 source IDs**. Many-to-one is valid. One VanillaSoft ContactID may never map to more than one ERP person.
- The source decision workbook is `PlasticOS_ERP_VanillaSoft_Contact_Review_v3_OPERATOR_CONFIRMED_2026-10-16(1).xlsx`, SHA256 `fcac6112a8d1a9b72805459ab7016446581a934169dfd4e0ea4cd2d7c46d42d0`. The pack CSV reproduces exactly the workbook's `APPROVED LINKS` tab. The later operator-confirmed projection was independently compared and is pair-identical.
- A selected `erp_ct_id` represents the original `Contact.CT_ID`. Resolve it by the existing Odoo external identity `plasticos_transaction.legacy_erp_contact_<CT_ID>` through `ir.model.data` to an existing `res.partner` person (include archived records and grouped ERP aliases). **Never** treat CT_ID as `res.partner.id` or invent a new person if the marker is missing.
- The permanent VanillaSoft identity is `(provider='vanillasoft', external_id=<VanillaSoft ContactID>)`, using the existing `plasticos.crm.external.ref` authority. Pin an approved association to the ERP person, not email, phone, name, company text, or a database-generated ID.
- These pairs are **operator-confirmed matches** regardless of score/tier. STRONG 541 + LIKELY 173 + REVIEW 49 = 763. Do not reinstate the earlier 366 heuristic holds or demote an operator approval because an email/name/company string differs.

## 2. Evidence normalization, not authoritative identity

| Input evidence | Rule |
|---|---|
| Company | Case-insensitive and whitespace/punctuation-tolerant for corroboration. `ERP ALL CAPS` and `VanillaSoft Mixed Case` are compatible; usual legal suffix differences do not revoke a confirmed link. |
| ERP emails | A field may contain **multiple** addresses separated by semicolons, commas, whitespace or display-name syntax. Extract full email tokens; casefold and compare the entire VanillaSoft address against each token. Exact token membership is evidence of a match, not whole-cell equality. Do not use unsafe substring matches within different addresses. |
| Person name | Normalize for evidence only. A differing name never overturns a selected operator-confirmed crosswalk pair. Preserve ERP name. |
| Phones | Normalize to comparable dialable numbers for evidence; shared office numbers are insufficient as identity keys. Existing ERP values win; save distinct CRM-origin numbers without overwriting trusted values. |
| CRM new/source data | Retain as provenance and enrichment; no new automatic cross-source match for contacts absent from this approved CSV. |

## 3. Deterministic resolution (before record creation)

1. Verify the mapping file shape, hash, count, unique VanillaSoft IDs and numeric-string source IDs before **any** associated ORM writes. Do not reinterpret lower-ranked candidates as additional CRM records.
2. For each incoming VanillaSoft ContactID, first check its existing provider reference and any existing `crm.lead` carrying that ID, including archived leads. A previously linked source ID must be replay-stable. Any disagreement between an existing canonical target and the approved ERP person is an **identity conflict**: fail closed on that source ID and produce actionable evidence, without silently repointing or creating a replacement.
3. If the ID appears in this CSV, resolve the chosen ERP CT_ID's `ir.model.data` marker to exactly one existing person partner. Validate model, existence, company/person type, alias resolution and conflicts. If missing/ambiguous, **defer only that ID** with exact reason; never guess by name/email or create a lead/person as fallback.
4. Once resolved and conflict-free, bind the VanillaSoft provider identity to the existing `res.partner` through the current external reference owner, and enrich non-destructively. **Create zero new `res.partner` and zero new `crm.lead` records for approved links**. Report the outcome as an existing person linked/enriched using the existing audit semantics; never misclassify it as a new lead or `duplicate_rejected`. Do not extend a locked audit schema solely for a nicer label. Subsequent syncs use the stored reference rather than repeating heuristics.
5. Reconcile any pre-existing VanillaSoft-sourced lead for that ID explicitly, without deleting history or silently maintaining competing canonical refs. Preserve genuine sales opportunities as a distinct commercial concern; do not spawn a second lead merely to host contact history. Ambiguous legacy records stop that source ID pending reconciliation.
6. For contacts *not in this CSV*, keep the existing VanillaSoft API import path and source-ID deduplication behavior. Do not automatically extend these approvals or infer a person is new solely from missing crosswalk membership.
7. Process records in the existing CRM API importer, with the same source IDs, page accounting, watermark, failure classifications, archive semantics, and replay properties. The crosswalk is identity-control input, **not a CSV replacement for the ERP SQL source or VanillaSoft API source**, and not a manual import wizard.

## 4. Explicit exclusions

- The **457 lower-ranked candidate pairings** in the review workbook are excluded. The selected rank 1 ERP person wins. They are alternative candidate rows, **not** 457 more VanillaSoft contacts.
- The following **18** VanillaSoft IDs had an explicit **NO** decision for the suggested ERP match (none is in this CSV):
  `572648239, 572648618, 576091977, 595729642, 616784202, 641494831, 644925689, 649940912, 679638894, 683418149, 957774711, 572647726, 576092719, 602172624, 572647346, 651612412, 580438523, 628377432`.
  **Do not link them to the rejected suggested ERP contacts**. This negative decision does not mean the person is globally unmatched or automatically cleared to create a new lead; existing source-ID conflict checks still apply.
- **4,095** additional VanillaSoft IDs were unreviewed in the October workbook. They have **no approved ERP linkage**. Their existing API sync remains governed by the current CRM importer, not this approval set.

## 5. Field authority and data retention

| Destination concern | Required action |
|---|---|
| `res.partner` name, parent/company, primary email, existing phone/mobile | **ERP wins**. Preserve populated ERP values, including Scott Fidler's differing ERP email. Fill only safe blanks if compatible with ERP replay; otherwise retain CRM-origin values separately. |
| ERP `res.partner.comment` | ERP replay rewrites source-owned notes. **Do not append CRM notes directly into this field**. Preserve CRM notes/activity in an existing provenance-safe record/history path and surface alongside the person. |
| Existing additional phone lines | Reuse the existing labeled phone-line representation where suitable; no destructive overwrite or duplicate line on replay. |
| Calls / custom-table rows | Keep provider IDs and CRM ContactID; route all to the matched ERP person without requiring a new `crm.lead`. No dropped/deferred-forever events. Existing ledgers must replay idempotently. |
| Material evidence | Merge only into a **verified facility/material profile**; otherwise retain unresolved evidence with provenance. A person match never proves facility location. |
| Archived ERP person | Find through `active_test=False`; do not reactivate automatically. |
| Sales stage / CRM owner | Preserve source evidence and established Odoo-native semantics without clobbering ERP-owned person fields; do not invent a new lead solely for stage data. |

## 6. Hard acceptance

- Exactly 763 approved provider IDs link to the 763 selected ERP CT_ID aliases, targeting the correct 716 grouped people in the **source snapshot**; every live target must independently resolve to one real `res.partner`. Static count is not proof of live installation.
- Zero new Odoo persons or CRM leads *for these mapped source IDs*; zero competing lead/person canonical refs; zero wrong ERP targets from excluded candidate ranks or the 18 explicit NO entries.
- ERP-owned fields unchanged on initial link, ERP replay, CRM replay and changed CRM source data. CRM notes, alternate emails/phones, all source event IDs, material evidence and dependent rows retained through repeat sync.
- Same input twice => the same partners/refs, unchanged provider-event cardinalities and valid import counters. Any missing/conflicting live marker, source-ref conflict or incomplete CRM enumeration remains reported as **not accepted**, never quietly green.

## 7. Operator case assertions

| VanillaSoft ContactID | Selected ERP CT_ID | Decision |
|---|---:|---|
| `572647371` | `188500001` | Confirmed; ERP wins |
| `572648103` | `2350001` | Todd Byrum rank 1; rank 2 excluded |
| `575088842` | `56550001` | Larry Dalla Betta rank 1; rank 2 excluded |
| `576094121` | `95700001` | Eugene Niuh rank 1; ranks 2-4 excluded |
| `608344913` | `84950001` | Keith Owens rank 1; rank 2 excluded |
| `1082805107` | `192650001` | Scott Fidler; ERP primary email wins even when both sources have different emails |
