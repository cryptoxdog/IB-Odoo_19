import logging
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models, tools
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

PLASTICOS_LOAD = "plasticos.load"
LINDA_APPROVAL = "plasticos.linda.approval"
MAIL_ACTIVITY = "mail.activity"
# DEC-012 exception activity types owned by plasticos_documents (TASK-060). plasticos_documents
# depends on this module, so they are looked up by XML id; when absent the KPI is unavailable.
DOCUMENT_EXCEPTION_TYPES = (
    "plasticos_documents.activity_type_missing_documents",
    "plasticos_documents.activity_type_missing_scale_ticket",
    "plasticos_documents.activity_type_association_review",
    "plasticos_documents.activity_type_classification_review",
    "plasticos_documents.activity_type_evidence_gap",
    "plasticos_documents.activity_type_split_review",
    "plasticos_documents.activity_type_duplicate_candidate",
    "plasticos_documents.activity_type_blocked_bill",
)
EVIDENCE_GAP_TYPE = "plasticos_documents.activity_type_evidence_gap"
SCALE_TICKET_TYPE = "plasticos_documents.activity_type_missing_scale_ticket"
# The router (plasticos.exception.router.upsert) stamps the owning role into the activity note.
LOGISTICS_ROUTED_NOTE = "Routed to logistics:"

