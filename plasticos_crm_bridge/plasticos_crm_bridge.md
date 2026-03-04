<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# also create a crm.lead -> lead_source_id=web_lead

Add match_count and best_match_score -> material profile not res.partner main screen
if multiple material profiles can' thave just one match score/count
Add transaction_count and total_revenue -> also add date last load shipped (picked-up)... so bridge to logistics too!?

is there a way to bridge them all in one shot?

Yes — a single `plasticos_crm_bridge` module can wire **everything** in one shot using Odoo's `_inherit` pattern. Here's the architecture based on what's actually in the repo.

## Why One Module Works

Every bridge is just computed fields and `_inherit` extensions — no new tables needed . The existing models already have the foreign keys that make traversal possible. The only real *write* is web lead → CRM lead creation. Everything else is read-only computation.

## The Dependency Graph (Already Wired)

```
plasticos.web.lead
  └─ partner_id, intake_id

plasticos.match.result
  └─ intake_id → intake_id.partner_id

plasticos.material.profile
  └─ partner_id (facility-level)
  └─ unique(partner_id, polymer_id, form_id)

plasticos.transaction
  └─ supplier_profile_id (material.profile)
  └─ buyer_profile_id (material.profile)
  └─ load_id → plasticos.load

plasticos.load
  └─ pickup_datetime, state (picked_up/delivered/closed)
```

All those FKs already exist . The bridge module just adds computed fields that *read along* those existing links.

## Module Blueprint: `plasticos_crm_bridge`

```
plasticos_crm_bridge/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── crm_lead.py          # _inherit crm.lead — the hub
│   ├── web_lead.py           # _inherit plasticos.web.lead — auto-create CRM lead
│   ├── material_profile.py   # _inherit plasticos.material.profile — match + tx stats
│   └── transaction.py        # _inherit plasticos.transaction — crm_lead_id backlink
├── views/
│   ├── crm_lead_views.xml
│   └── material_profile_views.xml
├── data/
│   └── lead_source_data.xml  # seed lead_source_id = "web_lead"
└── security/
    └── ir.model.access.csv
```


### `__manifest__.py`

```python
{
    "name": "PlastOS CRM Bridge",
    "version": "19.0.1.0.0",
    "depends": [
        "crm",
        "plasticos_web_leads",
        "plasticos_matching",
        "plasticos_material_profile",
        "plasticos_transaction",
        "plasticos_logistics",
    ],
    "data": [
        "data/lead_source_data.xml",
        "views/crm_lead_views.xml",
        "views/material_profile_views.xml",
        "security/ir.model.access.csv",
    ],
    "category": "PlastOS",
    "license": "LGPL-3",
}
```


## File 1: `web_lead.py` — Auto-Create CRM Lead

This is the entry point you asked for: HOT web lead → `crm.lead` with `lead_source_id=web_lead` .

```python
from odoo import api, fields, models

class PlasticosWebLeadCRM(models.Model):
    _inherit = "plasticos.web.lead"

    crm_lead_id = fields.Many2one(
        "crm.lead",
        string="CRM Lead",
        index=True,
        ondelete="set null",
    )

    def _create_crm_lead(self):
        """Called after HOT classification — creates crm.lead with web_lead source."""
        self.ensure_one()
        if self.crm_lead_id:
            return self.crm_lead_id

        # Resolve lead_source_id record
        LeadSource = self.env["utm.source"]
        source = LeadSource.search([("name", "=", "web_lead")], limit=1)

        vals = {
            "name": f"{self.company_name} — {self.material_description or 'Web Lead'}",
            "partner_name": self.company_name,
            "contact_name": self.contact_name,
            "email_from": self.contact_email,
            "phone": self.contact_phone,
            "description": self.material_description,
            "source_id": source.id if source else False,
            "type": "lead",
            # Link to partner if already created
            "partner_id": self.partner_id.id if self.partner_id else False,
        }

        lead = self.env["crm.lead"].create(vals)
        self.crm_lead_id = lead
        self.message_post(body=f"CRM Lead created: {lead.name}")
        return lead
```

