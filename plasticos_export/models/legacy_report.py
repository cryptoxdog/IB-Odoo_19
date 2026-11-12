"""The 43-column legacy booking report as a read-only projection (S10 OP10-E04, BRS-EXP-14-R011).

The legacy booking report is a comparison fixture, not a system of record. This
projection lays live Export and owner facts out under the 43 legacy headings,
one row per live cargo link, grouped by booking. It reads; it never imports or
writes. Every cell says where its value is missing or unknown instead of
leaving it blank:

- ``MISSING``: the owner record that would hold the value is absent, e.g. no
  buyer sale yet (BRS-EXP-01-R003) or no container bound.
- ``UNKNOWN``: the booking source does not state the value. A date or port is
  never inferred (BRS-EXP-02-R003, BRS-EXP-09-R002).
- ``NOT_RECORDED``: no owner records the fact in PlasticOS.
- ``NOT_MAPPED``: the legacy column's meaning still needs owner proof.
- ``PHASE_2``: the source belongs to Phase 2 (original ocean B/L).
- ``RESTRICTED``: the acting user may not read the owner record.
"""

from collections import OrderedDict

from odoo import api, models

from .owner_facts import NOT_RECORDED, RESTRICTED, VERIFIED_GROSS_MASS, evidence_verdict, readable

MISSING = "Missing"
UNKNOWN = "Unknown: not stated by the booking source"
NOT_MAPPED = "Not mapped: requires owner proof"
PHASE_2 = "Phase 2: original B/L"
UNASSIGNED_BUYER = "Missing: no buyer sale assigned"

# The 43 legacy headings in source order, and how Export fills each one.
# ``owner`` names who holds the fact; ``status`` is ``mapped``, ``not_recorded``,
# ``requires_owner_proof`` or ``phase_2``.
LEGACY_BOOKING_REPORT_COLUMNS = (
    ("Container No", "Logistics container journey", "mapped"),
    ("Booking No", "Export booking", "mapped"),
    ("Seal No", "Logistics container journey", "mapped"),
    ("Cutoff", "Export current accepted revision", "mapped"),
    ("POL", "Export current accepted revision", "mapped"),
    ("POD", "Export current accepted revision", "mapped"),
    ("PDLV", "Export revision additional terms", "mapped"),
    ("Carrier", "Export revision steamship line", "mapped"),
    ("Vessel", "Export revision additional terms", "mapped"),
    ("Voyage No", "Export revision additional terms", "mapped"),
    ("ETS", "Export revision additional terms", "mapped"),
    ("ETA", "Export revision additional terms", "mapped"),
    ("Grade", "Native purchase or sale line product", "mapped"),
    ("Weight LBS", "Stock or Logistics verified net weight", "not_recorded"),
    ("Supplier", "Native purchase order partner", "mapped"),
    ("Location", "Native Stock or Logistics pickup location", "not_recorded"),
    ("PO No", "Native purchase order", "mapped"),
    ("Source Wks", "Legacy provenance", "requires_owner_proof"),
    ("Customer", "Native sale order partner", "mapped"),
    ("SO No", "Native sale order", "mapped"),
    ("Invoice No", "Native Accounting posted invoice", "mapped"),
    ("Units", "Native Stock packages", "mapped"),
    ("PRVC", "Legacy column", "requires_owner_proof"),
    ("Rcv Dt", "Stock or Logistics verified receipt", "not_recorded"),
    ("Release No", "Legacy release reference", "requires_owner_proof"),
    ("Pickup No", "Logistics load", "mapped"),
    ("Shipping Notes", "Logistics load notes", "mapped"),
    ("Wt (MT)", "Derived from an accepted weight", "not_recorded"),
    ("Ship Dt", "Logistics actual pickup", "mapped"),
    ("Ship Time", "Logistics actual pickup", "mapped"),
    ("Rcvd Wt", "Stock or Logistics verified received weight", "not_recorded"),
    ("User", "Export cargo link author", "mapped"),
    ("PRA Status", "Owner not yet identified", "requires_owner_proof"),
    ("PRA Sent Date", "Owner not yet identified", "requires_owner_proof"),
    ("VGM", "Documents verified_gross_mass verdict", "mapped"),
    ("Eq Tare Wt", "Logistics container journey tare fact", "mapped"),
    ("BL No", "Documents original ocean B/L", "phase_2"),
    ("Invoice-User", "Native Accounting invoice author", "mapped"),
    ("Container-Ref", "Logistics container journey", "mapped"),
    ("Customer-Loc", "Native sale delivery address", "mapped"),
    ("PO-Ref", "Native purchase vendor reference", "mapped"),
    ("UDF-Date", "Legacy freeform date", "requires_owner_proof"),
    ("Doc-Cutoff", "Export revision additional terms", "mapped"),
)
LEGACY_BOOKING_REPORT_HEADINGS = tuple(heading for heading, _owner, _status in LEGACY_BOOKING_REPORT_COLUMNS)
# One name per heading, so code never repeats a heading as a bare string.
(
    H_CONTAINER_NO,
    H_BOOKING_NO,
    H_SEAL_NO,
    H_CUTOFF,
    H_POL,
    H_POD,
    H_PDLV,
    H_CARRIER,
    H_VESSEL,
    H_VOYAGE_NO,
    H_ETS,
    H_ETA,
    H_GRADE,
    H_WEIGHT_LBS,
    H_SUPPLIER,
    H_LOCATION,
    H_PO_NO,
    H_SOURCE_WKS,
    H_CUSTOMER,
    H_SO_NO,
    H_INVOICE_NO,
    H_UNITS,
    H_PRVC,
    H_RCV_DT,
    H_RELEASE_NO,
    H_PICKUP_NO,
    H_SHIPPING_NOTES,
    H_WT_MT,
    H_SHIP_DT,
    H_SHIP_TIME,
    H_RCVD_WT,
    H_USER,
    H_PRA_STATUS,
    H_PRA_SENT_DATE,
    H_VGM,
    H_EQ_TARE_WT,
    H_BL_NO,
    H_INVOICE_USER,
    H_CONTAINER_REF,
    H_CUSTOMER_LOC,
    H_PO_REF,
    H_UDF_DATE,
    H_DOC_CUTOFF,
) = LEGACY_BOOKING_REPORT_HEADINGS
_STATUS_MARKER = {"not_recorded": NOT_RECORDED, "requires_owner_proof": NOT_MAPPED, "phase_2": PHASE_2}
LIVE_LINK_STATES = ("committed", "held")