# Control Tower (TASK-032, DEC-007). Load states that still move: neither delivered nor closed.
OPEN_STATES = (
    "draft",
    "awaiting_ready",
    "ready_confirmed",
    "rate_confirmed",
    "scheduled",
    "dispatched",
    "picked_up",
    "exception",
)
# Ready for carrier booking but no confirmed carrier rate yet.
CARRIER_PENDING_STATES = ("awaiting_ready", "ready_confirmed")
# Booked but not yet released to the carrier: the release guards apply here.
PRE_RELEASE_STATES = ("rate_confirmed", "scheduled")
ATTENTION_SELECTION = [
    ("linda", "Linda Held Command"),
    ("exception", "Load Exception"),
    ("sla", "SLA Breached"),
    ("missing_bol", "Missing BOL"),
    ("carrier", "Carrier Unconfirmed"),
    ("none", "On Track"),
]
# SQL for the attention bucket of a load row ``l``, highest priority first. One definition, used by
# the view column and mirrored by the KPI domains below (test_load_dashboard asserts they agree).
# The Linda-pending predicate is inlined verbatim in both static VIEW literals below (no interpolation).


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
    # The load's own company. A global rule in plasticos_security_base filters on
    # it: this SQL model is not protected by the plasticos.load rule.
    company_id = fields.Many2one("res.company", string="Company", readonly=True, ondelete="restrict")
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

    # ── Control Tower (TASK-032) ──────────────────────────────────────────
    missing_bol = fields.Boolean(
        string="Missing BOL",
        readonly=True,
        help="Picked up or delivered without a pickup BOL, or delivered without a delivery BOL.",
    )
    carrier_unconfirmed = fields.Boolean(
        string="Carrier Unconfirmed",
        readonly=True,
        help="Ready (or awaiting readiness) with no confirmed carrier rate, or booked without a carrier.",
    )
    linda_pending = fields.Boolean(
        string="Linda Held Command",
        readonly=True,
        help="Linda holds a command on this load, its appointment or its shipment event proposal.",
    )
    attention_reason = fields.Selection(
        ATTENTION_SELECTION,
        string="Attention",
        readonly=True,
        help="The highest-priority reason this open load needs attention; On Track when none applies.",
    )
    needs_attention = fields.Boolean(string="Needs Attention", readonly=True)

    write_date = fields.Datetime(string="Last Updated", readonly=True)

    # ── SQL VIEW ──────────────────────────────────────────────────────────
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        # The parent is plasticos_load.transaction_id, one row per load. Probe for that
        # column and fall back to a transaction-less view if this module's table is not
        # ready yet; the next module update rebuilds the full view.
        # nosemgrep: odoo-raw-sql -- static information_schema probe, no interpolation
        self.env.cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'plasticos_load' AND column_name = 'transaction_id'
        """)
        has_tx_link = bool(self.env.cr.fetchone())
        # Two fully-static VIEW definitions instead of f-string interpolation: the
        # transaction-linked variant and the fresh-install fallback (column
        # plasticos_load.transaction_id may not exist yet on the first build).
        # Static literals keep this free of any SQL-injection surface and mirror the
        # convention used by the admin/sales dashboard VIEWs.
        if has_tx_link:
            self.env.cr.execute("""
                CREATE VIEW plasticos_load_dashboard AS
                SELECT
                    l.id                        AS id,
                    l.id                        AS load_id,
                    l.name                      AS load_ref,
                    l.company_id                AS company_id,
                    t.name                      AS transaction_ref,
                    t.user_id                   AS user_id,
                    t.supplier_id               AS supplier_id,
                    t.buyer_id                  AS buyer_id,
                    l.state                     AS load_state,
                    l.pickup_datetime           AS pickup_datetime,
                    l.delivery_datetime         AS delivery_datetime,
                    l.delivered_at              AS delivered_at,
                    l.pickup_partner_id         AS pickup_partner_id,
                    l.delivery_partner_id       AS delivery_partner_id,
                    l.carrier_id                AS carrier_id,
                    rp_carrier.name             AS carrier_name,
                    l.rate_amount               AS rate_amount,
                    l.trailer_number            AS trailer_number,
                    l.sla_breached              AS sla_breached,
                    l.cycle_time_hours          AS cycle_time_hours,
                    l.bol_pickup_attached       AS bol_pickup_attached,
                    l.bol_delivery_attached     AS bol_delivery_attached,
                    l.write_date                AS write_date,
                    (l.state IN ('picked_up', 'delivered')
                        AND (NOT COALESCE(l.bol_pickup_attached, FALSE)
                             OR (l.state = 'delivered' AND NOT COALESCE(l.bol_delivery_attached, FALSE)))
                    )                           AS missing_bol,
                    (l.state IN ('awaiting_ready', 'ready_confirmed')
                        OR (l.state IN ('rate_confirmed', 'scheduled') AND l.carrier_id IS NULL)
                    )                           AS carrier_unconfirmed,
                    (l.state NOT IN ('delivered', 'closed') AND (
                    EXISTS (
                    SELECT 1 FROM plasticos_linda_approval a
                    WHERE a.state = 'pending'
                    AND (
                    (a.subject_model = 'plasticos.load' AND a.subject_id = l.id)
                    OR (a.subject_model = 'plasticos.load.appointment'
                    AND a.subject_id IN (SELECT ap.id FROM plasticos_load_appointment ap WHERE ap.load_id = l.id))
                    OR (a.subject_model = 'plasticos.shipment.event.proposal'
                    AND a.subject_id IN (SELECT p.id FROM plasticos_shipment_event_proposal p WHERE p.load_id = l.id))
                    )
                    )
                    )) AS linda_pending,
                    CASE
                        WHEN l.state IN ('delivered', 'closed') THEN 'none'
                        WHEN (
                    EXISTS (
                    SELECT 1 FROM plasticos_linda_approval a
                    WHERE a.state = 'pending'
                    AND (
                    (a.subject_model = 'plasticos.load' AND a.subject_id = l.id)
                    OR (a.subject_model = 'plasticos.load.appointment'
                    AND a.subject_id IN (SELECT ap.id FROM plasticos_load_appointment ap WHERE ap.load_id = l.id))
                    OR (a.subject_model = 'plasticos.shipment.event.proposal'
                    AND a.subject_id IN (SELECT p.id FROM plasticos_shipment_event_proposal p WHERE p.load_id = l.id))
                    )
                    )
                    ) THEN 'linda'
                        WHEN l.state = 'exception' THEN 'exception'
                        WHEN COALESCE(l.sla_breached, FALSE) THEN 'sla'
                        WHEN l.state = 'picked_up' AND NOT COALESCE(l.bol_pickup_attached, FALSE) THEN 'missing_bol'
                        WHEN l.state IN ('awaiting_ready', 'ready_confirmed')
                          OR (l.state IN ('rate_confirmed', 'scheduled') AND l.carrier_id IS NULL) THEN 'carrier'
                        ELSE 'none'
                    END                         AS attention_reason,
                    (l.state NOT IN ('delivered', 'closed') AND (
                        (
                    EXISTS (
                    SELECT 1 FROM plasticos_linda_approval a
                    WHERE a.state = 'pending'
                    AND (
                    (a.subject_model = 'plasticos.load' AND a.subject_id = l.id)
                    OR (a.subject_model = 'plasticos.load.appointment'
                    AND a.subject_id IN (SELECT ap.id FROM plasticos_load_appointment ap WHERE ap.load_id = l.id))
                    OR (a.subject_model = 'plasticos.shipment.event.proposal'
                    AND a.subject_id IN (SELECT p.id FROM plasticos_shipment_event_proposal p WHERE p.load_id = l.id))
                    )
                    )
                    )
                        OR l.state = 'exception'
                        OR COALESCE(l.sla_breached, FALSE)
                        OR (l.state = 'picked_up' AND NOT COALESCE(l.bol_pickup_attached, FALSE))
                        OR l.state IN ('awaiting_ready', 'ready_confirmed')
                        OR (l.state IN ('rate_confirmed', 'scheduled') AND l.carrier_id IS NULL)
                    ))                          AS needs_attention
                FROM plasticos_load l
                LEFT JOIN plasticos_transaction t ON t.id = l.transaction_id
                LEFT JOIN res_partner rp_carrier ON rp_carrier.id = l.carrier_id
                WHERE l.state != 'closed'
                   OR l.write_date >= date_trunc('month', NOW())
            """)
        else:
            _logger.warning(
                "plasticos_load_dashboard: plasticos_load.transaction_id not present yet — "
                "building transaction-less view; it rebuilds fully on the next module update."
            )
            self.env.cr.execute("""
                CREATE VIEW plasticos_load_dashboard AS
                SELECT
                    l.id                        AS id,
                    l.id                        AS load_id,
                    l.name                      AS load_ref,
                    l.company_id                AS company_id,
                    NULL::varchar               AS transaction_ref,
                    NULL::integer               AS user_id,
                    NULL::integer               AS supplier_id,
                    NULL::integer               AS buyer_id,
                    l.state                     AS load_state,
                    l.pickup_datetime           AS pickup_datetime,
                    l.delivery_datetime         AS delivery_datetime,
                    l.delivered_at              AS delivered_at,
                    l.pickup_partner_id         AS pickup_partner_id,
                    l.delivery_partner_id       AS delivery_partner_id,
                    l.carrier_id                AS carrier_id,
                    rp_carrier.name             AS carrier_name,
                    l.rate_amount               AS rate_amount,
                    l.trailer_number            AS trailer_number,
                    l.sla_breached              AS sla_breached,
                    l.cycle_time_hours          AS cycle_time_hours,
                    l.bol_pickup_attached       AS bol_pickup_attached,
                    l.bol_delivery_attached     AS bol_delivery_attached,
                    l.write_date                AS write_date,
                    (l.state IN ('picked_up', 'delivered')
                        AND (NOT COALESCE(l.bol_pickup_attached, FALSE)
                             OR (l.state = 'delivered' AND NOT COALESCE(l.bol_delivery_attached, FALSE)))
                    )                           AS missing_bol,
                    (l.state IN ('awaiting_ready', 'ready_confirmed')
                        OR (l.state IN ('rate_confirmed', 'scheduled') AND l.carrier_id IS NULL)
                    )                           AS carrier_unconfirmed,
                    (l.state NOT IN ('delivered', 'closed') AND (
                    EXISTS (
                    SELECT 1 FROM plasticos_linda_approval a
                    WHERE a.state = 'pending'
                    AND (
                    (a.subject_model = 'plasticos.load' AND a.subject_id = l.id)
                    OR (a.subject_model = 'plasticos.load.appointment'
                    AND a.subject_id IN (SELECT ap.id FROM plasticos_load_appointment ap WHERE ap.load_id = l.id))
                    OR (a.subject_model = 'plasticos.shipment.event.proposal'
                    AND a.subject_id IN (SELECT p.id FROM plasticos_shipment_event_proposal p WHERE p.load_id = l.id))
                    )
                    )
                    )) AS linda_pending,
                    CASE
                        WHEN l.state IN ('delivered', 'closed') THEN 'none'
                        WHEN (
                    EXISTS (
                    SELECT 1 FROM plasticos_linda_approval a
                    WHERE a.state = 'pending'
                    AND (
                    (a.subject_model = 'plasticos.load' AND a.subject_id = l.id)
                    OR (a.subject_model = 'plasticos.load.appointment'
                    AND a.subject_id IN (SELECT ap.id FROM plasticos_load_appointment ap WHERE ap.load_id = l.id))
                    OR (a.subject_model = 'plasticos.shipment.event.proposal'
                    AND a.subject_id IN (SELECT p.id FROM plasticos_shipment_event_proposal p WHERE p.load_id = l.id))
                    )
                    )
                    ) THEN 'linda'
                        WHEN l.state = 'exception' THEN 'exception'
                        WHEN COALESCE(l.sla_breached, FALSE) THEN 'sla'
                        WHEN l.state = 'picked_up' AND NOT COALESCE(l.bol_pickup_attached, FALSE) THEN 'missing_bol'
                        WHEN l.state IN ('awaiting_ready', 'ready_confirmed')
                          OR (l.state IN ('rate_confirmed', 'scheduled') AND l.carrier_id IS NULL) THEN 'carrier'
                        ELSE 'none'
                    END                         AS attention_reason,
                    (l.state NOT IN ('delivered', 'closed') AND (
                        (
                    EXISTS (
                    SELECT 1 FROM plasticos_linda_approval a
                    WHERE a.state = 'pending'
                    AND (
                    (a.subject_model = 'plasticos.load' AND a.subject_id = l.id)
                    OR (a.subject_model = 'plasticos.load.appointment'
                    AND a.subject_id IN (SELECT ap.id FROM plasticos_load_appointment ap WHERE ap.load_id = l.id))
                    OR (a.subject_model = 'plasticos.shipment.event.proposal'
                    AND a.subject_id IN (SELECT p.id FROM plasticos_shipment_event_proposal p WHERE p.load_id = l.id))
                    )
                    )
                    )
                        OR l.state = 'exception'
                        OR COALESCE(l.sla_breached, FALSE)
                        OR (l.state = 'picked_up' AND NOT COALESCE(l.bol_pickup_attached, FALSE))
                        OR l.state IN ('awaiting_ready', 'ready_confirmed')
                        OR (l.state IN ('rate_confirmed', 'scheduled') AND l.carrier_id IS NULL)
                    ))                          AS needs_attention
                FROM plasticos_load l
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
        tx = self.load_id.transaction_id
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
        """Open documents attached to this dashboard row's own load."""
        self.ensure_one()
        if not self.load_id:
            return False
        doc_model = "documents.document" if "documents.document" in self.env else "plasticos.document"
        load_id = self.load_id.id
        domain = [("load_id", "=", load_id)]
        doc_fields = self.env[doc_model]._fields
        if "res_model" in doc_fields and "res_id" in doc_fields:
            domain = [
                "|",
                ("load_id", "=", load_id),
                "&",
                ("res_model", "=", "plasticos.load"),
                ("res_id", "=", load_id),
            ]
        return {
            "type": "ir.actions.act_window",
            "name": f"Documents — {self.load_ref}",
            "res_model": doc_model,
            "view_mode": "list,form",
            "domain": domain,
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

    # ── Control Tower KPIs (TASK-032, DEC-007 KPI-drill parity) ───────────
    # Each actionable KPI is declared once: (key, label, model, domain builder). The value is
    # ``search_count(domain)`` on that model and the drill opens the same model with the same
    # domain, so the two cannot drift. A KPI whose source cannot be read is ``unavailable``,
    # never 0 (a true zero and an unavailable source render differently).

    @api.model
    def _control_tower_window(self):
        """Today's local bounds and the next-48-hours window, as naive UTC datetimes."""
        tz = pytz.timezone(self.env.context.get("tz") or self.env.user.tz or "UTC")
        now = fields.Datetime.now()
        local_today = now.replace(tzinfo=pytz.UTC).astimezone(tz).date()

        def utc(day):
            return tz.localize(datetime.combine(day, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)

        return {
            "now": now,
            "today_start": utc(local_today),
            "tomorrow_start": utc(local_today + timedelta(days=1)),
            "horizon": now + timedelta(hours=48),
        }

    @api.model
    def _linda_pending_load_ids(self):
        """Open loads with a pending Linda command on the load, its appointment or its proposal.

        Mirrors the ``linda_pending`` SQL column; read as the acting user so record rules hold.
        """
        approvals = self.env[LINDA_APPROVAL].search([("state", "=", "pending")])
        load_ids, appointment_ids, proposal_ids = set(), set(), set()
        for approval in approvals:
            if approval.subject_model == PLASTICOS_LOAD:
                load_ids.add(approval.subject_id)
            elif approval.subject_model == "plasticos.load.appointment":
                appointment_ids.add(approval.subject_id)
            elif approval.subject_model == "plasticos.shipment.event.proposal":
                proposal_ids.add(approval.subject_id)
        if appointment_ids:
            appointments = self.env["plasticos.load.appointment"].browse(appointment_ids).exists()
            load_ids.update(appointments.mapped("load_id").ids)
        if proposal_ids:
            proposals = self.env["plasticos.shipment.event.proposal"].browse(proposal_ids).exists()
            load_ids.update(proposals.mapped("load_id").ids)
        return sorted(load_ids)

    @api.model
    def _release_blocked_load_ids(self):
        """Booked loads that a release owner withholds from dispatch now (load._physical_release_errors).

        A point-in-time snapshot: the guards are Python owned by several modules, so the drill
        carries the evaluated ids.
        """
        loads = self.env[PLASTICOS_LOAD].search([("state", "in", PRE_RELEASE_STATES)])
        return sorted(load.id for load in loads if load._physical_release_errors("dispatch"))

    @api.model
    def _control_tower_declarations(self):
        """The KPI table: ``[(key, label, model, domain)]``, evaluated for the acting user."""
        window = self._control_tower_window()
        open_load = [("state", "in", OPEN_STATES)]
        missing_bol = [
            ("state", "in", ("picked_up", "delivered")),
            "|",
            ("bol_pickup_attached", "=", False),
            "&",
            ("state", "=", "delivered"),
            ("bol_delivery_attached", "=", False),
        ]
        carrier_unconfirmed = [
            "|",
            ("state", "in", CARRIER_PENDING_STATES),
            "&",
            ("state", "in", PRE_RELEASE_STATES),
            ("carrier_id", "=", False),
        ]
        linda_ids = self._linda_pending_load_ids()
        needs_attention = [
            *open_load,
            "|",
            "|",
            "|",
            "|",
            "|",
            ("id", "in", linda_ids),
            ("state", "=", "exception"),
            ("sla_breached", "=", True),
            "&",
            ("state", "=", "picked_up"),
            ("bol_pickup_attached", "=", False),
            ("state", "in", CARRIER_PENDING_STATES),
            "&",
            ("state", "in", PRE_RELEASE_STATES),
            ("carrier_id", "=", False),
        ]
        exception_types = self._activity_type_ids(DOCUMENT_EXCEPTION_TYPES)
        evidence_gap = self._activity_type_ids((EVIDENCE_GAP_TYPE,))
        scale_ticket = self._activity_type_ids((SCALE_TICKET_TYPE,))
        return [
            (
                "pickups_today",
                "Pickups Today",
                PLASTICOS_LOAD,
                [
                    *open_load,
                    ("pickup_datetime", ">=", window["today_start"]),
                    ("pickup_datetime", "<", window["tomorrow_start"]),
                ],
            ),
            (
                "pickups_next_48h",
                "Pickups Next 48 Hours",
                PLASTICOS_LOAD,
                [
                    ("state", "in", tuple(s for s in OPEN_STATES if s != "picked_up")),
                    ("pickup_datetime", ">=", window["now"]),
                    ("pickup_datetime", "<=", window["horizon"]),
                ],
            ),
            (
                "deliveries_next_48h",
                "Deliveries Next 48 Hours",
                PLASTICOS_LOAD,
                [
                    ("state", "in", ("dispatched", "picked_up")),
                    ("delivery_datetime", ">=", window["now"]),
                    ("delivery_datetime", "<=", window["horizon"]),
                ],
            ),
            ("needs_attention", "Needs Attention", PLASTICOS_LOAD, needs_attention),
            ("linda_held", "Linda Held Commands", LINDA_APPROVAL, [("state", "=", "pending")]),
            (
                "linda_held_logistics",
                "Linda Commands Logistics Decides",
                LINDA_APPROVAL,
                [("state", "=", "pending"), ("routed_role", "=", "logistics_ops")],
            ),
            ("missing_bol", "Missing BOL", PLASTICOS_LOAD, missing_bol),
            ("carrier_unconfirmed", "Unconfirmed Carriers", PLASTICOS_LOAD, carrier_unconfirmed),
            (
                "release_blocked",
                "Blocked From Release",
                PLASTICOS_LOAD,
                [("id", "in", self._release_blocked_load_ids())],
            ),
            (
                "sla_breached",
                "SLA Breached",
                PLASTICOS_LOAD,
                [*open_load, ("sla_breached", "=", True)],
            ),
            (
                "logistics_exceptions",
                "Logistics Exceptions",
                MAIL_ACTIVITY,
                exception_types
                and [("activity_type_id", "in", exception_types), ("note", "ilike", LOGISTICS_ROUTED_NOTE)],
            ),
            (
                "evidence_gaps",
                "Evidence Gaps (shipping paperwork)",
                MAIL_ACTIVITY,
                evidence_gap and [("activity_type_id", "in", evidence_gap), ("note", "ilike", LOGISTICS_ROUTED_NOTE)],
            ),
            (
                "scale_ticket_exceptions",
                "Missing Scale Tickets",
                PLASTICOS_LOAD,
                scale_ticket and [("activity_ids.activity_type_id", "in", scale_ticket)],
            ),
        ]

    @api.model
    def _activity_type_ids(self, xmlids):
        """The ids of the named activity types, or None when any is not installed (KPI unavailable)."""
        ids = []
        for xmlid in xmlids:
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if not record or record._name != "mail.activity.type":
                return None
            ids.append(record.id)
        return ids

    @api.model
    def control_tower_kpis(self):
        """Every Control Tower KPI for the acting user: key, label, model, domain, value, available.

        ``value`` is ``search_count(domain)`` on ``model``; ``available`` is False (and ``value``
        None) when the source cannot be read, so an error never reads as a zero.
        """
        # One count per declared KPI (a fixed table, not a loop over records).
        kpis = [self._evaluate_kpi(*declaration) for declaration in self._control_tower_declarations()]
        return kpis

    @api.model
    def _evaluate_kpi(self, key, label, model, domain):
        """One KPI's value: ``search_count(domain)``, or unavailable (value None) when unreadable."""
        kpi = {"key": key, "label": label, "model": model, "domain": domain, "value": None, "available": False}
        if domain is None:
            return kpi
        try:
            kpi["value"] = self.env[model].search_count(domain)
            kpi["available"] = True
        except (AccessError, UserError, ValidationError) as error:
            _logger.warning("Control Tower KPI %s unavailable: %s", key, error)
        return kpi

    @api.model
    def action_drill_kpi(self, key=None):
        """Open the KPI's source model with exactly the domain its value counted (DEC-007)."""
        key = key or self.env.context.get("control_tower_kpi")
        for kpi_key, label, model, domain in self._control_tower_declarations():
            if kpi_key == key:
                if domain is None:
                    raise UserError(f"{label} is unavailable: its exception types are not installed.")
                return {
                    "type": "ir.actions.act_window",
                    "name": label,
                    "res_model": model,
                    "view_mode": "list,form",
                    "domain": domain,
                    "context": {"create": False},
                    "target": "current",
                }
        raise UserError(f"Unknown Control Tower KPI {key!r}.")


# The tiles, in display order: (key, label). Each key is a KPI of _control_tower_declarations.
CONTROL_TOWER_TILES = (
    ("needs_attention", "Needs Attention"),
    ("pickups_today", "Pickups Today"),
    ("pickups_next_48h", "Pickups Next 48h"),
    ("deliveries_next_48h", "Deliveries Next 48h"),
    ("linda_held", "Linda Held"),
    ("linda_held_logistics", "Linda: Logistics Decides"),
    ("logistics_exceptions", "Logistics Exceptions"),
    ("evidence_gaps", "Evidence Gaps"),
    ("scale_ticket_exceptions", "Missing Scale Tickets"),
    ("missing_bol", "Missing BOL"),
    ("carrier_unconfirmed", "Unconfirmed Carriers"),
    ("release_blocked", "Blocked From Release"),
    ("sla_breached", "SLA Breached"),
)


class PlasticosLogisticsControlTower(models.TransientModel):
    """Logistics Live Control Tower tiles (TASK-032). Presentation only: no business data.

    Every tile reads its value from plasticos.load.dashboard.control_tower_kpis() as the viewer
    and opens the same declaration's drill (DEC-007). An unavailable source shows Unavailable,
    never 0.
    """

    _name = "plasticos.logistics.control.tower"
    _description = "Logistics Control Tower"

    name = fields.Char(default="Logistics Control Tower", readonly=True)
    needs_attention = fields.Integer(compute="_compute_tiles")
    needs_attention_unavailable = fields.Boolean(compute="_compute_tiles")
    pickups_today = fields.Integer(compute="_compute_tiles")
    pickups_today_unavailable = fields.Boolean(compute="_compute_tiles")
    pickups_next_48h = fields.Integer(compute="_compute_tiles")
    pickups_next_48h_unavailable = fields.Boolean(compute="_compute_tiles")
    deliveries_next_48h = fields.Integer(compute="_compute_tiles")
    deliveries_next_48h_unavailable = fields.Boolean(compute="_compute_tiles")
    linda_held = fields.Integer(compute="_compute_tiles")
    linda_held_unavailable = fields.Boolean(compute="_compute_tiles")
    linda_held_logistics = fields.Integer(compute="_compute_tiles")
    linda_held_logistics_unavailable = fields.Boolean(compute="_compute_tiles")
    logistics_exceptions = fields.Integer(compute="_compute_tiles")
    logistics_exceptions_unavailable = fields.Boolean(compute="_compute_tiles")
    evidence_gaps = fields.Integer(compute="_compute_tiles")
    evidence_gaps_unavailable = fields.Boolean(compute="_compute_tiles")
    scale_ticket_exceptions = fields.Integer(compute="_compute_tiles")
    scale_ticket_exceptions_unavailable = fields.Boolean(compute="_compute_tiles")
    missing_bol = fields.Integer(compute="_compute_tiles")
    missing_bol_unavailable = fields.Boolean(compute="_compute_tiles")
    carrier_unconfirmed = fields.Integer(compute="_compute_tiles")
    carrier_unconfirmed_unavailable = fields.Boolean(compute="_compute_tiles")
    release_blocked = fields.Integer(compute="_compute_tiles")
    release_blocked_unavailable = fields.Boolean(compute="_compute_tiles")
    sla_breached = fields.Integer(compute="_compute_tiles")
    sla_breached_unavailable = fields.Boolean(compute="_compute_tiles")

    @api.depends_context("uid", "allowed_company_ids", "tz")
    def _compute_tiles(self):
        kpis = {kpi["key"]: kpi for kpi in self.env["plasticos.load.dashboard"].control_tower_kpis()}
        for rec in self:
            for key, _label in CONTROL_TOWER_TILES:
                kpi = kpis.get(key) or {"available": False, "value": None}
                rec[key] = kpi["value"] or 0
                rec[f"{key}_unavailable"] = not kpi["available"]

    @api.model
    def action_open(self):
        """Open a fresh tiles screen for the viewer."""
        tower = self.create({})
        return {
            "type": "ir.actions.act_window",
            "name": "Logistics Control Tower",
            "res_model": self._name,
            "res_id": tower.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_drill(self):
        """Open the clicked tile's KPI drill (the same model and domain its value counted)."""
        return self.env["plasticos.load.dashboard"].action_drill_kpi(self.env.context.get("control_tower_kpi"))