Then hook it into the existing `_run_triage_pipeline()` — after HOT classification succeeds, call `self._create_crm_lead()` .

## File 2: `material_profile.py` — Match + Transaction Stats (Per-Profile!)

You're 100% right that match score/count can't live on `res.partner` — a supplier with 3 material profiles (HDPE regrind, PP pellet, LDPE film) will have totally different match results for each . The `plasticos.match.result` links through `intake_id → intake_id.partner_id` AND the intake has polymer/form context , so we compute *per material profile*.

Same logic for transactions — `plasticos.transaction` already stores `supplier_profile_id` and `buyer_profile_id` as denormalized M2O fields , making the traversal trivial.

```python
from odoo import api, fields, models


class MaterialProfileCRMBridge(models.Model):
    _inherit = "plasticos.material.profile"

    # ── Match Stats (per-profile, NOT per-partner) ──────────
    match_count = fields.Integer(
        string="Match Count",
        compute="_compute_match_stats",
        store=True,
    )
    best_match_score = fields.Float(
        string="Best Match Score",
        digits=(5, 2),
        compute="_compute_match_stats",
        store=True,
    )
    pending_match_count = fields.Integer(
        string="Pending Matches",
        compute="_compute_match_stats",
        store=True,
    )

    # ── Transaction Stats (per-profile) ─────────────────────
    transaction_count = fields.Integer(
        string="Transactions",
        compute="_compute_tx_stats",
        store=True,
    )
    total_revenue = fields.Float(
        string="Total Revenue",
        compute="_compute_tx_stats",
        store=True,
    )

    # ── Logistics: Last Load Shipped ────────────────────────
    last_pickup_date = fields.Datetime(
        string="Last Load Shipped",
        compute="_compute_tx_stats",
        store=True,
        help="Most recent pickup_datetime from linked loads.",
    )

    @api.depends("partner_id", "polymer_id")
    def _compute_match_stats(self):
        """Match results link through intake → intake.partner_id + polymer.

        A match is 'for this profile' when the intake's supplier and
        polymer match this material profile's partner + polymer.
        """
        MatchResult = self.env["plasticos.match.result"]
        Intake = self.env["plasticos.intake"]
        for rec in self:
            if not rec.partner_id or not rec.polymer_id:
                rec.match_count = 0
                rec.best_match_score = 0.0
                rec.pending_match_count = 0
                continue

            # Find intakes for this facility + polymer
            intakes = Intake.search([
                ("partner_id", "=", rec.partner_id.id),
                ("polymer_id", "=", rec.polymer_id.id),
            ])
            if not intakes:
                rec.match_count = 0
                rec.best_match_score = 0.0
                rec.pending_match_count = 0
                continue

            matches = MatchResult.search([
                ("intake_id", "in", intakes.ids),
            ])
            rec.match_count = len(matches)
            rec.best_match_score = max(matches.mapped("score"), default=0.0)
            rec.pending_match_count = len(
                matches.filtered(lambda m: m.state == "pending")
            )

    @api.depends("partner_id", "polymer_id")
    def _compute_tx_stats(self):
        """Transactions already store supplier_profile_id / buyer_profile_id.

        Also reaches into plasticos.load for last_pickup_date.
        """
        Transaction = self.env["plasticos.transaction"]
        for rec in self:
            # Transactions where this is the supplier's profile
            txs = Transaction.search([
                "|",
                ("supplier_profile_id", "=", rec.id),
                ("buyer_profile_id", "=", rec.id),
            ])
            rec.transaction_count = len(txs)
            rec.total_revenue = sum(txs.mapped("revenue_total"))

            # Last load shipped — traverse tx → load_id → pickup_datetime
            loads = txs.mapped("load_id").filtered(
                lambda l: l.pickup_datetime and l.state in (
                    "picked_up", "delivered", "closed"
                )
            )
            if loads:
                rec.last_pickup_date = max(loads.mapped("pickup_datetime"))
            else:
                rec.last_pickup_date = False
```


### Why This Architecture Is Correct

