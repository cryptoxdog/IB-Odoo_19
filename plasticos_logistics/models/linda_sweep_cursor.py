"""Where the Linda load-obligation sweep resumes (S11, OP11-E03, F6).

One row per sweep lane and company (a company record rule isolates them). The
sweep reads and writes the row of the company it runs in, so each company pages
through its own loads; it pages by id and wraps, and the row holds the last id of
the last full page. The pre-S11 cursor was one global value per lane: the
migration put it in the sweep company's row only, and other companies start at 0. Before S11 the
cursor lived in ``ir.config_parameter`` (``plasticos_logistics.linda_load_sweep_cursor.<lane>``);
the 19.0.1.14.24 migration moved that value here once, and the sweep no longer
writes a system parameter. Behaviour is unchanged: the same page, the same wrap.
"""

from odoo import api, fields, models


class PlasticosLindaSweepCursor(models.Model):
    _name = "plasticos.linda.sweep.cursor"
    _description = "Plasticos Linda Load Sweep Cursor"

    lane = fields.Selection(
        [("ack", "Dispatch Acknowledgement"), ("chase", "Document Chase")],
        required=True,
        readonly=True,
        help="Which load-obligation sweep this cursor belongs to.",
    )
    company_id = fields.Many2one("res.company", required=True, readonly=True, index=True, ondelete="cascade")
    last_load_id = fields.Integer(
        readonly=True, default=0, help="Id of the last load of the last full page; 0 starts from the first load."
    )

    _one_cursor_per_lane = models.Constraint(
        "UNIQUE(lane, company_id)",
        "Each Linda sweep lane has one cursor per company.",
    )
    _non_negative = models.Constraint("CHECK(last_load_id >= 0)", "A sweep cursor is a load id or 0.")

    @api.model
    def _get_position(self, lane):
        """The current company's cursor for ``lane``; 0 when none is stored."""
        cursor = self.search([("lane", "=", lane), ("company_id", "=", self.env.company.id)], limit=1)
        return cursor.last_load_id or 0

    @api.model
    def _set_position(self, lane, last_load_id):
        """Store the cursor for ``lane`` in the current company, creating its row once."""
        company = self.env.company
        cursor = self.search([("lane", "=", lane), ("company_id", "=", company.id)], limit=1)
        if cursor:
            if cursor.last_load_id != last_load_id:
                cursor.write({"last_load_id": last_load_id})
            return cursor
        return self.create({"lane": lane, "company_id": company.id, "last_load_id": last_load_id})
