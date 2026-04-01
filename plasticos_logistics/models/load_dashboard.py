import logging

from odoo import fields, models, tools

_logger = logging.getLogger(__name__)

PLASTICOS_LOAD = "plasticos.load"


class PlasticosLoadDashboard(models.Model):
    """Read-only logistics dashboard backed by a PostgreSQL VIEW.

    One row per non-cancelled load. Sales reps see only loads linked to
    their transactions (via record rule). Logistics and managers see all.
    """

    _name = "plasticos.load.dashboard"
    _description = "Logistics Dashboard"
    _auto = False
    _rec_name = "load_ref"
    _order = "pickup_datetime desc, id desc"

    # ── Identity ──────────────────────────────────────────────────────────
    load_id = fields.Many2one(PLASTICOS_LOAD, readonly=True, ondelete="cascade")
    load_ref = fields.Char(string="Load #", readonly=True)
    transaction_ref = fields.Char(string="Deal #", readonly=True)
    user_id = fields.Many2one("res.users", string="Rep", readonly=True, ondelete="restrict")

    # ── Status ────────────────────────────────────────────────────────────
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

    # ── Schedule ──────────────────────────────────────────────────────────
    pickup_datetime = fields.Datetime(string="Pickup", readonly=True)
    delivery_datetime = fields.Datetime(string="Est. Delivery", readonly=True)
    delivered_at = fields.Datetime(string="Delivered At", readonly=True)

    # ── Parties ───────────────────────────────────────────────────────────
    supplier_id = fields.Many2one("res.partner", string="Supplier", readonly=True, ondelete="restrict")
    pickup_partner_id = fields.Many2one("res.partner", string="Pickup Location", readonly=True, ondelete="restrict")
    buyer_id = fields.Many2one("res.partner", string="Buyer", readonly=True, ondelete="restrict")
    delivery_partner_id = fields.Many2one("res.partner", string="Delivery Location", readonly=True, ondelete="restrict")

    # ── Carrier & Rate ────────────────────────────────────────────────────
    carrier_id = fields.Many2one("res.partner", string="Carrier", readonly=True, ondelete="restrict")
    carrier_name = fields.Char(string="Carrier Name", readonly=True)
    rate_amount = fields.Float(string="Rate", readonly=True)
    trailer_number = fields.Char(string="Trailer #", readonly=True)

    # ── Performance & Alerts ──────────────────────────────────────────────
    sla_breached = fields.Boolean(string="SLA Breached", readonly=True)
    cycle_time_hours = fields.Float(string="Cycle Time (hrs)", readonly=True)
    bol_pickup_attached = fields.Boolean(string="BOL Pickup", readonly=True)
    bol_delivery_attached = fields.Boolean(string="BOL Delivery", readonly=True)

    write_date = fields.Datetime(string="Last Updated", readonly=True)

    # ── SQL VIEW ──────────────────────────────────────────────────────────
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW plasticos_load_dashboard AS
            SELECT
                l.id                        AS id,
                l.id                        AS load_id,
                l.name                      AS load_ref,
                t.name                      AS transaction_ref,
                t.user_id                   AS user_id,
                l.state                     AS load_state,
                l.pickup_datetime           AS pickup_datetime,
                l.delivery_datetime         AS delivery_datetime,
                l.delivered_at              AS delivered_at,
                t.supplier_id               AS supplier_id,
                l.pickup_partner_id         AS pickup_partner_id,
                t.buyer_id                  AS buyer_id,
                l.delivery_partner_id       AS delivery_partner_id,
                l.carrier_id                AS carrier_id,
                rp_carrier.name             AS carrier_name,
                l.rate_amount               AS rate_amount,
                l.trailer_number            AS trailer_number,
                l.sla_breached              AS sla_breached,
                l.cycle_time_hours          AS cycle_time_hours,
                l.bol_pickup_attached       AS bol_pickup_attached,
                l.bol_delivery_attached     AS bol_delivery_attached,
                l.write_date                AS write_date
            FROM plasticos_load l
            LEFT JOIN plasticos_transaction t ON t.load_id = l.id
            LEFT JOIN res_partner rp_carrier ON rp_carrier.id = l.carrier_id
            WHERE l.state != 'closed'
               OR l.write_date >= date_trunc('month', NOW())
        """)

    # ── Drill-Through Actions ─────────────────────────────────────────────

    def action_view_load(self):
        """Open the full load form."""
        self.ensure_one()
        if not self.load_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": f"Load — {self.load_ref}",
            "res_model": PLASTICOS_LOAD,
            "res_id": self.load_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_transaction(self):
        """Open the linked transaction."""
        self.ensure_one()
        tx = self.env["plasticos.transaction"].search(
            [("load_id", "=", self.load_id.id)],
            limit=1,
        )
        if not tx:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "No Transaction",
                    "message": "No transaction linked to this load.",
                    "type": "warning",
                },
            }
        return {
            "type": "ir.actions.act_window",
            "name": f"Deal — {tx.name}",
            "res_model": "plasticos.transaction",
            "res_id": tx.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_documents(self):
        """Open documents for the linked transaction."""
        self.ensure_one()
        tx = self.env["plasticos.transaction"].search(
            [("load_id", "=", self.load_id.id)],
            limit=1,
        )
        if not tx:
            return False
        doc_model = "documents.document" if "documents.document" in self.env else "plasticos.document"
        return {
            "type": "ir.actions.act_window",
            "name": f"Documents — {self.load_ref}",
            "res_model": doc_model,
            "view_mode": "list,form",
            "domain": [("transaction_id", "=", tx.id)],
            "context": {"create": False},
        }

    def action_view_carrier(self):
        """Open the carrier partner form."""
        self.ensure_one()
        if not self.carrier_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": self.carrier_name or "Carrier",
            "res_model": "res.partner",
            "res_id": self.carrier_id.id,
            "view_mode": "form",
            "target": "current",
        }
