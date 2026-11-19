"""Export's downstream extensions of the Logistics, Linda and Documents owners.

Ordinary ``_inherit`` only: no monkey patch, plugin registry, reverse foreign
key or direct SMTP. Upstream modules never import Export; without it the hooks
below simply do not exist and the upstream defaults apply.

- Linda: Export registers the ``booking`` typed source resolver and its booking
  model for reply attribution. The resolver authorizes the caller (E3) before it
  proves the accepted revision, the audience and the original attachments, so
  an unauthorized ``request_booking_correspondence`` is ``not_available``.
- Logistics: a load that feeds a held, retired or cancelled booking slot may not
  receive a new physical instruction (BRS-EXP-11-R011). Actual events are never
  routed here.
- Documents: an Export booking may carry operation-scoped evidence.
"""

from odoo import api, models
from odoo.exceptions import AccessError
from odoo.tools import email_normalize

from .booking import (
    APPLIED,
    BLOCKED,
    CANCELLED,
    EXPORT_BOOKING,
    EXPORT_CARGO_LINK,
    NOT_AVAILABLE,
    STALE,
    export_actor_error,
)
from .document_inherit import BOOKING_CONFIRMATION, EXPORT_RELEASE_OBLIGATIONS

SOURCE_BOOKING = "booking"
NOT_STATED = "not stated"
# Confirmed cargo a physical instruction follows. A proposal holds nothing physical; it is
# deliberately narrower than booking_allocation.SOURCE_CLAIM_LINK_STATES (allocation guard).
PHYSICAL_HOLD_LINK_STATES = ("committed", "held")


def _plain(text, **values):
    """Untranslated party-facing text: a snapshot must not change with the worker's language (Linda rule)."""
    return text % values if values else text


def _time_label(local, tz_name, precision):
    """A source time as stated, with its zone and precision. Nothing is converted or guessed."""
    if precision == "unknown" or not local:
        return NOT_STATED
    if precision == "date":
        return _plain("%(day)s (date only)", day=local)
    return f"{local} {tz_name}" if tz_name else _plain("%(time)s (zone not stated)", time=local)


