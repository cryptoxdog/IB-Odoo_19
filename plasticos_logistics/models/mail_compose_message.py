"""The physical-release guard runs again when a carrier composer actually sends (S4, D2).

``action_send_dispatch_packet`` and the three carrier-document actions check the
release guard when they open the native composer. A composer can stay open while
the lane, freight context or an owner hold changes, so opening is not the
authorization point. Submitting is: the load row is locked, the guard is read
again, and a refused release raises before native Odoo Mail posts or queues
anything. Scheduling such a composer is refused, because a scheduled message
would leave without this check (BRS-EXP-10-R004/R008, Codex 4545252969).

Ordinary composers, and internal notes that email no one, are untouched.
"""

from odoo import _, models
from odoo.exceptions import LockError, UserError

PLASTICOS_LOAD = "plasticos.load"
# Context set by plasticos.load._open_mail_composer: the release this composer carries.
LOAD_RELEASE_CONTEXT = "plasticos_load_release_operation"
# A carrier template is a release whoever opened the composer and whatever it carried.
RELEASE_TEMPLATE_OPERATIONS = {
    "plasticos_automation.email_template_dispatch_packet": "dispatch_packet",
    "plasticos_automation.email_template_delivery_order": "carrier_document",
    "plasticos_automation.email_template_bol_pickup": "carrier_document",
    "plasticos_automation.email_template_bol_delivery": "carrier_document",
}


class MailComposeMessagePlasticosLoad(models.TransientModel):
    _inherit = "mail.compose.message"

    def _plasticos_load_release_operation(self):
        """The physical operation this composer would release, or ``False``."""
        self.ensure_one()
        if self.model != PLASTICOS_LOAD:
            return False
        if self.template_id:
            xmlid = self.template_id.get_external_id().get(self.template_id.id)
            operation = RELEASE_TEMPLATE_OPERATIONS.get(xmlid)
            if operation:
                return operation
        return self.env.context.get(LOAD_RELEASE_CONTEXT) or False

    def _plasticos_release_wizards(self):
        return self.filtered(lambda wizard: not wizard.subtype_is_log and wizard._plasticos_load_release_operation())

    def _plasticos_recheck_load_release(self):
        """Lock each load this composer addresses and re-read every owner's release verdict."""
        for wizard in self._plasticos_release_wizards():
            operation = wizard._plasticos_load_release_operation()
            loads = self.env[PLASTICOS_LOAD].browse(wizard._evaluate_res_ids()).exists()
            if not loads:
                raise UserError(_("The load this carrier email was opened for no longer exists. Nothing was sent."))
            try:
                # Serialize with load writes so the verdict read below is the one that sends.
                loads.lock_for_update(allow_referencing=True)
            except LockError as exc:
                raise UserError(_("The load is being changed right now. Nothing was sent; try again.")) from exc
            loads.invalidate_recordset()
            loads._require_physical_release(operation)

    def _action_send_mail(self, auto_commit=False):
        self._plasticos_recheck_load_release()
        return super()._action_send_mail(auto_commit=auto_commit)

    def _action_schedule_message(self):
        if self._plasticos_release_wizards():
            raise UserError(
                _(
                    "A carrier dispatch or document email cannot be scheduled: it must pass the "
                    "release check at the moment it is sent. Send it now instead."
                )
            )
        return super()._action_schedule_message()
