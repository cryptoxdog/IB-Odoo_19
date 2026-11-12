"""Physical ISO container journeys (J1) and their typed sources (J2).

J1 is one sourced physical container cycle. The same ISO number may recur in
another cycle, so the ISO number is not unique; the company and its source-cycle
key are. J2 is one exact provenance association from a real load, stock move line
or non-stock original evidence to one J1.

Neither model is a stock, weight, financial, booking or milestone ledger. No J1
is inferred from a load's trailer number, a booking, a package or a filename, and
no state is set automatically from a booking. Export binds slots to a J1 by
``journey_id`` through its own downstream module; nothing here depends on Export.
See ADR-130 and TECHNICAL_CONTRACT_v2.7 (J1, J2).
"""

import re

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

PLASTICOS_ISO_JOURNEY = "plasticos.iso.journey"
PLASTICOS_ISO_JOURNEY_SOURCE = "plasticos.iso.journey.source"
PLASTICOS_LOAD = "plasticos.load"
IR_ATTACHMENT = "ir.attachment"
RES_COMPANY = "res.company"
RES_PARTNER = "res.partner"

# ISO 6346 shape: owner code + category letter, then six digits and a check digit.
_ISO_NUMBER = re.compile(r"^[A-Z]{4}[0-9]{7}$")
_GUARDED_WRITE = "plasticos_iso_journey_guarded_write"
_GUARDED_WRITE_TOKEN = object()
# Identity facts become immutable once the journey is attributed.
_JOURNEY_IDENTITY_FIELDS = frozenset(
    {
        "company_id",
        "source_cycle_key",
        "equipment_class",
        "iso_number",
        "seal_number",
        "identity_evidence_attachment_id",
        "identity_state",
        "identity_attested_at",
        "identity_attested_by",
    }
)
_SOURCE_FIELDS = frozenset(
    {
        "journey_id",
        "company_id",
        "source_kind",
        "load_id",
        "stock_move_line_id",
        "source_party_id",
        "evidence_attachment_id",
        "source_reference",
        "acceptance_basis",
        "state",
    }
)
_SOURCE_SUBJECT_FIELD = {
    "load": "load_id",
    "stock_move_line": "stock_move_line_id",
    "nonstock_evidence": "evidence_attachment_id",
}


def _result(status, record=None, reason=None):
    result = {"status": status}
    if record:
        result["record_id"] = record.id
    if reason:
        result["reason"] = reason
    return result


def normalize_iso_number(value):
    """Uppercase, without spaces or dashes. Empty stays empty."""
    if not value:
        return False
    return re.sub(r"[\s\-]", "", str(value)).upper() or False


def _normalize_text(value):
    value = (value or "").strip()
    return value or False


def _require_logistics_actor(env):
    """J1/J2 commands belong to the Logistics business role."""
    if env.uid == SUPERUSER_ID or env.su:
        return
    if not env.user.has_group("plasticos_security_base.group_logistics"):
        raise AccessError("Only Logistics users may register container journeys or their sources.")


def _check_company_allowed(env, company):
    if env.su or not company:
        return
    if company not in env.user.company_ids:
        raise AccessError(f"You cannot record container journeys for company {company.display_name}.")


_LOCK_QUERIES = {
    "plasticos_iso_journey": "SELECT id FROM plasticos_iso_journey WHERE id IN %s ORDER BY id FOR UPDATE",
    "plasticos_load": "SELECT id FROM plasticos_load WHERE id IN %s ORDER BY id FOR UPDATE",
    "stock_move_line": "SELECT id FROM stock_move_line WHERE id IN %s ORDER BY id FOR UPDATE",
}


def _lock(env, table, ids):
    row_ids = tuple(sorted({row_id for row_id in ids if row_id}))
    if not row_ids:
        return
    query = _LOCK_QUERIES.get(table)
    if not query:
        raise ValidationError("Cannot lock an unexpected table for a container journey.")
    # justification: ordered row locks (C02 lock order); the ORM has no SELECT FOR UPDATE.
    env.cr.execute(query, [row_ids])


