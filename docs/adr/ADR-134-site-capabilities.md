# ADR-134 Site capabilities: what a site does, and with what material

- Status: Accepted (operator, 2026-11-17).
- Decision date: 2026-11-17
- Owners: `plasticos_facility_profile` (capabilities, site logistics fields); `plasticos_material_profile` (direction, vocabulary)
- Relates to: ADR-131 (sites as native addresses), ADR-132 (material profiles belong to the site), ADR-133 (selective VanillaSoft partners), ADR-004 and ADR-005 (intake vs material profile), ADR-012 and POS-INV-18 (writeback limits, unchanged here), ADR-122 and ADR-123 (semantic kernel, see §10), ADR-135 (dock rules and scheduling)

## Context

A broker's question about a site is simple: **what does this site do, and with what material?** The current facility profile answers it badly, for five reasons.

1. **One profile per site holds everything.** `unique(partner_id)` (`plasticos_facility_profile/models/facility_profile.py:261`) forces the whole site into one record, with one process type and one set of acceptance windows.
2. **Equipment is a mixed list.** `equipment_type_ids` points at 18 codes of `plasticos.equipment.type`. Nine are machines, five are material forms (bales, regrind, pellet, flake, rollstock) and four are outcomes (metal removal, moisture reduction, FR filtration, fines screening). Seven `has_*` checkboxes shadow the list. Nothing reads them since the local matcher was mothballed (ADR-003).
3. **Acceptance is recorded per site.** `accepted_polymer_ids`, `form_preference_id`, five `handles_*`, four `can_*`, and the density and melt-index windows sit on the site, not on the step that takes the material in.
4. **A material profile has no direction.** On a company that buys and sells, nothing tells supply from demand. The unique key (partner, polymer, form, grade; `material_profile.py:418-422`) also cannot hold an In and an Out profile for the same material.
5. **Some vocabulary is broken.** Grade "Superacs" and packaging "Super Sacks" are spelled two ways. REPRO and LOOSE are forms although they describe provenance and packaging.

Production is not live, so the model can still be corrected without harming a live workflow. Detail that only machines use stays in the graph of the Enrichment Inference Engine and Cognitive Engine Graphs. Odoo keeps what a person needs to decide.

## Decision

### 1. Model

```
Site (res.partner)                 site logistics fields (§4)
 └─ Facility profile               one per site: site-wide facts and acceptance limits kept (§7)
     ├─ Capability                 one row = one machine or line: type · model · detail fields · rated lb/hr
     └─ …                          ordered; the order shows the flow
 └─ Material profiles              In or Out, each optionally linked to the capability it enters or leaves
```

- **One row per line, three rows for three lines.** One row is one machine or one line. Three shredders are three rows, because lines never handle the same feedstock.
- **Model on every row.** Each row has one free-text **Model** field, for example "V60". The rule is the same for every type. A person may leave it blank; the AI broker fills it when known.
- **No model catalog.** Odoo has no model catalog. A catalog may be promoted later from real data.

### 2. Capability types and capabilities

**`plasticos.capability.type`**, a new master. It ships seed data, which people may extend.

| Field | Type |
|---|---|
| `name` | char, required |
| `code` | char, unique |
| `sequence` | integer |
| `active` | boolean |
| `details_definition` | `fields.PropertiesDefinition`: the detail fields this type's rows show |

**`plasticos.capability`**, new.

| Field | Type | Note |
|---|---|---|
| `facility_profile_id` | many2one, required, `ondelete="cascade"` | |
| `sequence` | integer | drag order |
| `capability_type_id` | many2one, required, `ondelete="restrict"` | the verb |
| `model` | char | free text |
| `rated_capacity_lb_hr` | float | the machine's rating |
| `details` | `fields.Properties(definition="capability_type_id.details_definition")` | only that type's detail fields |
| `in_material_ids`, `out_material_ids` | one2many on `material_profile.capability_id`, filtered by direction | shown on the row |
| `notes` | text | |

**Who edits.**
- The ACL rows live in `plasticos_security_base`, with the other facility-model rows. The operator approved this edit on 2026-11-17.
- **Capability types:** users may read them. `group_operations_manager` and `base.group_system` may write and create them.
- **Capabilities:** the same access as facility profiles.

**Properties constraints in Odoo 19** (`odoo/orm/fields_properties.py`), which the build must respect:

- **(a) Edits rewrite the definition.** Editing a definition from a row rewrites the type's definition as the acting user. The ACL above is therefore the only guard. The seed definitions are `noupdate="1"`, so an upgrade never erases fields an operations manager added.
- **(b) One type per write.** Writing a recordset whose rows have different types raises an error. Migrations and imports group their writes by type.
- **(c) Changing a row's type drops its detail values.** The form warns before it does this.
- **(d) Allowed types and names.** Property types are limited to boolean, integer, float, char, text, selection and tags. Property names are alphanumeric. A width-by-length opening is two float properties.
- **(e) Detail values are stored as jsonb with no index.** Nothing filters, groups or requires a detail value. Matching and filters use the fixed fields only.
- **(f) Detail values have no writeback kind.** Converge v2 has no value kind for Properties, so enrichment cannot write them (§8).

### 3. Seed capability types: the canonical list

| Code | Name | Detail fields (Properties) |
|---|---|---|
| shredding | Shredding | shafts (single / dual / quad), hp, feed_opening_w_in, feed_opening_l_in, screen (yes/no), screen_size_in |
| grinding | Grinding | hp, throat_opening_w_in, throat_opening_l_in, screen_size_in |
| sink_float | Sink-Float | separates (polyolefins from heavier plastics / metal / both) |
| washing | Washing | water (hot / cold), friction_washer (yes/no), dryer (yes/no) |
| metal_separation | Metal Separation | method (magnet / eddy current / both) |
| drying | Drying | — |
| sorting | Sorting | method (manual / optical-NIR) |
| baling | Baling | baler (HRB / downstroke / two-ram), ram (single / dual), bale_weight_lb |
| pelletizing | Pelletizing | screw (single / twin), screw_diameter_mm, melt_filter (screen changer / continuous / none), vented (yes/no) |
| extrusion | Extrusion | screw (single / twin), screw_diameter_mm |
| compounding | Compounding | screw (single / twin), screw_diameter_mm, melt_filter, vented |
| injection_molding | Injection Molding | — |
| blow_molding | Blow Molding | — |
| film_blowing | Film Blowing | — |
| film_casting | Film Casting | — |
| thermoforming | Thermoforming | — |
| rotomolding | Rotomolding | — |
| compression_molding | Compression Molding | — |
| purification | Purification | — |

### 4. Site logistics on `res.partner`

These fields appear on the site itself, or on a company that has no sites. They are not buried in the facility profile.

| Field | Type | Options (nothing selected means unknown) |
|---|---|---|
| `default_delivery_term`, "Dock Rule" (existing) | selection | FCFS / Appointment. **It keeps its Appointment default,** the guardrail described in ADR-135. |
| `dock_rule_confirmed_on` | date | Defined in ADR-135 §2 |
| `shipping_hours` | char | Defined in ADR-135 §2 |
| `loading_docks` | selection | none (ground level) / 1 / 2 / 3–5 / 6+ |
| `export_container_loading` | selection | yes / can't / won't |
| `truck_scale` | selection | yes / no |

- **How documents use them.** Logistics and Export read these fields live from the site. Only the dock rule and the hours are copied onto documents, into fields that already exist (ADR-135 §2 and §3).
- **Lookup order.** The site's value is used first, then its commercial company's value, then the default.

### 5. Material profile direction

New fields on `plasticos.material.profile`:

- `direction`, a selection of in or out. It is defined in `plasticos_material_profile`.
- `capability_id`, many2one, optional, `ondelete="set null"`. It is added by `plasticos_facility_profile` through `_inherit`, the same pattern `plasticos_crm_bridge` uses.
- `rate_lb_hr`, float: how fast this material goes through its capability. Throughput depends on the feedstock: pallets and toters run at different rates on the same shredder.

**The unique key becomes partner + polymer + form + grade + direction** (operator decision 2026-11-17).

- Packaging stays out of the key, and the form stays single-select.
- Loose toters and baled toters are different grades.
- The migration checks for collisions before changing the key. A collision is reported and never deleted.

**How direction is set.**

- **On create only.** Direction defaults from the **commercial partner's** ranks: only `supplier_rank` gives out, only `customer_rank` gives in, both or neither leaves it blank for a person.
- **When the site type is known.** If ADR-131's site type is known (pickup vs delivery address), it decides first.
- **Writers set it explicitly:**
  - The ERP material-profile loader: supplier list → out, customer list → in. This reverses the 2026-11-13 note.
  - The VanillaSoft sync: from its Buyer/Supplier field.
  - The AI broker, through native Odoo operations.
- **Enrichment never writes material profiles.** The POS-INV-18 amendment of 2026-11-13 stands (§8).
- **Auto-link.** A site with exactly one capability auto-links its unlinked profiles to it. A person may leave the link blank.

### 6. Vocabulary fixes (`plasticos_material_profile`)

