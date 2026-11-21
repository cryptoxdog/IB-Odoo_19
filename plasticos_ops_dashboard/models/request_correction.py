"""Request Correction: an internal request on the one existing exception activity (CTO ruling, TASK-040).

The Operations Manager writes a required reason. The record carries an internal note (no recipient,
``mail.mt_note``); the same activity keeps its routed owner, records the reason and is due today.
Nothing is emailed outside the company (Linda stays the only external chase sender), no second
activity is created, and the document and its business evidence are not edited.

The wizard is transient: it holds the reason for one click and stores no queue.
"""

from markupsafe import Markup

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

OPERATIONS_GROUP_XMLID = "plasticos_security_base.group_operations_manager"


class PlasticosOpsRequestCorrection(models.TransientModel):
    _name = "plasticos.ops.request.correction"
    _description = "Request Correction (internal, one click)"

    activity_id = fields.Many2one(
        "mail.activity",
        string="Exception",
        required=True,
        ondelete="cascade",
        help="The exception activity the correction is requested on.",
    )
    reason = fields.Text(string="Reason", required=True, help="What must be corrected and why.")

    def action_request_correction(self):
        """Note the record internally and put the reason on the same activity. Server-side checks."""
        self.ensure_one()
        if not self.env.user.has_group(OPERATIONS_GROUP_XMLID):
            raise AccessError(_("Only an Operations Manager can request a correction."))
        reason = (self.reason or "").strip()
        if not reason:
            raise UserError(_("A reason is required to request a correction."))
        activity = self.activity_id
        body = Markup("<p>Correction requested by %s: %s</p>") % (self.env.user.name, reason)
        record = activity._plasticos_record()
        if record is not None and hasattr(record, "message_post"):
            record.message_post(body=body, message_type="comment", subtype_xmlid="mail.mt_note", partner_ids=[])
        activity.write(
            {
                "note": (activity.note or Markup()) + body,
                "date_deadline": fields.Date.context_today(self),
            }
        )
        return {"type": "ir.actions.act_window_close"}
