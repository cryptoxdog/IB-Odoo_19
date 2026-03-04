<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# The manifest references view files (crm_lead_views.xml, material_profile_views.xml) that were not provided in the source document please create

Now I have everything needed — the existing form structures, xpath targets, and field names. Here are the two complete view files.

***

## `views/crm_lead_views.xml`

This inherits the stock `crm.crm_lead_view_form` and adds smart buttons plus a PlastOS Pipeline tab. It sits alongside the existing `plasticos_enrichment_bridge` view that already adds an Enrichment tab  — no conflicts because we use distinct `xpath` targets and a separate `name` attribute on the notebook page.

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <!-- ═══════════════════════════════════════════════════════════════
         CRM Lead Form — PlastOS Pipeline Smart Buttons + Tab
         Inherits: crm.crm_lead_view_form (Odoo core)
         ═══════════════════════════════════════════════════════════════ -->

    <record id="crm_lead_plastos_bridge_form" model="ir.ui.view">
        <field name="name">crm.lead.plastos.bridge.form</field>
        <field name="model">crm.lead</field>
        <field name="inherit_id" ref="crm.crm_lead_view_form"/>
        <field name="priority">30</field>
        <field name="arch" type="xml">

            <!-- ═══ Smart Buttons ═══ -->
            <xpath expr="//div[@name='button_box']" position="inside">

                <!-- Web Leads -->
                <button name="action_view_web_leads"
                        type="object"
                        class="oe_stat_button"
                        icon="fa-globe"
                        invisible="web_lead_count == 0">
                    <field name="web_lead_count"
                           string="Web Leads"
                           widget="statinfo"/>
                </button>

                <!-- Material Profiles -->
                <button name="action_view_material_profiles"
                        type="object"
                        class="oe_stat_button"
                        icon="fa-cubes"
                        invisible="material_profile_count == 0">
                    <field name="material_profile_count"
                           string="Profiles"
                           widget="statinfo"/>
                </button>

                <!-- Total Matches (across all profiles) -->
                <button name="action_view_match_results"
                        type="object"
                        class="oe_stat_button"
                        icon="fa-handshake-o"
                        invisible="total_match_count == 0">
                    <field name="total_match_count"
                           string="Matches"
                           widget="statinfo"/>
                </button>

                <!-- Total Transactions -->
                <button name="action_view_transactions"
                        type="object"
                        class="oe_stat_button"
                        icon="fa-exchange"
                        invisible="total_transaction_count == 0">
                    <field name="total_transaction_count"
                           string="Transactions"
                           widget="statinfo"/>
                </button>

            </xpath>

            <!-- ═══ PlastOS Pipeline Tab ═══ -->
            <xpath expr="//notebook" position="inside">
                <page string="PlastOS Pipeline" name="plastos_pipeline_tab">

                    <!-- KPI Banner -->
                    <div class="alert alert-info" role="alert"
                         invisible="total_transaction_count == 0">
                        <div class="d-flex justify-content-between">
                            <span>
                                <strong>Revenue:</strong>
                                <field name="partner_total_revenue"
                                       widget="monetary"
                                       nolabel="1"/>
                            </span>
                            <span>
                                <strong>Last Load Shipped:</strong>
                                <field name="partner_last_pickup" nolabel="1"
                                       widget="date"/>
                            </span>
                        </div>
                    </div>

                    <!-- Web Lead Origins -->
                    <group string="Web Lead Origins"
                           invisible="web_lead_count == 0">
                        <field name="web_lead_ids" nolabel="1" readonly="1">
                            <list>
                                <field name="lead_id"/>
                                <field name="company_name"/>
                                <field name="decision" widget="badge"
                                       decoration-success="decision == 'hot'"
                                       decoration-muted="decision == 'cold'"/>
                                <field name="state" widget="badge"
                                       decoration-info="state == 'received'"
                                       decoration-success="state == 'intake_created'"
                                       decoration-muted="state == 'skipped'"
                                       decoration-danger="state == 'error'"/>
                                <field name="material_description"/>
                                <field name="estimated_lbs_per_load"/>
                                <field name="create_date"/>
                            </list>
                        </field>
                    </group>

                    <!-- Pipeline Summary -->
                    <group string="Pipeline Summary">
                        <group>
                            <field name="material_profile_count"
                                   string="Material Profiles"/>
                            <field name="total_match_count"
                                   string="Total Matches"/>
                        </group>
                        <group>
                            <field name="total_transaction_count"
                                   string="Transactions"/>
                            <field name="partner_total_revenue"
                                   string="Total Revenue"
                                   widget="monetary"/>
                            <field name="partner_last_pickup"
                                   string="Last Load Shipped"/>
                        </group>
                    </group>

                </page>
            </xpath>

        </field>
    </record>

    <!-- ═══════════════════════════════════════════════════════════════
         CRM Lead List — Add PlastOS columns
         ═══════════════════════════════════════════════════════════════ -->

    <record id="crm_lead_plastos_bridge_list" model="ir.ui.view">
        <field name="name">crm.lead.plastos.bridge.list</field>
        <field name="model">crm.lead</field>
        <field name="inherit_id" ref="crm.crm_case_tree_view_leads"/>
        <field name="priority">30</field>
        <field name="arch" type="xml">
            <xpath expr="//list" position="inside">
                <field name="total_match_count" string="Matches" optional="hide"/>
                <field name="total_transaction_count" string="Txns" optional="hide"/>
                <field name="partner_last_pickup" string="Last Shipped" optional="hide"/>
            </xpath>
        </field>
    </record>

    <!-- ═══════════════════════════════════════════════════════════════
         Web Lead Form — Inject crm_lead_id field
         Inherits: plasticos_web_leads.view_web_lead_form
         ═══════════════════════════════════════════════════════════════ -->

    <record id="web_lead_crm_bridge_form" model="ir.ui.view">
        <field name="name">plasticos.web.lead.crm.bridge.form</field>
        <field name="model">plasticos.web.lead</field>
        <field name="inherit_id" ref="plasticos_web_leads.view_web_lead_form"/>
        <field name="arch" type="xml">
            <!-- Add CRM Lead link next to existing partner_id + intake_id -->
            <xpath expr="//group[@string='Links']" position="inside">
                <field name="crm_lead_id"/>
            </xpath>
        </field>
    </record>

    <!-- ═══════════════════════════════════════════════════════════════
         Web Lead List — Add crm_lead_id column
         ═══════════════════════════════════════════════════════════════ -->

    <record id="web_lead_crm_bridge_list" model="ir.ui.view">
        <field name="name">plasticos.web.lead.crm.bridge.list</field>
        <field name="model">plasticos.web.lead</field>
        <field name="inherit_id" ref="plasticos_web_leads.view_web_lead_list"/>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='intake_id']" position="after">
                <field name="crm_lead_id" optional="show"/>
            </xpath>
        </field>
    </record>