| Stat | Lives On | Reason |
| :-- | :-- | :-- |
| `match_count` / `best_match_score` | `material.profile` | A partner's HDPE regrind profile matches different buyers than their PP pellet profile |
| `transaction_count` / `total_revenue` | `material.profile` | Transaction already stores `supplier_profile_id` per-polymer  — aggregating at partner level would mix HDPE and PP revenue |
| `last_pickup_date` | `material.profile` | Traverses `transaction.load_id.pickup_datetime`  — answers "when did we last ship *this specific material* from *this facility*?" |

## File 3: `crm_lead.py` — The Hub (Rollup View)

The CRM lead form gets *summary* stats rolled up from the partner's material profiles:

```python
from odoo import api, fields, models


class CrmLeadPlastOS(models.Model):
    _inherit = "crm.lead"

    # ── Web Lead Link ──────────────────────────────────────
    web_lead_ids = fields.One2many(
        "plasticos.web.lead",
        "crm_lead_id",
        string="Web Leads",
    )
    web_lead_count = fields.Integer(
        compute="_compute_web_lead_count",
    )

    # ── Material Profile Summary (rolled up from partner) ──
    material_profile_count = fields.Integer(
        compute="_compute_profile_summary",
    )
    total_match_count = fields.Integer(
        string="Total Matches (All Profiles)",
        compute="_compute_profile_summary",
    )
    total_transaction_count = fields.Integer(
        string="Total Transactions",
        compute="_compute_profile_summary",
    )
    partner_total_revenue = fields.Float(
        string="Total Revenue (All Profiles)",
        compute="_compute_profile_summary",
    )
    partner_last_pickup = fields.Datetime(
        string="Last Load Shipped",
        compute="_compute_profile_summary",
    )

    def _compute_web_lead_count(self):
        for rec in self:
            rec.web_lead_count = len(rec.web_lead_ids)

    def _compute_profile_summary(self):
        Profile = self.env["plasticos.material.profile"]
        for rec in self:
            if not rec.partner_id:
                rec.material_profile_count = 0
                rec.total_match_count = 0
                rec.total_transaction_count = 0
                rec.partner_total_revenue = 0.0
                rec.partner_last_pickup = False
                continue

            # All profiles for this partner's facilities
            facilities = rec.partner_id.child_ids
            profiles = Profile.search([
                ("partner_id", "in", facilities.ids),
            ])
            rec.material_profile_count = len(profiles)
            rec.total_match_count = sum(profiles.mapped("match_count"))
            rec.total_transaction_count = sum(
                profiles.mapped("transaction_count")
            )
            rec.partner_total_revenue = sum(
                profiles.mapped("total_revenue")
            )
            pickups = profiles.mapped("last_pickup_date")
            pickups = [d for d in pickups if d]
            rec.partner_last_pickup = max(pickups) if pickups else False
```

The CRM lead form shows **summary** numbers, with a smart button that drills into the individual material profiles where the per-profile breakdown lives .

## The Logistics Bridge Is Already There

You asked "bridge to logistics too?" — the good news is `plasticos.transaction` already has `load_id = fields.Many2one("plasticos.load")` , and `plasticos.load` already has `pickup_datetime`, `delivered_at`, and the full state machine from `draft` → `picked_up` → `delivered` → `closed` . The `_compute_tx_stats` method above just follows that existing FK chain: `material_profile → transaction → load → pickup_datetime`. No new bridge needed — it's one hop.

## Data File: `lead_source_data.xml`

```xml
<odoo>
  <data noupdate="1">
    <record id="utm_source_web_lead" model="utm.source">
      <field name="name">web_lead</field>
    </record>
  </data>
</odoo>
```


## One Module, Full Pipeline Visibility

After installing `plasticos_crm_bridge`, a salesperson looking at a CRM lead would see:

- **Where it came from**: Web Lead count + link (HOT/COLD, AI triage log)
- **Material Profiles** smart button: drill into per-profile stats
- **Per-profile on the material profile form**: match count, best match score, transaction count, revenue, last load shipped
- **Rolled-up on CRM lead**: total matches, total transactions, total revenue, last pickup date

The key architectural decision — **stats on material profile, summaries on CRM lead** — respects the reality that a single partner with 5 polymer+form combinations is really 5 independent deal pipelines .
