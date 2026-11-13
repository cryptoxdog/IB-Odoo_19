"""Export booking (E1) and its immutable revisions (E2).

E1 is one carrier reservation of one company, identified by its issuer and the
exact source booking cycle, never by the booking number alone (a number may be
reissued). E2 is one source snapshot of that reservation. A revision is recorded
as a candidate from an exact original file or email; only an authorized
acceptance makes it current, through a compare-and-set on the booking's
``current_revision_id``. An accepted revision never changes again; a later notice
is a new candidate that supersedes it (BRS-EXP-02-R004, BRS-EXP-11-R005/R006).

Confirmed capacity becomes distinct slots (E3) in the same transaction as the
acceptance, so capacity and currentness can never disagree. Original files stay
with native Documents and verification with ``plasticos_documents``: a revision
points at its original and copies nothing out of it (BRS-EXP-03-R002).

Public commands (TECHNICAL_CONTRACT_v2.7 ``target_command_signatures``) return
``{"status": applied|already_applied|stale|blocked|ambiguous|not_available,
"record_id"?, "reason"?}`` and never raise for an ordinary business refusal.
"""

import hashlib
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import AccessError, LockError, UserError, ValidationError
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)

EXPORT_BOOKING = "plasticos.export.booking"
EXPORT_REVISION = "plasticos.export.booking.revision"
EXPORT_REVISION_ACCEPT = "plasticos.export.booking.revision.accept"
EXPORT_SLOT = "plasticos.export.booking.slot"
EXPORT_CARGO_LINK = "plasticos.export.booking.cargo.link"
RES_COMPANY = "res.company"
RES_PARTNER = "res.partner"
RES_USERS = "res.users"
MAIL_MESSAGE = "mail.message"
DOCUMENTS_DOCUMENT = "documents.document"
LOGISTICS_REQUEST = "plasticos.logistics.request"
EXPORT_ACTOR_GROUP = "plasticos_security_base.group_logistics"

APPLIED = "applied"
ALREADY_APPLIED = "already_applied"
STALE = "stale"
BLOCKED = "blocked"
AMBIGUOUS = "ambiguous"
NOT_AVAILABLE = "not_available"

# BRS-EXP-07-R003: the five booking choices; 40HC is the suggested default, never enforced.
EQUIPMENT_CLASSES = [
    ("20STD", "20' Standard"),
    ("40STD", "40' Standard"),
    ("40HC", "40' High Cube"),
    ("45STD", "45' Standard"),
    ("45HC", "45' High Cube"),
]
EQUIPMENT_CODES = tuple(code for code, _label in EQUIPMENT_CLASSES)
DEFAULT_EQUIPMENT = "40HC"
PRECISIONS = [("date", "Date only"), ("datetime", "Date and time"), ("unknown", "Unknown")]
DECISIONS = [("candidate", "Candidate"), ("accepted", "Accepted"), ("rejected", "Rejected")]
# BRS-EXP-13-R007: status the source states. Nothing is inferred; absent means not stated.
BOOKING_STATUSES = ("confirmed", "revised", "rolled", "cancelled")
CANCELLED = "cancelled"