**Supersacs.**
- The grade "Superacs" and the packaging "Super Sacks" become **Supersacs**.
- The grade data is `noupdate`, so the rename is a migration.
- The grade code `SUPERACS` is kept, under rule 91, because `grade_codes.py`, `ERP-Products.csv` and crm_sync tests read it. Only the name changes.
- Aliases in `material_mapping.csv`: superacs, supersacks, super sacks, super sacs, supersac.

**REPRO is retired as a form.**
- Repro is the existing attribute `attr_repro`.
- A profile whose form is REPRO becomes Pellets + attribute Repro **only where its description or ERP product confirms pellets**. Every other REPRO profile is listed for review, with its form left unchanged until reviewed.
- `enrichment_service.py` maps REPRO to REGRIND. That mapping is reconciled with the reviewed table.
- A pre-migration clears the stored REPRO value before `FORM_CODES` drops it, because `form` is a Selection built from `FORM_CODES`.

**LOOSE is retired as a form.** A LOOSE profile becomes packaging Loose with an empty form, through the same pre-migration.

**Consumers updated with these retirements.**
- `material_mapping.csv`: 25 REPRO rows and 8 LOOSE rows
- `ERP-Products.csv`
- `enrichment_service.py` form maps
- `plasticos_web_leads/models/material_catalog.py`
- `grade_template_data.xml`
- The tests that read them

**Grade templates** (`plasticos.grade.template`) are migrated so they keep pointing at valid forms. They are not redesigned here; that is a separate, later campaign.

**New grade (seed, pending operator approval).** "Baled Toters" (HDPE), so that loose and baled toters are separate profiles.

### 7. What the facility profile keeps, and what is retired

**Kept on the facility profile:**
- the site-wide facts: certifications, spot or contract, truckload, lot sizes, capacity per month, feedstock type
- the acceptance limits that apply to the whole site: `contamination_tolerance_pct`, `moisture_tolerance_pct`, `pcr_pct_min/max`, `application_class`, `accepts_filled_materials`, `application_notes`, `freeform_notes`

Moving those limits would change their meaning or lose data: material profiles hold actual values, not tolerances, and have no PCR field. They stay until a later decision.

**Retired, with where the data goes:**

| Retired | Goes to |
|---|---|
| `equipment_type_ids` | Capabilities, one per mapped code (table below) |
| `plasticos.equipment.type` and its records | **Deleted.** Its consumers are repointed (table below). |
| `has_*` (7) | Deleted |
| `process_type` | A capability of the mapped type |
| `handles_*` (5), `form_preference_id`, `form_preference` | The form of the In profile. Forms that cannot be placed are listed for review. |
| `can_*` (4) | Metal Separation and Drying capabilities. FR filtration and fines screening go to the review list, not to a capability, so no Pelletizing row is invented. |
| `accepted_polymer_ids` | One In profile per polymer |
| `density_min/max`, `melt_index_min/max` | `density_min/max` and `mfi_min/max` on those In profiles |
| `plasticos.facility.template` | **Deleted.** `get_template_values()` has no caller and `action_facility_template` has no menu, so the model is unreachable. |

**Code to type mapping (complete):**

| Source | Values | Becomes |
|---|---|---|
| Equipment code | horizontal_baler | Baling (baler: HRB) |
| Equipment code | downstroke_baler | Baling (baler: downstroke) |
| Equipment code | shredder | Shredding |
| Equipment code | granulator | Grinding |
| Equipment code | wash_line | Washing |
| Equipment code | pelletizer | Pelletizing |
| Equipment code | extruder | Extrusion |
| Equipment code | compounder | Compounding |
| Equipment code | sorting_line | Sorting |
| Equipment code | metal_removal | Metal Separation |
| Equipment code | moisture_reduction | Drying |
| Equipment code | fr_filtration, fines_screening | Review list |
| Equipment code | bales, regrind, pellet, flake, rollstock | The In-profile form |
| `process_type` | blow_mold | Blow Molding |
| `process_type` | compounding | Compounding |
| `process_type` | compression_mold | Compression Molding |
| `process_type` | extrusion | Extrusion |
| `process_type` | film_blown | Film Blowing |
| `process_type` | film_cast | Film Casting |
| `process_type` | injection | Injection Molding |
| `process_type` | rotomold | Rotomolding |
| `process_type` | thermoform | Thermoforming |
| `process_type` | other | Review list |

**Repointed consumers of the equipment-type master:**
- `plasticos_semantic_kernel/models/facility_material_rule.py:63`: `equipment_type_id` becomes `capability_type_id`. The module is uninstalled and optional, so this is a code change only.
- `plasticos_enrichment`: `res_config_settings.plasticos_sweep_equipment_type_ids`, its view (`enrichment_sweep_views.xml:126`), `sweep_policy.py` and `enrichment_sweep.py` filter on capability types instead.
- `plasticos_security_base/security/ir.model.access.csv:35-37`: the rows are removed.

