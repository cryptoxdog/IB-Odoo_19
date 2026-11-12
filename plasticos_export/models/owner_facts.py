"""Owner facts shown on Export slots and cargo links (S10, OP10-E01, OP10-E02).

Export binds cargo to its owners and displays their facts; it stores none of
them (BRS-EXP-01-R002, POS-INV-02). Every value below is computed live, as the
acting user, from the owner's own record:

- Documents (``plasticos_documents``): the current evidence verdict of each
  Export obligation, through the frozen ``get_scoped_evidence_verdict`` command.
- Logistics (``plasticos_logistics``): the load's freight status.
- Native Stock: the exact stock move line, its destination package, the
  package's recorded shipping weight and its package type's tare weight.
- Native Accounting: posted customer invoices and vendor bills of the exact
  sale and purchase lines.

A value the user may not read is shown as ``RESTRICTED``, never as an empty
value or a zero (BRS-EXP-14-R022). A value no owner records is shown as such.
Package weights are summed as recorded and are labelled as package totals: they
are never a certified VGM or a settlement quantity (BRS-EXP-07-R006). The VGM is
the Documents verdict of the ``verified_gross_mass`` obligation.

The commercial trade label (BRS-EXP-02-R006) is the one fact this file adds to
Export: the recycler usage quoted for a cargo (FOB, FAS, CNF). It is kept apart
from the formal Incoterm of the native orders, which Export shows and never
writes.
"""

from odoo import api, fields, models
from odoo.exceptions import AccessError

from .booking import AMBIGUOUS, APPLIED, BLOCKED, EXPORT_CARGO_LINK, NOT_AVAILABLE, STALE, guarded
from .document_inherit import BOOKING_CONFIRMATION, LOADING_PHOTOS, TERMINAL_INGATE_RECEIPT, VERIFIED_GROSS_MASS

PLASTICOS_DOCUMENT = "plasticos.document"
PLASTICOS_LOAD = "plasticos.load"
ACCOUNT_MOVE = "account.move"

RESTRICTED = "Restricted: you have no access to this owner record"
NOT_RECORDED = "Not recorded by its owner"
NO_CONTAINER_TARE = "Not recorded: no owner records container tare"

# Display order of the Export obligations and their labels.
OBLIGATION_LABELS = (
    (BOOKING_CONFIRMATION, "Booking confirmation"),
    (VERIFIED_GROSS_MASS, "VGM"),
    (LOADING_PHOTOS, "Loading photos"),
    (TERMINAL_INGATE_RECEIPT, "Terminal in-gate receipt"),
)
VERDICT_LABELS = {
    APPLIED: "verified and current",
    BLOCKED: "awaits verification",
    STALE: "stale",
    AMBIGUOUS: "ambiguous",
    NOT_AVAILABLE: "not available",
}
MISSING_EVIDENCE = "missing"

# BRS-EXP-02-R006: recycler trade usage, never an ICC Incoterm.
COMMERCIAL_TRADE_LABELS = [
    ("fob", "FOB (trade usage: buyer pickup)"),
    ("fas", "FAS (trade usage: seller freight to the agreed port or rail)"),
    ("cnf", "CNF / C&F (trade usage)"),
]


def readable(record):
    """True when the acting user may read ``record`` (an empty record is readable)."""
    if not record:
        return True
    try:
        record.check_access("read")
    except AccessError:
        return False
    return True


