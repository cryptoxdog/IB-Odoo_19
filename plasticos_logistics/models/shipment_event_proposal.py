"""Typed shipment-event proposals (BRS-EXP-09-R007, BRS-EXP-11-R010).

A proposal is a reviewable candidate that one exact shipment event happened:
the supplier is ready, a load was loaded, the terminal accepted a container at
gate-in, or the vessel sailed. It names one exact subject (a load, or a J1
container journey) and the original that supports it, and says who asserted it.

A proposal changes nothing by itself. Creating one, from a Linda reply or from
manual evidence, never writes a load, a transaction, a picking, a stock record
or a journey fact. Only accepting it runs the owner's command, and that command
keeps all of its own prerequisites and idempotency:

========================  ===========  ========================================================
event                     subject      owner command
========================  ===========  ========================================================
``supplier_ready``        load         ``plasticos.load.action_confirm_ready``
``loaded``                load         ``plasticos.load.action_record_actual_event('pickup')``
``gate_accepted``         journey      ``plasticos.iso.journey.fact.action_record_gate_in``
``sailed``                journey      ``plasticos.iso.journey.fact.action_record_departure``
========================  ===========  ========================================================

A supplier's "booking complete" is supplier-reported: it may support a
``loaded`` proposal for the one load it names. It can never attest a terminal
gate-in or a sailing, and it never touches the sibling loads of the same order.
"""

import uuid

import psycopg2
import psycopg2.errors

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .iso_journey import _check_company_allowed, _normalize_text, _require_logistics_actor, _result
from .linda_approval import hold_for_approval, is_linda, linda_acting, prior_refusal, record_refusal

PLASTICOS_LOAD = "plasticos.load"
ISO_JOURNEY = "plasticos.iso.journey"
JOURNEY_FACT = "plasticos.iso.journey.fact"
IR_ATTACHMENT = "ir.attachment"
RES_PARTNER = "res.partner"
_DECISION_WRITE = "plasticos_shipment_event_proposal_decision"
_DECISION_WRITE_TOKEN = object()
# Set only by action_propose_shipment_event: Linda creates proposals through it alone (C12-SCOPE-3 (3)).
_PROPOSE_CREATE = "plasticos_shipment_event_proposal_propose"
_PROPOSE_CREATE_TOKEN = object()

# Linda dispositions that still identify a current reply on the right request.
_USABLE_DISPOSITIONS = frozenset({"identity_unverified", "unresolved"})
# Who a Linda request was addressed to decides who its reply speaks for. Linda never
# writes to a terminal, so a reply is never terminal-issued.
_SUPPLIER_PURPOSES = frozenset({"po_issue", "po_cancel"})
# Typed load requests go to the load's road carrier (plasticos.load.carrier_id, the trucker).
# Booking requests (Export) are not listed: a booking reply is about a booking, never a load,
# so it cannot be cited here, and Logistics does not depend on Export's ocean carrier.
_ROAD_CARRIER_PURPOSES = frozenset({"load_ack_notice", "load_ack_escalation", "document_chase"})
# A Linda reply comes from a supplier or a road carrier. Neither is an authority for a
# terminal gate-in or a vessel departure, so no cited Linda reply can support these events.
_LINDA_EXCLUDED_EVENTS = frozenset({"gate_accepted", "sailed"})
_DECISION_FIELDS = ("state", "command_status", "decision_note", "decided_at", "decided_by")
_LOAD_EVENTS = frozenset({"supplier_ready", "loaded"})
_JOURNEY_EVENTS = frozenset({"gate_accepted", "sailed"})
# Who may attest each event. A supplier cannot attest a terminal gate-in or a sailing.
_ALLOWED_ASSERTERS = {
    "supplier_ready": frozenset({"supplier_reported", "carrier_issued", "operator_observed"}),
    "loaded": frozenset({"supplier_reported", "carrier_issued", "operator_observed"}),
    "gate_accepted": frozenset({"terminal_issued", "carrier_issued"}),
    "sailed": frozenset({"carrier_issued"}),
}
_PROPOSAL_FIELDS = frozenset(
    {
        "company_id",
        "event_kind",
        "load_id",
        "journey_id",
        "occurred_at",
        "facility_partner_id",
        "vessel",
        "voyage",
        "evidence_attachment_id",
        "linda_response_id",
        "asserted_by",
        "source_reference",
        "operation_key",
    }
)


