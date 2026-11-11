"""Send Offer through the native Odoo 19 email composer.

Ordinary composers are untouched. A composer opened by
``plasticos.offer.action_send`` carries ``OFFER_SEND_CONTEXT``; when it is
submitted, the offer row is locked, re-validated (state, terms, buyer
audience, attachments), the email is posted through the native
``_action_send_mail`` path, and only then is the offer marked Sent with the
resulting ``mail.message``. Any failure before or during the native post
raises, so the transaction rolls back and the offer stays Draft.

Odoo accepting the email into its outgoing queue is not proof of SMTP
delivery: the offer records the submitted message, and the message's own
notifications carry the delivery outcome.
"""

from odoo import _, models
from odoo.exceptions import UserError

from .offer import OFFER_SEND_CONTEXT

OFFER_MODEL = "plasticos.offer"
COMPOSER_MODEL = "mail.compose.message"


class MailComposeMessagePlasticosOffer(models.TransientModel):
    _inherit = "mail.compose.message"

    def _plasticos_offer_send_wizards(self):
        if not self.env.context.get(OFFER_SEND_CONTEXT):
            return self.browse()
        return self.filtered(lambda wizard: wizard.model == OFFER_MODEL)

    def _plasticos_offer_for_send(self):
        """The one offer this composer sends, locked and re-validated."""
        self.ensure_one()
        if self.composition_mode != "comment" or self.res_domain:
            raise UserError(_("An offer email is sent from its own composer, one offer at a time."))
        res_ids = self._evaluate_res_ids()
        if len(res_ids) != 1:
            raise UserError(_("Send one offer at a time: open the offer and use Send Offer."))
        offer = self.env[OFFER_MODEL].browse(res_ids[0]).exists()
        if not offer:
            raise UserError(_("The offer no longer exists."))
        offer.check_access("write")
        # Serialize sends of one offer: a retried or double-clicked request waits
        # here, then sees the committed Sent state and is refused below.
        self.env.cr.execute("SELECT id FROM plasticos_offer WHERE id = %s FOR UPDATE", [offer.id])
        offer.invalidate_recordset()
        if offer.state != "draft":
            raise UserError(_("Offer %s was already sent. No second email was sent.") % offer.name)
        offer._plasticos_raise_send_blockers()
        if self.subtype_is_log:
            raise UserError(_("Send Offer emails the buyer; an internal note does not send the offer."))
        return offer

    def _plasticos_prepare_offer_attachments(self, offer):
        """Keep only attachments this offer may carry; store the sent pictures on the offer.

        Source pictures belong to the opportunity's material sheet. Each distinct
        content sent is stored once on the offer (``ir.attachment.copy`` reuses
        the same filestore object), so a later removal of the source picture
        cannot break a queued email.
        """
        self.ensure_one()
        Attachment = self.env["ir.attachment"]
        allowed = offer._plasticos_allowed_email_attachments()
        uploads = self.attachment_ids.filtered(
            lambda att: (
                att.res_model == COMPOSER_MODEL and att.res_id in (0, self.id or 0) and att.create_uid == self.env.user
            )
        )
        foreign = self.attachment_ids - uploads - allowed
        if foreign:
            raise UserError(
                _(
                    "These attachments do not belong to offer %(offer)s and cannot be sent with it: %(names)s.",
                    offer=offer.name,
                    names=", ".join(foreign.mapped("name")),
                )
            )
        owned = Attachment.search([("res_model", "=", OFFER_MODEL), ("res_id", "=", offer.id)])
        by_checksum = {att.checksum: att for att in owned if att.checksum}
        final = uploads
        for attachment in (self.attachment_ids - uploads).sorted("id"):
            if attachment.res_model == OFFER_MODEL and attachment.res_id == offer.id:
                final |= attachment
                continue
            existing = by_checksum.get(attachment.checksum) if attachment.checksum else None
            if existing:
                final |= existing
                continue
            copy = attachment.copy({"res_model": OFFER_MODEL, "res_id": offer.id, "res_field": False})
            if copy.checksum:
                by_checksum[copy.checksum] = copy
            final |= copy
        self.attachment_ids = [(6, 0, final.ids)]

    def _plasticos_check_offer_message(self, offer, message):
        """Native Odoo Mail produced an outgoing email for this offer, or nothing is recorded."""
        if not message or message.model != OFFER_MODEL or message.res_id != offer.id:
            raise UserError(_("Odoo Mail did not post the email for offer %s; it stays Draft.") % offer.name)
        # Reading the notification rows of the message this user just posted is
        # evidence only; mail.notification is not readable by every internal user.
        email_notifications = (
            self.env["mail.notification"]
            .sudo()
            .search_count([("mail_message_id", "=", message.id), ("notification_type", "=", "email")])
        )
        if not email_notifications:
            raise UserError(
                _("Odoo Mail queued no outgoing email for offer %s; it stays Draft. Check the recipients.") % offer.name
            )

    def _action_send_mail(self, auto_commit=False):
        offer_wizards = self._plasticos_offer_send_wizards()
        if not offer_wizards:
            return super()._action_send_mail(auto_commit=auto_commit)
        if offer_wizards != self:
            raise UserError(_("An offer email cannot be sent together with other emails."))
        offers = {}
        for wizard in self:
            offer = wizard._plasticos_offer_for_send()
            offer._plasticos_check_recipients(wizard.partner_ids)
            wizard._plasticos_prepare_offer_attachments(offer)
            # Followers are not the offer audience; scheduling would mark Sent before dispatch.
            wizard.write({"notify_skip_followers": True, "scheduled_date": False})
            offers[wizard.id] = offer
        result_mails, messages = super()._action_send_mail(auto_commit=False)
        for wizard in self:
            offer = offers[wizard.id]
            message = messages.filtered(lambda msg, offer=offer: msg.model == OFFER_MODEL and msg.res_id == offer.id)[
                -1:
            ]
            wizard._plasticos_check_offer_message(offer, message)
            offer._plasticos_mark_sent(message)
        return result_mails, messages

    def _action_schedule_message(self):
        if self._plasticos_offer_send_wizards():
            raise UserError(_("Scheduled sending is not available for offers. Send the offer now or discard."))
        return super()._action_schedule_message()