def evidence_verdict(env, subject, kind):
    """The Documents verdict of one Export obligation on one subject, as a label.

    The newest accepted evidence row names the operation revision; Documents
    then decides whether that revision is proven. Rows the user may not read
    are reported as restricted, not as missing evidence.
    """
    Document = env[PLASTICOS_DOCUMENT]
    domain = [
        ("res_model", "=", subject._name),
        ("res_id", "=", subject.id),
        ("obligation_kind", "=", kind),
        ("association_state", "=", "accepted"),
    ]
    try:
        row = Document.search(domain, order="id DESC", limit=1)
    except AccessError:
        return RESTRICTED
    if not row:
        hidden = Document.sudo().search_count(domain, limit=1)  # sudo: count only, to label hidden rows restricted
        if hidden:
            return RESTRICTED
        return MISSING_EVIDENCE
    try:
        verdict = Document.get_scoped_evidence_verdict(
            subject.company_id.id, subject._name, subject.id, kind, row.operation_revision_key
        )
    except AccessError:
        return RESTRICTED
    label = VERDICT_LABELS.get(verdict.get("status"), verdict.get("status") or MISSING_EVIDENCE)
    reason = verdict.get("reason")
    return f"{label} ({reason})" if reason and verdict.get("status") != APPLIED else label


def weight_unit(env):
    return env["product.template"]._get_weight_uom_name_from_ir_config_parameter()


def package_lines(packages, unit):
    """One line per native package: its recorded shipping weight and its type's tare."""
    rows = []
    for package in packages:
        weight = f"{package.shipping_weight:g} {unit}" if package.shipping_weight else NOT_RECORDED
        tare = (
            f"{package.package_type_id.base_weight:g} {unit}"
            if package.package_type_id and package.package_type_id.base_weight
            else NOT_RECORDED
        )
        rows.append(f"{package.display_name}: shipping weight {weight}; package tare {tare}")
    return rows