def _proposal_subject_key(subject, event_kind):
    """The Linda ledger subject of a proposal: its load, or its journey and event kind."""
    if subject._name == "plasticos.load":
        return f"load:{subject.id}"
    return f"journey:{subject.id}:{event_kind}"


class _ProbeRollback(Exception):
    """Rolls back the validation probe of a held Linda proposal."""


class PlasticosShipmentEventProposal(models.Model):
    _name = "plasticos.shipment.event.proposal"
    _description = "Plasticos Shipment Event Proposal"
    _order = "id desc"

    company_id = fields.Many2one(
        "res.company", required=True, readonly=True, index=True, ondelete="restrict", help="Company of the subject."
    )
    event_kind = fields.Selection(
        [
            ("supplier_ready", "Supplier Ready"),
            ("loaded", "Loaded"),
            ("gate_accepted", "Gate Accepted"),
            ("sailed", "Sailed"),
        ],
        required=True,
        index=True,
    )
    load_id = fields.Many2one(PLASTICOS_LOAD, string="Load", index="btree_not_null", ondelete="restrict")
    journey_id = fields.Many2one(ISO_JOURNEY, string="Container Journey", index="btree_not_null", ondelete="restrict")
    occurred_at = fields.Datetime(string="Occurred At", help="When the source says the event happened.")
    facility_partner_id = fields.Many2one(
        RES_PARTNER, string="Gate-In Facility", ondelete="restrict", help="Terminal or rail ramp, for gate-in."
    )
    vessel = fields.Char(help="Vessel, for a sailing.")
    voyage = fields.Char(help="Voyage, for a sailing.")
    evidence_attachment_id = fields.Many2one(
        IR_ATTACHMENT,
        string="Evidence",
        required=True,
        ondelete="restrict",
        help="Original document attached to the subject that supports this event.",
    )
    linda_response_id = fields.Many2one(
        "plasticos.logistics.response",
        string="Linda Reply",
        ondelete="restrict",
        help="The Linda reply this proposal was taken from, if any. The reply itself stays unchanged.",
    )
    asserted_by = fields.Selection(
        [
            ("supplier_reported", "Supplier Reported"),
            ("carrier_issued", "Carrier Issued"),
            ("terminal_issued", "Terminal Issued"),
            ("operator_observed", "Operator Observed"),
        ],
        required=True,
        help="Who states the event in the source. A supplier report never attests gate-in or a sailing.",
    )
    source_reference = fields.Char(help="Reference in the source, e.g. a scale ticket or an email subject.")
    operation_key = fields.Char(
        required=True,
        index=True,
        default=lambda self: f"form:{uuid.uuid4()}",
        help="Idempotency key for proposing. The form generates one; a caller may pass its own.",
    )
    state = fields.Selection(
        [("candidate", "Candidate"), ("accepted", "Accepted"), ("rejected", "Rejected")],
        required=True,
        default="candidate",
        readonly=True,
        index=True,
    )
    command_status = fields.Selection(
        [("applied", "Applied"), ("already_applied", "Already Applied")],
        readonly=True,
        help="What the owner command returned when this proposal was accepted.",
    )
    decision_note = fields.Text(readonly=True)
    decided_at = fields.Datetime(readonly=True)
    decided_by = fields.Many2one("res.users", readonly=True, ondelete="restrict")

    _subject_matches_kind = models.Constraint(
        """CHECK(
            (event_kind IN ('supplier_ready', 'loaded') AND load_id IS NOT NULL AND journey_id IS NULL)
            OR (event_kind IN ('gate_accepted', 'sailed') AND journey_id IS NOT NULL AND load_id IS NULL)
        )""",
        "A shipment event proposal names exactly one subject matching its event.",
    )
    _operation_key_unique = models.Constraint(
        "UNIQUE(company_id, operation_key)",
        "A shipment event proposal with this operation key already exists.",
    )
    _decided_has_actor = models.Constraint(
        "CHECK(state = 'candidate' OR (decided_by IS NOT NULL AND decided_at IS NOT NULL))",
        "A decided proposal records who decided it and when.",
    )

    @api.depends("event_kind", "load_id", "journey_id", "state")
    def _compute_display_name(self):
        kinds = dict(self._fields["event_kind"].selection)
        for rec in self:
            subject = rec.load_id.display_name or rec.journey_id.display_name or ""
            rec.display_name = f"{kinds.get(rec.event_kind, '')} · {subject} ({rec.state})"

    # ── Integrity ─────────────────────────────────────────────────────

    def _decision(self):
        return self.with_context(**{_DECISION_WRITE: _DECISION_WRITE_TOKEN})

    def _is_decision_write(self):
        return self.env.context.get(_DECISION_WRITE) is _DECISION_WRITE_TOKEN

    @api.model_create_multi
    def create(self, vals_list):
        _require_logistics_actor(self.env)
        if is_linda(self.env) and self.env.context.get(_PROPOSE_CREATE) is not _PROPOSE_CREATE_TOKEN:
            raise AccessError("Linda proposes shipment events only through action_propose_shipment_event.")
        for vals in vals_list:
            if vals.get("state", "candidate") != "candidate" or any(vals.get(name) for name in _DECISION_FIELDS[1:]):
                raise UserError("A shipment event proposal starts as a candidate; accept it to run the owner command.")
            subject = self._subject_from_vals(vals)
            if subject and not vals.get("company_id"):
                vals["company_id"] = subject.company_id.id
            if "operation_key" in vals:
                vals["operation_key"] = _normalize_text(vals["operation_key"])
        records = super().create(vals_list)
        for rec in records:
            error = rec._proposal_error()
            if error:
                raise ValidationError(error)
        return records

    def write(self, vals):
        if not self._is_decision_write():
            raise UserError("A shipment event proposal is evidence. Accept or reject it; never edit it.")
        if _PROPOSAL_FIELDS & set(vals):
            raise UserError("A decision never rewrites the proposed facts.")
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda rec: rec.state != "candidate"):
            raise UserError("An accepted or rejected shipment event proposal cannot be deleted.")
        return super().unlink()

    def _subject_from_vals(self, vals):
        if vals.get("load_id"):
            return self.env[PLASTICOS_LOAD].browse(vals["load_id"]).exists()
        if vals.get("journey_id"):
            return self.env[ISO_JOURNEY].browse(vals["journey_id"]).exists()
        return None

    def _subject(self):
        self.ensure_one()
        return self.load_id or self.journey_id

    def _proposal_error(self):
        """Why this proposal cannot stand, or None. Nothing outside it is read for write."""
        self.ensure_one()
        subject = self._subject()
        if not subject:
            return "A shipment event proposal needs its load or container journey."
        if not subject.company_id or subject.company_id != self.company_id:
            return "A shipment event proposal is in its subject's company."
        _check_company_allowed(self.env, self.company_id)
        if self.asserted_by not in _ALLOWED_ASSERTERS[self.event_kind]:
            return (
                f"A {self.asserted_by.replace('_', ' ')} source cannot attest {self.event_kind.replace('_', ' ')}. "
                "A supplier's booking-complete note is not a terminal gate-in or a sailing."
            )
        attachment = self.evidence_attachment_id
        try:
            attachment.check_access("read")
        except AccessError:
            return "The evidence is not visible to you."
        if attachment.res_model != subject._name or attachment.res_id != subject.id:
            return "Attach the original to the proposal's load or container journey first."
        if attachment.company_id and attachment.company_id != self.company_id:
            return "Proposal evidence belongs to another company."
        error = self._linda_response_error()
        if error:
            return error
        if self.event_kind != "supplier_ready" and not self.occurred_at:
            return "A loaded, gate-in or sailing proposal needs the time it happened."
        if self.event_kind == "gate_accepted" and not self.facility_partner_id:
            return "A gate-in proposal names the terminal or rail ramp."
        facility = self.facility_partner_id
        if facility:
            try:
                facility.check_access("read")
            except AccessError:
                return "The gate-in facility is not visible to you."
            if facility.company_id and facility.company_id != self.company_id:
                return "The gate-in facility belongs to another company."
        if self.event_kind == "sailed" and not _normalize_text(self.vessel):
            return "A sailing proposal names the vessel."
        return None

    def _linda_response_error(self):
        """A cited Linda reply must answer the current request about this exact shipment.

        It must be bound to its current request, keep a usable disposition, and be
        about this load (its typed source, its sale order or a purchase order of its
        transaction) or, for a journey, about a load accepted as a source of it.
        """
        self.ensure_one()
        response = self.linda_response_id
        if not response:
            return None
        if response.company_id != self.company_id:
            return "The Linda reply belongs to another company."
        if response.binding != "current" or response.disposition not in _USABLE_DISPOSITIONS:
            return "The Linda reply is stale, unbound or unattributed; it cannot support a shipment event."
        loads = self._subject_loads()
        if not any(self._response_is_about(response, load) for load in loads):
            return "The Linda reply is not about this shipment."
        if self.event_kind in _LINDA_EXCLUDED_EVENTS:
            return (
                "A Linda reply comes from a supplier or a road carrier; it cannot attest a terminal gate-in "
                "or a vessel departure."
            )
        asserter = self._linda_asserter(response, loads)
        if not asserter:
            return "The Linda reply's recipient is not a party that can attest this shipment event."
        if self.asserted_by != asserter:
            return (
                f"The cited Linda reply answers a request sent to a {asserter.split('_')[0]}, so it is "
                f"{asserter.replace('_', ' ')}, not {self.asserted_by.replace('_', ' ')}."
            )
        return None

    def _subject_loads(self):
        self.ensure_one()
        if self.load_id:
            return self.load_id
        return self.journey_id.source_ids.filtered(
            lambda source: source.state == "accepted" and source.source_kind == "load"
        ).load_id

    @staticmethod
    def _response_is_about(response, load):
        if response.source_kind == "load" and response.source_res_id == load.id:
            return True
        if response.sale_order_id and response.sale_order_id == load.sale_order_id:
            return True
        return bool(response.purchase_order_id and response.purchase_order_id in load.transaction_id.purchase_order_ids)

    @staticmethod
    def _linda_asserter(response, loads):
        """Who the cited reply speaks for, from the answered request's recipient. None if no one who may attest.

        The supplier role wins: a recipient that is the load's pickup party, the transaction's
        supplier or the vendor of a purchase order on the transaction is supplier-reported, even
        when it also hauls the load. Otherwise the load's road carrier is carrier-issued.
        """
        request = response.request_id
        if not request:
            return None
        recipient = request.partner_id.commercial_partner_id
        if not recipient:
            return None
        transactions = loads.transaction_id
        suppliers = (
            loads.pickup_partner_id | transactions.supplier_id | transactions.purchase_order_ids.partner_id
        ).commercial_partner_id
        if request.purpose in _SUPPLIER_PURPOSES or recipient in suppliers:
            return "supplier_reported"
        if request.purpose in _ROAD_CARRIER_PURPOSES and recipient in loads.carrier_id.commercial_partner_id:
            return "carrier_issued"
        return None

    # ── Commands ──────────────────────────────────────────────────────

    @api.model
    def action_propose_shipment_event(self, values, operation_key):
        """Record one typed candidate. Writes nothing but the proposal.

        Linda's refusal is recorded in the approval ledger against the subject, so her
        next proposal there is held (C12-SCOPE-3 (2)).

        Returns ``{status, record_id?, reason?}`` with status ``applied``,
        ``already_applied``, ``blocked``, ``not_available`` or ``rejected``.
        Replay by ``operation_key`` returns the same proposal (``already_applied``)
        when its facts match, ``rejected`` when that proposal was rejected, and
        ``blocked`` when the facts differ.
        """
        _require_logistics_actor(self.env)
        result = self._propose_shipment_event(values, operation_key)
        if linda_acting(self.env):
            subject = self._subject_from_vals(values or {})
            if subject:
                record_refusal(
                    self.env,
                    "propose_shipment_event",
                    _proposal_subject_key(subject, values.get("event_kind")),
                    subject.company_id,
                    result,
                    {"values": values, "operation_key": _normalize_text(operation_key)},
                    operation_key,
                    subject,
                )
        return result

    @api.model
    def _propose_shipment_event(self, values, operation_key):
        key = _normalize_text(operation_key)
        if not key:
            return _result("blocked", reason="operation_key is required")
        if values.get("event_kind") not in dict(self._fields["event_kind"].selection):
            return _result("not_available", reason=f"unknown shipment event {values.get('event_kind')!r}")
        subject = self._subject_from_vals(values)
        if not subject:
            return _result("not_available", reason="load or container journey not found")
        subject.check_access("read")
        company = subject.company_id
        existing = self.search([("company_id", "=", company.id), ("operation_key", "=", key)], limit=1)
        if existing and existing.state == "rejected":
            return {"status": "rejected", "record_id": existing.id, "reason": "this operation key was rejected"}
        if existing:
            same = all(
                existing._stored_value(name) == existing._proposed_value(name, values.get(name))
                for name in _PROPOSAL_FIELDS - {"company_id", "operation_key"}
            )
            return (
                _result("already_applied", existing)
                if same
                else _result("blocked", existing, "this operation key already proposed different facts")
            )
        unknown = set(values) - _PROPOSAL_FIELDS
        if unknown:
            return _result("blocked", reason=f"unexpected fields {sorted(unknown)}")
        if linda_acting(self.env):
            held = self._linda_propose_gate(values, key, company, subject)
            if held:
                return held
        try:
            with self.env.cr.savepoint():
                proposal = self._proposer().create({**values, "company_id": company.id, "operation_key": key})
        except psycopg2.errors.UniqueViolation:
            # A concurrent propose with the same key won; answer from its row.
            self.env.invalidate_all()
            winner = self.search([("company_id", "=", company.id), ("operation_key", "=", key)], limit=1)
            if winner:
                return self._propose_shipment_event(values, key)
            return _result("blocked", reason="constraint violated: a unique key is taken by a row you cannot read")
        except psycopg2.IntegrityError as error:
            return _result("blocked", reason=f"constraint violated: {error.diag.constraint_name or 'database'}")
        except (UserError, ValidationError) as error:
            return _result("blocked", reason=str(error.args[0] if error.args else error))
        return _result("applied", proposal)

    def _proposer(self):
        return self.with_context(**{_PROPOSE_CREATE: _PROPOSE_CREATE_TOKEN})

    @api.model
    def _linda_propose_gate(self, values, key, company, subject):
        """Hold Linda's proposal citing an unverified Linda reply, or retrying after a refusal.

        The proposal is first built and checked inside a rolled-back savepoint, so
        an invalid one is refused as usual and only a standing one is held.
        """
        response = self.env["plasticos.logistics.response"].browse(int(values.get("linda_response_id") or 0))
        subject_key = _proposal_subject_key(subject, values.get("event_kind"))
        edge = None
        if response.exists() and response.disposition in ("identity_unverified", "unresolved"):
            edge = "unverified_linda_reply"
        if prior_refusal(self.env, "propose_shipment_event", subject_key, company):
            edge = "refusal_retry"
        if not edge:
            return None
        try:
            with self.env.cr.savepoint():
                self._proposer().create({**values, "company_id": company.id, "operation_key": key})
                raise _ProbeRollback
        except _ProbeRollback:
            self.env.invalidate_all()
        except psycopg2.errors.UniqueViolation:
            # A concurrent propose with the same key won while the probe ran; answer from its row.
            self.env.invalidate_all()
            return self._propose_shipment_event(values, key)
        except (UserError, ValidationError) as error:
            self.env.invalidate_all()
            return _result("blocked", reason=str(error.args[0] if error.args else error))
        reason = (
            f"the cited Linda reply is {response.disposition.replace('_', ' ')}"
            if edge == "unverified_linda_reply"
            else "Linda's previous proposal on this subject was refused"
        )
        arguments = {"values": values, "operation_key": key}
        return hold_for_approval(
            self.env, "propose_shipment_event", edge, reason, arguments, key, company, subject, subject_key=subject_key
        )

    def _stored_value(self, name):
        value = self[name]
        if self._fields[name].type == "many2one":
            return value.id or False
        if self._fields[name].type == "datetime":
            return value.replace(microsecond=0) if value else False
        return value or False

    def _proposed_value(self, name, value):
        if self._fields[name].type == "datetime":
            value = fields.Datetime.to_datetime(value) if value else False
            return value.replace(microsecond=0) if value else False
        if self._fields[name].type == "char":
            return _normalize_text(value)
        return value or False

    def _run_owner_command(self):
        """Run the subject owner's command. Raises when the owner refuses."""
        self.ensure_one()
        kind = self.event_kind
        if kind == "supplier_ready":
            load = self.load_id
            if load.ready_confirmed_at:
                return "already_applied"
            load.action_confirm_ready()
            return "applied"
        if kind == "loaded":
            result = self.load_id.action_record_actual_event("pickup", self.occurred_at, self.evidence_attachment_id)
            return result["status"]
        journeys = self.env[JOURNEY_FACT]
        key = f"proposal:{self.id}"
        if kind == "gate_accepted":
            result = journeys.action_record_gate_in(
                self.journey_id.id, self.occurred_at, self.facility_partner_id.id, self.evidence_attachment_id.id, key
            )
        else:
            result = journeys.action_record_departure(
                self.journey_id.id, self.occurred_at, self.vessel, self.voyage, self.evidence_attachment_id.id, key
            )
        if result["status"] not in ("applied", "already_applied"):
            raise UserError(f"The container journey refused the {kind.replace('_', ' ')}: {result.get('reason')}")
        return result["status"]

    def action_accept(self, note=None):
        """Accept a candidate: the owner command runs with its own guards, then the proposal is decided.

        Linda's acceptance is always held for an Operations Manager (C12-SCOPE-2) and
        returns ``{status: pending, approval_id, reason}``; a person's applies at once.
        """
        _require_logistics_actor(self.env)
        if linda_acting(self.env):
            return self._linda_accept_gate(note)
        for rec in self:
            # Serialize a concurrent accept of the same proposal on its row, then re-read it.
            # justification: the ORM has no SELECT FOR UPDATE.
            self.env.cr.execute("SELECT id FROM plasticos_shipment_event_proposal WHERE id = %s FOR UPDATE", [rec.id])
            rec.invalidate_recordset()
            if rec.state == "accepted":
                continue
            if rec.state != "candidate":
                raise UserError("A rejected shipment event proposal cannot be accepted. Propose it again.")
            error = rec._proposal_error()
            if error:
                raise UserError(error)
            status = rec._run_owner_command()
            rec._decision().write(
                {
                    "state": "accepted",
                    "command_status": status,
                    "decision_note": _normalize_text(note),
                    "decided_at": fields.Datetime.now(),
                    "decided_by": self.env.user.id,
                }
            )
        return True

    def _linda_accept_gate(self, note):
        held = []
        for rec in self:
            rec.check_access("read")
            subject_key = f"proposal:{rec.id}"
            arguments = {"proposal_id": rec.id, "note": _normalize_text(note)}
            if rec.state == "accepted":
                held.append(_result("already_applied", rec))
                continue
            if rec.state != "candidate":
                refused = _result("blocked", rec, "a rejected shipment event proposal cannot be accepted")
                held.append(
                    record_refusal(
                        self.env,
                        "accept_shipment_event",
                        subject_key,
                        rec.company_id,
                        refused,
                        arguments,
                        f"accept:{rec.id}",
                        rec,
                    )
                )
                continue
            retry = prior_refusal(self.env, "accept_shipment_event", subject_key, rec.company_id)
            edge = "refusal_retry" if retry else "acceptance"
            reason = f"Linda accepts the {rec.event_kind.replace('_', ' ')} proposal"
            held.append(
                hold_for_approval(
                    self.env,
                    "accept_shipment_event",
                    edge,
                    reason,
                    arguments,
                    f"accept:{rec.id}",
                    rec.company_id,
                    rec,
                    subject_key=subject_key,
                )
            )
        return held[0] if len(held) == 1 else held

    def action_reject(self, note=None):
        """Reject a candidate. Nothing else changes."""
        _require_logistics_actor(self.env)
        for rec in self.filtered(lambda proposal: proposal.state == "candidate"):
            rec._decision().write(
                {
                    "state": "rejected",
                    "decision_note": _normalize_text(note),
                    "decided_at": fields.Datetime.now(),
                    "decided_by": self.env.user.id,
                }
            )
        return True
