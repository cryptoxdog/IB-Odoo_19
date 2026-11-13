"""Export's operation obligations on the Documents owner (C05 amendments E1, E2).

Core Documents declares no operation obligation and, by default, lets every
declared obligation withhold every physical operation. Export is the owner of
the export obligations, so it declares them here and states which of them gates
which Logistics operation (BRS-EXP-03-R002, BRS-EXP-03-R007). Documents still
decides whether exact current evidence meets an obligation; Export only says
which obligation applies. Obligations other owners declare keep the Documents
default: this narrowing touches Export's own kinds only.

Export decision (C05-SCOPE-1):

- ``booking_confirmation``: the carrier's original booking confirmation. A load
  is not scheduled, dispatched or sent its packet or carrier documents on a
  booking whose accepted confirmation evidence is no longer current.
- ``verified_gross_mass``: VGM evidence. It gates only carrier documents, the
  one operation that hands weights to the carrier.
- ``loading_photos`` and ``terminal_ingate_receipt``: they prove an event that
  already happened (loading; terminal acceptance from the in-gate receipt the
  trucker sends with the scale tickets, operator decision 2026-11-11). They
  never gate a new physical instruction.
"""

from odoo import api, models

BOOKING_CONFIRMATION = "booking_confirmation"
VERIFIED_GROSS_MASS = "verified_gross_mass"
LOADING_PHOTOS = "loading_photos"
TERMINAL_INGATE_RECEIPT = "terminal_ingate_receipt"

EXPORT_OBLIGATION_KINDS = frozenset(
    {BOOKING_CONFIRMATION, VERIFIED_GROSS_MASS, LOADING_PHOTOS, TERMINAL_INGATE_RECEIPT}
)

# Logistics operation kind -> the Export obligations whose stale evidence withholds it.
EXPORT_RELEASE_OBLIGATIONS = {
    "schedule": frozenset({BOOKING_CONFIRMATION}),
    "dispatch": frozenset({BOOKING_CONFIRMATION}),
    "dispatch_packet": frozenset({BOOKING_CONFIRMATION}),
    "carrier_document": frozenset({BOOKING_CONFIRMATION, VERIFIED_GROSS_MASS}),
}


class PlasticosDocumentExportObligations(models.Model):
    _inherit = "plasticos.document"

    @api.model
    def _scoped_obligation_kinds(self):
        return super()._scoped_obligation_kinds() | EXPORT_OBLIGATION_KINDS

    @api.model
    def _release_obligations(self, operation_kind):
        """Other owners' obligations keep their default; Export's follow its own mapping."""
        inherited = super()._release_obligations(operation_kind)
        return (inherited - EXPORT_OBLIGATION_KINDS) | (
            inherited & EXPORT_RELEASE_OBLIGATIONS.get(operation_kind, frozenset())
        )