def _stated(value, marker=UNKNOWN):
    text = (str(value).strip() if value is not None and value is not False else "") or ""
    return text or marker


def _time(local, tz_name, precision):
    if precision == "unknown" or not local:
        return UNKNOWN
    if precision == "date":
        return f"{local} (date only)"
    return f"{local} {tz_name}" if tz_name else f"{local} (zone not stated)"


class PlasticosExportCargoLinkLegacyReport(models.Model):
    _inherit = "plasticos.export.booking.cargo.link"

    @api.model
    def _legacy_booking_report_groups(self, domain=None):
        """Live cargo links under the 43 legacy headings, grouped by booking number in booking order.

        Returns ``OrderedDict(booking label -> [row dict])``. Only records the
        acting user may read are included; nothing is written.
        """
        links = self.search([("state", "in", LIVE_LINK_STATES), *(domain or [])], order="booking_id, slot_id, id")
        groups = OrderedDict()
        for link in links:
            row = link._legacy_booking_report_row()
            groups.setdefault(row[H_BOOKING_NO], []).append(row)
        return groups

    def _legacy_booking_report_row(self):
        self.ensure_one()
        booking = self.booking_id
        revision = booking.current_revision_id
        terms = revision.additional_terms or {} if revision else {}
        slot = self.slot_id
        journey = slot.journey_id
        purchase = self.purchase_line_id
        sale = self.sale_line_id
        load = self.source_load_id
        row = {
            heading: _STATUS_MARKER.get(status, MISSING) for heading, _owner, status in LEGACY_BOOKING_REPORT_COLUMNS
        }
        row.update(
            {
                H_BOOKING_NO: booking.carrier_booking_no or MISSING,
                H_CUTOFF: _time(revision.cargo_cutoff_local, revision.cargo_cutoff_tz, revision.cargo_cutoff_precision)
                if revision
                else UNKNOWN,
                H_POL: _stated(revision.pol_text),
                H_POD: _stated(revision.pod_text),
                H_PDLV: _stated(terms.get("pdlv")),
                H_CARRIER: _stated(revision.steamship_line_id.display_name),
                H_VESSEL: _stated(terms.get("vessel")),
                H_VOYAGE_NO: _stated(terms.get("voyage")),
                H_ETS: _stated(terms.get("ets")),
                H_ETA: _stated(terms.get("eta")),
                H_DOC_CUTOFF: _stated(terms.get("doc_cutoff")),
                H_USER: self.create_uid.name or MISSING,
            }
        )
        row.update(self._legacy_container_cells(journey))
        # Container tare is a Logistics journey fact (S9); read live, never copied.
        row[H_EQ_TARE_WT] = slot.owner_container_tare
        row.update(self._legacy_purchase_cells(purchase))
        row.update(self._legacy_sale_cells(sale))
        row.update(self._legacy_load_cells(load))
        row[H_UNITS] = self._legacy_units()
        return row

    @staticmethod
    def _legacy_container_cells(journey):
        if not journey:
            return {H_CONTAINER_NO: MISSING, H_SEAL_NO: MISSING, H_CONTAINER_REF: MISSING}
        if not readable(journey):
            return {H_CONTAINER_NO: RESTRICTED, H_SEAL_NO: RESTRICTED, H_CONTAINER_REF: RESTRICTED}
        return {
            H_CONTAINER_NO: journey.iso_number or MISSING,
            H_SEAL_NO: journey.seal_number or MISSING,
            H_CONTAINER_REF: journey.display_name,
        }

    @staticmethod
    def _legacy_purchase_cells(line):
        if not line:
            return {H_SUPPLIER: MISSING, H_PO_NO: MISSING, H_PO_REF: MISSING, H_GRADE: MISSING}
        if not readable(line):
            return dict.fromkeys((H_SUPPLIER, H_PO_NO, H_PO_REF, H_GRADE), RESTRICTED)
        order = line.order_id
        return {
            H_SUPPLIER: order.partner_id.display_name or MISSING,
            H_PO_NO: order.name,
            H_PO_REF: order.partner_ref or MISSING,
            H_GRADE: line.product_id.display_name or MISSING,
        }

    def _legacy_sale_cells(self, line):
        if not line:
            return {
                H_CUSTOMER: UNASSIGNED_BUYER,
                H_SO_NO: UNASSIGNED_BUYER,
                H_CUSTOMER_LOC: UNASSIGNED_BUYER,
                H_INVOICE_NO: UNASSIGNED_BUYER,
                H_INVOICE_USER: UNASSIGNED_BUYER,
            }
        if not readable(line):
            return dict.fromkeys((H_CUSTOMER, H_SO_NO, H_CUSTOMER_LOC, H_INVOICE_NO, H_INVOICE_USER), RESTRICTED)
        order = line.order_id
        cells = {
            H_CUSTOMER: order.partner_id.display_name or MISSING,
            H_SO_NO: order.name,
            H_CUSTOMER_LOC: order.partner_shipping_id.display_name or MISSING,
        }
        if not self.purchase_line_id:
            cells[H_GRADE] = line.product_id.display_name or MISSING
        invoices = self._posted_invoices(line)
        if invoices == RESTRICTED:
            cells.update({H_INVOICE_NO: RESTRICTED, H_INVOICE_USER: RESTRICTED})
        else:
            moves = line.invoice_lines.move_id.filtered(lambda move: move.state == "posted").sorted("id")
            cells[H_INVOICE_NO] = ", ".join(moves.mapped("name")) or MISSING
            cells[H_INVOICE_USER] = ", ".join(moves.mapped("create_uid.name")) or MISSING
        return cells

    @staticmethod
    def _legacy_load_cells(load):
        if not load:
            return {H_PICKUP_NO: MISSING, H_SHIPPING_NOTES: MISSING, H_SHIP_DT: MISSING, H_SHIP_TIME: MISSING}
        if not readable(load):
            return dict.fromkeys((H_PICKUP_NO, H_SHIPPING_NOTES, H_SHIP_DT, H_SHIP_TIME, H_VGM), RESTRICTED)
        picked = load.actual_pickup_at
        return {
            H_PICKUP_NO: load.name,
            H_SHIPPING_NOTES: load.notes or MISSING,
            H_SHIP_DT: picked.strftime("%Y-%m-%d") if picked else MISSING,
            H_SHIP_TIME: picked.strftime("%H:%M UTC") if picked else MISSING,
            H_VGM: evidence_verdict(load.env, load, VERIFIED_GROSS_MASS),
        }

    def _legacy_units(self):
        line = self.stock_move_line_id
        if not line:
            return MISSING
        if not readable(line):
            return RESTRICTED
        packages = line.result_package_id
        return str(len(packages)) if packages else MISSING
