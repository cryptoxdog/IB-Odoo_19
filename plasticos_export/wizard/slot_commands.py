"""Screens for the slot commands (S10 OP10-E05, coordinator C11-SCOPE-2).

Commit Cargo, Release Cargo and Bind Container open a dialog that calls the
existing frozen command (``action_commit_cargo``, ``action_release_cargo`` or
``action_bind_journey``) as the acting user. Every guard stays in the command:
the Logistics role, record and company access, the expected booking revision,
slot usability, exact same-company sources, equipment match and the one-slot
journey binding. A dialog stores no business fact. Each screen has its own
operation key, so a double click applies the command once.

The booking's current revision is captured when the dialog opens. If another
acceptance moves the booking in between, the command answers ``stale`` and
nothing changes.
"""

import uuid

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.booking import ALREADY_APPLIED, APPLIED, EXPORT_CARGO_LINK, EXPORT_REVISION, EXPORT_SLOT
from ..models.booking_allocation import (
    IR_ATTACHMENT,
    ISO_JOURNEY,
    PHYSICAL_SOURCE_KINDS,
    PLASTICOS_LOAD,
    PURCHASE_LINE,
    SALE_LINE,
    STOCK_MOVE_LINE,
    UOM,
)


class PlasticosExportSlotCommandMixin(models.AbstractModel):
    _name = "plasticos.export.slot.command.mixin"
    _description = "Export slot command screen"

    slot_id = fields.Many2one(EXPORT_SLOT, string="Slot", required=True, readonly=True, ondelete="cascade")
    booking_id = fields.Many2one(related="slot_id.booking_id", string="Booking")
    company_id = fields.Many2one(related="slot_id.company_id", string="Company")
    expected_booking_revision_id = fields.Many2one(
        EXPORT_REVISION,
        string="Booking Revision When Opened",
        readonly=True,
        ondelete="cascade",
        help="The booking's current revision when this screen opened. The command compares against it.",
    )
    operation_key = fields.Char(
        required=True,
        readonly=True,
        default=lambda self: f"{self._operation_prefix}-{uuid.uuid4()}",
        help="One key per screen: a second click applies the command once.",
    )

    _operation_prefix = "slot-command"

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        slot = self.env[EXPORT_SLOT].browse(values.get("slot_id") or 0).exists()
        if slot:
            values["expected_booking_revision_id"] = slot.booking_id.current_revision_id.id or False
        return values

    def _outcome(self, outcome, what):
        """Close on applied or already applied; otherwise show the command's own refusal."""
        if outcome["status"] not in (APPLIED, ALREADY_APPLIED):
            raise UserError(f"{what} not done ({outcome['status']}): {outcome.get('reason', '')}")
        return {"type": "ir.actions.act_window_close"}