</odoo>
```


### Key Design Decisions

- **Smart buttons** use `invisible="... == 0"` so they only appear when data exists — keeps the CRM lead form clean for leads that haven't progressed yet .
- The **PlastOS Pipeline tab** sits alongside the Enrichment tab from `plasticos_enrichment_bridge`  — separate `name` attributes (`plastos_pipeline_tab` vs `enrichment_tab`) prevent conflicts.
- The **KPI banner** (revenue + last shipped) only shows when transactions exist — it's the first thing a salesperson sees when they open a lead with history.
- The web lead form gets `crm_lead_id` injected into the existing `Links` group right next to `partner_id` and `intake_id` , so the full chain is visible: Partner → Intake → CRM Lead.

***

## `views/material_profile_views.xml`

This inherits the existing material profile form  and adds the match/transaction/logistics stats as smart buttons and a new notebook page.

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <!-- ═══════════════════════════════════════════════════════════════
         Material Profile Form — CRM Bridge Smart Buttons + Stats Tab
         Inherits: plasticos_material_profile.view_material_profile_form
         ═══════════════════════════════════════════════════════════════ -->

    <record id="material_profile_crm_bridge_form" model="ir.ui.view">
        <field name="name">plasticos.material.profile.crm.bridge.form</field>
        <field name="model">plasticos.material.profile</field>
        <field name="inherit_id"
               ref="plasticos_material_profile.view_material_profile_form"/>
        <field name="priority">20</field>
        <field name="arch" type="xml">

            <!-- ═══ Smart Buttons ═══ -->
            <xpath expr="//div[@name='button_box']" position="inside">

                <!-- Match Results -->
                <button name="action_view_match_results"
                        type="object"
                        class="oe_stat_button"
                        icon="fa-handshake-o"
                        invisible="match_count == 0">
                    <div class="o_stat_info">
                        <span class="o_stat_value">
                            <field name="match_count" nolabel="1"/>
                        </span>
                        <span class="o_stat_text">Matches</span>
                    </div>
                </button>

                <!-- Best Match Score (visual indicator) -->
                <button name="action_view_match_results"
                        type="object"
                        class="oe_stat_button"
                        icon="fa-trophy"
                        invisible="best_match_score == 0">
                    <div class="o_stat_info">
                        <span class="o_stat_value">
                            <field name="best_match_score" nolabel="1"
                                   widget="float" digits="[5,1]"/>%
                        </span>
                        <span class="o_stat_text">Best Match</span>
                    </div>
                </button>

                <!-- Transactions -->
                <button name="action_view_transactions"
                        type="object"
                        class="oe_stat_button"
                        icon="fa-exchange"
                        invisible="transaction_count == 0">
                    <field name="transaction_count"
                           string="Transactions"
                           widget="statinfo"/>
                </button>

            </xpath>

            <!-- ═══ Pipeline & Logistics Tab ═══ -->
            <xpath expr="//notebook" position="inside">
                <page string="Pipeline &amp; Logistics"
                      name="pipeline_logistics_tab">

                    <!-- Last Shipped Banner -->
                    <div class="alert alert-success" role="alert"
                         invisible="not last_pickup_date">
                        <i class="fa fa-truck"/> <strong>Last Load Shipped:</strong>
                        <field name="last_pickup_date" nolabel="1" widget="date"/>
                    </div>

                    <div class="alert alert-warning" role="alert"
                         invisible="last_pickup_date or transaction_count == 0">
                        <i class="fa fa-exclamation-triangle"/>
                        Transactions exist but no loads have been picked up yet.
                    </div>

                    <!-- Matching Stats -->
                    <group string="Matching">
                        <group>
                            <field name="match_count"/>
                            <field name="best_match_score"
                                   widget="progressbar"/>
                        </group>
                        <group>
                            <field name="pending_match_count"/>
                        </group>
                    </group>

                    <!-- Transaction Stats -->
                    <group string="Transaction History">
                        <group>
                            <field name="transaction_count"/>
                            <field name="total_revenue" widget="monetary"/>
                        </group>
                        <group>
                            <field name="last_pickup_date"
                                   string="Last Load Shipped"/>
                        </group>
                    </group>

                </page>
            </xpath>

        </field>
    </record>

    <!-- ═══════════════════════════════════════════════════════════════
         Material Profile List — Add pipeline columns
         ═══════════════════════════════════════════════════════════════ -->

    <record id="material_profile_crm_bridge_list" model="ir.ui.view">
        <field name="name">plasticos.material.profile.crm.bridge.list</field>
        <field name="model">plasticos.material.profile</field>
        <field name="inherit_id"
               ref="plasticos_material_profile.view_material_profile_list"/>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='contamination_percent']" position="after">
                <field name="match_count" string="Matches" optional="show"/>
                <field name="best_match_score" string="Best Match %"
                       optional="show"/>
                <field name="transaction_count" string="Txns" optional="show"/>
                <field name="total_revenue" string="Revenue" optional="hide"
                       sum="Total Revenue"/>
                <field name="last_pickup_date" string="Last Shipped"
                       optional="show"/>
            </xpath>
        </field>
    </record>

    <!-- ═══════════════════════════════════════════════════════════════
         Partner Form — Add pipeline stats to Material Profiles tab
         Extends the existing plasticos_material_profile partner extension
         to show pipeline columns inline on the embedded list.
         ═══════════════════════════════════════════════════════════════ -->

    <record id="partner_form_material_bridge_stats" model="ir.ui.view">
        <field name="name">res.partner.form.material.bridge.stats</field>
        <field name="model">res.partner</field>
        <field name="inherit_id"
               ref="plasticos_material_profile.view_partner_form_material_tab"/>
        <field name="priority">20</field>
        <field name="arch" type="xml">
            <!-- Add pipeline columns to the embedded material profiles list -->
            <xpath expr="//field[@name='material_profile_ids']//list/field[@name='contamination_percent']"
                   position="after">
                <field name="match_count" string="Matches"/>
                <field name="best_match_score" string="Best %"/>
                <field name="transaction_count" string="Txns"/>
                <field name="last_pickup_date" string="Last Shipped"/>
            </xpath>
        </field>
    </record>

</odoo>
```