# Scalar snapshot terms a candidate may carry; everything else goes in additional_terms.
_SNAPSHOT_TEXT_TERMS = ("carrier_booking_no", "pol_text", "pod_text")
_SNAPSHOT_TERMS = frozenset(
    {
        *_SNAPSHOT_TEXT_TERMS,
        "steamship_line_id",
        "erd_local",
        "erd_tz",
        "erd_precision",
        "cargo_cutoff_local",
        "cargo_cutoff_tz",
        "cargo_cutoff_precision",
        "equipment_counts",
        "additional_terms",
        "affected_scope",
        "source_issued_at",
    }
)
_LOCAL_FORMATS = {"date": ("%Y-%m-%d",), "datetime": ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M")}

_GUARD = "plasticos_export_guarded_write"
_GUARD_TOKEN = object()

# Accepted revision facts never change. Draft review notes and the decision
# pointer are the only things the acceptance itself writes.
_REVISION_IMMUTABLE = frozenset(
    {
        "booking_id",
        "source_revision_key",
        "source_original_id",
        "source_message_id",
        "observed_at",
        "source_issued_at",
        "carrier_booking_no",
        "steamship_line_id",
        "pol_text",
        "pod_text",
        "erd_local",
        "erd_tz",
        "erd_precision",
        "erd_utc",
        "cargo_cutoff_local",
        "cargo_cutoff_tz",
        "cargo_cutoff_precision",
        "cargo_cutoff_utc",
        "equipment_counts",
        "additional_terms",
        "affected_scope",
        "decision",
        "accepted_at",
        "accepted_by",
        "acceptance_basis",
        "supersedes_revision_id",
        "operation_key",
        "accept_operation_key",
    }
)


def result(status, record=None, reason=None):
    """The frozen command result shape."""
    out = {"status": status}
    if record:
        out["record_id"] = record.id
    if reason:
        out["reason"] = reason
    return out


def guarded(env):
    """True inside an Export command's own write."""
    return env.context.get(_GUARD) is _GUARD_TOKEN


def guard(records):
    """The same records, allowed to write their command-owned fields."""
    return records.with_context(**{_GUARD: _GUARD_TOKEN})


def derived_write_error(records, vals):
    """Why an ordinary write may not set these keys, or False.

    Computed and related fields are derived: a related field's inverse would
    otherwise write through to its source, and a stored computed value could be
    forged. ``company_id`` is set at creation or by an Export command only, so a
    row is never relabelled across the company rules (C05 review D1).
    """
    derived = sorted(
        name
        for name in vals
        if name == "company_id"
        or (name in records._fields and (records._fields[name].compute or records._fields[name].related))
    )
    if derived:
        return f"{records._description}: {', '.join(derived)} cannot be written; it is derived or set by its owner."
    return False


def export_actor_error(env, company=None):
    """Why this user may not run an Export command for ``company``, or False.

    The actor is the Logistics business role in the record's company. Sudo and
    a context flag never stand in for the user (E3).
    """
    if env.su or env.uid == SUPERUSER_ID:
        return "commands run as the acting user, never through sudo"
    if not env.user.has_group(EXPORT_ACTOR_GROUP):
        return "only Logistics users may run Export booking commands"
    if company and company not in env.user.company_ids:
        return "the booking belongs to a company this user cannot act for"
    return False


def utc_from_local(local, tz_name, precision):
    """UTC instant of a source time, only when the source gave date, time and zone.

    A date-only or zoneless value stays local text; nothing is guessed (BRS-EXP-02-R003).
    """
    if precision != "datetime" or not local or not tz_name:
        return False
    try:
        zone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValidationError(f"Unknown time zone {tz_name!r}.") from error
    for pattern in _LOCAL_FORMATS["datetime"]:
        try:
            naive = datetime.strptime(local.strip(), pattern)
        except ValueError:
            continue
        utc = ZoneInfo("UTC")
        first = naive.replace(tzinfo=zone, fold=0).astimezone(utc)
        second = naive.replace(tzinfo=zone, fold=1).astimezone(utc)
        if first.astimezone(zone).replace(tzinfo=None) != naive:
            # A spring-forward gap: this wall-clock time never happens in that zone.
            raise ValidationError(f"{local!r} does not exist in {tz_name}.")
        if first != second:
            # A daylight-saving fall-back hour occurs twice; the source must say which.
            raise ValidationError(f"{local!r} occurs twice in {tz_name}; the source time is ambiguous.")
        return first.replace(tzinfo=None)
    raise ValidationError(f"{local!r} is not a local date and time.")


def _check_local(local, precision, label):
    if precision == "unknown" or not local:
        return
    for pattern in _LOCAL_FORMATS[precision]:
        try:
            datetime.strptime(local.strip(), pattern)
            return
        except ValueError:
            continue
    raise ValidationError(f"{label} {local!r} does not match its stated precision {precision!r}.")


def normalize_equipment_counts(value):
    """``{class: {"requested": int|None, "confirmed": int|None}}``, requested and confirmed kept apart."""
    if not value:
        return {}
    if not isinstance(value, dict):
        raise ValidationError("Equipment counts must map an equipment class to its counts.")
    out = {}
    for code, counts in value.items():
        if code not in EQUIPMENT_CODES:
            raise ValidationError(f"{code!r} is not a booking equipment class.")
        if not isinstance(counts, dict) or set(counts) - {"requested", "confirmed"}:
            raise ValidationError(f"Equipment {code} needs separate requested and confirmed counts.")
        entry = {}
        for key in ("requested", "confirmed"):
            number = counts.get(key)
            if number is None:
                entry[key] = None
                continue
            if isinstance(number, bool) or not isinstance(number, int) or number < 0:
                raise ValidationError(f"Equipment {code} {key} count must be a whole number.")
            entry[key] = number
        out[code] = entry
    return out


class PlasticosExportBooking(models.Model):
    _name = "plasticos.export.booking"
    _description = "Export Booking"
    _inherit = ["mail.thread"]
    _order = "id desc"
    _rec_name = "carrier_booking_no"

    company_id = fields.Many2one(
        RES_COMPANY,
        required=True,
        index=True,
        ondelete="restrict",
        default=lambda self: self.env.company,
        tracking=True,
        help="Company that holds this reservation. Immutable once a revision is accepted.",
    )
    carrier_booking_no = fields.Char(
        string="Booking No.",
        index=True,
        tracking=True,
        help="Booking number exactly as the carrier issued it. Not unique: a number may be reissued.",
    )
    carrier_id = fields.Many2one(
        RES_PARTNER,
        string="Carrier",
        index=True,
        ondelete="restrict",
        tracking=True,
        help="Ocean carrier that holds the reservation. Not the drayage trucker (BRS-EXP-10-R001).",
    )
    issuer_id = fields.Many2one(
        RES_PARTNER,
        string="Issuer",
        index=True,
        ondelete="restrict",
        tracking=True,
        help="Party that issued the booking confirmation (carrier, forwarder or agent). Required to accept.",
    )
    source_occurrence_key = fields.Char(
        string="Source Booking Cycle",
        index=True,
        tracking=True,
        help="Exact booking-cycle identity from the source. Required to accept; never the number alone.",
    )
    current_revision_id = fields.Many2one(
        EXPORT_REVISION,
        string="Current Revision",
        readonly=True,
        index=True,
        ondelete="restrict",
        tracking=True,
        help="The accepted revision that is current. Only Accept Revision moves it.",
    )
    revision_ids = fields.One2many(EXPORT_REVISION, "booking_id", string="Revisions", readonly=True)
    slot_ids = fields.One2many(EXPORT_SLOT, "booking_id", string="Slots", readonly=True)
    display_state = fields.Selection(
        [("candidate", "Candidate"), ("confirmed", "Confirmed"), ("held", "Held"), ("cancelled", "Cancelled")],
        compute="_compute_display_state",
        store=True,
        index=True,
        help="Derived from the current accepted revision and its slots. Never written directly.",
    )
    # Read-only projections of the current accepted revision, for search, calendar and lists.
    current_steamship_line_id = fields.Many2one(
        related="current_revision_id.steamship_line_id", string="Steamship Line", store=True, index=True
    )
    current_pol_text = fields.Char(related="current_revision_id.pol_text", string="Port of Loading", store=True)
    current_pod_text = fields.Char(related="current_revision_id.pod_text", string="Port of Discharge", store=True)
    current_erd_utc = fields.Datetime(related="current_revision_id.erd_utc", string="ERD (UTC)", store=True)
    current_cargo_cutoff_utc = fields.Datetime(
        related="current_revision_id.cargo_cutoff_utc", string="Cargo Cutoff (UTC)", store=True
    )
    current_cargo_cutoff_date = fields.Date(
        compute="_compute_current_cargo_cutoff_date",
        store=True,
        index=True,
        string="Cargo Cutoff Date",
        help="Calendar day of the current cargo cutoff: the local date the source stated, at date or "
        "datetime precision. Unset when no cutoff is stated (reviews D4, R2).",
    )
    slot_confirmed_count = fields.Integer(compute="_compute_slot_counts", string="Confirmed Slots")
    slot_committed_count = fields.Integer(compute="_compute_slot_counts", string="Committed Slots")
    slot_available_count = fields.Integer(compute="_compute_slot_counts", string="Available Slots")
    slot_held_count = fields.Integer(compute="_compute_slot_counts", string="Held Slots")

    _source_occurrence_unique = models.UniqueIndex(
        "(company_id, issuer_id, source_occurrence_key) WHERE source_occurrence_key IS NOT NULL",
        "This company already has a booking for that issuer and source booking cycle.",
    )
    _carrier_is_not_issuer = models.Constraint(
        "CHECK(carrier_id IS NULL OR issuer_id IS NULL OR carrier_id != issuer_id)",
        "The carrier and the issuer of a booking are different parties.",
    )

    @api.depends(
        "current_revision_id",
        "current_revision_id.additional_terms",
        "slot_ids.active",
        "slot_ids.hold_reason",
    )
    def _compute_display_state(self):
        for booking in self:
            revision = booking.current_revision_id
            if not revision:
                booking.display_state = "candidate"
            elif revision._stated_status() == CANCELLED:
                booking.display_state = "cancelled"
            elif booking.slot_ids.filtered(lambda slot: slot.active and slot.hold_reason):
                booking.display_state = "held"
            else:
                booking.display_state = "confirmed"

    @api.depends(
        "current_revision_id.cargo_cutoff_local",
        "current_revision_id.cargo_cutoff_precision",
    )
    def _compute_current_cargo_cutoff_date(self):
        for booking in self:
            revision = booking.current_revision_id
            # The day the source stated, in its own zone: a late-evening local cutoff stays on its
            # local day instead of moving to the next UTC day (review R2, BRS-EXP-02-R003).
            if revision.cargo_cutoff_precision in ("date", "datetime") and revision.cargo_cutoff_local:
                booking.current_cargo_cutoff_date = fields.Date.to_date(revision.cargo_cutoff_local.strip()[:10])
            else:
                booking.current_cargo_cutoff_date = False

    @api.depends(
        "slot_ids.allocation_state",
        "current_revision_id",
        "current_revision_id.equipment_counts",
        "current_revision_id.additional_terms",
    )
    def _compute_slot_counts(self):
        for booking in self:
            states = booking.slot_ids.mapped("allocation_state")
            # Confirmed capacity is what the current accepted revision confirms; held slots are counted apart.
            revision = booking.current_revision_id
            booking.slot_confirmed_count = sum(revision._confirmed_counts().values()) if revision else 0
            booking.slot_committed_count = states.count("committed")
            booking.slot_available_count = states.count("available")
            booking.slot_held_count = states.count("held")

    @api.depends("carrier_booking_no", "issuer_id", "source_occurrence_key")
    def _compute_display_name(self):
        for booking in self:
            number = booking.carrier_booking_no or "Unconfirmed booking"
            cycle = booking.source_occurrence_key
            booking.display_name = f"{number} ({cycle})" if cycle else number

    # ── ORM guards ───────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("current_revision_id") and not guarded(self.env):
                raise UserError("A booking starts without a current revision; accept one with Accept Revision.")
            if not self.env.su:
                company = self.env[RES_COMPANY].browse(vals.get("company_id") or self.env.company.id)
                error = export_actor_error(self.env, company)
                if error:
                    raise AccessError(error)
        return super().create(vals_list)

    def write(self, vals):
        if not guarded(self.env):
            error = derived_write_error(self, vals)
            if error:
                raise UserError(error)
            if "current_revision_id" in vals:
                raise UserError("Only Accept Revision moves a booking's current revision.")
            accepted = self.filtered("current_revision_id")
            if accepted and {"company_id", "issuer_id", "source_occurrence_key"} & set(vals):
                raise UserError("An accepted booking keeps its company, issuer and source booking cycle.")
            if (
                accepted
                and "carrier_booking_no" in vals
                and any(vals["carrier_booking_no"] != booking.carrier_booking_no for booking in accepted)
            ):
                raise UserError("The booking number of an accepted booking comes from its accepted revision.")
        return super().write(vals)

    def unlink(self):
        if self.filtered("current_revision_id") or self.revision_ids:
            raise UserError("A booking with revisions is history and cannot be deleted.")
        return super().unlink()

    # ── helpers ──────────────────────────────────────────────

    def _lock_booking(self):
        """Row-lock this booking first (C05 lock order: booking, then slots by id)."""
        self.ensure_one()
        self.lock_for_update()
        self.invalidate_recordset()

    def _command_preflight(self, operation_key):
        """Common refusals of every booking command, or False."""
        self.ensure_one()
        if not (operation_key or "").strip():
            return result(BLOCKED, reason="operation_key is required")
        # Role first, then record access, then company: an outsider learns nothing by a read error.
        error = export_actor_error(self.env)
        if error:
            return result(NOT_AVAILABLE, reason=error)
        try:
            self.check_access("write")
        except AccessError:
            return result(NOT_AVAILABLE, reason="no access to this booking")
        error = export_actor_error(self.env, self.company_id)
        if error:
            return result(NOT_AVAILABLE, reason=error)
        return False

    def _validated_original(self, source_original_id):
        """The native original document of this exact booking, or an error reason."""
        if not source_original_id:
            return self.env[DOCUMENTS_DOCUMENT], False
        original = self.env[DOCUMENTS_DOCUMENT].browse(int(source_original_id)).exists()
        if not original:
            return original, "source original not found"
        try:
            original.check_access("read")
        except AccessError:
            return self.env[DOCUMENTS_DOCUMENT], "source original not readable"
        if original.res_model != self._name or original.res_id != self.id:
            return self.env[DOCUMENTS_DOCUMENT], "source original belongs to another record"
        if original.company_id and original.company_id != self.company_id:
            return self.env[DOCUMENTS_DOCUMENT], "source original belongs to another company"
        if not original.attachment_id:
            return self.env[DOCUMENTS_DOCUMENT], "source original has no file"
        return original, False

    def _validated_message(self, source_message_id):
        """The incoming mail message on this exact booking, or an error reason."""
        if not source_message_id:
            return self.env[MAIL_MESSAGE], False
        message = self.env[MAIL_MESSAGE].browse(int(source_message_id)).exists()
        if not message:
            return message, "source message not found"
        if message.model != self._name or message.res_id != self.id:
            return self.env[MAIL_MESSAGE], "source message belongs to another record"
        if message.message_type != "email":
            return self.env[MAIL_MESSAGE], "source message is not an incoming email"
        return message, False

    def _candidate_values(self, extracted_terms):
        """Snapshot values of one candidate. Unknown keys are refused, never dropped."""
        terms = dict(extracted_terms or {})
        unknown = set(terms) - _SNAPSHOT_TERMS
        if unknown:
            raise ValidationError(
                f"Unknown booking terms {sorted(unknown)}; put source terms Export does not model in additional_terms."
            )
        vals = {}
        for name in _SNAPSHOT_TEXT_TERMS:
            vals[name] = str(terms[name]).strip() or False if terms.get(name) is not None else False
        vals["steamship_line_id"] = False
        line = terms.get("steamship_line_id")
        if line:
            partner = self.env[RES_PARTNER].browse(int(line)).exists()
            if not partner:
                raise ValidationError("The steamship line partner does not exist.")
            vals["steamship_line_id"] = partner.id
        for prefix, label in (("erd", "ERD"), ("cargo_cutoff", "Cargo cutoff")):
            precision = terms.get(f"{prefix}_precision") or "unknown"
            if precision not in dict(PRECISIONS):
                raise ValidationError(f"{label} precision {precision!r} is not date, datetime or unknown.")
            local = (terms.get(f"{prefix}_local") or "").strip() or False
            tz_name = (terms.get(f"{prefix}_tz") or "").strip() or False
            if precision == "unknown" and local:
                raise ValidationError(f"{label} has a value but no stated precision.")
            _check_local(local, precision, label)
            vals.update(
                {
                    f"{prefix}_precision": precision,
                    f"{prefix}_local": local,
                    f"{prefix}_tz": tz_name,
                    f"{prefix}_utc": utc_from_local(local, tz_name, precision),
                }
            )
        vals["equipment_counts"] = normalize_equipment_counts(terms.get("equipment_counts"))
        additional = terms.get("additional_terms") or {}
        if not isinstance(additional, dict):
            raise ValidationError("additional_terms must be a mapping of term to its source value.")
        status = additional.get("booking_status")
        if status is not None and status not in BOOKING_STATUSES:
            raise ValidationError(f"Booking status {status!r} is not one the source can state.")
        vals["additional_terms"] = additional
        scope = terms.get("affected_scope")
        if scope is not None and not isinstance(scope, dict):
            raise ValidationError("affected_scope must name exact ids or say the scope is unknown.")
        vals["affected_scope"] = scope or {"scope": "unknown"}
        issued = terms.get("source_issued_at")
        vals["source_issued_at"] = fields.Datetime.to_datetime(issued) if issued else False
        return vals

    # ── Frozen command: record_booking_revision_candidate ────

    def record_booking_revision_candidate(
        self, source_original_id, source_message_id, source_revision_key, extracted_terms, operation_key
    ):
        """Record one source snapshot of this booking as a candidate revision (BRS-EXP-09-R006).

        The candidate needs an exact original file or incoming email on this
        booking. It changes nothing current. Replaying the same operation or the
        same source revision with the same terms returns ``already_applied``; a
        different payload under the same key is ``stale``. An AI proposal reaches
        Export only through this bounded command.
        """
        self.ensure_one()
        refusal = self._command_preflight(operation_key)
        if refusal:
            return refusal
        key = (source_revision_key or "").strip()
        if not key:
            return result(BLOCKED, reason="source_revision_key is required")
        if not source_original_id and not source_message_id:
            return result(BLOCKED, reason="a candidate needs its source original or source message")
        original, reason = self._validated_original(source_original_id)
        if reason:
            return result(BLOCKED, reason=reason)
        message, reason = self._validated_message(source_message_id)
        if reason:
            return result(BLOCKED, reason=reason)
        try:
            vals = self._candidate_values(extracted_terms)
        except ValidationError as error:
            return result(BLOCKED, reason=str(error.args[0]))
        try:
            self._lock_booking()
        except LockError:
            return result(BLOCKED, reason="booking_busy")
        Revision = self.env[EXPORT_REVISION]
        fingerprint = Revision._payload_fingerprint(key, original, message, vals)
        prior = Revision.search(
            [
                ("booking_id", "=", self.id),
                "|",
                ("operation_key", "=", operation_key),
                ("source_revision_key", "=", key),
            ]
        )
        for revision in prior:
            if revision._fingerprint() == fingerprint:
                return result(ALREADY_APPLIED, revision)
        if prior.filtered(lambda revision: revision.operation_key == operation_key):
            return result(STALE, prior[:1], "operation_key was used for a different candidate")
        if prior:
            return result(STALE, prior[:1], "this source revision was already recorded with different terms")
        revision = guard(Revision).create(
            {
                **vals,
                "booking_id": self.id,
                "source_revision_key": key,
                "source_original_id": original.id or False,
                "source_message_id": message.id or False,
                "observed_at": fields.Datetime.now(),
                "decision": "candidate",
                "operation_key": operation_key,
            }
        )
        return result(APPLIED, revision)

    # ── Frozen command: action_accept_booking_revision ───────

    def action_accept_booking_revision(
        self, revision_id, expected_current_revision_id, operation_key, acceptance_reason
    ):
        """Make one candidate the current revision and reconcile slot capacity atomically.

        Compare-and-set: the caller names the revision it believes current. If
        another acceptance moved it first the answer is ``stale`` and nothing is
        written (V05). Confirmed counts become distinct slots; a reduction keeps
        committed or bound slots held for an owner decision instead of
        releasing cargo silently (BRS-EXP-14-R016).
        """
        self.ensure_one()
        refusal = self._command_preflight(operation_key)
        if refusal:
            return refusal
        basis = (acceptance_reason or "").strip()
        if not basis:
            return result(BLOCKED, reason="acceptance_reason is required")
        try:
            self._lock_booking()
        except LockError:
            return result(BLOCKED, reason="booking_busy")
        revision = self.env[EXPORT_REVISION].browse(int(revision_id or 0)).exists()
        if not revision or revision.booking_id != self:
            return result(NOT_AVAILABLE, reason="revision not found on this booking")
        if revision.decision == "accepted":
            if revision.accept_operation_key == operation_key or revision == self.current_revision_id:
                return result(ALREADY_APPLIED, revision)
            return result(STALE, revision, "revision was already accepted and is no longer current")
        if revision.decision != "candidate":
            return result(BLOCKED, revision, "a rejected revision cannot be accepted")
        if (self.current_revision_id.id or False) != (expected_current_revision_id or False):
            return result(STALE, self.current_revision_id, "current revision changed")
        number = revision.carrier_booking_no or self.carrier_booking_no
        if not number or not self.issuer_id or not self.source_occurrence_key:
            return result(BLOCKED, revision, "acceptance needs the booking number, issuer and source booking cycle")
        if (
            self.carrier_booking_no
            and revision.carrier_booking_no
            and revision.carrier_booking_no != self.carrier_booking_no
        ):
            return result(BLOCKED, revision, "a different booking number is a replacement booking, not a revision")
        previous = self.current_revision_id
        guard(revision).write(
            {
                "decision": "accepted",
                "accepted_at": fields.Datetime.now(),
                "accepted_by": self.env.uid,
                "acceptance_basis": basis,
                "supersedes_revision_id": previous.id or False,
                "accept_operation_key": operation_key,
            }
        )
        guard(self).write({"current_revision_id": revision.id, "carrier_booking_no": number})
        self.env[EXPORT_SLOT]._reconcile_capacity(self, revision)
        self.message_post(
            body=f"Revision {revision.source_revision_key} accepted: {basis}",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        return result(APPLIED, revision)

    # ── Frozen command: action_request_booking_notice ────────

    def action_request_booking_notice(
        self, purpose, audience_partner_id, recipient_email, expected_current_revision_id, operation_key, audience_basis
    ):
        """Ask Linda to send one booking notice; Export never sends mail itself (BRS-EXP-03-R005).

        Export checks currentness and its own audience basis, then hands the
        exact accepted revision and its original to Linda's frozen command.
        Linda's answer is returned unchanged.
        """
        self.ensure_one()
        refusal = self._command_preflight(operation_key)
        if refusal:
            return refusal
        if not (audience_basis or "").strip():
            return result(BLOCKED, reason="audience_basis is required")
        current = self.current_revision_id
        if not current:
            return result(BLOCKED, reason="the booking has no accepted revision")
        if current.id != (expected_current_revision_id or False):
            return result(STALE, current, "current revision changed")
        if not email_normalize(recipient_email or ""):
            return result(BLOCKED, reason="recipient email is not valid")
        attachments = current._original_attachment_ids()
        return self.env[LOGISTICS_REQUEST].request_booking_correspondence(
            self.id,
            current.id,
            purpose,
            audience_partner_id,
            recipient_email,
            attachments,
            current._notice_fingerprint(),
            operation_key,
        )

    # ── Views ─────────────────────────────────────────────────

    def action_view_slots(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Slots — {self.display_name}",
            "res_model": EXPORT_SLOT,
            "view_mode": "list,form",
            "domain": [("booking_id", "=", self.id)],
            "context": {"active_test": False},
        }


class PlasticosExportBookingRevision(models.Model):
    _name = "plasticos.export.booking.revision"
    _description = "Export Booking Revision"
    _order = "booking_id, id desc"
    _rec_name = "source_revision_key"

    booking_id = fields.Many2one(EXPORT_BOOKING, required=True, index=True, ondelete="restrict")
    company_id = fields.Many2one(related="booking_id.company_id", store=True, index=True)
    booking_current_revision_id = fields.Many2one(
        related="booking_id.current_revision_id",
        string="Booking's Current Revision",
        help="The revision the booking had when this form was loaded. Accept Revision compares against it.",
    )
    source_revision_key = fields.Char(required=True, index=True, help="Source revision identity; unique per booking.")
    source_original_id = fields.Many2one(
        DOCUMENTS_DOCUMENT, string="Source Original", index=True, ondelete="restrict", help="Native original file."
    )
    source_message_id = fields.Many2one(
        MAIL_MESSAGE, string="Source Message", index=True, ondelete="restrict", help="Incoming email it came from."
    )
    observed_at = fields.Datetime(required=True, help="When Export observed this source.")
    source_issued_at = fields.Datetime(help="When the source says it was issued. Never inferred.")
    carrier_booking_no = fields.Char(string="Booking No.")
    steamship_line_id = fields.Many2one(RES_PARTNER, string="Steamship Line", ondelete="restrict")
    pol_text = fields.Char(string="Port of Loading")
    pod_text = fields.Char(string="Port of Discharge")
    erd_local = fields.Char(string="ERD (local)")
    erd_tz = fields.Char(string="ERD Time Zone")
    erd_precision = fields.Selection(PRECISIONS, required=True, default="unknown")
    erd_utc = fields.Datetime(string="ERD (UTC)")
    cargo_cutoff_local = fields.Char(string="Cargo Cutoff (local)")
    cargo_cutoff_tz = fields.Char(string="Cargo Cutoff Time Zone")
    cargo_cutoff_precision = fields.Selection(PRECISIONS, required=True, default="unknown")
    cargo_cutoff_utc = fields.Datetime(string="Cargo Cutoff (UTC)")
    equipment_counts = fields.Json(help="Per equipment class: requested and confirmed counts, kept apart.")
    additional_terms = fields.Json(help="Other source terms with their original values and status.")
    affected_scope = fields.Json(help="Exact affected ids, or scope unknown.")
    decision = fields.Selection(DECISIONS, required=True, default="candidate", index=True)
    accepted_at = fields.Datetime(readonly=True)
    accepted_by = fields.Many2one(RES_USERS, readonly=True, ondelete="restrict")
    acceptance_basis = fields.Text(readonly=True)
    supersedes_revision_id = fields.Many2one(
        EXPORT_REVISION, string="Supersedes", readonly=True, index=True, ondelete="restrict"
    )
    operation_key = fields.Char(readonly=True, index=True, help="Operation that recorded this candidate.")
    accept_operation_key = fields.Char(readonly=True, help="Operation that accepted it.")
    equipment_summary = fields.Char(compute="_compute_equipment_summary", string="Equipment")
    booking_status = fields.Char(compute="_compute_equipment_summary", string="Stated Status")

    _booking_revision_unique = models.Constraint(
        "UNIQUE(booking_id, source_revision_key)", "This booking already has that source revision."
    )
    _accepted_complete = models.Constraint(
        "CHECK(decision != 'accepted' OR (accepted_at IS NOT NULL AND accepted_by IS NOT NULL"
        " AND acceptance_basis IS NOT NULL))",
        "An accepted revision records who accepted it, when and why.",
    )
    _source_present = models.Constraint(
        "CHECK(source_original_id IS NOT NULL OR source_message_id IS NOT NULL)",
        "A booking revision needs its source original or source message.",
    )

    @api.depends("equipment_counts", "additional_terms")
    def _compute_equipment_summary(self):
        for revision in self:
            parts = []
            for code, counts in sorted((revision.equipment_counts or {}).items()):
                requested = counts.get("requested")
                confirmed = counts.get("confirmed")
                parts.append(
                    f"{code}: requested {'?' if requested is None else requested}, "
                    f"confirmed {'?' if confirmed is None else confirmed}"
                )
            revision.equipment_summary = "; ".join(parts)
            revision.booking_status = revision._stated_status() or ""

    def _stated_status(self):
        self.ensure_one()
        return (self.additional_terms or {}).get("booking_status") or False

    def _confirmed_counts(self):
        """Confirmed slots per class, for the classes whose confirmed count the source stated.

        A stated count, 0 included, is in the mapping. A class the revision does not
        mention, or whose confirmed count is not stated (None), is absent: not stated
        is not zero (POS-INV-03), so its slots are left as they are. A cancelled
        booking confirms nothing.
        """
        self.ensure_one()
        if self._stated_status() == CANCELLED:
            return {}
        return {
            code: counts["confirmed"]
            for code, counts in (self.equipment_counts or {}).items()
            if counts.get("confirmed") is not None
        }

    def _original_attachment_ids(self):
        self.ensure_one()
        return [self.source_original_id.attachment_id.id] if self.source_original_id.attachment_id else []

    @api.model
    def _payload_fingerprint(self, key, original, message, vals):
        payload = {"key": key, "original": original.id or False, "message": message.id or False}
        payload.update({name: vals.get(name) for name in sorted(vals)})
        return json.dumps(payload, sort_keys=True, default=str)

    def _fingerprint(self):
        self.ensure_one()
        vals = {name: self[name] for name in _SNAPSHOT_TERMS if name in self._fields}
        vals["steamship_line_id"] = self.steamship_line_id.id or False
        for prefix in ("erd", "cargo_cutoff"):
            vals[f"{prefix}_precision"] = self[f"{prefix}_precision"]
            vals[f"{prefix}_local"] = self[f"{prefix}_local"] or False
            vals[f"{prefix}_tz"] = self[f"{prefix}_tz"] or False
            vals[f"{prefix}_utc"] = self[f"{prefix}_utc"] or False
        vals["equipment_counts"] = self.equipment_counts or {}
        vals["additional_terms"] = self.additional_terms or {}
        vals["affected_scope"] = self.affected_scope or {"scope": "unknown"}
        vals["source_issued_at"] = self.source_issued_at or False
        for name in _SNAPSHOT_TEXT_TERMS:
            vals[name] = self[name] or False
        return self._payload_fingerprint(
            self.source_revision_key, self.source_original_id, self.source_message_id, vals
        )

    def _notice_fingerprint(self):
        """Digest of this revision's source snapshot; Linda checks it before recording a notice."""
        self.ensure_one()
        return hashlib.sha256(self._fingerprint().encode()).hexdigest()

    @api.model_create_multi
    def create(self, vals_list):
        if not guarded(self.env):
            raise UserError("Record booking revisions with Record Candidate; they are never typed in.")
        return super().create(vals_list)

    def write(self, vals):
        if not guarded(self.env):
            error = derived_write_error(self, vals)
            if error:
                raise UserError(error)
            raise UserError("A booking revision is a source snapshot and is not edited.")
        frozen = self.filtered(lambda revision: revision.decision != "candidate")
        if frozen and _REVISION_IMMUTABLE & set(vals):
            raise UserError("An accepted or rejected booking revision is immutable.")
        return super().write(vals)

    def unlink(self):
        raise UserError("Booking revisions are history and cannot be deleted.")

    def action_open_accept_wizard(self):
        """Open the acceptance confirmation; it captures the booking's current revision now (review R1)."""
        self.ensure_one()
        if self.decision != "candidate":
            raise UserError("Only a candidate revision can be accepted.")
        return {
            "type": "ir.actions.act_window",
            "name": "Accept Revision",
            "res_model": EXPORT_REVISION_ACCEPT,
            "view_mode": "form",
            "target": "new",
            "context": {"default_revision_id": self.id},
        }

    def action_reject(self):
        """Reject a candidate; it stays as history."""
        for revision in self:
            error = export_actor_error(self.env, revision.company_id)
            if error:
                raise AccessError(error)
            if revision.decision != "candidate":
                raise UserError("Only a candidate revision can be rejected.")
            guard(revision).write({"decision": "rejected"})
            revision.booking_id.message_post(
                body=f"Revision {revision.source_revision_key} rejected by {self.env.user.name}",
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        return True


class PlasticosExportBookingRevisionAccept(models.TransientModel):
    """Confirmation of one revision acceptance (C05 review R1).

    The booking's current revision is captured when the confirmation opens and
    stored on the wizard; the reason is typed here, not on the revision form, so
    no form save reloads the expected value at click time. Confirm runs the
    frozen compare-and-set command: if another acceptance moved the booking in
    between, the answer is stale and nothing changes.
    """

    _name = "plasticos.export.booking.revision.accept"
    _description = "Accept Export Booking Revision"

    revision_id = fields.Many2one(EXPORT_REVISION, required=True, readonly=True, ondelete="cascade")
    booking_id = fields.Many2one(related="revision_id.booking_id", string="Booking")
    expected_current_revision_id = fields.Many2one(
        EXPORT_REVISION,
        string="Current Revision When Opened",
        readonly=True,
        ondelete="cascade",
        help="The booking's current revision when this confirmation opened. Acceptance compares against it.",
    )
    acceptance_reason = fields.Text(required=True, help="Why this source is accepted. Frozen in Acceptance Basis.")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        revision = self.env[EXPORT_REVISION].browse(values.get("revision_id") or 0).exists()
        if revision:
            values["expected_current_revision_id"] = revision.booking_id.current_revision_id.id or False
        return values

    def action_confirm(self):
        self.ensure_one()
        revision = self.revision_id
        outcome = revision.booking_id.action_accept_booking_revision(
            revision.id,
            self.expected_current_revision_id.id or False,
            f"wizard-accept:{self.id}",
            self.acceptance_reason or "",
        )
        if outcome["status"] not in (APPLIED, ALREADY_APPLIED):
            raise UserError(f"Revision not accepted ({outcome['status']}): {outcome.get('reason', '')}")
        return {"type": "ir.actions.act_window_close"}