**Every other consumer** of the retired fields is updated in the same change:
- `intake_normalizer.py:567-579`
- `form_codes.EQUIPMENT_GATED_FORMS`
- `.cursor/rules/95-plasticos-equipment-policy.mdc`
- `ARCHITECTURE.md`
- the module READMEs
- `contracts/schemas/examples/buyer-demand.json`
- `plasticos_enrichment/knowledge_base/*.yaml`
- the tests listed in the C5 lane brief

### 8. Writeback and the Gate vocabulary

- **C5 does not change the engine side.** The Gate/EIE vocabulary 0.7.0 is a follow-up campaign, scheduled after C5's Odoo side is final.
- **Retired targets are refused, with a reason.** The facility-profile writeback vocabulary (`gate_allowlists.py`) governs *inbound* writes. The active pin is empty, so 0.5.0 applies; 0.6.0 is a candidate. A converge result that targets a retired field is refused with the reason "retired by ADR-134; awaiting the follow-up vocabulary". It is never silently dropped.
- **Nothing new is written back.** Converge v2 cannot write capabilities or Properties, and POS-INV-18 keeps material profiles out of converge. The follow-up campaign designs that writeback and the invariant change it needs.

### 9. Migration (idempotent; reports counts; nothing silently lost)

For each facility profile:
- create capabilities from the mapping above;
- create In profiles from the accepted polymers, carrying form and windows;
- check the new unique key and report collisions;
- write a review list covering: unplaceable forms, `other` processes, FR filtration and fines screening, profiles on two-sided companies with no direction, REPRO profiles awaiting review, and key collisions.

Retired columns are removed only after their values have moved. The migration runs first on a Production copy (C5 lane R).

### 10. Semantic kernel

ADR-122 and ADR-123 (`plasticos_semantic_kernel`, uninstalled) model buyer demand and facility material rules on the same ground. ADR-134 is the installed model. The kernel's facility rule points at capability types (§7). Reconciling ADR-122 and ADR-123 with capabilities is left to the follow-up campaign.

## Worked examples (acceptance tests; synthetic names)

**Border shredding site.** In: stacked mixed pallets and loose HDPE toters. Out: pallet regrind and injection-grade toter regrind.

| seq | Capability | Model | Details | Rated lb/hr | Material in / out |
|---|---|---|---|---|---|
| 1 | Shredding | blank | shafts: single; screen: no; feed opening smaller than a pallet | — | in: PP/PE (PP_PE) · Pallets · packaging Stacked · 1,000 lb/hr · note "must precut"; in: HDPE · Toters · packaging Loose · 2,000 lb/hr; in: HDPE · Baled Toters · packaging Bales (once the grade is approved) |
| 2 | Metal Separation | — | method: magnet | — | — |
| 3 | Grinding | blank | — | 2,000 | out: PP/PE · Regrind · Pallets; out: HDPE · Regrind · Toters · origin process `injection` |

**Solvent-recycling PP plant.**

| seq | Capability | Material in / out |
|---|---|---|
| 1 | Shredding | in: PP · Supersacs |
| 2 | Grinding | — |
| 3 | Washing | — |
| 4 | Pelletizing | out: PP · Pellets · attribute Repro |

**Three shred lines on different feedstock.** Three Shredding rows, each with its own model and its own In materials.

**MRF with a V60.** One Baling row with model "V60". The detail fields are entered by people, or left blank until the follow-up campaign adds inference writeback.

## New fields and models (for operator approval)

Each item states why nothing native or existing serves.

- **`plasticos.capability.type` and `plasticos.capability`.** Odoo has no model for what a counterparty site can do. `mrp.workcenter` describes our own production and carries routing, costing and scheduling we do not need.
- **`material_profile.direction`, `capability_id`, `rate_lb_hr`.**
  - Without `direction`, supply and demand cannot be told apart on a two-sided site.
  - The link and the rate hold the per-feedstock throughput a single machine rating cannot.
- **`res.partner.loading_docks`, `export_container_loading`, `truck_scale`.** Odoo has no site fields for these logistics facts.
- `dock_rule_confirmed_on` and `shipping_hours` are justified in ADR-135.
- **Grade "Baled Toters".** Seed data, not a field.

**Native or existing pieces reused:** the partner `tz`, `default_delivery_term`, the existing material-profile windows (`density_min/max`, `mfi_min/max`), `attr_repro`, the packaging records, and the Properties mechanism.
