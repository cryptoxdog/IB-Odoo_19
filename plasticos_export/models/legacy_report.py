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
    ("Eq Tare Wt", "Container tare evidence", "not_recorded"),
    ("BL No", "Documents original ocean B/L", "phase_2"),
    ("Invoice-User", "Native Accounting invoice author", "mapped"),
    ("Container-Ref", "Logistics container journey", "mapped"),
    ("Customer-Loc", "Native sale delivery address", "mapped"),
    ("PO-Ref", "Native purchase vendor reference", "mapped"),
    ("UDF-Date", "Legacy freeform date", "requires_owner_proof"),
    ("Doc-Cutoff", "Export revision additional terms", "mapped"),
)
LEGACY_BOOKING_REPORT_HEADINGS = tuple(heading for heading, _owner, _status in LEGACY_BOOKING_REPORT_COLUMNS)
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
            groups.setdefault(row["Booking No"], []).append(row)
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
                "Booking No": booking.carrier_booking_no or MISSING,
                "Cutoff": _time(revision.cargo_cutoff_local, revision.cargo_cutoff_tz, revision.cargo_cutoff_precision)
                if revision
                else UNKNOWN,
                "POL": _stated(revision.pol_text),
                "POD": _stated(revision.pod_text),
                "PDLV": _stated(terms.get("pdlv")),
                "Carrier": _stated(revision.steamship_line_id.display_name),
                "Vessel": _stated(terms.get("vessel")),
                "Voyage No": _stated(terms.get("voyage")),
                "ETS": _stated(terms.get("ets")),
                "ETA": _stated(terms.get("eta")),
                "Doc-Cutoff": _stated(terms.get("doc_cutoff")),
                "User": self.create_uid.name or MISSING,
            }
        )
        row.update(self._legacy_container_cells(journey))
        row.update(self._legacy_purchase_cells(purchase))
        row.update(self._legacy_sale_cells(sale))
        row.update(self._legacy_load_cells(load))
        row["Units"] = self._legacy_units()
        return row

    @staticmethod
    def _legacy_container_cells(journey):
        if not journey:
            return {"Container No": MISSING, "Seal No": MISSING, "Container-Ref": MISSING}
        if not readable(journey):
            return {"Container No": RESTRICTED, "Seal No": RESTRICTED, "Container-Ref": RESTRICTED}
        return {
            "Container No": journey.iso_number or MISSING,
            "Seal No": journey.seal_number or MISSING,
            "Container-Ref": journey.display_name,
        }

    @staticmethod
    def _legacy_purchase_cells(line):
        if not line:
            return {"Supplier": MISSING, "PO No": MISSING, "PO-Ref": MISSING, "Grade": MISSING}
        if not readable(line):
            return dict.fromkeys(("Supplier", "PO No", "PO-Ref", "Grade"), RESTRICTED)
        order = line.order_id
        return {
            "Supplier": order.partner_id.display_name or MISSING,
            "PO No": order.name,
            "PO-Ref": order.partner_ref or MISSING,
            "Grade": line.product_id.display_name or MISSING,
        }

    def _legacy_sale_cells(self, line):
        if not line:
            return {
                "Customer": UNASSIGNED_BUYER,
                "SO No": UNASSIGNED_BUYER,
                "Customer-Loc": UNASSIGNED_BUYER,
                "Invoice No": UNASSIGNED_BUYER,
                "Invoice-User": UNASSIGNED_BUYER,
            }
        if not readable(line):
            return dict.fromkeys(("Customer", "SO No", "Customer-Loc", "Invoice No", "Invoice-User"), RESTRICTED)
        order = line.order_id
        cells = {
            "Customer": order.partner_id.display_name or MISSING,
            "SO No": order.name,
            "Customer-Loc": order.partner_shipping_id.display_name or MISSING,
        }
        if not self.purchase_line_id:
            cells["Grade"] = line.product_id.display_name or MISSING
        invoices = self._posted_invoices(line)
        if invoices == RESTRICTED:
            cells.update({"Invoice No": RESTRICTED, "Invoice-User": RESTRICTED})
        else:
            moves = line.invoice_lines.move_id.filtered(lambda move: move.state == "posted").sorted("id")
            cells["Invoice No"] = ", ".join(moves.mapped("name")) or MISSING
            cells["Invoice-User"] = ", ".join(moves.mapped("create_uid.name")) or MISSING
        return cells

    @staticmethod
    def _legacy_load_cells(load):
        if not load:
            return {"Pickup No": MISSING, "Shipping Notes": MISSING, "Ship Dt": MISSING, "Ship Time": MISSING}
        if not readable(load):
            return dict.fromkeys(("Pickup No", "Shipping Notes", "Ship Dt", "Ship Time", "VGM"), RESTRICTED)
        picked = load.actual_pickup_at
        return {
            "Pickup No": load.name,
            "Shipping Notes": load.notes or MISSING,
            "Ship Dt": picked.strftime("%Y-%m-%d") if picked else MISSING,
            "Ship Time": picked.strftime("%H:%M UTC") if picked else MISSING,
            "VGM": evidence_verdict(load.env, load, VERIFIED_GROSS_MASS),
        }

    def _legacy_units(self):
        line = self.stock_move_line_id
        if not line:
            return MISSING
        if not readable(line):
            return RESTRICTED
        packages = line.result_package_id
        return str(len(packages)) if packages else MISSING
