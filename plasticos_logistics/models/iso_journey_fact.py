"""Recorded physical facts of one container journey (BRS-EXP-08-R007, BRS-EXP-10-R007).

A J1 ``plasticos.iso.journey`` is identity only. What later happened to that
container is recorded here, one immutable row per fact kind:

* ``gate_in``: the terminal or rail ramp accepted the container;
* ``departure``: the vessel carrying it sailed (after its gate-in);
* ``regulatory_parties``: who files the export and who takes delivery;
* ``container_tare`` and ``verified_gross_mass``: the container's tare and its
  VGM weight, each a weight and a unit, from a scale ticket attached to the
  journey or from the Documents ``verified_gross_mass`` verdict on the journey.
  Neither is ever inferred from the equipment class or a road equipment type.

Each fact comes from an original attached to the journey, in its company, and
is written only by the commands below. A recorded fact is never rewritten or
deleted. A buyer allocation, a new sale order or a resale reaches none of
these rows, so the departure, gate-in, filer and delivery partner of a
container already afloat survive its sale. Milestones stay distinct: a
supplier's "booking complete", a loaded event or a gate appointment is not a
gate-in, and a gate-in is not a sailing.
"""

from odoo import api, fields, models
from odoo.exceptions import UserError

from .iso_journey import _check_company_allowed, _lock, _normalize_text, _require_logistics_actor, _result

PLASTICOS_ISO_JOURNEY = "plasticos.iso.journey"
IR_ATTACHMENT = "ir.attachment"
RES_PARTNER = "res.partner"
_RECORD_WRITE = "plasticos_iso_journey_fact_record"
_RECORD_WRITE_TOKEN = object()
# The facts of each kind that a replay must match exactly.
_KIND_FACTS = {
    "gate_in": ("occurred_at", "facility_partner_id", "evidence_attachment_id"),
    "departure": ("occurred_at", "vessel", "voyage", "evidence_attachment_id"),
    "regulatory_parties": ("customs_filer_id", "delivery_partner_id", "evidence_attachment_id"),
    "container_tare": ("weight", "weight_uom_id", "weight_basis", "evidence_reference", "evidence_attachment_id"),
    "verified_gross_mass": ("weight", "weight_uom_id", "weight_basis", "evidence_reference", "evidence_attachment_id"),
}
WEIGHT_KINDS = ("container_tare", "verified_gross_mass")
# Documents owns verification; it depends on Logistics, so it is a soft reference here.
DOCUMENT = "plasticos.document"
VGM_OBLIGATION = "verified_gross_mass"