class PlasticosExportCargoLinkOwnerFacts(models.Model):
    _inherit = "plasticos.export.booking.cargo.link"

    commercial_trade_label = fields.Selection(
        COMMERCIAL_TRADE_LABELS,
        string="Commercial Trade Label",
        help="The recycler trade usage quoted for this cargo. It is not an ICC Incoterm "
        "and is never written into an order's Incoterm (BRS-EXP-02-R006).",
    )
    commercial_trade_label_quote = fields.Char(
        string="Quoted Trade Terms",
        help="The trade terms as the quote states them, e.g. the agreed port or rail ramp.",
    )
    sale_incoterm_display = fields.Char(
        compute="_compute_owner_order_facts", string="Customer SO Incoterm", compute_sudo=False
    )
    purchase_incoterm_display = fields.Char(
        compute="_compute_owner_order_facts", string="Supplier PO Incoterm", compute_sudo=False
    )
    owner_invoice_display = fields.Text(
        compute="_compute_owner_order_facts", string="Posted Invoices (Accounting)", compute_sudo=False
    )
    owner_freight_status = fields.Char(
        compute="_compute_owner_load_facts", string="Freight Status (Logistics)", compute_sudo=False
    )
    owner_document_verdict = fields.Text(
        compute="_compute_owner_load_facts", string="Document Verdict (Documents)", compute_sudo=False
    )
    owner_stock_move_display = fields.Char(
        compute="_compute_owner_stock_facts", string="Stock Move (Stock)", compute_sudo=False
    )
    owner_package_display = fields.Text(
        compute="_compute_owner_stock_facts", string="Package (Stock)", compute_sudo=False
    )

    # ── native orders and accounting ─────────────────────────

    @staticmethod
    def _incoterm_label(order, field_name):
        if not order:
            return False
        if not readable(order):
            return RESTRICTED
        if field_name not in order._fields:
            return NOT_RECORDED
        term = order[field_name]
        if not term:
            return "No Incoterm on the order"
        place_field = "incoterm_location" if "incoterm_location" in order._fields else False
        place = order[place_field] if place_field else False
        label = term.code or term.name
        return f"{label} {place}" if place else label

    @staticmethod
    def _posted_invoices(lines):
        """Posted invoice identities and payment state of exact order lines, or a marker."""
        if not lines:
            return False
        if not readable(lines):
            return RESTRICTED
        try:
            moves = lines.invoice_lines.move_id
            moves.check_access("read")
            posted = moves.filtered(lambda move: move.state == "posted").sorted("id")
            rows = [f"{move.name} posted, payment {move.payment_state}" for move in posted]
        except AccessError:
            return RESTRICTED
        return "\n".join(rows) or "No posted invoice"

    @api.depends_context("uid", "allowed_company_ids")
    def _compute_owner_order_facts(self):
        for link in self:
            sale_order = link.sale_line_id.order_id if readable(link.sale_line_id) else False
            purchase_order = link.purchase_line_id.order_id if readable(link.purchase_line_id) else False
            link.sale_incoterm_display = (
                self._incoterm_label(sale_order, "incoterm") if sale_order is not False else RESTRICTED
            )
            link.purchase_incoterm_display = (
                self._incoterm_label(purchase_order, "incoterm_id") if purchase_order is not False else RESTRICTED
            )
            invoices = [
                f"{side}: {text}"
                for side, text in (
                    ("Customer invoices", self._posted_invoices(link.sale_line_id)),
                    ("Vendor bills", self._posted_invoices(link.purchase_line_id)),
                )
                if text
            ]
            link.owner_invoice_display = "\n".join(invoices) or False

    # ── Logistics load and Documents ─────────────────────────

    @api.depends_context("uid", "allowed_company_ids")
    def _compute_owner_load_facts(self):
        for link in self:
            load = link.source_load_id
            if not load:
                link.owner_freight_status = False
                link.owner_document_verdict = False
                continue
            if not readable(load):
                link.owner_freight_status = RESTRICTED
                link.owner_document_verdict = RESTRICTED
                continue
            state = dict(load._fields["state"]._description_selection(self.env)).get(load.state, load.state)
            link.owner_freight_status = f"{load.name}: {state}"
            link.owner_document_verdict = "\n".join(
                f"{label}: {evidence_verdict(self.env, load, kind)}" for kind, label in OBLIGATION_LABELS
            )

    # ── native Stock ─────────────────────────────────────────

    @api.depends_context("uid", "allowed_company_ids")
    def _compute_owner_stock_facts(self):
        unit = weight_unit(self.env)
        for link in self:
            line = link.stock_move_line_id
            if not line:
                link.owner_stock_move_display = False
                link.owner_package_display = False
                continue
            if not readable(line):
                link.owner_stock_move_display = RESTRICTED
                link.owner_package_display = RESTRICTED
                continue
            state = dict(line._fields["state"]._description_selection(self.env)).get(line.state, line.state)
            reference = line.reference or line.move_id.reference or line.display_name
            link.owner_stock_move_display = f"{reference}: {state}, {line.quantity:g} {line.product_uom_id.name or ''}"
            package = line.result_package_id
            if not package:
                link.owner_package_display = "No package recorded by Stock"
            elif not readable(package):
                link.owner_package_display = RESTRICTED
            else:
                link.owner_package_display = "\n".join(package_lines(package, unit))

    # ── commercial trade label ───────────────────────────────

    def action_open_trade_label(self):
        """Open the trade-label dialog: the label is editable there, every command-owned field is not."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Commercial Trade Label",
            "res_model": EXPORT_CARGO_LINK,
            "res_id": self.id,
            "view_mode": "form",
            "views": [(self.env.ref("plasticos_export.view_export_cargo_link_trade_label_form").id, "form")],
            "target": "new",
        }

    def write(self, vals):
        before = {}
        if not guarded(self.env) and {"commercial_trade_label", "commercial_trade_label_quote"} & set(vals):
            before = {link.id: (link.commercial_trade_label, link.commercial_trade_label_quote) for link in self}
        result = super().write(vals)
        labels = dict(COMMERCIAL_TRADE_LABELS)
        for link in self.filtered(lambda rec: rec.id in before):
            if before[link.id] == (link.commercial_trade_label, link.commercial_trade_label_quote):
                continue
            label = labels.get(link.commercial_trade_label) or "none"
            quote = link.commercial_trade_label_quote or "no quoted terms"
            link.booking_id.message_post(
                body=f"Cargo {link.allocation_key}: commercial trade label set to {label} ({quote}). "
                "The order Incoterms are unchanged.",
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        return result


class PlasticosExportSlotOwnerFacts(models.Model):
    _inherit = "plasticos.export.booking.slot"

    owner_package_summary = fields.Text(
        compute="_compute_owner_package_summary", string="Packages (Stock)", compute_sudo=False
    )
    owner_vgm_verdict = fields.Text(
        compute="_compute_owner_package_summary", string="VGM (Documents)", compute_sudo=False
    )
    owner_container_tare = fields.Char(
        compute="_compute_owner_package_summary", string="Container Tare", compute_sudo=False
    )

    def _live_links(self):
        self.ensure_one()
        return self.cargo_link_ids.filtered(lambda link: link.state in ("committed", "held"))

    @api.depends_context("uid", "allowed_company_ids")
    def _compute_owner_package_summary(self):
        unit = weight_unit(self.env)
        for slot in self:
            links = slot._live_links()
            slot.owner_container_tare = NO_CONTAINER_TARE
            move_lines = links.stock_move_line_id
            if not readable(move_lines):
                slot.owner_package_summary = RESTRICTED
            else:
                packages = move_lines.result_package_id
                if not packages:
                    slot.owner_package_summary = "No package recorded by Stock"
                elif not readable(packages):
                    slot.owner_package_summary = RESTRICTED
                else:
                    slot.owner_package_summary = self._package_summary(packages, unit)
            loads = links.source_load_id
            if not loads:
                slot.owner_vgm_verdict = "No Logistics load committed"
            elif not readable(loads):
                slot.owner_vgm_verdict = RESTRICTED
            else:
                slot.owner_vgm_verdict = "\n".join(
                    f"{load.name}: {evidence_verdict(self.env, load, VERIFIED_GROSS_MASS)}"
                    for load in loads.sorted("id")
                )

    @api.model
    def _package_summary(self, packages, unit):
        """Recorded package totals; an unrecorded weight makes the total explicitly incomplete."""
        weighed = packages.filtered("shipping_weight")
        tared = packages.filtered(lambda package: package.package_type_id.base_weight)
        total = sum(weighed.mapped("shipping_weight"))
        tare = sum(tared.mapped("package_type_id.base_weight"))
        head = [
            f"Packages: {len(packages)}",
            f"Recorded shipping weight: {total:g} {unit}"
            + ("" if len(weighed) == len(packages) else f" (incomplete: {len(packages) - len(weighed)} not recorded)"),
            f"Package tare: {tare:g} {unit}"
            + ("" if len(tared) == len(packages) else f" (incomplete: {len(packages) - len(tared)} not recorded)"),
            "Package totals are not a certified VGM.",
        ]
        return "\n".join(head + package_lines(packages.sorted("id"), unit))


class PlasticosExportBookingOwnerFacts(models.Model):
    _inherit = "plasticos.export.booking"

    owner_booking_confirmation_verdict = fields.Char(
        compute="_compute_owner_booking_confirmation_verdict",
        string="Booking Confirmation (Documents)",
        compute_sudo=False,
    )

    @api.depends_context("uid", "allowed_company_ids")
    def _compute_owner_booking_confirmation_verdict(self):
        for booking in self:
            booking.owner_booking_confirmation_verdict = (
                evidence_verdict(self.env, booking, BOOKING_CONFIRMATION) if booking.id else False
            )

    def action_open_manual_candidate(self):
        """Open the manual 'Record booking candidate' screen (BRS-EXP-09-R001 fallback)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Record Booking Candidate",
            "res_model": "plasticos.export.booking.manual.candidate",
            "view_mode": "form",
            "target": "new",
            "context": {"default_booking_id": self.id},
        }
