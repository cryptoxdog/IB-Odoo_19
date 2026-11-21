import logging

from odoo import api, fields, models, tools

_logger = logging.getLogger(__name__)

PLASTICOS_TRANSACTION = "plasticos.transaction"


class PlasticosSalesDashboard(models.Model):
    """Read-only sales rep deal dashboard.

    Backed by a PostgreSQL VIEW (_auto = False). One row per non-cancelled
    transaction. Row-level security in plasticos_security_base/security/record_rules.xml
    limits reps to their own deals (user_id = uid).

    DEC-003: a row opens its underlying records (the transaction, its loads, its
    payout) only where the user's own access rights and record rules already allow
    reading them. Navigation never widens access and never uses sudo.
    """

    _name = "plasticos.sales.dashboard"
    _description = "Sales Rep Deal Dashboard"
    _auto = False
    _rec_name = "transaction_ref"
    _order = "transaction_state desc, write_date desc"

    # ── Identity ──────────────────────────────────────────────────────────────
    transaction_id = fields.Many2one(PLASTICOS_TRANSACTION, readonly=True, ondelete="cascade")
    transaction_ref = fields.Char(string="Deal #", readonly=True)
    user_id = fields.Many2one("res.users", string="Rep", readonly=True, ondelete="restrict")

    # ── Deal Basics ───────────────────────────────────────────────────────────
    supplier_id = fields.Many2one("res.partner", string="Supplier", readonly=True, ondelete="restrict")
    buyer_id = fields.Many2one("res.partner", string="Buyer", readonly=True, ondelete="restrict")
    product_id = fields.Many2one("product.product", string="Material", readonly=True, ondelete="restrict")
    quantity = fields.Float(string="Quantity", readonly=True)
    uom_id = fields.Many2one("uom.uom", string="UOM", readonly=True, ondelete="restrict")

    # ── Financials ────────────────────────────────────────────────────────────
    unit_price = fields.Float(string="Sell $/unit", digits="Product Price", readonly=True)
    revenue_total = fields.Float(string="Sell Total", digits="Product Price", readonly=True)
    purchase_cost_total = fields.Float(string="Buy Total", digits="Product Price", readonly=True)
    freight_cost_total = fields.Float(string="Freight", digits="Product Price", readonly=True)
    gross_margin = fields.Float(string="Gross Margin", digits="Product Price", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True, ondelete="restrict")

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
    load_id = fields.Many2one("plasticos.load", readonly=True, ondelete="cascade")
    load_count = fields.Integer(string="Loads", readonly=True)
    pickup_datetime = fields.Datetime(string="Pickup", readonly=True)
    delivery_datetime = fields.Datetime(string="Est. Delivery", readonly=True)
    delivered_at = fields.Datetime(string="Delivered At", readonly=True)
    carrier_name = fields.Char(string="Carrier", readonly=True)
    trailer_number = fields.Char(string="Trailer #", readonly=True)
    delivery_term = fields.Selection(
        [("fcfs", "FCFS"), ("appointment", "Appointment")],
        string="Delivery Dock Rule",
        readonly=True,
    )
    pickup_dock_rule = fields.Selection(
        [("fcfs", "FCFS"), ("appointment", "Appointment")],
        string="Pickup Dock Rule",
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
    # DEC-006: locked amount from the transaction once its commission is locked;
    # pay status from the newest non-cancelled payout of the deal's own rep
    # (payout.sales_rep_id = transaction.user_id) linked through
    # commission_payout_tx_rel, else unpaid. Narrowed to the deal's own rep so the
    # projection never shows a payout the rep cannot read ("Sales Reps see own
    # payouts only"; DEC-003 navigation never widens access). plasticos.transaction.commission_payout_state
    # is never the source (no payout action writes it; RISK-003).
    commission_locked = fields.Boolean(string="Commission Locked", readonly=True)
    commission_locked_amount = fields.Float(string="Final Commission", digits="Product Price", readonly=True)
    commission_payout_state = fields.Selection(
        [("unpaid", "Unpaid"), ("draft", "Payout Draft"), ("confirmed", "Awaiting Payment"), ("paid", "Paid")],
        string="Pay Status",
        readonly=True,
    )

    write_date = fields.Datetime(string="Last Updated", readonly=True)

    # ── Navigation (computed, not in SQL view) ───────────────────────────────
    can_open_transaction = fields.Boolean(
        string="Can Open Deal",
        compute="_compute_can_open_transaction",
        help="True when the current user may read the underlying transaction (ACL and record rules).",
    )

    # ── SQL View ──────────────────────────────────────────────────────────────
    def init(self):
        """Create the view once every column it reads exists.

        Odoo 19 ``Registry.init_models`` runs ``_auto_init(); init()`` model by
        model in import order, and this module's ``plasticos.transaction``
        extension (``commission_locked``, ``commission_locked_amount``) is
        initialised after this model. Inside ``init_models`` the view is queued
        with ``Registry.post_init`` so it is built after every table and column
        of the module; a direct call builds it at once.
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        if hasattr(self.pool, "_post_init_queue"):
            self.pool.post_init(self._create_view)
        else:
            self._create_view()

    def _create_view(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
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
                COALESCE(t.commission_locked, FALSE)          AS commission_locked,
                CASE WHEN t.commission_locked
                     THEN t.commission_locked_amount
                END                                           AS commission_locked_amount,
                COALESCE(lp.state, 'unpaid')::varchar         AS commission_payout_state,
                l.id                                          AS load_id,
                COALESCE(lc.load_count, 0)                    AS load_count,
                l.state                                       AS load_state,
                COALESCE(l.pickup_datetime, lc.earliest_pickup) AS pickup_datetime,
                COALESCE(l.delivery_datetime, lc.latest_delivery) AS delivery_datetime,
                COALESCE(l.delivered_at, lc.latest_delivered) AS delivered_at,
                l.trailer_number                              AS trailer_number,
                COALESCE(l.delivery_term, t.delivery_term)    AS delivery_term,
                COALESCE(l.pickup_dock_rule, t.pickup_dock_rule) AS pickup_dock_rule,
                COALESCE(rp.name, lc.carrier_names)           AS carrier_name
            FROM plasticos_transaction t
            LEFT JOIN (
                SELECT pl.transaction_id,
                       COUNT(*)::integer AS load_count,
                       CASE WHEN COUNT(*) = 1 THEN MIN(pl.id) ELSE NULL::integer END AS sole_load_id,
                       MIN(pl.pickup_datetime) AS earliest_pickup,
                       MAX(pl.delivery_datetime) AS latest_delivery,
                       MAX(pl.delivered_at) AS latest_delivered,
                       string_agg(DISTINCT carrier.name, ', ' ORDER BY carrier.name) AS carrier_names
                  FROM plasticos_load pl
                  LEFT JOIN res_partner carrier ON carrier.id = pl.carrier_id
                 WHERE pl.transaction_id IS NOT NULL
                 GROUP BY pl.transaction_id
            ) lc ON lc.transaction_id = t.id
            LEFT JOIN plasticos_load l ON l.id = lc.sole_load_id
            LEFT JOIN res_partner rp ON rp.id = l.carrier_id
            LEFT JOIN LATERAL (
                SELECT p.state
                  FROM commission_payout_tx_rel rel
                  JOIN plasticos_commission_payout p ON p.id = rel.payout_id
                 WHERE rel.transaction_id = t.id
                   AND p.sales_rep_id = t.user_id
                   AND p.state != 'cancelled'
                 ORDER BY p.id DESC
                 LIMIT 1
            ) lp ON TRUE
            WHERE t.state != 'cancelled'
        """)

    # ── Doc Checklist Compute ─────────────────────────────────────────────────
    # Checklist item -> plasticos.document.tag code of the legacy business row.
    _CHECKLIST_TAG_CODES = {
        "bol": "BOL",
        "scale_ticket": "SCALE",
        "invoice": "INV",
        "customer_order": "CO",
    }
    _CHECKLIST_FIELDS = {
        "bol": "doc_bol",
        "scale_ticket": "doc_scale_ticket",
        "invoice": "doc_invoice",
        "customer_order": "doc_customer_order",
    }

    def _doc_checklist_source(self):
        """Business rows when PlasticOS Documents is installed, else the native records, else none.

        Commission does not depend on Documents, so the model is looked up by name.
        """
        if "plasticos.document" in self.env:
            return "plasticos.document"
        if "documents.document" in self.env:
            return "documents.document"
        return False

    @api.depends("transaction_id")
    def _compute_doc_checklist(self):
        """Per-transaction checklist. One dashboard row per transaction; nothing is multiplied.

        Status per item:
          ok      → a current legacy business row (verified or overridden, not
                    expired, superseded, replaced or conflicting) on the transaction
                    or on one of its loads
          pending → a row of that type exists but is not currently eligible
          missing → no row of that type
        An operation-scoped row never clears a legacy checklist item, and the
        native per-original projection is not the source when business rows exist.
        """
        source = self._doc_checklist_source()
        tx_ids = self.mapped("transaction_id").ids
        if not source or not tx_ids:
            lookup = {}
        elif source == "plasticos.document":
            lookup = self._doc_checklist_from_business_rows(tx_ids)
        else:
            lookup = self._doc_checklist_from_native(tx_ids)

        for rec in self:
            tx_docs = lookup.get(rec.transaction_id.id, {})
            all_clear = True
            for item, field_name in self._CHECKLIST_FIELDS.items():
                status = tx_docs.get(item, "missing")
                rec[field_name] = status
                if status != "ok":
                    all_clear = False
            rec.docs_all_clear = all_clear

    @staticmethod
    def _merge_checklist_status(lookup, tid, item, status):
        current = lookup.setdefault(tid, {}).get(item, "missing")
        if current != "ok":
            lookup[tid][item] = status

    def _doc_checklist_from_business_rows(self, tx_ids):
        tags = (
            self.env["plasticos.document.tag"]
            .sudo()  # sudo: read-only rep dashboard; tag codes only
            .search([("code", "in", list(self._CHECKLIST_TAG_CODES.values()))])
        )
        item_by_tag = {}
        for item, code in self._CHECKLIST_TAG_CODES.items():
            for tag in tags.filtered(lambda t, code=code: t.code == code):
                item_by_tag[tag.id] = item
        if not item_by_tag:
            return {}
        loads = (
            self.env["plasticos.load"]
            .sudo()  # sudo: read-only rep dashboard; reps never read loads directly
            .search([("transaction_id", "in", tx_ids)])
        )
        rows = (
            self.env["plasticos.document"]
            .sudo()  # sudo: read-only rep dashboard; document ACL is narrower
            .search(
                [
                    ("tag_id", "in", list(item_by_tag)),
                    *self.env["plasticos.document"]._legacy_obligation_domain(),
                    "|",
                    "|",
                    "|",
                    ("transaction_id", "in", tx_ids),
                    "&",
                    ("res_model", "=", PLASTICOS_TRANSACTION),
                    ("res_id", "in", tx_ids),
                    ("load_id", "in", loads.ids),
                    "&",
                    ("res_model", "=", "plasticos.load"),
                    ("res_id", "in", loads.ids),
                ]
            )
        )
        load_parent = {load.id: load.transaction_id.id for load in loads}
        wanted = set(tx_ids)
        lookup = {}
        for row in rows:
            if row._association_conflict_reason():
                continue
            if row.transaction_id:
                tid = row.transaction_id.id
            elif row.res_model == PLASTICOS_TRANSACTION:
                tid = row.res_id
            elif row.load_id:
                tid = load_parent.get(row.load_id.id)
            else:
                tid = load_parent.get(row.res_id)
            if tid not in wanted:
                continue
            status = "ok" if row._currently_eligible() else "pending"
            self._merge_checklist_status(lookup, tid, item_by_tag[row.tag_id.id], status)
        return lookup

    def _doc_checklist_from_native(self, tx_ids):
        """Fallback when no business rows exist: native records by their plastics type."""
        name = self._doc_checklist_source()
        if name != "documents.document":
            return {}
        docs = (
            self.env[name]
            .sudo()  # sudo: read-only rep dashboard; document ACL is narrower
            .search(
                [
                    ("transaction_id", "in", tx_ids),
                    ("doc_type", "in", list(self._CHECKLIST_TAG_CODES)),
                ]
            )
        )
        lookup = {}
        for doc in docs:
            verified = getattr(doc, "verified", False) or getattr(doc, "override", False)
            self._merge_checklist_status(lookup, doc.transaction_id.id, doc.doc_type, "ok" if verified else "pending")
        return lookup

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

    @api.depends("transaction_id")
    def _compute_can_open_transaction(self):
        for rec in self:
            rec.can_open_transaction = bool(rec.transaction_id) and rec.transaction_id.has_access("read")

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

    def action_view_transaction(self):
        """Open the owning transaction (DEC-003) when the user may read it.

        The check runs here, server-side; the hidden button is not the control.
        """
        self.ensure_one()
        self.transaction_id.check_access("read")
        return {
            "type": "ir.actions.act_window",
            "name": self.transaction_ref,
            "res_model": PLASTICOS_TRANSACTION,
            "res_id": self.transaction_id.id,
            "view_mode": "form",
        }

    def action_view_load(self):
        """Open the load, or the loads, of this deal.

        One load opens its form. Several loads open a list of exactly the loads
        whose transaction_id is this deal; record rules decide which of them the
        user reads. The deal row stays one financial record.
        """
        self.ensure_one()
        if self.load_count > 1:
            return {
                "type": "ir.actions.act_window",
                "name": f"Loads — {self.transaction_ref}",
                "res_model": "plasticos.load",
                "view_mode": "list,form",
                "domain": [("transaction_id", "=", self.transaction_id.id)],
                "context": {"create": False},
            }
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
        """Commission payout batch detail — shown when a non-cancelled payout exists."""
        self.ensure_one()
        payout_ids = (
            self.env["plasticos.commission.payout"]
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
