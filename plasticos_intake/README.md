---
auto_generated: false
authority: derived-index
component_id: plasticos_intake
component_name: PlasticOS Intake
module_version: 19.0.5.4.4
layer: 2
installable: true
auto_install: true
application: false
depends:
  - base
  - contacts
  - crm
  - mail
  - utm
  - plasticos_base
  - plasticos_material_profile
  - plasticos_facility_profile
models_owned:
  - plasticos.intake
  - plasticos.intake.match
models_extended:
  - res.partner
  - plasticos.material.profile
crons: []
---

# PlasticOS Intake

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` win on any conflict.

## What it does

Records one supplier's offer of material: who is selling, from which facility, what material, how much, and in what condition. The intake form fills contact, facility, and material details from what the partner and profile already hold.

## How it works

- **Intake.** `plasticos.intake` (`models/intake.py`) gets its reference from the `plasticos.intake` sequence (`data/sequence.xml`) on create. `status` is `draft`, `matched`, `offer_sent`, `processing`, `won`, `lost`, or `expired`. `action_mark_processing`, `action_mark_won`, `action_mark_lost`, `action_mark_expired`, and `action_reset_to_draft` move it by hand.
- **Smart cascade.** Onchanges on partner, facility, and material profile fill dependent fields. A contact change writes `preferred_contact_id` back on the facility so the next intake reuses it.
- **Lineage.** `crm_lead_id` is a Many2one to the `crm.lead` that created the intake. `source_lead_id` is the integer id of a source web lead.
- **Match lines.** `plasticos.intake.match` holds one buyer line per intake (`buyer_id`, `match_score`, `typical_price`), ordered by score.
- **Match button.** `action_match_to_buyers()` in this module refuses when `GATE_URL` is unset. Otherwise it creates the partner from a pending company name and a material profile from the intake when they are missing, logs the request, and shows a notification. It writes no match result. `plasticos_matching` overrides this method with the Gate match run.
- **Create Intake from a partner or profile.** `res.partner.action_create_intake()` and `plasticos.material.profile.action_create_intake()` open a native CRM Opportunity when `crm.lead` exposes `_plasticos_manual_opportunity_action` (added by `plasticos_crm_bridge`). Without it they open a new intake form. Nothing is created until the user saves.
- **Counts.** The `res.partner` and `plasticos.material.profile` extensions add intake counts and an `action_view_intakes()` button.

## Models

| Model                        | Kind     | File                                |
| ---------------------------- | -------- | ----------------------------------- |
| `plasticos.intake`           | owned    | `models/intake.py`                  |
| `plasticos.intake.match`     | owned    | `models/intake_match.py`            |
| `res.partner`                | extended | `models/res_partner_intake.py`      |
| `plasticos.material.profile` | extended | `models/material_profile_intake.py` |

## Runtime

- No cron, no install hook.
- `auto_install` is true.
- `action_match_to_buyers` reads `GATE_URL` from the process environment.

## Boundaries

- No matching, scoring, or Gate call here. `plasticos_matching` owns the match run.
- `action_send_offers` is not defined in this module. Offers are created by `plasticos_crm_bridge` from reviewed match results.
- The intake is not the commercial pursuit owner when `plasticos_crm_bridge` is installed; the CRM Opportunity is.

## Read next

- [`models/intake.py`](models/intake.py)
- [`../plasticos_matching/README.md`](../plasticos_matching/README.md)
- [`../plasticos_offer/README.md`](../plasticos_offer/README.md)
- [`../docs/adr/ADR-004-intake-vs-material-profile-domain-split.md`](../docs/adr/ADR-004-intake-vs-material-profile-domain-split.md)
