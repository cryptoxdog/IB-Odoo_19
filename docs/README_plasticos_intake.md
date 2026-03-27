# plasticos_intake

**Version:** 19.0.5.2.0
**Category:** PlasticOS / Core Pipeline
**Depends:** `plasticos_base`, `plasticos_material_profile`, `plasticos_facility_profile`, `plasticos_intake_normalizer`, `plasticos_offer`, `plasticos_security_base`

---

## Purpose

`plasticos_intake` is the **entry point of the PlasticOS brokerage pipeline**. It captures a supplier's material availability, drives it through normalization, matching, and offer dispatch — producing `plasticos.offer` records that brokers send to buyers.

This is the highest-traffic module in the system. Every brokerage deal begins here.

---

## Pipeline Overview

```
Intake Created (draft)
  │
  ├─ Normalized (intake_normalizer assembles structured packet)
  │
  ├─ action_match_to_buyers() → CEG HTTP POST → match lines written → status: matched
  │
  ├─ Broker selects buyers on match lines
  │
  ├─ action_send_offers() → plasticos.offer.create() per selected match line → status: offer_sent
  │
  └─ Offer accepted → Transaction created → Pipeline complete
```

---

## Models

### `plasticos.intake`

The primary intake record. ~42KB model.

**Status field** (`status`, not `state`) — selection with the following valid values:

| Value | Label | Set By |
|---|---|---|
| `draft` | Draft | Default on create |
| `processing` | Processing | System (normalizer running) |
| `matched` | Matched | `action_match_to_buyers()` on success |
| `offer_sent` | Offers Sent | `action_send_offers()` on success |
| `won` | Won | Linked transaction closed |
| `lost` | Lost | Manual or cron expiry |
| `expired` | Expired | Cron — system-set terminal state, NOT shown in statusbar |

**Statusbar order:** `draft → matched → offer_sent → processing → won/lost`
`expired` is intentionally excluded from the statusbar widget — it is not a user-navigable step.

#### Key Fields

| Field | Type | Notes |
|---|---|---|
| `partner_id` | `Many2one(res.partner)` | Supplier company |
| `facility_id` | `Many2one(res.partner)` | Location-level partner (`is_facility=True`) |
| `contact_id` | `Many2one(res.partner)` | Auto-populated from `facility.preferred_contact_id` |
| `polymer_id` | `Many2one(plasticos.polymer)` | |
| `form_id` | `Many2one(plasticos.material.form)` | Current form of material |
| `origin_form_id` | `Many2one(plasticos.material.form)` | What the material was before processing |
| `origin_process_type` | `Selection` | Imported from `PROCESS_SELECTION` in `plasticos_material_profile.process_codes` |
| `quantity_per_load_lbs` | `Float` | Used in offer creation and CEG payload |
| `mfi_value` | `Float` | Melt flow index |
| `density_value` | `Float` | |
| `moisture_pct` | `Float` | **Note:** field is `moisture_pct`, NOT `moisture_ppm` — normalizer packet key was corrected |
| `contamination_pct` | `Float` | |
| `material_attribute_ids` | `Many2many(plasticos.material.attribute)` | Single source of truth for all condition flags |
| `has_metal` | `Boolean` | **Computed** from `material_attribute_ids` — `store=True` |
| `is_metalized` | `Boolean` | **Computed** from `material_attribute_ids` — `store=True` |
| `has_fr` | `Boolean` | **Computed** from `material_attribute_ids` — `store=True` |
| `has_residue` | `Boolean` | **Computed** from `contamination_pct` — different pattern, not attribute-synced |
| `match_line_ids` | `One2many(plasticos.intake.match)` | Written by `action_match_to_buyers()` |
| `offer_count` | `Integer` | Computed — drives the smart button |
| `lat` / `lon` | `Float` | Geolocation — passed to CEG for distance scoring |
| `target_price` | `Float` | Passed to CEG query payload |

#### Boolean Flags — Important History

`has_metal`, `is_metalized`, `has_fr` are **computed** from `material_attribute_ids`. They were previously stored fields with bidirectional `onchange` sync — that pattern was removed as redundant. `material_attribute_ids` is now the single source of truth. The computed values are wired to `store=True` so CEG consumers can still query them via SQL.

`has_residue` is a **separate computed field** derived from `contamination_pct` — it is NOT attribute-synced and was deliberately left as-is.

---

### `plasticos.intake.match`

One record per buyer candidate returned by the CEG.