class PlasticosIsoJourney(models.Model):
    _name = "plasticos.iso.journey"
    _description = "Plasticos ISO Container Journey"
    _order = "id desc"

    company_id = fields.Many2one(
        RES_COMPANY, required=True, index=True, ondelete="restrict", help="Company whose source attests this cycle."
    )
    source_cycle_key = fields.Char(
        index=True,
        help="The source's identity for this one container cycle. Required once attributed; unique per company.",
    )
    equipment_class = fields.Char(required=True, help="Container class as the real source states it, e.g. 40HC.")
    iso_number = fields.Char(index=True, help="ISO 6346 container number. Not unique: a container recurs.")
    seal_number = fields.Char(help="Seal number from the same source.")
    identity_state = fields.Selection(
        [("candidate", "Candidate"), ("attributed", "Attributed"), ("verified", "Verified")],
        required=True,
        default="candidate",
        index=True,
    )
    identity_evidence_attachment_id = fields.Many2one(
        IR_ATTACHMENT,
        string="Identity Evidence",
        ondelete="restrict",
        help="Original document that attests this journey. Required for Verified.",
    )
    identity_attested_at = fields.Datetime(readonly=True)
    identity_attested_by = fields.Many2one("res.users", readonly=True, ondelete="restrict")
    source_ids = fields.One2many(PLASTICOS_ISO_JOURNEY_SOURCE, "journey_id", string="Sources")

    _company_cycle_unique = models.Constraint(
        "UNIQUE(company_id, source_cycle_key)",
        "This company already has a container journey for that source cycle.",
    )
    _attributed_needs_cycle = models.Constraint(
        "CHECK(identity_state = 'candidate' OR source_cycle_key IS NOT NULL)",
        "An attributed or verified container journey needs its source-cycle key.",
    )
    _verified_needs_evidence = models.Constraint(
        "CHECK(identity_state != 'verified' OR identity_evidence_attachment_id IS NOT NULL)",
        "A verified container journey needs its identity evidence.",
    )

    @api.depends("iso_number", "source_cycle_key", "equipment_class")
    def _compute_display_name(self):
        for rec in self:
            identity = rec.iso_number or "No ISO number"
            cycle = rec.source_cycle_key or "unattributed"
            rec.display_name = f"{identity} · {cycle} ({rec.equipment_class or '?'})"

    def _guarded(self):
        return self.env.context.get(_GUARDED_WRITE) is _GUARDED_WRITE_TOKEN

    @staticmethod
    def _normalize_vals(vals):
        if "iso_number" in vals:
            vals["iso_number"] = normalize_iso_number(vals["iso_number"])
        for name in ("source_cycle_key", "seal_number"):
            if name in vals:
                vals[name] = _normalize_text(vals[name])
        if "equipment_class" in vals:
            vals["equipment_class"] = (
                _normalize_text(vals["equipment_class"]) and vals["equipment_class"].strip().upper()
            )
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._normalize_vals(dict(vals)) for vals in vals_list]
        if not self._guarded():
            for vals in vals_list:
                if vals.get("identity_state", "candidate") != "candidate" or vals.get("identity_attested_at"):
                    raise UserError("A container journey starts as a candidate; attribute it with Confirm Identity.")
                if vals.get("identity_attested_by"):
                    raise UserError("The attesting user is recorded by the server.")
        for vals in vals_list:
            _check_company_allowed(self.env, self.env[RES_COMPANY].browse(vals.get("company_id")))
        return super().create(vals_list)

    def write(self, vals):
        vals = self._normalize_vals(dict(vals))
        if not self._guarded():
            if {"identity_state", "identity_attested_at", "identity_attested_by"} & set(vals):
                raise UserError("Container journey identity changes only through Confirm Identity.")
            if _JOURNEY_IDENTITY_FIELDS & set(vals):
                accepted = self.filtered(lambda journey: journey.identity_state != "candidate")
                if accepted:
                    raise UserError(
                        f"Container journey {accepted[0].display_name} is attributed. Its identity is immutable."
                    )
        if "company_id" in vals:
            _check_company_allowed(self.env, self.env[RES_COMPANY].browse(vals["company_id"]))
            if self.source_ids:
                raise ValidationError("A container journey with sources cannot move to another company.")
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.identity_state != "candidate" or rec.source_ids:
                raise UserError(
                    f"Container journey {rec.display_name} is attributed or has sources and cannot be deleted."
                )
        return super().unlink()

    @api.constrains("iso_number")
    def _check_iso_number(self):
        for rec in self:
            if rec.iso_number and not _ISO_NUMBER.match(rec.iso_number):
                raise ValidationError(
                    f"{rec.iso_number} is not an ISO 6346 container number (four letters, seven digits). "
                    "A trailer, booking or package number is not a container identity."
                )

    @api.constrains("company_id", "identity_evidence_attachment_id")
    def _check_evidence_company(self):
        for rec in self:
            attachment = rec.identity_evidence_attachment_id
            if attachment and attachment.company_id and attachment.company_id != rec.company_id:
                raise ValidationError("Container journey evidence must belong to the journey's company.")

    def _attest_values(self, attachment):
        return {
            "identity_state": "verified" if attachment else "attributed",
            "identity_attested_at": fields.Datetime.now(),
            "identity_attested_by": self.env.user.id,
        }

    def action_confirm_identity(self):
        """Attribute a candidate from its source-cycle key; verify it when evidence is attached."""
        _require_logistics_actor(self.env)
        for rec in self:
            if rec.identity_state != "candidate":
                continue
            if not rec.source_cycle_key:
                raise UserError("Enter the source-cycle key before confirming the container journey.")
            attachment = rec.identity_evidence_attachment_id
            if attachment:
                attachment.check_access("read")
            rec.with_context(**{_GUARDED_WRITE: _GUARDED_WRITE_TOKEN}).write(rec._attest_values(attachment))
        return True

    @api.model
    def action_register_iso_journey(
        self,
        company_id,
        source_cycle_key,
        equipment_class,
        identity_attachment_id,
        iso_number,
        seal_number,
        operation_key,
    ):
        """Frozen Logistics command: register one sourced container cycle.

        Replay is by natural identity, company plus source-cycle key: the same
        facts return the existing journey as ``already_applied``. Different facts
        for an existing cycle are refused, never rewritten in place.
        """
        _require_logistics_actor(self.env)
        if not _normalize_text(operation_key):
            return _result("blocked", reason="operation_key is required")
        company = self.env[RES_COMPANY].browse(company_id).exists()
        cycle = _normalize_text(source_cycle_key)
        equipment = _normalize_text(equipment_class)
        if not company or not cycle or not equipment:
            return _result("blocked", reason="company, source-cycle key and equipment class are required")
        _check_company_allowed(self.env, company)
        attachment = self.env[IR_ATTACHMENT]
        if identity_attachment_id:
            attachment = self.env[IR_ATTACHMENT].browse(identity_attachment_id).exists()
            if not attachment:
                return _result("not_available", reason="identity evidence not found")
            attachment.check_access("read")
            if attachment.company_id and attachment.company_id != company:
                return _result("blocked", reason="identity evidence belongs to another company")
        facts = self._normalize_vals(
            {
                "company_id": company.id,
                "source_cycle_key": cycle,
                "equipment_class": equipment,
                "iso_number": iso_number,
                "seal_number": seal_number,
                "identity_evidence_attachment_id": attachment.id or False,
            }
        )
        # advisory lock: serialize two registrations of the same cycle before reading.
        self.env.cr.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            [f"plasticos_logistics.iso_journey:{company.id}:{cycle}"],
        )
        existing = self.search([("company_id", "=", company.id), ("source_cycle_key", "=", cycle)], limit=1)
        if existing:
            same = all(
                (existing[name].id if name.endswith("_id") else existing[name]) == (value or False)
                for name, value in facts.items()
            )
            if same:
                return _result("already_applied", existing)
            return _result(
                "blocked",
                existing,
                "this source cycle is already registered with different facts; record a successor cycle",
            )
        if facts["iso_number"] and not _ISO_NUMBER.match(facts["iso_number"]):
            return _result("blocked", reason=f"{facts['iso_number']} is not an ISO 6346 container number")
        journey = self.with_context(**{_GUARDED_WRITE: _GUARDED_WRITE_TOKEN}).create(
            {**facts, **self._attest_values(attachment)}
        )
        return _result("applied", journey)


