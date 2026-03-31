import logging

from odoo import api, fields, models, tools

_logger = logging.getLogger(__name__)

PLASTICOS_TRANSACTION = "plasticos.transaction"


class PlasticosSalesDashboard(models.Model):
    """Read-only sales rep deal dashboard.

    Backed by a PostgreSQL VIEW (_auto = False). One row per non-cancelled
    transaction. Row-level security in plasticos_security_base/security/record_rules.xml
    limits reps to their own deals (user_id = uid).

    Reps NEVER access plasticos.transaction, plasticos.load, or
    plasticos.commission.payout directly. All data surfaces here.
    """

    _name = "plasticos.sales.dashboard"
    _description = "Sales Rep Deal Dashboard"
    _auto = False
    _rec_name = "transaction_ref"
    _order = "transaction_state desc, write_date desc"

    # ── Identity ──────────────────────────────────────────────────────────────
    transaction_id = fields.Many2one(PLASTICOS_TRANSACTION, readonly=True)
    transaction_ref = fields.Char(string="Deal #", readonly=True)
    user_id = fields.Many2one("res.users", string="Rep", readonly=True)

    # ── Deal Basics ───────────────────────────────────────────────────────────
    supplier_id = fields.Many2one("res.partner", string="Supplier", readonly=True)
    buyer_id = fields.Many2one("res.partner", string="Buyer", readonly=True)
    product_id = fields.Many2one("product.product", string="Material", readonly=True)
    quantity = fields.Float(string="Quantity", readonly=True)
    uom_id = fields.Many2one("uom.uom", string="UOM", readonly=True)

    # ── Financials ────────────────────────────────────────────────────────────
    unit_price = fields.Float(string="Sell $/unit", digits="Product Price", readonly=True)
    revenue_total = fields.Float(string="Sell Total", digits="Product Price", readonly=True)
    purchase_cost_total = fields.Float(string="Buy Total", digits="Product Price", readonly=True)
    freight_cost_total = fields.Float(string="Freight", digits="Product Price", readonly=True)
    gross_margin = fields.Float(string="Gross Margin", digits="Product Price", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)

    # ── Weight ────────────────────────────────────────────────────────────────
    final_weight = fields.Float(string="Net Weight (lbs)", readonly=True)
    weight_source = fields.Selection(
        [("scale", "Scale Ticket"), ("buyer", "Buyer Report"), ("supplier", "Supplier Weight"), ("none", "No Weight")],
        string="Weight Source",
        readonly=True,
    )
    weight_discrepancy_flagged = fields.Boolean(string="Discrepancy", readonly=True)
    weight_discrepancy_pct = fields.Float(string="Discrepancy %", readonly=True)

    # ── Logistics ─────────────────────────────────────────────────────────────
    transaction_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("pending_supplier", "Pending Supplier"),
            ("supplier_not_ready", "Supplier Not Ready"),
            ("supplier_ready", "Supplier Ready"),
            ("do_created", "DO Created"),
            ("dispatched", "Dispatched"),
            ("in_progress", "In Progress"),
            ("in_transit", "In Transit"),
            ("delivered", "Delivered"),
            ("invoiced", "Invoiced"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        string="Deal Status",
        readonly=True,
    )
    load_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("awaiting_ready", "Awaiting Ready"),
            ("ready_confirmed", "Ready Confirmed"),
            ("rate_confirmed", "Rate Confirmed"),
            ("scheduled", "Scheduled"),
            ("dispatched", "Dispatched"),
            ("picked_up", "Picked Up"),
            ("delivered", "Delivered"),
            ("closed", "Closed"),
            ("exception", "Exception"),
        ],
        string="Load Status",
        readonly=True,
    )
    load_id = fields.Many2one("plasticos.load", readonly=True)
    pickup_datetime = fields.Datetime(string="Pickup", readonly=True)
    delivery_datetime = fields.Datetime(string="Est. Delivery", readonly=True)
    delivered_at = fields.Datetime(string="Delivered At", readonly=True)
    carrier_name = fields.Char(string="Carrier", readonly=True)
    trailer_number = fields.Char(string="Trailer #", readonly=True)
    delivery_term = fields.Selection(
        [("fcfs", "FCFS"), ("appointment", "Appointment")],
        string="Delivery Term",
        readonly=True,
    )

    # ── Document Checklist (computed, not in SQL view) ────────────────────────
    doc_bol = fields.Selection(
        [("ok", "✓"), ("pending", "Pending Review"), ("missing", "Missing")],
        string="BOL",
        compute="_compute_doc_checklist",
        readonly=True,
    )
    doc_scale_ticket = fields.Selection(
        [("ok", "✓"), ("pending", "Pending Review"), ("missing", "Missing")],
        string="Scale Ticket",
        compute="_compute_doc_checklist",
        readonly=True,
    )
    doc_invoice = fields.Selection(
        [("ok", "✓"), ("pending", "Pending Review"), ("missing", "Missing")],
        string="Invoice",
        compute="_compute_doc_checklist",
        readonly=True,
    )
    doc_customer_order = fields.Selection(
        [("ok", "✓"), ("pending", "Pending Review"), ("missing", "Missing")],
        string="Customer Order",
        compute="_compute_doc_checklist",
        readonly=True,
    )
    docs_all_clear = fields.Boolean(
        string="Docs Clear",
        compute="_compute_doc_checklist",
        readonly=True,
        search="_search_docs_all_clear",
    )

    # ── Commission ────────────────────────────────────────────────────────────
    commission_amount = fields.Float(string="Est. Commission", digits="Product Price", readonly=True)
    commission_locked_amount = fields.Float(string="Final Commission", digits="Product Price", readonly=True)
    commission_payout_state = fields.Selection(
        [("unpaid", "Unpaid"), ("confirmed", "Awaiting Payment"), ("paid", "Paid")],
        string="Pay Status",
        readonly=True,
    )

    write_date = fields.Datetime(string="Last Updated", readonly=True)

    # ── SQL View ──────────────────────────────────────────────────────────────
    def init(self):
        tools.drop_view_if_exists(self.env.cr, "plasticos_sales_dashboard")
        self.env.cr.execute("""
            CREATE VIEW plasticos_sales_dashboard AS
            SELECT
                t.id                                          AS id,
                t.id                                          AS transaction_id,
                t.name                                        AS transaction_ref,
                t.user_id                                     AS user_id,
                t.supplier_id                                 AS supplier_id,
                t.buyer_id                                    AS buyer_id,
                t.product_id                                  AS product_id,
                t.quantity                                     AS quantity,
                t.uom_id                                      AS uom_id,
                t.unit_price                                  AS unit_price,
                t.revenue_total                               AS revenue_total,
                t.purchase_cost_total                         AS purchase_cost_total,
                t.freight_cost_total                          AS freight_cost_total,
                t.gross_margin                                AS gross_margin,
                NULL::integer                                 AS currency_id,
                COALESCE(t.final_weight, 0.0)                 AS final_weight,
                COALESCE(t.weight_source, 'none')             AS weight_source,
                COALESCE(t.weight_discrepancy_flagged, FALSE)  AS weight_discrepancy_flagged,
                COALESCE(t.weight_discrepancy_pct, 0.0)       AS weight_discrepancy_pct,
                t.state                                       AS transaction_state,
                t.write_date                                  AS write_date,
                COALESCE(t.commission_amount, 0.0)            AS commission_amount,
                0.0::double precision                         AS commission_locked_amount,
                'unpaid'::varchar                             AS commission_payout_state,
                l.id                                          AS load_id,
                l.state                                       AS load_state,
                l.pickup_datetime                             AS pickup_datetime,
                l.delivery_datetime                           AS delivery_datetime,
                l.delivered_at                                AS delivered_at,
                l.trailer_number                              AS trailer_number,
                l.delivery_term                               AS delivery_term,
                rp.name                                       AS carrier_name
            FROM plasticos_transaction t
            LEFT JOIN plasticos_load l ON l.id = t.load_id
            LEFT JOIN res_partner rp ON rp.id = l.carrier_id
            WHERE t.state != 'cancelled'
        """)

    # ── Doc Checklist Compute ─────────────────────────────────────────────────
    @api.depends("transaction_id")
    def _compute_doc_checklist(self):
        """Batch-fetch documents for all transactions in this recordset.

        Status priority per doc_type:
          ok      → at least one doc with verified=True or override=True
          pending → doc exists but not yet verified (AI flagged or just uploaded)
          missing → no document of this type on file
        """
        DOC_TYPES = {
            "bol": "doc_bol",
            "scale_ticket": "doc_scale_ticket",
            "invoice": "doc_invoice",
            "customer_order": "doc_customer_order",
        }

        if "documents.document" in self.env:
            active_model = "documents.document"
        elif "plasticos.document" in self.env:
            active_model = "plasticos.document"
        else:
            for rec in self:
                for f in DOC_TYPES.values():
                    rec[f] = "missing"
                rec.docs_all_clear = False
            return

        tx_ids = self.mapped("transaction_id").ids
        if not tx_ids:
            for rec in self:
                for f in DOC_TYPES.values():
                    rec[f] = "missing"
                rec.docs_all_clear = False
            return

        docs = (
            self.env[active_model]
            .sudo()
            .search(
                [
                    ("transaction_id", "in", tx_ids),
                    ("doc_type", "in", list(DOC_TYPES.keys())),
                ]
            )
        )

        lookup = {}
        for doc in docs:
            tid = doc.transaction_id.id
            dtype = doc.doc_type
            if tid not in lookup:
                lookup[tid] = {}
            verified = getattr(doc, "verified", False) or getattr(doc, "override", False)
            new_status = "ok" if verified else "pending"
            if lookup[tid].get(dtype, "missing") != "ok":
                lookup[tid][dtype] = new_status

        for rec in self:
            tid = rec.transaction_id.id
            tx_docs = lookup.get(tid, {})
            all_clear = True
            for doc_type, field_name in DOC_TYPES.items():
                status = tx_docs.get(doc_type, "missing")
                rec[field_name] = status
                if status != "ok":
                    all_clear = False
            rec.docs_all_clear = all_clear

    def _search_docs_all_clear(self, operator, value):
        """Search method for docs_all_clear — translates to compliance_status domain.

        Allows Odoo 19 domain filters on this non-stored computed field.
        Uses plasticos.transaction.compliance_status (stored) as the proxy.
        """
        if operator not in ("=", "!="):
            return []
        want_clear = (operator == "=" and value) or (operator == "!=" and not value)
        compliance_val = "compliant" if want_clear else "missing"
        txs = self.env["plasticos.transaction"].search([("compliance_status", "=", compliance_val)])
        return [("transaction_id", "in", txs.ids)]

    # ══════════════════════════════════════════════════════════════════════════
    # Drill-Through Actions
    # ══════════════════════════════════════════════════════════════════════════

    def action_view_my_docs(self):
        """All documents for this deal — rep sees everything including buyer docs."""
        self.ensure_one()
        doc_model = "documents.document" if "documents.document" in self.env else "plasticos.document"
        return {
            "type": "ir.actions.act_window",
            "name": f"Documents — {self.transaction_ref}",
            "res_model": doc_model,
            "view_mode": "list,form",
            "domain": [("transaction_id", "=", self.transaction_id.id)],
            "context": {"create": False, "edit": False},
        }

    def action_view_scale_docs(self):
        """Scale ticket documents for this deal.
        Surfaced when weight_source != 'scale' so rep can chase the supplier.
        """
        self.ensure_one()
        doc_model = "documents.document" if "documents.document" in self.env else "plasticos.document"
        return {
            "type": "ir.actions.act_window",
            "name": f"Scale Tickets — {self.transaction_ref}",
            "res_model": doc_model,
            "view_mode": "list,form",
            "domain": [("transaction_id", "=", self.transaction_id.id), ("doc_type", "=", "scale_ticket")],
            "context": {"create": False, "edit": False},
        }

    def action_view_bol_docs(self):
        """BOL documents for this deal."""
        self.ensure_one()
        doc_model = "documents.document" if "documents.document" in self.env else "plasticos.document"
        return {
            "type": "ir.actions.act_window",
            "name": f"BOL — {self.transaction_ref}",
            "res_model": doc_model,
            "view_mode": "list,form",
            "domain": [("transaction_id", "=", self.transaction_id.id), ("doc_type", "=", "bol")],
            "context": {"create": False, "edit": False},
        }

    def action_view_load(self):
        """Open the linked load record (read-only dialog).
        Gives rep carrier contact, pickup/delivery ETA, trailer number
        without navigating into the full logistics module.
        """
        self.ensure_one()
        if not self.load_id:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "No Load Yet",
                    "message": "A load has not been created for this transaction yet.",
                    "type": "warning",
                },
            }
        return {
            "type": "ir.actions.act_window",
            "res_model": "plasticos.load",
            "res_id": self.load_id.id,
            "view_mode": "form",
            "target": "new",
            "flags": {"mode": "readonly"},
        }

    def action_view_payout(self):
        """Commission payout batch detail — shown when pay status is not Unpaid."""
        self.ensure_one()
        payout_ids = (
            self.env["plasticos.commission.payout"]
            .sudo()
            .search(
                [
                    ("transaction_ids", "in", [self.transaction_id.id]),
                ]
            )
            .ids
        )
        if not payout_ids:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "No Payout Record",
                    "message": "No commission payout has been created yet for this deal.",
                    "type": "info",
                },
            }
        return {
            "type": "ir.actions.act_window",
            "name": "My Commission Payout",
            "res_model": "plasticos.commission.payout",
            "view_mode": "list,form",
            "domain": [("id", "in", payout_ids)],
            "context": {"create": False, "edit": False},
        }