| Field | Type | Notes |
|---|---|---|
| `intake_id` | `Many2one(plasticos.intake)` | Parent |
| `buyer_partner_id` | `Many2one(res.partner)` | Matched buyer |
| `buyer_name` | `Char` | Denormalized from CEG response |
| `match_score` | `Float` | 0–100, normalized from CEG 0–1 |
| `match_reason` | `Text` | Gate failure summary |
| `facility_profile_id` | `Many2one(plasticos.facility.profile)` | Buyer's matching facility |
| `typical_price` | `Float` | From `facility.typical_buy_price` — price anchor for offer creation |
| `is_selected` | `Boolean` | Broker selects/deselects per row before sending offers |

---

## Key Methods

### `action_match_to_buyers()`

**Entry point for matching.** Calls `create_material_profile_from_intake()` to ensure a material profile exists, then makes an HTTP POST to the CEG:

```
POST {plasticos.graphengine.url}/v1/execute
Authorization: Bearer {plasticos.graphengine.apikey}
{
  "action": "match",
  "tenant": "plasticos",
  "payload": {
    "match_direction": "intake_to_buyer",
    "query": { ...intake fields... },
    "top_n": 20
  }
}
```

On success: clears stale `match_line_ids`, writes new match lines, advances `status` to `matched`.

**Config params required:**
- `plasticos.graphengine.url` (e.g., `https://ceg.yourdomain.com`)
- `plasticos.graphengine.apikey`
- `plasticos.matching.engine.enabled` → `True`

### `action_send_offers()`

Loops over **selected** match lines → creates one `plasticos.offer` per line → advances `status` to `offer_sent` → returns list view of created offers.

```python
# Offer creation per selected match line:
self.env['plasticos.offer'].create({
    'intake_id': self.id,
    'buyer_partner_id': match.buyer_partner_id.id,
    'match_line_id': match.id,
    'offered_price': match.typical_price or 0.0,
    'quantity': self.quantity_per_load_lbs,
})
```

### `create_material_profile_from_intake()`

Creates a `plasticos.material.profile` from intake data if one doesn't exist for this partner/polymer/form combination.

**Key fix applied:** `name` key was removed from `profilevals` — `plasticos.material.profile` has no `name` field. Profile identity is defined by `(partner_id, polymer_id)` order.

### `onchange_facility_id()`

Auto-populates `contact_id` from `facility.preferred_contact_id`. Uses the correct field name (`preferred_contact_id`, not `x_preferred_contact_id` — migration renamed it).

---

## Views

| File | Description |
|---|---|
| `intake_views.xml` | Full form (Specs, Facility Info, Normalization tabs), list, search, kanban |
| `intake_match_views.xml` | Embedded list of match lines with `is_selected` toggle and score |

**Smart button — Offers:** `offer_count` field + `action_view_offers()` → drives the "X Offers" smart button on the intake form.

---

## Crons

| Cron | Action | Schedule |
|---|---|---|
| PlasticOS Intake Expiry | Sets `status = expired` on intakes past threshold | Daily |

`ir.config_parameter` key: `plasticos.intake.expiry_days` (default: 90)

---

## Deployment

```bash
docker compose -p odoo19 run --rm odoo \
  -d odoo --db-host db --db-port 5432 --db-user odoo --db-password odoo \
  -u plasticos_intake --stop-after-init
```

**Requires `--update`** when adding stored fields, changing ACL, or adding new cron XML.

---

## Integration Points

| Module / System | Direction | Notes |
|---|---|---|
| `plasticos_intake_normalizer` | Outbound | `assemble_packet()` builds the structured dict for CEG |
| `plasticos_material_profile` | Bidirectional | Profile created from intake; `origin_process_type` sourced from shared registry |
| `plasticos_offer` | Outbound | `action_send_offers()` creates offer records |
| CEG (external repo) | HTTP POST | `POST /v1/execute` — match action |
| `plasticos_claims` | Inbound bridge | Claims bridge injects `action_view_claims()` via `_inherit` — do NOT redefine on this model |

---

## Known Gaps / Pending

| Item | Priority | Notes |
|---|---|---|
| CEG HTTP client (`graphservice.py`) | **GATE** | Without this, `action_match_to_buyers()` returns no results |
| `typical_price` population | High | Populated once CEG returns `typical_buy_price` from facility profile |
| `offer_count` smart button | Medium | Field exists; XML button may need review |
| Intake expiry cron | Medium | XML + Python method — 15-min write |

