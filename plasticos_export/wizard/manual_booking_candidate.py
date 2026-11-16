"""Manual 'Record booking candidate' screen (S10 OP10-E03, BRS-EXP-09-R001 fallback).

BRS-EXP-09-R001 permits controlled manual booking entry while the native Odoo
Documents AI path is not activated. This screen only collects what a person
reads from the carrier's original or email and hands it to the frozen
``record_booking_revision_candidate`` command, as the acting user. The command
keeps every guard: the Logistics role, record and company access, an exact
original or incoming email on this booking, typed terms, replay and
idempotency. The screen writes nothing itself and never makes a revision
current: acceptance stays a separate, reasoned command.

Native Documents AI is not called here and is not activated by this module.
"""

import uuid

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.booking import (
    ALREADY_APPLIED,
    APPLIED,
    BOOKING_STATUSES,
    DEFAULT_EQUIPMENT,
    DOCUMENTS_DOCUMENT,
    EQUIPMENT_CLASSES,
    EXPORT_BOOKING,
    EXPORT_REVISION,
    MAIL_MESSAGE,
    PRECISIONS,
    RES_PARTNER,
)

MANUAL_CANDIDATE = "plasticos.export.booking.manual.candidate"
MANUAL_CANDIDATE_LINE = "plasticos.export.booking.manual.candidate.line"


class PlasticosExportBookingManualCandidate(models.TransientModel):
    _name = "plasticos.export.booking.manual.candidate"
    _description = "Record Booking Candidate (manual entry)"

    booking_id = fields.Many2one(EXPORT_BOOKING, required=True, readonly=True, ondelete="cascade")
    company_id = fields.Many2one(related="booking_id.company_id", string="Company")
    source_original_id = fields.Many2one(
        DOCUMENTS_DOCUMENT,
        string="Source Original",
        ondelete="cascade",
        domain="[('res_model', '=', 'plasticos.export.booking'), ('res_id', '=', booking_id)]",
        help="The carrier's original file on this booking, held by native Documents.",
    )
    source_message_id = fields.Many2one(
        MAIL_MESSAGE,
        string="Source Email",
        ondelete="cascade",
        domain="[('model', '=', 'plasticos.export.booking'), ('res_id', '=', booking_id), "
        "('message_type', '=', 'email')]",
        help="The incoming email on this booking that states these terms.",
    )
    source_revision_key = fields.Char(
        required=True, help="The source's own revision identity, e.g. the booking number and its notice date."
    )
    source_issued_at = fields.Datetime(help="When the source says it was issued. Leave empty when not stated.")
    carrier_booking_no = fields.Char(string="Booking No.", help="Exactly as the source writes it.")
    steamship_line_id = fields.Many2one(RES_PARTNER, string="Steamship Line", ondelete="cascade")
    pol_text = fields.Char(string="Port of Loading", help="Leave empty when the source does not state it.")
    pod_text = fields.Char(string="Port of Discharge", help="Leave empty when the source does not state it.")
    erd_local = fields.Char(string="ERD (local)", help="As stated: YYYY-MM-DD or YYYY-MM-DD HH:MM.")
    erd_tz = fields.Char(string="ERD Time Zone", help="IANA zone the source states, e.g. America/Los_Angeles.")
    erd_precision = fields.Selection(PRECISIONS, string="ERD Precision", required=True, default="unknown")
    cargo_cutoff_local = fields.Char(string="Cargo Cutoff (local)")
    cargo_cutoff_tz = fields.Char(string="Cargo Cutoff Time Zone")
    cargo_cutoff_precision = fields.Selection(
        PRECISIONS, string="Cargo Cutoff Precision", required=True, default="unknown"
    )
    booking_status = fields.Selection(
        [(status, status.capitalize()) for status in BOOKING_STATUSES],
        string="Stated Status",
        help="Only what the source states. Leave empty when it states no status.",
    )
    vessel = fields.Char(help="Vessel name as stated; kept in the revision's additional terms.")
    voyage = fields.Char(help="Voyage number as stated; kept in the revision's additional terms.")
    line_ids = fields.One2many(MANUAL_CANDIDATE_LINE, "wizard_id", string="Equipment")
    operation_key = fields.Char(
        required=True,
        readonly=True,
        default=lambda self: f"manual-candidate-{uuid.uuid4()}",
        help="One key per screen: pressing Record twice records the candidate once.",
    )

    @api.model
    def _equipment_counts(self, lines):
        counts = {}
        for line in lines:
            if line.equipment_class in counts:
                raise UserError(f"Equipment {line.equipment_class} is listed twice.")
            counts[line.equipment_class] = {
                "requested": line.requested_count if line.requested_stated else None,
                "confirmed": line.confirmed_count if line.confirmed_stated else None,
            }
        return counts

    def _extracted_terms(self):
        """The command's ``extracted_terms``. An empty field is unknown, never a guessed value."""
        self.ensure_one()
        additional = {}
        if self.booking_status:
            additional["booking_status"] = self.booking_status
        for name in ("vessel", "voyage"):
            if (self[name] or "").strip():
                additional[name] = self[name].strip()
        terms = {
            "carrier_booking_no": self.carrier_booking_no or None,
            "pol_text": self.pol_text or None,
            "pod_text": self.pod_text or None,
            "steamship_line_id": self.steamship_line_id.id or None,
            "erd_local": self.erd_local or None,
            "erd_tz": self.erd_tz or None,
            "erd_precision": self.erd_precision,
            "cargo_cutoff_local": self.cargo_cutoff_local or None,
            "cargo_cutoff_tz": self.cargo_cutoff_tz or None,
            "cargo_cutoff_precision": self.cargo_cutoff_precision,
            "equipment_counts": self._equipment_counts(self.line_ids),
            "additional_terms": additional,
        }
        if self.source_issued_at:
            terms["source_issued_at"] = fields.Datetime.to_string(self.source_issued_at)
        return terms

    def action_record(self):
        """Hand the typed terms to the frozen command; show its refusal as it states it."""
        self.ensure_one()
        outcome = self.booking_id.record_booking_revision_candidate(
            self.source_original_id.id or False,
            self.source_message_id.id or False,
            self.source_revision_key,
            self._extracted_terms(),
            self.operation_key,
        )
        if outcome["status"] not in (APPLIED, ALREADY_APPLIED):
            raise UserError(f"Booking candidate not recorded ({outcome['status']}): {outcome.get('reason', '')}")
        return {
            "type": "ir.actions.act_window",
            "res_model": EXPORT_REVISION,
            "res_id": outcome["record_id"],
            "view_mode": "form",
            "target": "current",
        }


class PlasticosExportBookingManualCandidateLine(models.TransientModel):
    _name = "plasticos.export.booking.manual.candidate.line"
    _description = "Record Booking Candidate: equipment line"

    wizard_id = fields.Many2one(MANUAL_CANDIDATE, required=True, ondelete="cascade")
    equipment_class = fields.Selection(EQUIPMENT_CLASSES, required=True, default=DEFAULT_EQUIPMENT)
    requested_stated = fields.Boolean(string="Requested Stated", help="The source states a requested count.")
    requested_count = fields.Integer(string="Requested")
    confirmed_stated = fields.Boolean(string="Confirmed Stated", help="The source states a confirmed count.")
    confirmed_count = fields.Integer(string="Confirmed")
