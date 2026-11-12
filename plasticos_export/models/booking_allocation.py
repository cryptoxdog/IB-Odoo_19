"""Booking slots (E3) and cargo links (E4).

A slot is one distinct confirmed equipment unit of a booking, created only from
an accepted revision. Capacity is the count of distinct slots, never the count
of cargo links: two feeder loads into one container are two links on one slot
(BRS-EXP-14-R014/R015). A slot may bind one physical container journey (J1,
owned by Logistics); a journey is actively bound to at most one slot, enforced
by a partial unique index.

A cargo link is the exact native source of planned cargo for a slot: a
purchase or sale line, a Logistics load, a stock move line or a verified
non-stock original. Its quantity is planned only; it never writes stock,
weights, money or physical state (BRS-EXP-08-R005). Native PO facts are shown
from the PO line itself and are never copied (BRS-EXP-11-R007).

Allocation is exclusive and bounded (BRS-EXP-08-R006): one physical load or
stock move line sits on at most one live link, and the known planned quantities
on one PO or SO line never exceed that line's own quantity. A correction or a
split commits a new link that names the link it replaces; the replaced link is
released, never edited, and the booking chatter records who did it and why.

Lock order for every command: the booking row, then slot rows in id order, then
the cargo source rows.
"""

from odoo import api, fields, models
from odoo.exceptions import AccessError, LockError, UserError, ValidationError
from odoo.tools import SQL, float_compare

from .booking import (
    ALREADY_APPLIED,
    APPLIED,
    BLOCKED,
    DEFAULT_EQUIPMENT,
    EQUIPMENT_CLASSES,
    EXPORT_BOOKING,
    EXPORT_CARGO_LINK,
    EXPORT_REVISION,
    NOT_AVAILABLE,
    STALE,
    derived_write_error,
    export_actor_error,
    guard,
    guarded,
    result,
)

ISO_JOURNEY = "plasticos.iso.journey"
PO_NOT_READABLE = "PO not readable for your role."
PLASTICOS_LOAD = "plasticos.load"
PURCHASE_LINE = "purchase.order.line"
SALE_LINE = "sale.order.line"
STOCK_MOVE_LINE = "stock.move.line"
IR_ATTACHMENT = "ir.attachment"
UOM = "uom.uom"
EXPORT_SOURCE_LINE_CLAIM = "plasticos.export.source.line.claim"
# A released link is history; every other state, a proposal included, still claims its
# source for the allocation guard (BRS-EXP-08-R006). This is deliberately wider than
# logistics_integration.PHYSICAL_HOLD_LINK_STATES, which is only the confirmed cargo a
# physical instruction may follow.
SOURCE_CLAIM_LINK_STATES = ("proposed", "committed", "held")
# Physical subjects one live link holds exclusively.
_EXCLUSIVE_SOURCES = {
    "source_load_id": "load",
    "stock_move_line_id": "stock move line",
}
# Order lines whose own quantity bounds the planned quantity committed on them.
_BOUNDED_LINES = {
    "purchase_line_id": ("product_qty", "PO"),
    "sale_line_id": ("product_uom_qty", "SO"),
}
# Command-only keys of ``source_refs`` that are not link fields.
_CORRECTION_REFS = ("replaces_link_id", "correction_reason", "replaced_booking_revision_id")

# Planned weight normalization (C13 OP12-E02a): a pound total never adds a unit that is not a weight.
UOM_LB = "uom.product_uom_lb"
WEIGHT_BASIS_WEIGHT = "weight"
WEIGHT_BASIS_NOT_WEIGHT = "not_weight"
WEIGHT_BASIS_UNKNOWN = "unknown"
PLANNED_WEIGHT_BASES = [
    (WEIGHT_BASIS_WEIGHT, "Converted to lb"),
    (WEIGHT_BASIS_NOT_WEIGHT, "Excluded: not a weight unit"),
    (WEIGHT_BASIS_UNKNOWN, "No planned quantity"),
]

PHYSICAL_SOURCE_KINDS = [
    ("native_stock", "Native stock move"),
    ("logistics_load", "Logistics load"),
    ("verified_nonstock", "Verified non-stock original"),
    ("pending", "Pending"),
]
# The physical subject each kind needs; ``pending`` claims nothing physical.
_KIND_SUBJECT = {
    "native_stock": "stock_move_line_id",
    "logistics_load": "source_load_id",
    "verified_nonstock": "original_attachment_id",
}
_SOURCE_REF_FIELDS = (
    "purchase_line_id",
    "sale_line_id",
    "source_load_id",
    "stock_move_line_id",
    "original_attachment_id",
)
_SOURCE_REF_MODELS = {
    "purchase_line_id": PURCHASE_LINE,
    "sale_line_id": SALE_LINE,
    "source_load_id": PLASTICOS_LOAD,
    "stock_move_line_id": STOCK_MOVE_LINE,
    "original_attachment_id": IR_ATTACHMENT,
}
_SLOT_COMMAND_FIELDS = frozenset(
    {
        "booking_id",
        "slot_key",
        "equipment_class",
        "created_from_revision_id",
        "journey_id",
        "journey_binding_state",
        "hold_reason",
        "hold_revision_id",
        "active",
    }
)
_LINK_COMMAND_FIELDS = frozenset(
    {
        "slot_id",
        "allocation_key",
        "state",
        "planned_quantity",
        "planned_quantity_known",
        "uom_id",
        "physical_source_kind",
        "physical_source_ref",
        "source_revision_key",
        "replaces_link_id",
        *_SOURCE_REF_FIELDS,
    }
)


