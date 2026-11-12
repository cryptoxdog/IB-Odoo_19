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

Corrections (S11, OP11-E01, operator decision 2026-11-12) are append-only too.
A correction never edits a row: it records revision ``n + 1`` of the same kind,
names the revision it supersedes, and carries a required reason, its author and
its time. The current fact of a kind is its highest revision, read only through
``plasticos.iso.journey.current_facts()`` / ``current_fact()``. A correction
passes the same evidence, company, Documents and party guards as the first
record, and a correction that changes nothing is refused.
"""

import psycopg2
import psycopg2.errors

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare, float_round

from .iso_journey import _check_company_allowed, _lock, _normalize_text, _require_logistics_actor, _result
from .linda_approval import hold_for_approval, linda_acting, prior_refusal

PLASTICOS_ISO_JOURNEY = "plasticos.iso.journey"
IR_ATTACHMENT = "ir.attachment"
RES_PARTNER = "res.partner"
_RECORD_WRITE = "plasticos_iso_journey_fact_record"
_RECORD_WRITE_TOKEN = object()
# Returned by _create_fact when a concurrent writer won a unique index first.
_UNIQUE_RACE = object()
# The facts of each kind that a replay must match exactly.
_KIND_FACTS = {
    "gate_in": ("occurred_at", "facility_partner_id", "evidence_attachment_id"),
    "departure": ("occurred_at", "vessel", "voyage", "evidence_attachment_id"),
    "regulatory_parties": ("customs_filer_id", "delivery_partner_id", "evidence_attachment_id"),
    "container_tare": ("weight", "weight_uom_id", "weight_basis", "evidence_reference", "evidence_attachment_id"),
    "verified_gross_mass": ("weight", "weight_uom_id", "weight_basis", "evidence_reference", "evidence_attachment_id"),
}
WEIGHT_KINDS = ("container_tare", "verified_gross_mass")
# Refusals Linda's edge-case gate holds instead of returning (S11, OP11-E02).
R_ORIGINAL_REQUIRED = "the original document is required"
R_ATTACH_TO_JOURNEY = "attach the original to this container journey first"
R_EVIDENCE_COMPANY = "evidence belongs to another company"
R_EVIDENCE_NOT_VISIBLE = "the original document is not visible to you"
R_NOT_VERIFIED_ORIGINAL = "the evidence is not the verified Documents original"
R_GATE_IN_FIRST = "record the terminal gate-in before the departure"
R_SAIL_BEFORE_GATE_IN = "a vessel cannot sail before the container's gate-in"
R_GATE_IN_AFTER_SAILING = "a container's gate-in cannot follow its vessel's departure"
R_WEIGHT_UNIT_REQUIRED = "the weight unit is required"
_EVIDENCE_REASONS = (
    R_ORIGINAL_REQUIRED,
    R_ATTACH_TO_JOURNEY,
    R_EVIDENCE_COMPANY,
    R_EVIDENCE_NOT_VISIBLE,
    R_NOT_VERIFIED_ORIGINAL,
)
_SEQUENCE_REASONS = (R_GATE_IN_FIRST, R_SAIL_BEFORE_GATE_IN, R_GATE_IN_AFTER_SAILING)
NOT_A_WEIGHT_UNIT = " is not a unit of weight"
_DOCUMENTS_EVIDENCE_PREFIXES = ("the Documents ", "the verified Documents ", "no installed owner declares")


def _edge_case_of(reason):
    """The Linda edge-case class of a refusal, or None for a plain refusal."""
    reason = reason or ""
    if reason in _EVIDENCE_REASONS or reason.startswith(_DOCUMENTS_EVIDENCE_PREFIXES):
        return "evidence_unverified"
    if reason in _SEQUENCE_REASONS:
        return "out_of_sequence"
    if reason == R_WEIGHT_UNIT_REQUIRED or reason.endswith(NOT_A_WEIGHT_UNIT):
        return "unit_mismatch"
    return None


# Documents owns verification; it depends on Logistics, so it is a soft reference here.
DOCUMENT = "plasticos.document"
WEIGHT_DIGITS = 3
VGM_OBLIGATION = "verified_gross_mass"


class PlasticosIsoJourneyFact(models.Model):
    _name = "plasticos.iso.journey.fact"
    _description = "Plasticos ISO Container Journey Fact"
    _order = "journey_id, fact_kind, revision, id"

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
    weight = fields.Float(
        readonly=True, digits=(16, WEIGHT_DIGITS), help="Tare or VGM weight, as the evidence states it."
    )
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
    revision = fields.Integer(
        required=True,
        readonly=True,
        default=1,
        help="1 for the first record of this kind; each correction adds the next revision.",
    )
    supersedes_id = fields.Many2one(
        "plasticos.iso.journey.fact",
        string="Supersedes",
        readonly=True,
        index=True,
        ondelete="restrict",
        help="The revision this correction replaces. That row is kept unchanged.",
    )
    correction_reason = fields.Text(readonly=True, help="Why the fact was corrected. Required on every correction.")
    corrected_by = fields.Many2one("res.users", readonly=True, ondelete="restrict")
    corrected_at = fields.Datetime(readonly=True)
    operation_key = fields.Char(readonly=True, index=True, help="Idempotency key of the correction that wrote it.")

    _one_fact_per_revision = models.Constraint(
        "UNIQUE(journey_id, fact_kind, revision)",
        "This container journey already has that revision of the fact; a recorded fact is immutable.",
    )
    _one_correction_per_key = models.Constraint(
        "UNIQUE(journey_id, operation_key)",
        "This correction was already recorded on this container journey.",
    )
    _revision_shape = models.Constraint(
        """CHECK(
            (revision = 1 AND supersedes_id IS NULL AND correction_reason IS NULL)
            OR (revision > 1 AND supersedes_id IS NOT NULL AND correction_reason IS NOT NULL
                AND corrected_by IS NOT NULL AND corrected_at IS NOT NULL AND operation_key IS NOT NULL)
        )""",
        "A first record supersedes nothing; a correction names the revision it supersedes, its reason, "
        "author, time and operation key.",
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
            return journey, None, _result("blocked", journey, R_ORIGINAL_REQUIRED)
        try:
            attachment.check_access("read")
        except AccessError:
            if not linda_acting(self.env):
                raise
            # Linda's unreadable original is unverified evidence: held, and the refusal names nothing (Codex P2).
            return journey, None, _result("blocked", journey, R_EVIDENCE_NOT_VISIBLE)
        if attachment.res_model != PLASTICOS_ISO_JOURNEY or attachment.res_id != journey.id:
            return journey, None, _result("blocked", journey, R_ATTACH_TO_JOURNEY)
        if attachment.company_id and attachment.company_id != journey.company_id:
            return journey, None, _result("blocked", journey, R_EVIDENCE_COMPANY)
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

    def _same_fact(self, name, value):
        """Replay comparison at stored precision."""
        if name == "weight":
            return float_compare(self.weight, value or 0.0, precision_digits=WEIGHT_DIGITS) == 0
        return self._value(name) == (value or False)

    @api.model
    def _partner_error(self, partner, journey, label):
        """The actor must be able to read the party, and it must be shared or in the journey's company."""
        try:
            partner.check_access("read")
        except AccessError:
            return f"the {label} is not visible to you"
        if partner.company_id and partner.company_id != journey.company_id:
            return f"the {label} belongs to another company"
        return None

    # ── Current revision (the one read path is plasticos.iso.journey.current_facts) ──

    @api.model
    def _current(self, journey, kind):
        """The highest revision of one kind on one journey, or an empty recordset."""
        return journey.current_fact(kind)

    @api.model
    def _existing_result(self, journey, kind, facts):
        existing = self._current(journey, kind)
        if not existing:
            return None
        if all(existing._same_fact(name, facts.get(name)) for name in _KIND_FACTS[kind]):
            return _result("already_applied", existing)
        return _result("blocked", existing, f"this container journey's {kind.replace('_', ' ')} is recorded")

    @api.model
    def _create_fact(self, journey, kind, facts, extra=None):
        """Insert one row inside a savepoint. Returns ``(fact, error_result)``.

        ``error_result`` is ``None`` on success, ``_UNIQUE_RACE`` when a concurrent
        writer won a unique index first, or a blocked result for any other
        constraint, never a raw IntegrityError.
        """
        now = fields.Datetime.now()
        try:
            with self.env.cr.savepoint():
                fact = self.with_context(**{_RECORD_WRITE: _RECORD_WRITE_TOKEN}).create(
                    {
                        **facts,
                        **(extra or {}),
                        "journey_id": journey.id,
                        "company_id": journey.company_id.id,
                        "fact_kind": kind,
                        "recorded_at": now,
                        "recorded_by": self.env.user.id,
                    }
                )
        except psycopg2.errors.UniqueViolation:
            self.env.invalidate_all()
            return None, _UNIQUE_RACE
        except psycopg2.IntegrityError as error:
            return None, _result("blocked", journey, f"constraint violated: {error.diag.constraint_name or 'database'}")
        return fact, None

    @api.model
    def _record(self, journey, kind, facts):
        """Record one fact once. The same facts replay; different facts are refused.

        A concurrent duplicate that wins the unique index first is answered from the
        row it wrote, never with a raw IntegrityError.
        """
        existing = self._existing_result(journey, kind, facts)
        if existing:
            return existing
        fact, error = self._create_fact(journey, kind, facts)
        if error is _UNIQUE_RACE:
            # A concurrent record of the same fact won the unique index; answer from its row.
            return self._existing_result(journey, kind, facts) or _result(
                "blocked", journey, "constraint violated: a concurrent record of this fact could not be read back"
            )
        return error or _result("applied", fact)

    # ── Per-kind validation, shared by the first record and every correction ──

    @api.model
    def _validated(self, kind, journey_id, values, operation_key):
        """Run every guard of ``kind``. Returns ``(journey, facts, blocked_result)``."""
        if kind in WEIGHT_KINDS:
            return self._validated_weight(kind, journey_id, values, operation_key)
        journey, attachment, blocked = self._preconditions(
            journey_id, values.get("evidence_attachment_id"), operation_key
        )
        if blocked:
            return journey, None, blocked
        if kind == "gate_in":
            facts, error = self._gate_in_facts(journey, values)
        elif kind == "departure":
            facts, error = self._departure_facts(journey, values)
        else:
            facts, error = self._regulatory_facts(journey, values)
        if error:
            return journey, None, _result("blocked", journey, error)
        return journey, {**facts, "evidence_attachment_id": attachment.id}, None

    @api.model
    def _gate_in_facts(self, journey, values):
        when, error = self._past_time(values.get("occurred_at"))
        facility = self.env[RES_PARTNER].browse(int(values.get("facility_partner_id") or 0)).exists()
        if error or not facility:
            return None, error or "the gate-in facility is required"
        error = self._partner_error(facility, journey, "gate-in facility")
        if error:
            return None, error
        departure = self._current(journey, "departure")
        if departure and when > departure.occurred_at:
            # Only a correction can meet a recorded departure; the order still holds.
            return None, R_GATE_IN_AFTER_SAILING
        return {"occurred_at": when, "facility_partner_id": facility.id}, None

    @api.model
    def _departure_facts(self, journey, values):
        when, error = self._past_time(values.get("departed_at"))
        vessel = _normalize_text(values.get("vessel"))
        if error or not vessel:
            return None, error or "the vessel is required"
        gate_in = self._current(journey, "gate_in")
        if not gate_in:
            return None, R_GATE_IN_FIRST
        if when < gate_in.occurred_at:
            return None, R_SAIL_BEFORE_GATE_IN
        return dict(occurred_at=when, vessel=vessel, voyage=_normalize_text(values.get("voyage"))), None

    @api.model
    def _regulatory_facts(self, journey, values):
        partners = self.env[RES_PARTNER]
        filer = partners.browse(int(values.get("customs_filer_id") or 0)).exists()
        delivery = partners.browse(int(values.get("delivery_partner_id") or 0)).exists()
        if not filer and not delivery:
            return None, "name the customs filer or the delivery partner"
        for partner, label in ((filer, "customs filer"), (delivery, "delivery partner")):
            error = partner and self._partner_error(partner, journey, label)
            if error:
                return None, error
        return {"customs_filer_id": filer.id or False, "delivery_partner_id": delivery.id or False}, None

    @api.model
    def _record_kind(self, kind, journey_id, values, operation_key):
        journey, facts, blocked = self._validated(kind, journey_id, values, operation_key)
        if linda_acting(self.env) and journey:
            held = self._linda_record_gate(kind, journey, facts, blocked, values, operation_key)
            if held:
                return held
        if blocked:
            return blocked
        return self._record(journey, kind, facts)

    @api.model
    def _linda_record_gate(self, kind, journey, facts, blocked, values, operation_key):
        """Linda's edge case of a first record, held for approval; ``None`` when straight-through."""
        command = f"record_{kind}"
        key = _normalize_text(operation_key)
        arguments = {**values, "journey_id": journey.id, "operation_key": key}
        edge, reason = None, None
        if blocked:
            edge = _edge_case_of(blocked.get("reason"))
            reason = blocked.get("reason")
        else:
            existing = self._existing_result(journey, kind, facts)
            if existing and existing["status"] == "blocked":
                edge, reason = "value_conflict", existing["reason"]
            elif existing:
                return None
        if not edge and key and prior_refusal(self.env, command, key, journey.company_id):
            edge, reason = "refusal_retry", "this operation key was refused or rejected before"
        if not edge:
            return None
        return hold_for_approval(self.env, command, edge, reason, arguments, key, journey.company_id, journey)

    # ── First-record commands ──────────────────────────────────────────

    @api.model
    def action_record_gate_in(
        self, journey_id, occurred_at, facility_partner_id, evidence_attachment_id, operation_key
    ):
        """The terminal or rail ramp accepted this container, from its original.

        A supplier's "booking complete" or a loaded event never stands in for it.
        """
        values = {
            "occurred_at": occurred_at,
            "facility_partner_id": facility_partner_id,
            "evidence_attachment_id": evidence_attachment_id,
        }
        return self._record_kind("gate_in", journey_id, values, operation_key)

    @api.model
    def action_record_departure(self, journey_id, departed_at, vessel, voyage, evidence_attachment_id, operation_key):
        """The vessel carrying this container sailed. A departure follows its gate-in."""
        values = {
            "departed_at": departed_at,
            "vessel": vessel,
            "voyage": voyage,
            "evidence_attachment_id": evidence_attachment_id,
        }
        return self._record_kind("departure", journey_id, values, operation_key)

    @api.model
    def action_record_regulatory_parties(
        self, journey_id, customs_filer_id, delivery_partner_id, evidence_attachment_id, operation_key
    ):
        """Who files the export and who takes delivery, from filing authority, never from a buyer."""
        values = {
            "customs_filer_id": customs_filer_id,
            "delivery_partner_id": delivery_partner_id,
            "evidence_attachment_id": evidence_attachment_id,
        }
        return self._record_kind("regulatory_parties", journey_id, values, operation_key)

    # ── Container tare and verified gross mass (C10-SCOPE-2, BRS-EXP-07-R006) ──

    def _weight_unit_error(self, uom):
        kilogram = self.env.ref("uom.product_uom_kgm", raise_if_not_found=False)
        if not uom or not kilogram:
            return R_WEIGHT_UNIT_REQUIRED
        root = (uom.parent_path or "").split("/")[0]
        if not root or root != (kilogram.parent_path or "").split("/")[0]:
            return f"{uom.display_name}{NOT_A_WEIGHT_UNIT}"
        return None

    def _documents_vgm_evidence(self, journey, revision_key):
        """The Documents VGM verdict on this journey. Returns ``(document_id, attachment, error)``.

        The error is ``(status, reason)``. Without Documents the answer is ``not_available``.
        The verified row must exist and be about this exact journey in its company,
        so no dangling or foreign document id is ever stored.
        """
        if DOCUMENT not in self.env:
            return None, None, ("not_available", "the Documents verification owner is not installed")
        documents = self.env[DOCUMENT]
        if VGM_OBLIGATION not in documents._scoped_obligation_kinds():
            # Documents is installed but no owner (Export) declares the VGM obligation.
            return None, None, ("not_available", "no installed owner declares the verified_gross_mass obligation")
        try:
            verdict = documents.get_scoped_evidence_verdict(
                journey.company_id.id, PLASTICOS_ISO_JOURNEY, journey.id, VGM_OBLIGATION, revision_key
            )
        except AccessError:
            return None, None, ("blocked", "the Documents verdict is not visible to you")
        if verdict.get("status") != "applied" or not verdict.get("record_id"):
            reason = verdict.get("reason") or verdict.get("status")
            return None, None, ("blocked", f"the Documents verified_gross_mass verdict is not applied: {reason}")
        document = documents.browse(int(verdict["record_id"])).exists()
        if not document:
            return None, None, ("blocked", "the verified Documents record does not exist")
        try:
            document.check_access("read")
        except AccessError:
            return None, None, ("blocked", "the verified Documents record is not visible to you")
        if document.res_model != PLASTICOS_ISO_JOURNEY or document.res_id != journey.id:
            return None, None, ("blocked", "the verified Documents record is not about this container journey")
        if document.subject_company_id != journey.company_id:
            return None, None, ("blocked", "the verified Documents record is not established in this company")
        if not document.attachment_id:
            return None, None, ("blocked", "the verified Documents record has no original")
        return document.id, document.attachment_id, None

    @api.model
    def _validated_weight(self, kind, journey_id, values, key):
        _require_logistics_actor(self.env)
        weight_basis = values.get("weight_basis")
        documents_basis = weight_basis == "documents_verified_gross_mass"
        if weight_basis not in ("scale_ticket", "documents_verified_gross_mass"):
            return (
                None,
                None,
                _result("blocked", reason="a tare or VGM weight needs a scale ticket or the Documents VGM verdict"),
            )
        if documents_basis and kind != "verified_gross_mass":
            # A VGM verdict proves gross mass only; it is not a tare measurement.
            return (
                None,
                None,
                _result("blocked", reason="the Documents VGM verdict attests gross mass, not container tare"),
            )
        journey, attachment, blocked = self._preconditions(
            journey_id, values.get("evidence_attachment_id"), key, attachment_required=not documents_basis
        )
        if blocked:
            return journey, None, blocked
        reference = _normalize_text(values.get("evidence_reference"))
        if not reference:
            return (
                journey,
                None,
                _result("blocked", journey, "name the scale ticket or the Documents operation revision"),
            )
        try:
            weight = float(values.get("weight") or 0.0)
        except (TypeError, ValueError):
            weight = 0.0
        weight = float_round(weight, precision_digits=WEIGHT_DIGITS)
        if weight <= 0:
            return journey, None, _result("blocked", journey, "a weight must be positive")
        uom = self.env["uom.uom"].browse(int(values.get("weight_uom_id") or 0)).exists()
        error = self._weight_unit_error(uom)
        if error:
            return journey, None, _result("blocked", journey, error)
        document_id = False
        if documents_basis:
            document_id, verified, error = self._documents_vgm_evidence(journey, reference)
            if error:
                return journey, None, _result(error[0], journey, error[1])
            if attachment and attachment != verified:
                return journey, None, _result("blocked", journey, R_NOT_VERIFIED_ORIGINAL)
            attachment = verified
        facts = {
            "weight": weight,
            "weight_uom_id": uom.id,
            "weight_basis": weight_basis,
            "evidence_reference": reference,
            "verified_document_id": document_id,
            "evidence_attachment_id": attachment.id,
        }
        return journey, facts, None

    @api.model
    def action_record_container_tare(
        self, journey_id, weight, weight_uom_id, weight_basis, evidence_attachment_id, evidence_reference, operation_key
    ):
        """The container's tare, from a scale ticket on the journey or the Documents VGM verdict."""
        values = {
            "weight": weight,
            "weight_uom_id": weight_uom_id,
            "weight_basis": weight_basis,
            "evidence_attachment_id": evidence_attachment_id,
            "evidence_reference": evidence_reference,
        }
        return self._record_kind("container_tare", journey_id, values, operation_key)

    @api.model
    def action_record_verified_gross_mass(
        self, journey_id, weight, weight_uom_id, weight_basis, evidence_attachment_id, evidence_reference, operation_key
    ):
        """The container's VGM weight, from a scale ticket on the journey or the Documents VGM verdict."""
        values = {
            "weight": weight,
            "weight_uom_id": weight_uom_id,
            "weight_basis": weight_basis,
            "evidence_attachment_id": evidence_attachment_id,
            "evidence_reference": evidence_reference,
        }
        return self._record_kind("verified_gross_mass", journey_id, values, operation_key)

    # ── Corrections (S11, OP11-E01) ────────────────────────────────────

    def _as_values(self):
        """This revision's facts in the argument names of its record command."""
        self.ensure_one()
        values = {name: self._value(name) for name in _KIND_FACTS[self.fact_kind]}
        if self.fact_kind == "departure":
            values["departed_at"] = values.pop("occurred_at")
        return values

    @api.model
    def action_correct_fact(self, fact_id, values, correction_reason, operation_key):
        """Record the next revision of one fact. The superseded row is never touched.

        ``values`` uses the argument names of the kind's record command; a name it
        omits keeps the current revision's value. The correction passes every guard
        of the first record (evidence on the journey in its company, the Documents
        VGM verdict, visible same-company parties, gate-in before departure). An
        empty reason, an unchanged value or a stale revision is refused, and the
        same operation key replays the correction it recorded.
        """
        _require_logistics_actor(self.env)
        key = _normalize_text(operation_key)
        if not key:
            return _result("blocked", reason="operation_key is required")
        reason = _normalize_text(correction_reason)
        if not reason:
            return _result("blocked", reason="a correction needs its reason")
        if not isinstance(values, dict):
            return _result("blocked", reason="the corrected values must be a mapping")
        fact = self.browse(int(fact_id or 0)).exists()
        if not fact:
            return _result("not_available", reason="container journey fact not found")
        fact.check_access("read")
        kind = fact.fact_kind
        allowed = set(fact._as_values())
        unknown = sorted(set(values) - allowed)
        if unknown:
            return _result("blocked", fact, f"a {kind.replace('_', ' ')} has no {', '.join(unknown)}")
        merged = {**fact._as_values(), **values}
        journey, facts, blocked = self._validated(kind, fact.journey_id.id, merged, key)
        if linda_acting(self.env) and journey:
            # Every Linda correction waits for an Operations Manager (C12-SCOPE-2).
            replay = None if blocked else self._correction_replay(fact, journey, facts, reason, key)
            if replay:
                return replay
            edge = _edge_case_of(blocked.get("reason")) if blocked else "correction"
            if edge and prior_refusal(self.env, "correct_fact", key, journey.company_id):
                edge = "refusal_retry"
            if edge:
                arguments = {
                    "fact_id": fact.id,
                    "values": values,
                    "correction_reason": reason,
                    "operation_key": key,
                }
                cause = blocked.get("reason") if blocked else reason
                return hold_for_approval(
                    self.env, "correct_fact", edge, cause, arguments, key, journey.company_id, fact
                )
        if blocked:
            return blocked
        return self._correct(fact, journey, facts, reason, key)

    @api.model
    def _correction_replay(self, fact, journey, facts, reason, key):
        """The answer for an operation key already used on this journey, or ``None``."""
        done = self.search([("journey_id", "=", journey.id), ("operation_key", "=", key)], limit=1)
        if not done:
            return None
        same = (
            done.supersedes_id == fact
            and done.correction_reason == reason
            and all(done._same_fact(name, facts.get(name)) for name in _KIND_FACTS[done.fact_kind])
        )
        if same:
            return _result("already_applied", done)
        return _result("blocked", done, "this operation key already recorded a different correction")

    @api.model
    def _correct(self, fact, journey, facts, reason, key):
        replay = self._correction_replay(fact, journey, facts, reason, key)
        if replay:
            return replay
        current = self._current(journey, fact.fact_kind)
        if current != fact:
            return _result("blocked", current, f"correct the current revision ({current.revision}) of this fact")
        if all(fact._same_fact(name, facts.get(name)) for name in _KIND_FACTS[fact.fact_kind]):
            return _result("blocked", fact, "the correction changes nothing")
        now = fields.Datetime.now()
        extra = {
            "revision": fact.revision + 1,
            "supersedes_id": fact.id,
            "correction_reason": reason,
            "corrected_by": self.env.user.id,
            "corrected_at": now,
            "operation_key": key,
        }
        corrected, error = self._create_fact(journey, fact.fact_kind, facts, extra)
        if error is _UNIQUE_RACE:
            return self._correction_replay(fact, journey, facts, reason, key) or _result(
                "blocked", journey, "a concurrent correction of this fact was recorded first"
            )
        return error or _result("applied", corrected)