class PlasticosExportSlotCommitCargo(models.TransientModel):
    _name = "plasticos.export.slot.commit.cargo"
    _inherit = ["plasticos.export.slot.command.mixin"]
    _description = "Commit Cargo to an Export Slot"
    _operation_prefix = "commit-cargo"

    purchase_line_id = fields.Many2one(PURCHASE_LINE, string="Supplier PO Line", ondelete="cascade")
    sale_line_id = fields.Many2one(SALE_LINE, string="Customer SO Line", ondelete="cascade")
    source_load_id = fields.Many2one(PLASTICOS_LOAD, string="Source Load", ondelete="cascade")
    stock_move_line_id = fields.Many2one(STOCK_MOVE_LINE, string="Stock Move Line", ondelete="cascade")
    original_attachment_id = fields.Many2one(IR_ATTACHMENT, string="Original", ondelete="cascade")
    physical_source_kind = fields.Selection(PHYSICAL_SOURCE_KINDS, required=True, default="pending")
    physical_source_ref = fields.Char(help="Exact source reference, never a name match.")
    source_revision_key = fields.Char(help="The source owner's revision of this cargo.")
    planned_quantity_known = fields.Boolean(string="Planned Quantity Known")
    planned_quantity = fields.Float(help="Planned only. Never shipped, scaled or stocked quantity.")
    uom_id = fields.Many2one(UOM, string="Unit", ondelete="cascade")

    def action_confirm(self):
        self.ensure_one()
        refs = {
            "purchase_line_id": self.purchase_line_id.id or False,
            "sale_line_id": self.sale_line_id.id or False,
            "source_load_id": self.source_load_id.id or False,
            "stock_move_line_id": self.stock_move_line_id.id or False,
            "original_attachment_id": self.original_attachment_id.id or False,
            "physical_source_kind": self.physical_source_kind,
            "physical_source_ref": self.physical_source_ref or False,
            "source_revision_key": self.source_revision_key or False,
        }
        quantity = self.planned_quantity if self.planned_quantity_known else None
        outcome = self.slot_id.action_commit_cargo(
            refs,
            quantity,
            self.uom_id.id if self.planned_quantity_known else None,
            self.expected_booking_revision_id.id or False,
            self.operation_key,
        )
        return self._outcome(outcome, "Cargo commitment")


class PlasticosExportSlotReleaseCargo(models.TransientModel):
    _name = "plasticos.export.slot.release.cargo"
    _inherit = ["plasticos.export.slot.command.mixin"]
    _description = "Release Cargo from an Export Slot"
    _operation_prefix = "release-cargo"

    cargo_link_id = fields.Many2one(
        EXPORT_CARGO_LINK,
        string="Cargo",
        required=True,
        ondelete="cascade",
        domain="[('slot_id', '=', slot_id), ('state', '!=', 'released')]",
    )
    reason = fields.Text(required=True, help="Why this cargo is released. Posted on the booking.")

    def action_confirm(self):
        self.ensure_one()
        outcome = self.slot_id.action_release_cargo(
            self.cargo_link_id.id,
            self.expected_booking_revision_id.id or False,
            self.operation_key,
            self.reason or "",
        )
        return self._outcome(outcome, "Cargo release")


class PlasticosExportSlotBindJourney(models.TransientModel):
    _name = "plasticos.export.slot.bind.journey"
    _inherit = ["plasticos.export.slot.command.mixin"]
    _description = "Bind a Container Journey to an Export Slot"
    _operation_prefix = "bind-journey"

    journey_id = fields.Many2one(
        ISO_JOURNEY,
        string="Container Journey",
        required=True,
        ondelete="cascade",
        domain="[('company_id', '=', company_id), ('identity_state', 'in', ('attributed', 'verified'))]",
    )
    source_basis = fields.Text(required=True, help="The evidence that this container carries this slot.")

    def action_confirm(self):
        self.ensure_one()
        outcome = self.slot_id.action_bind_journey(
            self.journey_id.id,
            self.expected_booking_revision_id.id or False,
            self.operation_key,
            self.source_basis or "",
        )
        return self._outcome(outcome, "Container binding")


class PlasticosExportSlotCommandEntry(models.Model):
    _inherit = "plasticos.export.booking.slot"

    def _open_command_screen(self, model, name):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": "form",
            "target": "new",
            "context": {"default_slot_id": self.id},
        }

    def action_open_commit_cargo(self):
        """Commit Cargo screen; the frozen ``action_commit_cargo`` decides."""
        return self._open_command_screen("plasticos.export.slot.commit.cargo", "Commit Cargo")

    def action_open_release_cargo(self):
        """Release Cargo screen; the frozen ``action_release_cargo`` decides."""
        return self._open_command_screen("plasticos.export.slot.release.cargo", "Release Cargo")

    def action_open_bind_journey(self):
        """Bind Container screen; the frozen ``action_bind_journey`` decides."""
        return self._open_command_screen("plasticos.export.slot.bind.journey", "Bind Container")