### Key Design Decisions

- **Smart buttons on material profile**: Match count, best match score (trophy icon), and transaction count each get their own button — the salesperson can drill into the exact match results or transactions for *this specific polymer+form at this facility* .
- **`best_match_score` uses `widget="progressbar"`** inside the tab for a visual 0–100% bar, and plain numeric display in the smart button — two contexts, two widgets.
- **`last_pickup_date` as a banner**: The green "Last Load Shipped" alert is the most prominent element on the Pipeline tab — it answers the \#1 question a salesperson has: "when did we last move material from this source?" It traverses `transaction → load → pickup_datetime` .
- **Partner form embedded list**: The existing partner form's Material Profiles tab  gets pipeline columns added inline (`match_count`, `best_match_score`, `transaction_count`, `last_pickup_date`) — so on the partner form you see at-a-glance which profiles are active and which are dormant, **per-profile**, not aggregated.
- **`optional="show"` vs `"hide"`**: Match count and best match are shown by default on the list view; revenue is hidden by default (opt-in) since it's sensitive data.

***

## Navigation Actions Needed on the Python Side

The views reference several `action_view_*` methods that need to exist on the models. Here's the companion Python for the `crm.lead` actions:

```python
# In crm_lead.py — add these action methods

def action_view_web_leads(self):
    self.ensure_one()
    return {
        "type": "ir.actions.act_window",
        "name": f"Web Leads — {self.partner_name or self.name}",
        "res_model": "plasticos.web.lead",
        "view_mode": "list,form",
        "domain": [("crm_lead_id", "=", self.id)],
    }

def action_view_material_profiles(self):
    self.ensure_one()
    facilities = self.partner_id.child_ids if self.partner_id else self.env["res.partner"]
    return {
        "type": "ir.actions.act_window",
        "name": f"Material Profiles — {self.partner_id.name or ''}",
        "res_model": "plasticos.material.profile",
        "view_mode": "list,form",
        "domain": [("partner_id", "in", facilities.ids)],
    }

def action_view_match_results(self):
    self.ensure_one()
    facilities = self.partner_id.child_ids if self.partner_id else self.env["res.partner"]
    profiles = self.env["plasticos.material.profile"].search([
        ("partner_id", "in", facilities.ids),
    ])
    intakes = self.env["plasticos.intake"].search([
        ("partner_id", "in", facilities.ids),
    ])
    return {
        "type": "ir.actions.act_window",
        "name": f"Match Results — {self.partner_id.name or ''}",
        "res_model": "plasticos.match.result",
        "view_mode": "list,form",
        "domain": [("intake_id", "in", intakes.ids)],
    }

def action_view_transactions(self):
    self.ensure_one()
    facilities = self.partner_id.child_ids if self.partner_id else self.env["res.partner"]
    profiles = self.env["plasticos.material.profile"].search([
        ("partner_id", "in", facilities.ids),
    ])
    return {
        "type": "ir.actions.act_window",
        "name": f"Transactions — {self.partner_id.name or ''}",
        "res_model": "plasticos.transaction",
        "view_mode": "list,form",
        "domain": [
            "|",
            ("supplier_profile_id", "in", profiles.ids),
            ("buyer_profile_id", "in", profiles.ids),
        ],
    }
```

And for the `material.profile` actions:

```python
# In material_profile.py — add these action methods

def action_view_match_results(self):
    self.ensure_one()
    intakes = self.env["plasticos.intake"].search([
        ("partner_id", "=", self.partner_id.id),
        ("polymer_id", "=", self.polymer_id.id),
    ])
    return {
        "type": "ir.actions.act_window",
        "name": f"Matches — {self.polymer_id.name} @ {self.partner_id.name}",
        "res_model": "plasticos.match.result",
        "view_mode": "list,form",
        "domain": [("intake_id", "in", intakes.ids)],
    }

def action_view_transactions(self):
    self.ensure_one()
    return {
        "type": "ir.actions.act_window",
        "name": f"Transactions — {self.polymer_id.name}",
        "res_model": "plasticos.transaction",
        "view_mode": "list,form",
        "domain": [
            "|",
            ("supplier_profile_id", "=", self.id),
            ("buyer_profile_id", "=", self.id),
        ],
    }
```

These action methods follow the same pattern already used in the material profile for `action_view_po_lines` and `action_view_so_lines`  — `ensure_one()`, build a domain, return an `act_window` dict.