class PlasticosIsoJourneyFact(models.Model):
    _name = "plasticos.iso.journey.fact"
    _description = "Plasticos ISO Container Journey Fact"
    _order = "journey_id, occurred_at, id"

    journey_id = fields.Many2one(PLASTICOS_ISO_JOURNEY, required=True, readonly=True, index=True, ondelete="restrict")
    company_id = fields.Many2one("res.company", required=True, readonly=True, index=True, ondelete="restrict")
    fact_kind = fields.Selection(
        [
            ("gate_in", "Gate-In Accepted"),
            ("departure", "Vessel Departure"),
            ("regulatory_parties", "Filer/Delivery"),
            ("container_tare", "Container Tare"),
            ("verified_gross_mass", "Verified Gross Mass"),
        ],
        required=True,
        readonly=True,
    )
    occurred_at = fields.Datetime(readonly=True, help="When it happened, from the original.")
    facility_partner_id = fields.Many2one(
        RES_PARTNER, string="Gate-In Facility", readonly=True, ondelete="restrict", help="Terminal or rail ramp."
    )
    vessel = fields.Char(readonly=True)
    voyage = fields.Char(readonly=True)
    customs_filer_id = fields.Many2one(
        RES_PARTNER,
        string="Customs Filer",
        readonly=True,
        ondelete="restrict",
        help="Party that files the export. Never set or changed by a buyer allocation.",
    )
    delivery_partner_id = fields.Many2one(
        RES_PARTNER,
        string="Delivery Partner",
        readonly=True,
        ondelete="restrict",
        help="Party that takes physical delivery at destination. Never set or changed by a buyer allocation.",
    )
    weight = fields.Float(readonly=True, digits=(16, 3), help="Tare or VGM weight, as the evidence states it.")
    weight_uom_id = fields.Many2one("uom.uom", string="Weight Unit", readonly=True, ondelete="restrict")
    weight_basis = fields.Selection(
        [("scale_ticket", "Scale Ticket"), ("documents_verified_gross_mass", "Documents VGM Verdict")],
        readonly=True,
        help="The verified evidence the weight comes from.",
    )
    evidence_reference = fields.Char(
        readonly=True,
        help="Scale ticket number, or the Documents operation revision whose VGM verdict was applied.",
    )
    verified_document_id = fields.Integer(
        string="Verified Document",
        readonly=True,
        help="Id of the plasticos.document row the Documents VGM verdict returned (soft reference).",
    )
    evidence_attachment_id = fields.Many2one(
        IR_ATTACHMENT, string="Evidence", required=True, readonly=True, ondelete="restrict"
    )
    recorded_at = fields.Datetime(required=True, readonly=True)
    recorded_by = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")

    _one_fact_per_kind = models.Constraint(
        "UNIQUE(journey_id, fact_kind)",
        "This container journey already has that fact; a recorded fact is immutable.",
    )
    _kind_shape = models.Constraint(
        """CHECK(
            (fact_kind = 'gate_in' AND occurred_at IS NOT NULL AND facility_partner_id IS NOT NULL)
            OR (fact_kind = 'departure' AND occurred_at IS NOT NULL AND vessel IS NOT NULL)
            OR (fact_kind = 'regulatory_parties'
                AND (customs_filer_id IS NOT NULL OR delivery_partner_id IS NOT NULL))
            OR (fact_kind IN ('container_tare', 'verified_gross_mass')
                AND weight > 0 AND weight_uom_id IS NOT NULL AND weight_basis IS NOT NULL
                AND evidence_reference IS NOT NULL
                AND (weight_basis = 'scale_ticket' OR verified_document_id IS NOT NULL))
        )""",
        "A gate-in names its time and facility, a departure its time and vessel, regulatory parties a party, "
        "and a tare or VGM a positive weight, its unit and its verified evidence.",
    )

    @api.depends("fact_kind", "journey_id")
    def _compute_display_name(self):
        labels = dict(self._fields["fact_kind"].selection)
        for rec in self:
            rec.display_name = f"{rec.journey_id.display_name} · {labels.get(rec.fact_kind, '')}"

    # ── Integrity: append-only, written by the commands only ──────────

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get(_RECORD_WRITE) is not _RECORD_WRITE_TOKEN:
            raise UserError("Container journey facts are recorded only by the Logistics record commands.")
        return super().create(vals_list)

    def write(self, vals):
        raise UserError("A recorded container journey fact is immutable.")

    def unlink(self):
        raise UserError("A recorded container journey fact cannot be deleted.")

    # ── Commands ──────────────────────────────────────────────────────

    @api.model
    def _preconditions(self, journey_id, evidence_attachment_id, operation_key, attachment_required=True):
        """Shared checks. Returns ``(journey, attachment, blocked_result)``."""
        _require_logistics_actor(self.env)
        if not _normalize_text(operation_key):
            return None, None, _result("blocked", reason="operation_key is required")
        journey = self.env[PLASTICOS_ISO_JOURNEY].browse(int(journey_id or 0)).exists()
        if not journey:
            return None, None, _result("not_available", reason="container journey not found")
        journey.check_access("read")
        _check_company_allowed(self.env, journey.company_id)
        if journey.identity_state == "candidate":
            return journey, None, _result("blocked", journey, "attribute the container journey first")
        attachment = self.env[IR_ATTACHMENT].browse(int(evidence_attachment_id or 0)).exists()
        if not attachment and not attachment_required:
            _lock(self.env, "plasticos_iso_journey", [journey.id])
            return journey, attachment, None
        if not attachment:
            return journey, None, _result("blocked", journey, "the original document is required")
        attachment.check_access("read")
        if attachment.res_model != PLASTICOS_ISO_JOURNEY or attachment.res_id != journey.id:
            return journey, None, _result("blocked", journey, "attach the original to this container journey first")
        if attachment.company_id and attachment.company_id != journey.company_id:
            return journey, None, _result("blocked", journey, "evidence belongs to another company")
        # One writer at a time per journey: the journey row is the lock.
        _lock(self.env, "plasticos_iso_journey", [journey.id])
        return journey, attachment, None

    @staticmethod
    def _past_time(value):
        when = fields.Datetime.to_datetime(value) if value else None
        if not when:
            return None, "the event time is required"
        when = when.replace(microsecond=0)
        if when > fields.Datetime.now():
            return None, "an event that happened cannot be in the future"
        return when, None

    def _value(self, name):
        value = self[name]
        if self._fields[name].type == "many2one":
            return value.id or False
        return value or False

    @api.model
    def _record(self, journey, kind, facts):
        """Record one fact once. The same facts replay; different facts are refused."""
        existing = self.search([("journey_id", "=", journey.id), ("fact_kind", "=", kind)], limit=1)
        if existing:
            if all(existing._value(name) == (facts.get(name) or False) for name in _KIND_FACTS[kind]):
                return _result("already_applied", existing)
            return _result("blocked", existing, f"this container journey's {kind.replace('_', ' ')} is recorded")
        fact = self.with_context(**{_RECORD_WRITE: _RECORD_WRITE_TOKEN}).create(
            {
                **facts,
                "journey_id": journey.id,
                "company_id": journey.company_id.id,
                "fact_kind": kind,
                "recorded_at": fields.Datetime.now(),
                "recorded_by": self.env.user.id,
            }
        )
        return _result("applied", fact)

    @api.model
    def action_record_gate_in(
        self, journey_id, occurred_at, facility_partner_id, evidence_attachment_id, operation_key
    ):
        """The terminal or rail ramp accepted this container, from its original.

        A supplier's "booking complete" or a loaded event never stands in for it.
        """
        journey, attachment, blocked = self._preconditions(journey_id, evidence_attachment_id, operation_key)
        if blocked:
            return blocked
        when, error = self._past_time(occurred_at)
        facility = self.env[RES_PARTNER].browse(int(facility_partner_id or 0)).exists()
        if error or not facility:
            return _result("blocked", journey, error or "the gate-in facility is required")
        return self._record(
            journey,
            "gate_in",
            {"occurred_at": when, "facility_partner_id": facility.id, "evidence_attachment_id": attachment.id},
        )

    @api.model
    def action_record_departure(self, journey_id, departed_at, vessel, voyage, evidence_attachment_id, operation_key):
        """The vessel carrying this container sailed. A departure follows its gate-in."""
        journey, attachment, blocked = self._preconditions(journey_id, evidence_attachment_id, operation_key)
        if blocked:
            return blocked
        when, error = self._past_time(departed_at)
        vessel = _normalize_text(vessel)
        if error or not vessel:
            return _result("blocked", journey, error or "the vessel is required")
        gate_in = self.search([("journey_id", "=", journey.id), ("fact_kind", "=", "gate_in")], limit=1)
        if not gate_in:
            return _result("blocked", journey, "record the terminal gate-in before the departure")
        if when < gate_in.occurred_at:
            return _result("blocked", journey, "a vessel cannot sail before the container's gate-in")
        return self._record(
            journey,
            "departure",
            {
                "occurred_at": when,
                "vessel": vessel,
                "voyage": _normalize_text(voyage),
                "evidence_attachment_id": attachment.id,
            },
        )

    @api.model
    def action_record_regulatory_parties(
        self, journey_id, customs_filer_id, delivery_partner_id, evidence_attachment_id, operation_key
    ):
        """Who files the export and who takes delivery, from filing authority, never from a buyer."""
        journey, attachment, blocked = self._preconditions(journey_id, evidence_attachment_id, operation_key)
        if blocked:
            return blocked
        partners = self.env[RES_PARTNER]
        filer = partners.browse(int(customs_filer_id or 0)).exists()
        delivery = partners.browse(int(delivery_partner_id or 0)).exists()
        if not filer and not delivery:
            return _result("blocked", journey, "name the customs filer or the delivery partner")
        return self._record(
            journey,
            "regulatory_parties",
            {
                "customs_filer_id": filer.id or False,
                "delivery_partner_id": delivery.id or False,
                "evidence_attachment_id": attachment.id,
            },
        )

    # ── Container tare and verified gross mass (C10-SCOPE-2, BRS-EXP-07-R006) ──

    def _weight_unit_error(self, uom):
        kilogram = self.env.ref("uom.product_uom_kgm", raise_if_not_found=False)
        if not uom or not kilogram:
            return "the weight unit is required"
        root = (uom.parent_path or "").split("/")[0]
        if not root or root != (kilogram.parent_path or "").split("/")[0]:
            return f"{uom.display_name} is not a unit of weight"
        return None

    def _documents_vgm_evidence(self, journey, revision_key):
        """The Documents VGM verdict on this journey. Returns ``(document_id, attachment, error)``.

        The error is ``(status, reason)``. Without Documents the answer is ``not_available``.
        The verified row must exist and be about this exact journey in its company,
        so no dangling or foreign document id is ever stored.
        """
        if DOCUMENT not in self.env:
            return None, None, ("not_available", "the Documents verification owner is not installed")
        verdict = self.env[DOCUMENT].get_scoped_evidence_verdict(
            journey.company_id.id, PLASTICOS_ISO_JOURNEY, journey.id, VGM_OBLIGATION, revision_key
        )
        if verdict.get("status") != "applied" or not verdict.get("record_id"):
            reason = verdict.get("reason") or verdict.get("status")
            return None, None, ("blocked", f"the Documents verified_gross_mass verdict is not applied: {reason}")
        document = self.env[DOCUMENT].browse(int(verdict["record_id"])).exists()
        if not document:
            return None, None, ("blocked", "the verified Documents record does not exist")
        if document.res_model != PLASTICOS_ISO_JOURNEY or document.res_id != journey.id:
            return None, None, ("blocked", "the verified Documents record is not about this container journey")
        if document.subject_company_id and document.subject_company_id != journey.company_id:
            return None, None, ("blocked", "the verified Documents record belongs to another company")
        if not document.attachment_id:
            return None, None, ("blocked", "the verified Documents record has no original")
        return document.id, document.attachment_id, None

    @api.model
    def _record_weight(
        self, kind, journey_id, weight, weight_uom_id, weight_basis, evidence_attachment_id, evidence_reference, key
    ):
        _require_logistics_actor(self.env)
        documents_basis = weight_basis == "documents_verified_gross_mass"
        if weight_basis not in ("scale_ticket", "documents_verified_gross_mass"):
            return _result("blocked", reason="a tare or VGM weight needs a scale ticket or the Documents VGM verdict")
        if documents_basis and kind != "verified_gross_mass":
            # A VGM verdict proves gross mass only; it is not a tare measurement.
            return _result("blocked", reason="the Documents VGM verdict attests gross mass, not container tare")
        journey, attachment, blocked = self._preconditions(
            journey_id, evidence_attachment_id, key, attachment_required=not documents_basis
        )
        if blocked:
            return blocked
        reference = _normalize_text(evidence_reference)
        if not reference:
            return _result("blocked", journey, "name the scale ticket or the Documents operation revision")
        try:
            weight = float(weight or 0.0)
        except (TypeError, ValueError):
            weight = 0.0
        if weight <= 0:
            return _result("blocked", journey, "a weight must be positive")
        uom = self.env["uom.uom"].browse(int(weight_uom_id or 0)).exists()
        error = self._weight_unit_error(uom)
        if error:
            return _result("blocked", journey, error)
        document_id = False
        if documents_basis:
            document_id, verified, error = self._documents_vgm_evidence(journey, reference)
            if error:
                return _result(error[0], journey, error[1])
            if attachment and attachment != verified:
                return _result("blocked", journey, "the evidence is not the verified Documents original")
            attachment = verified
        return self._record(
            journey,
            kind,
            {
                "weight": weight,
                "weight_uom_id": uom.id,
                "weight_basis": weight_basis,
                "evidence_reference": reference,
                "verified_document_id": document_id,
                "evidence_attachment_id": attachment.id,
            },
        )

    @api.model
    def action_record_container_tare(
        self, journey_id, weight, weight_uom_id, weight_basis, evidence_attachment_id, evidence_reference, operation_key
    ):
        """The container's tare, from a scale ticket on the journey or the Documents VGM verdict."""
        return self._record_weight(
            "container_tare",
            journey_id,
            weight,
            weight_uom_id,
            weight_basis,
            evidence_attachment_id,
            evidence_reference,
            operation_key,
        )

    @api.model
    def action_record_verified_gross_mass(
        self, journey_id, weight, weight_uom_id, weight_basis, evidence_attachment_id, evidence_reference, operation_key
    ):
        """The container's VGM weight, from a scale ticket on the journey or the Documents VGM verdict."""
        return self._record_weight(
            "verified_gross_mass",
            journey_id,
            weight,
            weight_uom_id,
            weight_basis,
            evidence_attachment_id,
            evidence_reference,
            operation_key,
        )