class PlasticosIsoJourneySource(models.Model):
    _name = "plasticos.iso.journey.source"
    _description = "Plasticos ISO Container Journey Source"
    _order = "id desc"

    journey_id = fields.Many2one(PLASTICOS_ISO_JOURNEY, required=True, index=True, ondelete="restrict")
    company_id = fields.Many2one(RES_COMPANY, required=True, index=True, ondelete="restrict")
    source_kind = fields.Selection(
        [("load", "Load"), ("stock_move_line", "Stock Move Line"), ("nonstock_evidence", "Non-Stock Evidence")],
        required=True,
    )
    load_id = fields.Many2one(PLASTICOS_LOAD, index=True, ondelete="restrict")
    stock_move_line_id = fields.Many2one("stock.move.line", index=True, ondelete="restrict")
    source_party_id = fields.Many2one(
        RES_PARTNER, required=True, ondelete="restrict", help="The party whose source attests this association."
    )
    evidence_attachment_id = fields.Many2one(IR_ATTACHMENT, string="Evidence", ondelete="restrict")
    source_reference = fields.Char()
    acceptance_basis = fields.Text(help="Why this association is accepted. Required to accept.")
    state = fields.Selection(
        [("candidate", "Candidate"), ("accepted", "Accepted"), ("rejected", "Rejected")],
        required=True,
        default="candidate",
        index=True,
    )

    # Exactly one physical subject, matching the kind. Non-stock evidence (FAS or
    # third-party delivery with no company-dispatched movement) is its attachment.
    _subject_matches_kind = models.Constraint(
        """CHECK(
            (source_kind = 'load' AND load_id IS NOT NULL AND stock_move_line_id IS NULL)
            OR (source_kind = 'stock_move_line' AND stock_move_line_id IS NOT NULL AND load_id IS NULL)
            OR (source_kind = 'nonstock_evidence' AND load_id IS NULL AND stock_move_line_id IS NULL
                AND evidence_attachment_id IS NOT NULL)
        )""",
        "A container journey source names exactly one physical subject matching its kind.",
    )
    _accepted_needs_basis = models.Constraint(
        "CHECK(state != 'accepted' OR acceptance_basis IS NOT NULL)",
        "An accepted container journey source needs its acceptance basis.",
    )
    # One row per journey and exact typed subject: no NULL-subject replay gap.
    _unique_load_source = models.UniqueIndex(
        "(journey_id, load_id) WHERE source_kind = 'load'",
        "This load is already a source of that container journey.",
    )
    _unique_move_line_source = models.UniqueIndex(
        "(journey_id, stock_move_line_id) WHERE source_kind = 'stock_move_line'",
        "This stock move line is already a source of that container journey.",
    )
    _unique_evidence_source = models.UniqueIndex(
        "(journey_id, evidence_attachment_id, source_party_id) WHERE source_kind = 'nonstock_evidence'",
        "This evidence from this party is already a source of that container journey.",
    )

    def _guarded(self):
        return self.env.context.get(_GUARDED_WRITE) is _GUARDED_WRITE_TOKEN

    @api.model_create_multi
    def create(self, vals_list):
        if not self._guarded():
            for vals in vals_list:
                if vals.get("state", "candidate") != "candidate":
                    raise UserError("A container journey source starts as a candidate; accept it with Accept.")
        records = super().create(vals_list)
        records._check_source_identity()
        return records

    def write(self, vals):
        if not self._guarded():
            if "state" in vals:
                raise UserError("A container journey source changes state only through Accept or Reject.")
            decided = self.filtered(lambda source: source.state != "candidate")
            if decided and _SOURCE_FIELDS & set(vals):
                raise UserError("An accepted or rejected container journey source is immutable.")
        result = super().write(vals)
        if _SOURCE_FIELDS & set(vals):
            self._check_source_identity()
        return result

    def unlink(self):
        if self.filtered(lambda source: source.state == "accepted"):
            raise UserError("An accepted container journey source cannot be deleted.")
        return super().unlink()

    def _subject_company(self):
        self.ensure_one()
        if self.source_kind == "load":
            return self.load_id.company_id
        if self.source_kind == "stock_move_line":
            return self.stock_move_line_id.company_id
        return self.evidence_attachment_id.company_id

    def _subject_parties(self):
        """Commercial parties the subject itself names. Empty when the subject names none."""
        self.ensure_one()
        partners = self.env[RES_PARTNER]
        if self.source_kind == "load":
            load = self.load_id
            partners = load.pickup_partner_id | load.delivery_partner_id | load.carrier_id
        elif self.source_kind == "stock_move_line":
            line = self.stock_move_line_id
            partners = line.picking_id.partner_id | line.move_id.partner_id
        return partners.commercial_partner_id

    def _identity_error(self):
        """Why this association cannot stand, or None. Company is never defaulted."""
        self.ensure_one()
        journey_company = self.journey_id.company_id
        if self.company_id != journey_company:
            return "A container journey source must be in its journey's company."
        if self.source_kind != "nonstock_evidence":
            subject_company = self._subject_company()
            if not subject_company:
                return "The source subject has no proven company."
            if subject_company != journey_company:
                return "The source subject belongs to another company."
        attachment = self.evidence_attachment_id
        if attachment and attachment.company_id and attachment.company_id != journey_company:
            return "Source evidence belongs to another company."
        if self.source_kind != "nonstock_evidence":
            parties = self._subject_parties()
            if not parties:
                return "The source subject names no party, so the source party cannot be proven."
            if self.source_party_id.commercial_partner_id not in parties:
                return "The source party is not a party of that subject."
        return None

    def _check_source_identity(self):
        for rec in self:
            error = rec._identity_error()
            if error:
                raise ValidationError(error)

    def _accept(self, basis):
        basis = _normalize_text(basis)
        if not basis:
            raise UserError("An acceptance basis is required to accept a container journey source.")
        self.with_context(**{_GUARDED_WRITE: _GUARDED_WRITE_TOKEN}).write(
            {"state": "accepted", "acceptance_basis": basis}
        )

    def action_accept(self):
        _require_logistics_actor(self.env)
        for rec in self.filtered(lambda source: source.state == "candidate"):
            rec._accept(rec.acceptance_basis)
        return True

    def action_reject(self):
        _require_logistics_actor(self.env)
        self.filtered(lambda source: source.state == "candidate").with_context(
            **{_GUARDED_WRITE: _GUARDED_WRITE_TOKEN}
        ).write({"state": "rejected"})
        return True

    @api.model
    def action_bind_journey_source(
        self,
        journey_id,
        source_kind,
        source_id,
        source_party_id,
        evidence_attachment_id,
        operation_key,
        acceptance_basis,
    ):
        """Frozen Logistics command: accept one exact source for one container journey.

        Replay of the same journey and typed subject returns ``already_applied``
        when the accepted facts match. A rejected or contradictory existing row is
        refused. Nothing is written to the load, stock or documents.
        """
        _require_logistics_actor(self.env)
        if not _normalize_text(operation_key):
            return _result("blocked", reason="operation_key is required")
        if source_kind not in _SOURCE_SUBJECT_FIELD:
            return _result("not_available", reason=f"unknown source kind {source_kind!r}")
        if not _normalize_text(acceptance_basis):
            return _result("blocked", reason="an acceptance basis is required")
        journey = self.env[PLASTICOS_ISO_JOURNEY].browse(journey_id).exists()
        party = self.env[RES_PARTNER].browse(source_party_id).exists()
        attachment = (
            self.env[IR_ATTACHMENT].browse(evidence_attachment_id).exists() if evidence_attachment_id else False
        )
        if not journey or not party or (evidence_attachment_id and not attachment):
            return _result("not_available", reason="journey, party or evidence not found")
        if journey.identity_state == "candidate":
            return _result("blocked", journey, "attribute the container journey before binding sources")
        _check_company_allowed(self.env, journey.company_id)
        if attachment:
            attachment.check_access("read")
        values = {
            "journey_id": journey.id,
            "company_id": journey.company_id.id,
            "source_kind": source_kind,
            "source_party_id": party.id,
            "evidence_attachment_id": attachment.id if attachment else False,
            "acceptance_basis": _normalize_text(acceptance_basis),
        }
        if source_kind == "load":
            subject = self.env[PLASTICOS_LOAD].browse(source_id).exists()
            values["load_id"] = subject.id
            lock_table = "plasticos_load"
        elif source_kind == "stock_move_line":
            subject = self.env["stock.move.line"].browse(source_id).exists()
            values["stock_move_line_id"] = subject.id
            lock_table = "stock_move_line"
        else:
            subject = attachment
            lock_table = None
            if source_id and attachment and source_id != attachment.id:
                return _result("blocked", reason="non-stock evidence source must be the evidence attachment")
        if not subject:
            return _result("not_available", reason="source subject not found")
        subject.check_access("read")
        # C02 lock order: journey, then its physical subject.
        _lock(self.env, "plasticos_iso_journey", [journey.id])
        if lock_table:
            _lock(self.env, lock_table, [subject.id])
        domain = [("journey_id", "=", journey.id), ("source_kind", "=", source_kind)]
        if source_kind == "nonstock_evidence":
            domain += [("evidence_attachment_id", "=", attachment.id), ("source_party_id", "=", party.id)]
        else:
            domain.append((_SOURCE_SUBJECT_FIELD[source_kind], "=", subject.id))
        existing = self.search(domain, limit=1)
        if existing:
            # Replay is idempotent only for the exact accepted facts; any changed
            # party, evidence or basis is a different claim, never a silent success.
            same_facts = (
                existing.state == "accepted"
                and existing.source_party_id == party
                and existing.evidence_attachment_id.id == (attachment.id if attachment else False)
                and existing.acceptance_basis == values["acceptance_basis"]
            )
            if same_facts:
                return _result("already_applied", existing)
            return _result("blocked", existing, f"an existing {existing.state} association differs")
        candidate = self.with_context(**{_GUARDED_WRITE: _GUARDED_WRITE_TOKEN}).new(values)
        error = candidate._identity_error()
        if error:
            return _result("blocked", reason=error)
        source = self.with_context(**{_GUARDED_WRITE: _GUARDED_WRITE_TOKEN}).create({**values, "state": "accepted"})
        return _result("applied", source)