class PlasticosLogisticsRequestExport(models.Model):
    _inherit = "plasticos.logistics.request"

    @api.model
    def _linda_source_resolvers(self):
        resolvers = super()._linda_source_resolvers()
        resolvers[SOURCE_BOOKING] = self._linda_resolve_export_booking
        return resolvers

    @api.model
    def _linda_source_models(self):
        models_map = super()._linda_source_models()
        models_map[EXPORT_BOOKING] = SOURCE_BOOKING
        return models_map

    @api.model
    def _export_booking_audiences(self, booking):
        """Who may receive a booking notice: the carrier, the issuer and suppliers of live cargo."""
        links = (
            self.env[EXPORT_CARGO_LINK]
            .sudo()  # sudo: audience is derived from the booking's own live cargo; Linda reads no PO content
            .search([("booking_id", "=", booking.id), ("state", "in", PHYSICAL_HOLD_LINK_STATES)])
        )
        return booking.carrier_id | booking.issuer_id | links.purchase_line_id.order_id.partner_id

    @api.model
    def _export_booking_purpose_error(self, revision, purpose):
        cancelled = revision._stated_status() == CANCELLED
        if purpose == "booking_cancel":
            return False if cancelled else "booking_not_cancelled"
        if cancelled:
            return "booking_cancelled"
        if purpose == "booking_issue" and revision.supersedes_revision_id:
            return "booking_already_issued_use_amend"
        if purpose == "booking_amend" and not revision.supersedes_revision_id:
            return "no_prior_revision_to_amend"
        return False

    @api.model
    def _linda_resolve_export_booking(self, purpose, res_id, audience_partner, **params):
        """Prove one booking notice from the current accepted revision (resolver contract of Linda)."""
        recheck = params.get("recheck")
        Booking = self.env[EXPORT_BOOKING]
        if recheck:
            # The request was authorized when it was recorded; the mail queue rechecks the source.
            Booking = Booking.sudo()  # sudo: send-time recheck by the mail queue, read-only
        booking = Booking.browse(int(res_id or 0)).exists()
        if not booking:
            return {"status": NOT_AVAILABLE, "reason": "booking_not_found"}
        if not recheck:
            # E3: role, then record access, then company, before any booking field is read.
            if export_actor_error(self.env):
                return {"status": NOT_AVAILABLE, "reason": "not_authorized"}
            try:
                booking.check_access("write")
            except AccessError:
                return {"status": NOT_AVAILABLE, "reason": "not_authorized"}
            if export_actor_error(self.env, booking.company_id) or booking.company_id not in self.env.companies:
                return {"status": NOT_AVAILABLE, "reason": "not_authorized"}
        revision = booking.current_revision_id
        if not revision:
            return {"status": BLOCKED, "reason": "no_accepted_revision"}
        accepted = params.get("accepted_revision_id")
        if accepted and accepted != revision.id:
            return {"status": STALE, "reason": "revision_not_current"}
        expected_key = params.get("revision_key")
        revision_key = f"booking_revision:{revision.id}:{revision.source_revision_key}"
        if expected_key and expected_key != revision_key:
            return {"status": STALE, "reason": "revision_not_current"}
        purpose_error = self._export_booking_purpose_error(revision, purpose)
        if purpose_error:
            return {"status": BLOCKED, "reason": purpose_error}
        if audience_partner not in self._export_booking_audiences(booking):
            return {"status": BLOCKED, "reason": "audience_not_permitted"}
        recipient = email_normalize(audience_partner.email or "") or ""
        number = booking.carrier_booking_no or ""
        equipment = revision.equipment_summary or NOT_STATED
        lines = [
            (_plain("Booking No."), number),
            (_plain("Steamship line"), revision.steamship_line_id.name or NOT_STATED),
            (_plain("Port of loading"), revision.pol_text or NOT_STATED),
            (_plain("Port of discharge"), revision.pod_text or NOT_STATED),
            (_plain("Earliest return date"), _time_label(revision.erd_local, revision.erd_tz, revision.erd_precision)),
            (
                _plain("Cargo cutoff"),
                _time_label(revision.cargo_cutoff_local, revision.cargo_cutoff_tz, revision.cargo_cutoff_precision),
            ),
            (_plain("Equipment"), equipment),
            (_plain("Revision"), revision.source_revision_key),
        ]
        subjects = {
            "booking_issue": _plain("Booking %(number)s confirmed", number=number),
            "booking_amend": _plain("Booking %(number)s amended", number=number),
            "booking_cancel": _plain("Booking %(number)s cancelled", number=number),
        }
        paragraphs = {
            "booking_issue": [
                _plain("The carrier confirmed booking %(number)s. The current terms are below.", number=number)
            ],
            "booking_amend": [
                _plain("Booking %(number)s changed. These terms replace the ones we sent before.", number=number)
            ],
            "booking_cancel": [
                _plain("Booking %(number)s was cancelled by its source. Do not load against it.", number=number)
            ],
        }
        snapshot = dict(
            reference=number,
            subject=subjects[purpose],
            paragraphs=paragraphs[purpose],
            lines=lines,
            closing=[booking.company_id.name or ""],
        )
        return {
            "status": APPLIED,
            "company": booking.company_id,
            "partner": audience_partner,
            "recipient_email": recipient,
            "model": EXPORT_BOOKING,
            "res_id": booking.id,
            "revision_key": revision_key,
            "snapshot": snapshot,
            "attachment_ids": revision._original_attachment_ids(),
            "source_fingerprint": revision._notice_fingerprint(),
        }

    def _export_link(self, load):
        """The unreleased cargo link that sets this load's export window."""
        link_model = self.env[EXPORT_CARGO_LINK]
        link = link_model.search(
            [("source_load_id", "=", load.id), ("state", "!=", "released")],
            order="id desc",
            limit=1,
        )
        if not link and load.sale_order_id:
            link = link_model.search(
                [("sale_order_id", "=", load.sale_order_id.id), ("state", "!=", "released")],
                order="id desc",
                limit=1,
            )
        return link


