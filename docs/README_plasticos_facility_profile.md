# plasticos_facility_profile

**Version:** 19.0.4.1.0
**Category:** PlasticOS / Operations
**Depends:** `plasticos_base`, `plasticos_material_profile`, `plasticos_security_base`

---

## Purpose

Manages physical facility profiles for supplier and buyer partners. A **facility profile** is a structured capability record attached to a `res.partner` location — capturing what materials a site can process, at what volumes, to what quality standards, and under what operational constraints.

Facility profiles are the primary data contract between Odoo and the Cognitive Engine Graph (CEG). Every time a profile is created or updated, its capability packet is available for sync to the graph, keeping match quality current.

---

## Architecture

### Key Model: `plasticos.facility.profile`

Extends `res.partner` at the location level. A profile may only be attached to:
- A **child partner** (location under a parent company), OR
- A **standalone company** with no child partners (the company itself is the facility)

Person contacts and parent companies with children are explicitly excluded via the `is_facility` computed field (sourced from `plasticos_material_profile.models.res_partner`).

### Partner Extension

`models/res_partner.py` — adds `is_facility` computed boolean (`store=True`, `index=True`) to every `res.partner` record. Logic:

| Condition | `is_facility` |
|---|---|
| Has `parent_id` (child/location partner) | `True` |
| Standalone company, no `child_ids` | `True` |
| Company with child locations | `False` |
| Individual person contact | `False` |

**Dependency chain:** `plasticos_facility_profile` depends on `plasticos_material_profile` (which owns the `is_facility` field definition). Do **not** attempt to import from `plasticos_facility_profile` in `plasticos_material_profile` — circular dependency.

---

## Data Model

### `plasticos.facility.profile`

| Field | Type | Description |
|---|---|---|
| `partner_id` | `Many2one(res.partner)` | The location-level partner this profile belongs to |
| `supplier_profile_id` | `Many2one(res.partner)` | Source of truth for dual-supplier resolution |
| `process_type` | `Selection` | Process codes sourced from `plasticos_material_profile.process_codes.PROCESS_SELECTION` |
| `feedstock_type` | `Selection` | Inline selection (single-use — acceptable) |
| `max_monthly_throughput_lbs` | `Float` | Capacity ceiling used in match scoring |
| `typical_buy_price` | `Float` | Price anchor written to `plasticos.intake.match.typical_price` during matching |
| `previously_washed` | `Boolean` | |
| `previously_pelletized` | `Boolean` | |
| `equipment_type_ids` | `Many2many(plasticos.equipment.type)` | |
| `certification_ids` | `Many2many(plasticos.certification)` | |
| `is_food_grade` | `Boolean` | Hard gate in CEG matching |
| `can_remove_metal` | `Boolean` | Hard gate — Gate 7 in CEG |
| `can_filter_fr` | `Boolean` | Hard gate — Gate 8 in CEG |
| `preferred_contact_id` | `Many2one(res.partner)` | Auto-populated when a contact is selected on an intake record for this facility |

### `plasticos.equipment.type` / `plasticos.partner.type`

Master data models for facility equipment and partner role classification.

---

## Process Codes Registry

`process_codes.py` — canonical source for `PROCESS_SELECTION`. All consumers import from here:

```python
from odoo.addons.plasticos_material_profile.process_codes import PROCESS_SELECTION
```

> **History:** `process_codes.py` was moved from `plasticos_facility_profile` → `plasticos_material_profile` to eliminate a circular dependency. All consumers updated. Do not move it back.

---

## Views

| View | Description |
|---|---|
| `facility_profile_views.xml` | Full form (5 tabs: Capability, Tolerances, Equipment, Quality/Certifications, Operational), list view, search |
| `facility_profile_actions.xml` | `ir.actions.act_window` + menu item under PlasticOS top-level menu |
| `facility_profile_ux.xml` | Partner form XPath — injects the **Facility Profile** tab (visible only when `is_facility = True`) |
| `partner_ux.xml` | Additional partner-level UX overrides |
| `partner_type_views.xml` | CRUD views for `plasticos.partner.type` master data |

**Tab visibility rule:** The Facility Profile tab on `res.partner` form is controlled by `invisible="not is_facility"`. This field is inherited from `plasticos_material_profile`. Do **not** redefine it here.

---

## Constraints

```python
@api.constrains('partner_id')
def _check_partner_is_facility(self):
    # Profile may only be saved on a child partner or standalone company
    # Enforced at ORM level — complements the is_facility visibility in views
```

This constraint is intentionally **complementary** to the view visibility logic, not redundant. The view hides the tab; the constraint blocks saving if somehow reached via API.

---

## Security

- ACL in `security/ir.model.access.csv` — all plasticos groups get appropriate read/write/create/unlink
- No record rules on this model — all authenticated users with group access can see all facility profiles

---

## Deployment

```bash
# Odoo.sh: bump version in __manifest__.py, push to staging branch
# Local Docker (dev only):
docker compose -p odoo19 run --rm odoo \
  -d odoo --db-host db --db-port 5432 --db-user odoo --db-password odoo \
  -u plasticos_facility_profile --stop-after-init
```

**Requires `--update`** when:
- Adding new stored computed fields (triggers recompute across all `res.partner`)
- Changing `ir.model.access.csv`
- Adding new `ir.actions.act_window` or menu items

---

## Known Gaps / Deferred

| Item | Status |
|---|---|
| `emit_capability_packet` method | **Removed** — was dead code (built packet, assigned to local var, discarded). Removed in debt cleanup. |
| `typical_buy_price` population from market data | Deferred — currently set manually |
| Freight Bill auto-link to facility | Deferred — manual linking for launch |

---

## Integration Points

| Consumer | How Used |
|---|---|
| `plasticos_intake` | `action_match_to_buyers` reads facility profiles for matching; `onchange_facility_id` reads `preferred_contact_id` |
| `plasticos_material_profile` | Provides `is_facility` computed field used in tab visibility |
| CEG (external) | Facility sync via `POST /v1/execute` `action=sync` — sends capability packet on profile write |
| `plasticos_logistics` | Load records reference facility for origin/destination |