def slot_number(key):
    """The trailing number of a slot key (``40HC-12`` → 12); 0 when the key ends in no number."""
    digits = ""
    for char in reversed(key or ""):
        if not char.isdigit():
            break
        digits = char + digits
    return int(digits) if digits else 0


def slot_order(slot):
    """Numeric slot order: ``40HC-9`` before ``40HC-10`` (C13 OP12-E02b)."""
    return (slot.equipment_class or "", slot_number(slot.slot_key), slot.slot_key or "")


def _record_company(record):
    if not record:
        return record
    if record._name == SALE_LINE or record._name == PURCHASE_LINE:
        return record.order_id.company_id
    return record.company_id if "company_id" in record._fields else False


class PlasticosExportBookingSlot(models.Model):
    _name = "plasticos.export.booking.slot"
    _description = "Export Booking Slot"
    _order = "booking_id, equipment_class, slot_number, slot_key"
    _rec_name = "slot_key"

    active = fields.Boolean(default=True, help="Cleared when an accepted revision retires this free slot.")
    booking_id = fields.Many2one(EXPORT_BOOKING, required=True, index=True, ondelete="restrict")
    company_id = fields.Many2one(related="booking_id.company_id", store=True, index=True)
    slot_key = fields.Char(required=True, help="Stable key of this slot within its booking.")
    slot_number = fields.Integer(
        compute="_compute_slot_number",
        store=True,
        index=True,
        aggregator=None,
        help="The number at the end of the slot key, so slot 10 sorts after slot 9 (C13 OP12-E02b).",
    )
    equipment_class = fields.Selection(
        EQUIPMENT_CLASSES,
        required=True,
        default=DEFAULT_EQUIPMENT,
        help="Confirmed equipment class of this slot. 40HC is suggested, never enforced (BRS-EXP-07-R003).",
    )
    created_from_revision_id = fields.Many2one(EXPORT_REVISION, required=True, index=True, ondelete="restrict")
    journey_id = fields.Many2one(
        ISO_JOURNEY,
        string="Container Journey",
        index=True,
        ondelete="restrict",
        help="The physical container cycle bound to this slot. Logistics owns it.",
    )
    journey_binding_state = fields.Selection(
        [("unbound", "Unbound"), ("active", "Active"), ("historical", "Historical")],
        required=True,
        default="unbound",
        index=True,
    )
    hold_reason = fields.Char(help="Why an accepted revision holds this slot for an owner decision.")
    hold_revision_id = fields.Many2one(EXPORT_REVISION, string="Held By Revision", ondelete="restrict")
    allocation_state = fields.Selection(
        [("available", "Available"), ("committed", "Committed"), ("held", "Held"), ("historical", "Historical")],
        compute="_compute_allocation_state",
        store=True,
        index=True,
    )
    cargo_link_ids = fields.One2many("plasticos.export.booking.cargo.link", "slot_id", string="Cargo")
    iso_number = fields.Char(related="journey_id.iso_number", string="Container No.")
    seal_number = fields.Char(related="journey_id.seal_number", string="Seal")
    journey_equipment_class = fields.Char(related="journey_id.equipment_class", string="Actual Equipment")
    carrier_booking_no = fields.Char(related="booking_id.carrier_booking_no", string="Booking No.", store=True)
    supplier_count = fields.Integer(compute="_compute_supplier_count", string="Suppliers", store=True)

    _booking_slot_unique = models.Constraint(
        "UNIQUE(booking_id, slot_key)", "This booking already has a slot with that key."
    )
    _one_active_slot_per_journey = models.UniqueIndex(
        "(journey_id) WHERE journey_binding_state = 'active'",
        "That container journey is already bound to another booking slot.",
    )
    _active_binding_has_journey = models.Constraint(
        "CHECK(journey_binding_state = 'unbound' OR journey_id IS NOT NULL)",
        "A bound slot needs its container journey.",
    )

    @api.depends("active", "hold_reason", "cargo_link_ids.state")
    def _compute_allocation_state(self):
        for slot in self:
            if not slot.active:
                slot.allocation_state = "historical"
            elif slot.hold_reason:
                slot.allocation_state = "held"
            elif any(state == "committed" for state in slot.cargo_link_ids.mapped("state")):
                slot.allocation_state = "committed"
            else:
                slot.allocation_state = "available"

    @api.depends("cargo_link_ids.state", "cargo_link_ids.supplier_id")
    def _compute_supplier_count(self):
        for slot in self:
            links = slot.cargo_link_ids.filtered(lambda link: link.state in ("committed", "held"))
            slot.supplier_count = len(links.purchase_line_id.order_id.partner_id)

    @api.depends("slot_key")
    def _compute_slot_number(self):
        for slot in self:
            slot.slot_number = slot_number(slot.slot_key)

    @api.depends("slot_key", "equipment_class", "booking_id")
    def _compute_display_name(self):
        for slot in self:
            slot.display_name = f"{slot.booking_id.display_name} · {slot.slot_key}"

    @api.model_create_multi
    def create(self, vals_list):
        if not guarded(self.env):
            raise UserError("Slots come from an accepted booking revision; they are never typed in.")
        return super().create(vals_list)

    def write(self, vals):
        if not guarded(self.env):
            error = derived_write_error(self, vals)
            if error:
                raise UserError(error)
            if _SLOT_COMMAND_FIELDS & set(vals):
                raise UserError("Booking slots change only through Export booking commands.")
        return super().write(vals)

    def unlink(self):
        raise UserError("Booking slots are history and cannot be deleted.")

    # ── capacity ──────────────────────────────────────────────

    @api.model
    def _reconcile_capacity(self, booking, revision):
        """Make the booking's live slots match the accepted revision's confirmed counts.

        Called inside the acceptance, after the booking row lock. Per equipment
        class, a slot already held by an earlier revision counts as capacity
        already withdrawn. When the new count covers more slots, holds are lifted
        first (lowest key first, their cargo committed again) and only then are
        new slots added with stable keys. When it covers fewer, extra holds are
        lifted or free slots retired (highest key first), and only committed or
        bound slots that cannot be retired are held, naming the revision.
        """
        Slot = guard(self.with_context(active_test=False))
        existing = Slot.search([("booking_id", "=", booking.id)], order="id ASC")
        existing.lock_for_update()
        live = existing.filtered("active")
        wanted = revision._confirmed_counts()
        for code in sorted(set(wanted) | set(live.mapped("equipment_class"))):
            target = wanted.get(code, 0)
            slots = live.filtered(lambda slot, code=code: slot.equipment_class == code)
            held = slots.filtered("hold_reason").sorted(slot_order)
            unheld = slots - held
            if len(unheld) >= target:
                # Capacity shrinks or stays: holds still cover part of the withdrawal.
                excess = len(unheld) - target
                if excess == 0:
                    continue
                free = unheld.filtered(
                    lambda slot: slot.allocation_state == "available" and slot.journey_binding_state != "active"
                ).sorted(slot_order, reverse=True)
                retire = free[:excess]
                retire.write({"active": False})
                busy = (unheld - retire).sorted(slot_order, reverse=True)[: excess - len(retire)]
                if busy:
                    busy.write(
                        {
                            "hold_reason": f"Revision {revision.source_revision_key} reduced confirmed {code} capacity",
                            "hold_revision_id": revision.id,
                        }
                    )
                    guard(busy.cargo_link_ids.filtered(lambda link: link.state == "committed")).write({"state": "held"})
                continue
            # Capacity grows past the unheld slots: lift holds first, then add slots.
            restore = held[: target - len(unheld)]
            if restore:
                restore.write({"hold_reason": False, "hold_revision_id": False})
                guard(restore.cargo_link_ids.filtered(lambda link: link.state == "held")).write({"state": "committed"})
            missing = target - len(unheld) - len(restore)
            used = set(existing.filtered(lambda slot, code=code: slot.equipment_class == code).mapped("slot_key"))
            number = 1
            for _index in range(missing):
                while f"{code}-{number}" in used:
                    number += 1
                used.add(f"{code}-{number}")
                Slot.create(
                    {
                        "booking_id": booking.id,
                        "slot_key": f"{code}-{number}",
                        "equipment_class": code,
                        "created_from_revision_id": revision.id,
                    }
                )
        return True

    # ── shared command plumbing ──────────────────────────────

    def _slot_preflight(self, operation_key, expected_booking_revision_id):
        """Lock booking then slot and check currentness. Returns a refusal or False."""
        self.ensure_one()
        if not (operation_key or "").strip():
            return result(BLOCKED, reason="operation_key is required")
        error = export_actor_error(self.env)
        if error:
            return result(NOT_AVAILABLE, reason=error)
        try:
            self.check_access("write")
        except AccessError:
            return result(NOT_AVAILABLE, reason="no access to this slot")
        booking = self.booking_id
        error = export_actor_error(self.env, booking.company_id)
        if error:
            return result(NOT_AVAILABLE, reason=error)
        try:
            booking._lock_booking()
            self.lock_for_update()
        except LockError:
            return result(BLOCKED, reason="booking_busy")
        self.invalidate_recordset()
        if (booking.current_revision_id.id or False) != (expected_booking_revision_id or False):
            return result(STALE, booking.current_revision_id, "booking revision changed")
        return False

    def _usable_error(self):
        self.ensure_one()
        if not self.active:
            return "the slot was retired by a later revision"
        if self.hold_reason:
            return f"the slot is held: {self.hold_reason}"
        if self.booking_id.display_state == "cancelled":
            return "the booking is cancelled"
        return False

    # ── Frozen command: action_commit_cargo ──────────────────

    def action_commit_cargo(self, source_refs, planned_quantity, uom_id, expected_booking_revision_id, operation_key):
        """Commit one exact native cargo source to this slot (planned only).

        ``source_refs`` names the source records by id (``purchase_line_id``,
        ``sale_line_id``, ``source_load_id``, ``stock_move_line_id``,
        ``original_attachment_id``), the ``physical_source_kind`` and optional
        ``physical_source_ref`` and ``source_revision_key``. Another feeder for
        the same container is another link on the same slot; it never consumes
        a second slot. ``operation_key`` is the link's allocation key.

        A load or stock move line already on another live link, or a planned
        quantity beyond the PO or SO line's own quantity, is refused
        (BRS-EXP-08-R006). A correction or split also names
        ``replaces_link_id`` and a ``correction_reason``: the replaced link is
        released, the new link records what it replaces, and the booking
        chatter attributes the change. Further split parts name the same
        replaced link. When the replaced link sits on another booking, that
        booking is locked too and ``replaced_booking_revision_id`` must name
        its current revision, as ``expected_booking_revision_id`` does here.

        Every commit that plans a quantity on a PO or SO line first claims that
        line's Export-owned row (``plasticos.export.source.line.claim``) with an
        upsert. Two transactions planning on one line therefore serialize on
        that row: the later one fails to serialize and is retried, and its
        retry counts the first one's quantity (no native row is written).
        """
        refusal = self._slot_preflight(operation_key, expected_booking_revision_id)
        if refusal:
            return refusal
        refs = dict(source_refs or {})
        correction = (refs.pop("correction_reason", None) or "").strip()
        replaced_expected = refs.pop("replaced_booking_revision_id", None)
        Link = self.env[EXPORT_CARGO_LINK]
        values, reason = Link._source_values(self, refs, planned_quantity, uom_id)
        prior = Link.search([("company_id", "=", self.company_id.id), ("allocation_key", "=", operation_key)], limit=1)
        if prior:
            if values and prior.slot_id == self and prior._same_source(values):
                return result(ALREADY_APPLIED, prior)
            return result(STALE, prior, "operation_key was used for a different cargo commitment")
        if reason:
            return result(BLOCKED, reason=reason)
        replaced = Link.browse(values["replaces_link_id"] or [])
        if replaced and not correction:
            return result(BLOCKED, replaced, "correction_reason is required to replace a cargo link")
        usable = self._usable_error()
        if usable:
            return result(BLOCKED, self, usable)
        if replaced and replaced.booking_id != self.booking_id:
            other = replaced.booking_id
            try:
                other._lock_booking()
                replaced.slot_id.lock_for_update()
            except LockError:
                return result(BLOCKED, reason="booking_busy")
            if (other.current_revision_id.id or False) != (int(replaced_expected or 0) or False):
                return result(STALE, other.current_revision_id, "the replaced cargo's booking revision changed")
        try:
            Link._lock_sources(values)
        except LockError:
            return result(BLOCKED, reason="cargo_source_busy")
        self.env[EXPORT_SOURCE_LINE_CLAIM]._claim(self.company_id, values)
        allocation = Link._allocation_error(values, replaced)
        if allocation:
            return result(BLOCKED, self, allocation)
        if replaced.state in SOURCE_CLAIM_LINK_STATES:
            guard(replaced).write({"state": "released"})
        link = guard(Link).create({**values, "slot_id": self.id, "allocation_key": operation_key, "state": "committed"})
        if replaced:
            body = (
                f"Cargo {link.allocation_key} on slot {self.slot_key} replaces cargo {replaced.allocation_key} "
                f"(slot {replaced.slot_id.slot_key}), by {self.env.user.name}: {correction}"
            )
            for booking in self.booking_id | replaced.booking_id:
                booking.message_post(body=body, message_type="comment", subtype_xmlid="mail.mt_note")
        return result(APPLIED, link)

    # ── Frozen command: action_release_cargo ─────────────────

    def action_release_cargo(self, cargo_link_id, expected_booking_revision_id, operation_key, reason):
        """Release one cargo link from this slot. The link stays as history."""
        refusal = self._slot_preflight(operation_key, expected_booking_revision_id)
        if refusal:
            return refusal
        why = (reason or "").strip()
        if not why:
            return result(BLOCKED, reason="reason is required")
        link = self.env[EXPORT_CARGO_LINK].browse(int(cargo_link_id or 0)).exists()
        if not link or link.slot_id != self:
            return result(NOT_AVAILABLE, reason="cargo link not found on this slot")
        if link.state == "released":
            return result(ALREADY_APPLIED, link)
        guard(link).write({"state": "released"})
        self.booking_id.message_post(
            body=f"Cargo {link.allocation_key} released from slot {self.slot_key}: {why}",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        return result(APPLIED, link)

    # ── Frozen command: action_bind_journey ──────────────────

    def action_bind_journey(self, journey_id, expected_booking_revision_id, operation_key, source_basis):
        """Bind one sourced physical container journey (J1) to this slot.

        The journey must be attributed or verified in the booking's company and
        carry the slot's equipment class; a mismatch is reported, never
        rewritten (BRS-EXP-07-R007). A journey already active on another slot is
        refused before the partial unique index would be.
        """
        refusal = self._slot_preflight(operation_key, expected_booking_revision_id)
        if refusal:
            return refusal
        basis = (source_basis or "").strip()
        if not basis:
            return result(BLOCKED, reason="source_basis is required")
        journey = self.env[ISO_JOURNEY].browse(int(journey_id or 0)).exists()
        if not journey:
            return result(NOT_AVAILABLE, reason="container journey not found")
        try:
            journey.check_access("read")
        except AccessError:
            return result(NOT_AVAILABLE, reason="container journey not readable")
        if self.journey_binding_state == "active":
            if self.journey_id == journey:
                return result(ALREADY_APPLIED, self)
            return result(BLOCKED, self, "the slot is already bound to another container journey")
        usable = self._usable_error()
        if usable:
            return result(BLOCKED, self, usable)
        if journey.company_id != self.company_id:
            return result(BLOCKED, self, "the container journey belongs to another company")
        if journey.identity_state not in ("attributed", "verified"):
            return result(BLOCKED, self, "the container journey is not attributed")
        if (journey.equipment_class or "").upper() != self.equipment_class:
            return result(
                BLOCKED,
                self,
                f"equipment mismatch: slot {self.equipment_class}, container {journey.equipment_class}; "
                "an authorized booking amendment or exception decides",
            )
        other = self.search([("journey_id", "=", journey.id), ("journey_binding_state", "=", "active")], limit=1)
        if other:
            return result(BLOCKED, other, "the container journey is bound to another slot")
        guard(self).write({"journey_id": journey.id, "journey_binding_state": "active"})
        self.booking_id.message_post(
            body=f"Slot {self.slot_key} bound to container {journey.display_name}: {basis}",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        return result(APPLIED, self)

    def action_open_journey(self):
        """Navigate to the Logistics owner of the physical container."""
        self.ensure_one()
        if not self.journey_id:
            raise UserError("This slot has no container journey.")
        return {
            "type": "ir.actions.act_window",
            "res_model": ISO_JOURNEY,
            "res_id": self.journey_id.id,
            "view_mode": "form",
        }


class PlasticosExportBookingCargoLink(models.Model):
    _name = "plasticos.export.booking.cargo.link"
    _description = "Export Booking Cargo Link"
    _order = "slot_id, id"
    _rec_name = "allocation_key"

    slot_id = fields.Many2one("plasticos.export.booking.slot", required=True, index=True, ondelete="restrict")
    booking_id = fields.Many2one(related="slot_id.booking_id", store=True, index=True, string="Booking")
    company_id = fields.Many2one(related="slot_id.company_id", store=True, index=True)
    allocation_key = fields.Char(required=True, help="Operation that committed this cargo; unique per company.")
    state = fields.Selection(
        [("proposed", "Proposed"), ("committed", "Committed"), ("held", "Held"), ("released", "Released")],
        required=True,
        default="proposed",
        index=True,
    )
    purchase_line_id = fields.Many2one(PURCHASE_LINE, string="Supplier PO Line", index=True, ondelete="restrict")
    sale_line_id = fields.Many2one(SALE_LINE, string="Customer SO Line", index=True, ondelete="restrict")
    source_load_id = fields.Many2one(PLASTICOS_LOAD, string="Source Load", index=True, ondelete="restrict")
    stock_move_line_id = fields.Many2one(STOCK_MOVE_LINE, string="Stock Move Line", index=True, ondelete="restrict")
    original_attachment_id = fields.Many2one(IR_ATTACHMENT, string="Original", ondelete="restrict")
    physical_source_kind = fields.Selection(PHYSICAL_SOURCE_KINDS, required=True, default="pending")
    physical_source_ref = fields.Char(help="Exact source reference, never a name match.")
    source_revision_key = fields.Char(help="Source owner's revision of this cargo, for identity and replay.")
    # No aggregator: planned quantities in different units are never summed (C13 OP12-E02a).
    planned_quantity = fields.Float(help="Planned only. Never shipped, scaled or stocked quantity.", aggregator=None)
    planned_quantity_known = fields.Boolean(required=True, default=False)
    uom_id = fields.Many2one(UOM, string="Unit", ondelete="restrict")
    planned_weight_lb = fields.Float(
        compute="_compute_planned_weight_lb",
        store=True,
        string="Planned Weight (lb)",
        help="The planned quantity converted to pounds through the native unit of measure. A planned "
        "quantity in a unit that is not a weight is excluded (0) and flagged by its weight basis.",
    )
    planned_weight_basis = fields.Selection(
        PLANNED_WEIGHT_BASES,
        compute="_compute_planned_weight_lb",
        store=True,
        string="Weight Basis",
        help="Whether the planned quantity counts in the pound total: a weight unit converts; any other "
        "unit is excluded and shown here instead of being added.",
    )
    replaces_link_id = fields.Many2one(EXPORT_CARGO_LINK, string="Replaces", ondelete="restrict")
    purchase_order_id = fields.Many2one(related="purchase_line_id.order_id", string="Supplier PO", store=True)
    supplier_id = fields.Many2one(related="purchase_line_id.order_id.partner_id", string="Supplier", store=True)
    sale_order_id = fields.Many2one(related="sale_line_id.order_id", string="Customer SO", store=True)
    equipment_class = fields.Selection(related="slot_id.equipment_class", store=True)
    iso_number = fields.Char(related="slot_id.journey_id.iso_number", string="Container No.")
    # Source names, read without access to the source record (related_sudo default).
    # Operator decision 2026-11-12: every same-company Sales Rep sees every cargo
    # allocation so no booking is overbooked, but the load, sale order and purchase
    # order behind another rep's row stay owner-scoped. Lists, the container
    # manifest and exports print these names instead of traversing the source in
    # the reader's environment. Names only: no economics (BRS-EXP-06-R001).
    # Searching them also bypasses the source rules (related search uses any!),
    # so a Sales Rep finds another rep's allocation by its PO or SO name.
    source_load_ref = fields.Char(related="source_load_id.name", string="Source Load Ref")
    sale_order_ref = fields.Char(related="sale_line_id.order_id.name", string="Customer SO Ref")
    purchase_order_ref = fields.Char(related="purchase_line_id.order_id.name", string="Supplier PO Ref")
    original_ref = fields.Char(related="original_attachment_id.name", string="Original Ref")
    supplier_ref = fields.Char(related="purchase_line_id.order_id.partner_id.name", string="Supplier Ref")
    po_constraint_display = fields.Text(
        compute="_compute_po_constraint_display",
        string="PO Constraints",
        help="Read live from the native PO line. Export copies no PO fact (BRS-EXP-11-R007).",
    )

    @api.depends("planned_quantity", "planned_quantity_known", "uom_id")
    def _compute_planned_weight_lb(self):
        pound = self.env.ref(UOM_LB, raise_if_not_found=False)
        for link in self:
            unit = link.uom_id
            if not link.planned_quantity_known or not unit:
                link.planned_weight_lb, link.planned_weight_basis = 0.0, WEIGHT_BASIS_UNKNOWN
            elif pound and unit._has_common_reference(pound):
                link.planned_weight_lb = unit._compute_quantity(link.planned_quantity, pound, round=False)
                link.planned_weight_basis = WEIGHT_BASIS_WEIGHT
            else:
                link.planned_weight_lb, link.planned_weight_basis = 0.0, WEIGHT_BASIS_NOT_WEIGHT

    _company_allocation_unique = models.UniqueIndex(
        "(company_id, allocation_key)", "This company already has a cargo commitment under that allocation key."
    )
    # The database twin of the exclusive-source guard: a concurrent second commit fails here (BRS-EXP-08-R006).
    _one_live_link_per_load = models.UniqueIndex(
        "(source_load_id) WHERE source_load_id IS NOT NULL AND state <> 'released'",
        "This load is already committed on another live cargo link.",
    )
    _one_live_link_per_move_line = models.UniqueIndex(
        "(stock_move_line_id) WHERE stock_move_line_id IS NOT NULL AND state <> 'released'",
        "This stock move line is already committed on another live cargo link.",
    )
    _known_quantity_has_unit = models.Constraint(
        "CHECK(NOT planned_quantity_known OR (uom_id IS NOT NULL AND planned_quantity > 0))",
        "A known planned quantity is positive and has its unit.",
    )
    _unknown_quantity_is_empty = models.Constraint(
        "CHECK(planned_quantity_known OR COALESCE(planned_quantity, 0) = 0)",
        "An unknown planned quantity carries no number.",
    )

    @api.depends(
        "purchase_line_id",
        "purchase_line_id.product_id",
        "purchase_line_id.product_qty",
        "purchase_line_id.product_uom_id",
        "purchase_line_id.name",
        "purchase_line_id.order_id.incoterm_id",
    )
    @api.depends_context("uid")
    def _compute_po_constraint_display(self):
        """Quantity, grade, unit, trade label and terms as the PO line states them now."""
        for link in self:
            line = link.purchase_line_id
            if not line:
                link.po_constraint_display = False
                continue
            try:
                line.check_access("read")
            except AccessError:
                # No sudo: a role without purchase read sees that the PO exists, not its terms (review D3).
                link.po_constraint_display = PO_NOT_READABLE
                continue
            order = line.order_id
            rows = [
                f"PO: {order.name}",
                f"Material: {line.product_id.display_name or ''}",
                f"Quantity: {line.product_qty:g} {line.product_uom_id.name or ''}".rstrip(),
            ]
            if order.incoterm_id:
                rows.append(f"Delivery terms: {order.incoterm_id.code or order.incoterm_id.name}")
            description = (line.name or "").strip()
            if description and description != line.product_id.display_name:
                rows.append(f"Line terms: {description}")
            link.po_constraint_display = "\n".join(rows)

    @api.model_create_multi
    def create(self, vals_list):
        if not guarded(self.env):
            raise UserError("Commit cargo through the slot's Commit Cargo command.")
        # Checked before the insert so a twin gets a clear refusal, not the unique index (BRS-EXP-08-R006).
        for vals in vals_list:
            if vals.get("state", "proposed") in SOURCE_CLAIM_LINK_STATES:
                error = self._allocation_error(vals)
                if error:
                    raise ValidationError(f"Cargo {vals.get('allocation_key')}: {error}")
        return super().create(vals_list)

    def write(self, vals):
        if not guarded(self.env):
            error = derived_write_error(self, vals)
            if error:
                raise UserError(error)
            if _LINK_COMMAND_FIELDS & set(vals):
                raise UserError("Cargo links change only through Export booking commands.")
        return super().write(vals)

    def unlink(self):
        raise UserError("Cargo links are history and cannot be deleted.")

    # ── allocation guard (BRS-EXP-08-R006) ───────────────────

    @api.model
    def _lock_sources(self, values):
        """Row-lock the exact cargo sources so two commitments on one source serialize.

        Raises ``LockError`` when another transaction holds one of them. The
        lock lets other rows keep referencing the source.
        """
        for name in (*_SOURCE_REF_FIELDS, "replaces_link_id"):
            if values.get(name):
                model = _SOURCE_REF_MODELS.get(name, EXPORT_CARGO_LINK)
                self.env[model].browse(values[name]).lock_for_update(allow_referencing=True)

    @api.model
    def _allocation_error(self, values, excluding=None):
        """Why these link values would double-allocate or over-allocate, or False.

        ``excluding`` is a link that does not count: the link itself, or the
        link a correction replaces.
        """
        excluding = excluding or self.browse()
        Live = self.sudo().with_context(active_test=False)  # sudo: count every live link, not only the visible ones
        live = [("state", "in", SOURCE_CLAIM_LINK_STATES), ("id", "not in", excluding.ids)]
        for name, label in _EXCLUSIVE_SOURCES.items():
            if values.get(name) and Live.search_count([*live, (name, "=", values[name])], limit=1):
                return (
                    f"this {label} is already committed on another live cargo link; release or replace that link first"
                )
        if not values.get("planned_quantity_known"):
            return False
        unit = self.env[UOM].browse(values.get("uom_id") or [])
        if not unit:
            return False  # the known-quantity CHECK constraint refuses a number without its unit
        for name, (quantity_field, label) in _BOUNDED_LINES.items():
            if not values.get(name):
                continue
            line = self.env[_SOURCE_REF_MODELS[name]].browse(values[name])
            line_unit = line.product_uom_id
            if not line_unit or not unit._has_common_reference(line_unit):
                return f"the planned unit {unit.name} does not convert to the {label} line unit {line_unit.name or '?'}"
            total = unit._compute_quantity(values.get("planned_quantity") or 0.0, line_unit, round=False)
            for other in Live.search([*live, (name, "=", line.id), ("planned_quantity_known", "=", True)]):
                total += other.uom_id._compute_quantity(other.planned_quantity, line_unit, round=False)
            ordered = line[quantity_field]
            if float_compare(total, ordered, precision_rounding=line_unit.rounding) > 0:
                return (
                    f"planned {total:g} {line_unit.name} would exceed the {label} line quantity "
                    f"{ordered:g} {line_unit.name}"
                )
        return False

    @api.constrains(
        "source_load_id",
        "stock_move_line_id",
        "purchase_line_id",
        "sale_line_id",
        "planned_quantity",
        "planned_quantity_known",
        "uom_id",
    )
    def _check_allocation(self):
        """The same guard at the model, for any guarded write that bypasses the command check."""
        for link in self.filtered(lambda link: link.state in SOURCE_CLAIM_LINK_STATES):
            values = {
                "planned_quantity": link.planned_quantity,
                "planned_quantity_known": link.planned_quantity_known,
                "uom_id": link.uom_id.id,
                **{name: link[name].id for name in (*_EXCLUSIVE_SOURCES, *_BOUNDED_LINES)},
            }
            error = self._allocation_error(values, link)
            if error:
                raise ValidationError(f"Cargo {link.allocation_key}: {error}")

    @api.model
    def _source_values(self, slot, refs, planned_quantity, uom_id):
        """Validated link values from exact source ids. Returns ``(values, reason)``."""
        unknown = set(refs) - {
            *_SOURCE_REF_FIELDS,
            *_CORRECTION_REFS,
            "physical_source_kind",
            "physical_source_ref",
            "source_revision_key",
        }
        if unknown:
            return {}, f"unknown source references {sorted(unknown)}"
        kind = refs.get("physical_source_kind") or "pending"
        if kind not in dict(PHYSICAL_SOURCE_KINDS):
            return {}, f"unknown physical source kind {kind!r}"
        values = {"physical_source_kind": kind}
        company = slot.company_id
        for name in _SOURCE_REF_FIELDS:
            raw = refs.get(name)
            if not raw:
                values[name] = False
                continue
            record = self.env[_SOURCE_REF_MODELS[name]].browse(int(raw)).exists()
            if not record:
                return {}, f"{name} not found"
            try:
                record.check_access("read")
            except AccessError:
                return {}, f"{name} not readable"
            record_company = _record_company(record)
            if record_company and record_company != company:
                return {}, f"{name} belongs to another company"
            values[name] = record.id
        if not any(values[name] for name in _SOURCE_REF_FIELDS):
            return {}, "a cargo commitment needs at least one exact source record"
        subject = _KIND_SUBJECT.get(kind)
        if subject and not values[subject]:
            return {}, f"physical source kind {kind} needs {subject}"
        if kind == "pending" and (values["stock_move_line_id"] or values["source_load_id"]):
            return {}, "a pending source cannot name a physical load or stock move"
        values["replaces_link_id"] = False
        if refs.get("replaces_link_id"):
            replaced = self.browse(int(refs["replaces_link_id"])).exists()
            if not replaced:
                return {}, "replaces_link_id not found"
            try:
                replaced.check_access("read")
            except AccessError:
                return {}, "replaces_link_id not readable"
            if replaced.company_id != company:
                return {}, "replaces_link_id belongs to another company"
            if replaced.state not in SOURCE_CLAIM_LINK_STATES and not self.search_count(
                [("replaces_link_id", "=", replaced.id)], limit=1
            ):
                return {}, "the replaced cargo link was released, not replaced; commit new cargo instead"
            values["replaces_link_id"] = replaced.id
        values["physical_source_ref"] = (refs.get("physical_source_ref") or "").strip() or False
        values["source_revision_key"] = (refs.get("source_revision_key") or "").strip() or False
        if planned_quantity is None:
            values.update(planned_quantity_known=False, planned_quantity=0.0, uom_id=False)
        else:
            uom = self.env[UOM].browse(int(uom_id or 0)).exists() if uom_id else self.env[UOM]
            if not uom:
                return {}, "a known planned quantity needs its unit"
            if planned_quantity <= 0:
                return {}, "a known planned quantity must be positive"
            values.update(planned_quantity_known=True, planned_quantity=float(planned_quantity), uom_id=uom.id)
        return values, False

    def _same_source(self, values):
        self.ensure_one()
        for name, value in values.items():
            current = self[name]
            current = current.id if isinstance(current, models.BaseModel) else current
            if (current or False) != (value or False):
                return False
        return True


class PlasticosExportSourceLineClaim(models.Model):
    """One Export-owned row per PO or SO line that cargo plans quantity on (BRS-EXP-08-R006).

    It stores no quantity: the planned quantities stay on the cargo links, and the
    order quantity stays on the native line. Its only job is serialization. The
    conflict key is (line model, line id), one partial unique index per line model;
    ``company_id`` is stored but not part of the key, which is equivalent because a
    line belongs to one company. Each commit that plans on a line upserts and bumps
    this row before it counts the line's live links. While a first commit is still
    in flight, a second one is refused earlier with ``cargo_source_busy`` (the
    SKIP LOCKED source lock). Once the first has committed, a second transaction
    whose REPEATABLE READ snapshot predates it fails to serialize on this row; Odoo
    retries it, and the retry sees the first link. The native PO and SO rows are
    never written.
    """

    _name = "plasticos.export.source.line.claim"
    _description = "Export Source Line Claim (internal: serializes allocation commits; no view or command)"
    _rec_name = "id"

    company_id = fields.Many2one("res.company", required=True, index=True, ondelete="restrict")
    purchase_line_id = fields.Many2one(PURCHASE_LINE, index=True, ondelete="cascade")
    sale_line_id = fields.Many2one(SALE_LINE, index=True, ondelete="cascade")
    claim_count = fields.Integer(
        default=0,
        help=(
            "Attempt and serialization counter. Bumped by every commit that plans on this line, before the guard "
            "checks, and it stays bumped when that attempt is refused. Its value is not used for any decision."
        ),
    )

    _one_source_line = models.Constraint(
        "CHECK((purchase_line_id IS NULL) <> (sale_line_id IS NULL))",
        "A source line claim names exactly one PO line or SO line.",
    )
    _one_claim_per_purchase_line = models.UniqueIndex(
        "(purchase_line_id) WHERE purchase_line_id IS NOT NULL",
        "This PO line already has its claim row.",
    )
    _one_claim_per_sale_line = models.UniqueIndex(
        "(sale_line_id) WHERE sale_line_id IS NOT NULL",
        "This SO line already has its claim row.",
    )

    @api.model
    def _claim(self, company, values):
        """Upsert and bump the claim row of each PO or SO line in ``values``. Returns the rows."""
        if not values.get("planned_quantity_known"):
            return self.browse()
        ids = []
        for column in _BOUNDED_LINES:
            if not values.get(column):
                continue
            # An upsert, not search-then-create: INSERT ... ON CONFLICT DO UPDATE takes the row lock,
            # and at REPEATABLE READ raises a serialization failure when the row changed after this
            # transaction's snapshot. The ORM has no upsert, hence SQL on this Export-owned table only.
            self.env.flush_all()
            self.env.cr.execute(  # sudo: n/a, a raw upsert on Export's own claim table, the guard's only writer
                SQL(
                    """
                    INSERT INTO %(table)s (company_id, %(column)s, claim_count,
                                           create_uid, create_date, write_uid, write_date)
                    VALUES (%(company)s, %(line)s, 1, %(uid)s, NOW() AT TIME ZONE 'UTC',
                            %(uid)s, NOW() AT TIME ZONE 'UTC')
                    ON CONFLICT (%(column)s) WHERE %(column)s IS NOT NULL
                    DO UPDATE SET claim_count = %(table)s.claim_count + 1,
                                  write_uid = EXCLUDED.write_uid,
                                  write_date = EXCLUDED.write_date
                    RETURNING id
                    """,
                    table=SQL.identifier(self._table),
                    column=SQL.identifier(column),
                    company=company.id,
                    line=values[column],
                    uid=self.env.uid,
                )
            )
            ids.append(self.env.cr.fetchone()[0])
        claims = self.browse(ids)
        claims.invalidate_recordset()
        return claims