class PlasticosLoadExport(models.Model):
    _inherit = "plasticos.load"

    def _physical_release_errors(self, operation_kind):
        """Export booking holds on the Logistics release guard (BRS-EXP-11-R011, BRS-EXP-14-R016).

        A load committed as cargo of a slot that is held, retired, or on a
        cancelled booking may not receive a new physical instruction until an
        owner decides. Only live links of this exact load count.

        The carrier's booking confirmation is evidence on the booking, not on
        the load, so the Documents load guard never reads it. For the operation
        kinds ``EXPORT_RELEASE_OBLIGATIONS`` maps to ``booking_confirmation``, a
        booking whose accepted confirmation was decided and is no longer current
        withholds the load (C05-SCOPE-1). Evidence that was never decided, or
        never existed, withholds nothing here.
        """
        self.ensure_one()
        errors = super()._physical_release_errors(operation_kind)
        links = (
            self.env[EXPORT_CARGO_LINK]
            .sudo()  # sudo: the guard must see every live Export link on this load; it only reads
            .search([("source_load_id", "=", self.id), ("state", "in", PHYSICAL_HOLD_LINK_STATES)], order="id ASC")
        )
        for link in links:
            slot = link.slot_id.with_context(active_test=False)
            booking = slot.booking_id
            label = f"{booking.carrier_booking_no or booking.display_name} slot {slot.slot_key}"
            if booking.display_state == "cancelled":
                errors.append(f"Load {self.name}: export booking {label} is cancelled.")
            elif not slot.active:
                errors.append(f"Load {self.name}: export booking {label} was retired by a later revision.")
            elif link.state == "held" or slot.hold_reason:
                errors.append(f"Load {self.name}: export booking {label} is held: {slot.hold_reason or 'cargo held'}.")
        if BOOKING_CONFIRMATION in EXPORT_RELEASE_OBLIGATIONS.get(operation_kind, ()):
            for booking in links.slot_id.booking_id:
                for revision in self._export_stale_booking_confirmations(booking):
                    errors.append(
                        f"Load {self.name}: the accepted {BOOKING_CONFIRMATION} evidence of export booking "
                        f"{booking.carrier_booking_no or booking.display_name} for revision {revision} "
                        "is no longer current."
                    )
        return errors

    @api.model
    def _export_stale_booking_confirmations(self, booking):
        """Operation revisions whose decided booking-confirmation evidence on ``booking`` is no longer current.

        The same rule the Documents load guard applies to evidence on a load:
        only current, not superseded accepted rows count (a superseded row is
        history, its successor decides), and only a revision with a decided
        (verified or overridden) row can be stale. Whether that revision is
        still proven is the Documents owner's answer, read through its frozen
        ``get_scoped_evidence_verdict`` command; Export decides nothing about
        the evidence itself. The verdict is per operation revision, so one
        eligible row of a revision keeps that revision current.
        """
        # The guard must see every accepted confirmation row on this booking, whoever releases the load.
        Document = self.env["plasticos.document"].sudo()  # sudo: read-only guard; the verdict command writes nothing
        rows = Document.search(
            [
                ("association_state", "=", "accepted"),
                ("res_model", "=", EXPORT_BOOKING),
                ("res_id", "=", booking.id),
                ("obligation_kind", "=", BOOKING_CONFIRMATION),
                ("subject_company_id", "=", booking.company_id.id),
            ],
            order="id ASC",
        ).filtered(lambda row: row.is_current and not row.superseded_by)
        decided = rows.filtered(lambda row: row.verified or row.override)
        stale = []
        for revision in sorted(set(decided.mapped("operation_revision_key"))):
            verdict = Document.get_scoped_evidence_verdict(
                booking.company_id.id, EXPORT_BOOKING, booking.id, BOOKING_CONFIRMATION, revision
            )
            if verdict.get("status") == STALE:
                stale.append(revision)
        return stale


class PlasticosDocumentExportSubject(models.Model):
    _inherit = "plasticos.document"

    @api.model
    def _scoped_subject_models(self):
        """An Export booking may carry operation evidence, e.g. its booking confirmation."""
        return super()._scoped_subject_models() | {EXPORT_BOOKING}
