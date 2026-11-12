# S12 evidence: alignment clean-up

Contract `PLASTICOS-EXPORT-C13-S12-ALIGNMENT-CLEANUP`.

- Contract digest: `sha256:05f9675e983c7cc925aa6dbed4f15d5d2642def32a420ac032a8479682e8838d` (C13-SCOPE-2). The original freeze was `cc6b768f…`.
- Base: `e71599d515634da6c66d01286e9ffe288b7ab630`, the accepted S10 head.
- Predecessor: `feat/plasticos-export-s11-fact-corrections`, merged into this branch with a merge commit before publication.
- Part of the PlasticOS Export campaign. Plan: `docs/campaigns/future-add-ons/PlasticOS_Export/STRATEGIC_EXECUTION_PLAN_v2.8.md`.

The S6 to S11 evidence folders are unchanged.

## Files

| File | Contents |
| --- | --- |
| `S12_EFFECT_WITNESSES.csv` | Every S12 witness method, by effect, rule or operator decision, and aspect. |

## What S12 changes

### OP12-E01: corrected container facts

- Export reads a journey's facts only through `plasticos.iso.journey.current_facts()`, the S11 Logistics helper. It runs as the acting user, so the slot shows the current revision of each fact.
- For a user who can read the facts, the shipment history lists every earlier revision: its number, who corrected it, when, the revision it replaced, and the reason.
- A user who cannot read the facts still sees Restricted, gets no correction text and no journey field. Export adds no sudo. The C11 rulings are unchanged.

### OP12-E02: display alignment

Approved by the operator on 2026-11-12 (decision B).

- **(a) Units.** `planned_quantity` has no aggregator, so no list group or pivot ever adds two units together.
  - The cargo pivot measures `planned_weight_lb`. It is converted through the native unit of measure (`_has_common_reference` with lb, then `_compute_quantity`). It is witnessed for lb, kg, Ton and a 2,000 lb short ton.
  - A quantity in a unit that is not a weight leaves the field empty and sets `planned_weight_basis` to "Not a weight unit".
  - The unit stays the first pivot column, which is the D5 witness of `BRS-EXP-14-R008`. The weight basis and the lb measure follow it.
  - Coordinator ruling 2026-11-12, Option A (`plasticos_export/business_rules/SUPERSESSION.md`). The two fields are Export's own planned quantity converted to lb for planning totals, not a weighed, VGM, stock or invoice weight.
    - Their `depends` name only the link's `planned_quantity`, `planned_quantity_known` and `uom_id`, and a witness introspects them.
    - The negative witnesses of `BRS-EXP-01-R002` and `BRS-EXP-07-R006` allow exactly these two fields on exactly the cargo link model. Every other model and field stays covered.
- **(b) Slot order.** A stored `slot_number` (the number at the end of the slot key) orders slots numerically. This applies to `_order` and to every slot sort in the models and tests (the `slot_order` helper), so `40HC-10` follows `40HC-9`. A capacity reduction therefore retires the highest-numbered free slots.
- **(c) Default unit.** The Commit Cargo screen defaults the planned unit to lb. The command still refuses a known quantity without a unit, and the refusal witness clears the unit explicitly.
- **(d) Supplier count.** `supplier_count` is stored and computed by the superuser, so a Sales Rep reads the same count as Logistics. This is consistent with the 2026-11-12 see-all rule for allocations.

### OP12-E03: ERP price basis (BRS-EXP-02-R006, ADR-021 amendment 2026-11-12)

- `fob`, `fob supplier dock` and `pickup` are domestic shipping points, not the Incoterms 2020 FOB. They map to no Incoterm and are reported.
- `fas` maps to `FAS` only. `delivered` is unchanged.
- A domestic basis never writes the Incoterm field of an order that already exists. The stored value is reported ("left unchanged"), so already-imported orders are not rewritten. No migration touches them, and no field is added.
- A declined basis is an anomaly row, not a rejected record, so the `records_seen` identity of the import summary is unchanged.
- The production-rehearsal fidelity verifier applies the same crosswalk.

### OP12-E04: module pages

- Odoo 19 (`ir.module.module._get_desc`, `odoo/modules/module.py`) renders a module page from the first of these that exists:
  1. `static/description/index.html`;
  2. a truthy manifest `description`;
  3. the first of `README.rst`, `README.md`, `README.txt` and `README`, read as RST.
- Every PlasticOS module whose `README.md` carries the `readme-module-version` front matter also has either a front-matter-free `README.rst` or a manifest description. No page resolves to front matter.
- Coordinator ruling: Option A. No manifest, README or version change was made, because a stub description would replace a full `README.rst` page.
- A stale stored description on a live database refreshes on Apps → Update Apps List. That is recorded as an operator note, not as a migration.
- Witnesses:
  - `tests/test_module_descriptions.py` resolves every module the way Odoo 19 does and includes a check that the test is not vacuous.
  - `plasticos_export/tests/test_module_pages.py` renders every installed `description_html` and includes a negative witness.

## Versions

| Module | From | To | Why |
| --- | --- | --- | --- |
| `plasticos_export` | 19.0.1.2.0 | 19.0.1.3.0 | New stored fields (E01 and E02). One bump for the slice. |
| `plasticos_partner_import` | 19.0.2.10.38 | 19.0.2.10.39 | Price-basis crosswalk (E03). |
| `plasticos_transaction` | 19.0.2.3.66 | 19.0.2.3.67 | Order upsert keeps a stored Incoterm (E03). |

No other module changed. The new stored computed fields fill on module upgrade, so no migration script is needed.

## Runtime fixture

- `make runtime-bootstrap` refused before any edit. The session proxy CA had rotated (label digest `073ce…` → `acf32…`), so bootstrap rebuilt the local `odoo:19` base with the new CA. That changed the image input of the pinned fixture `odoo_test_tpl_ee_c9e8a81f52f23680` from `content:e4cae957…` to `content:859c7b0b…`.
- The local `odoo:19` tag was pointed back at the S10-era image (`205f2b69`), which reproduces the admitted input `content:e4cae957…`. `scripts/test_env.sh status` then reports the template `ready`.
- No template was rebuilt, and no admission input was changed.
- The coordinator accepted this because it reproduces the admitted inputs. The coordinator runs the authoritative runtime.

## Validation

PENDING: filled in on the merged tree (S11 accepted head merged with a merge commit).

On the base `e71599d5` before any edit:
- `pytest tests/` gave 3076 passed, 49 skipped.
- `make audit-baseline` reported no new finding.
