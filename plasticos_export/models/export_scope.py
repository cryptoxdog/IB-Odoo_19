"""What the Export dialog offers a reader without Logistics rights (S10 OP10-E06, review N8 of C07).

Operator rule 2026-11-12: a Sales Rep sees every allocation on every booking of
their companies, so no booking is overbooked, but cannot open another rep's
load, order or a private supplier. Exporting such a source link would read the
linked record in the rep's environment and raise AccessError. The cargo-link
source fields below are therefore not offered in the Export dialog to a user
outside Logistics. The slot's container journey is hidden only from a user in
none of the groups the Logistics owner lets read it (Logistics, Operations
Manager, System). The source names stay
exportable through the sudo-related ``*_ref`` text fields. Nothing changes for
Logistics users, and no record rule or ACL changes.
"""

from odoo import api, models

LOGISTICS_GROUP = "plasticos_security_base.group_logistics"
# Groups the Logistics owner grants read on the container journey
# (plasticos_security_base/security/ir.model.access.csv, access_iso_journey_*; System sees all).
JOURNEY_READER_GROUPS = (
    LOGISTICS_GROUP,
    "plasticos_security_base.group_operations_manager",
    "base.group_system",
)

# Cargo-link fields whose comodel is owner-scoped for a Sales Rep.
CARGO_LINK_SOURCE_LINKS = frozenset(
    {
        "purchase_line_id",
        "purchase_order_id",
        "supplier_id",
        "sale_line_id",
        "sale_order_id",
        "source_load_id",
        "stock_move_line_id",
        "original_attachment_id",
    }
)
# Slot fields whose comodel a Sales Rep has no access to (the Logistics container journey).
SLOT_SOURCE_LINKS = frozenset({"journey_id"})


def _without_owner_links(env, description, hidden, attributes, reader_groups=(LOGISTICS_GROUP,)):
    if env.su or any(env.user.has_group(group) for group in reader_groups):
        return description
    if attributes is not None and "exportable" not in attributes:
        return description
    for name in hidden & set(description):
        description[name]["exportable"] = False
    return description


class PlasticosExportCargoLinkExportScope(models.Model):
    _inherit = "plasticos.export.booking.cargo.link"

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        description = super().fields_get(allfields, attributes)
        return _without_owner_links(self.env, description, CARGO_LINK_SOURCE_LINKS, attributes)


class PlasticosExportSlotExportScope(models.Model):
    _inherit = "plasticos.export.booking.slot"

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        description = super().fields_get(allfields, attributes)
        return _without_owner_links(self.env, description, SLOT_SOURCE_LINKS, attributes, JOURNEY_READER_GROUPS)
