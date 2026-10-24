"""Send-time guard for Linda supplier mail (WP01b, plan section 5 steps 5-6).

A queued Linda mail is rechecked when the native queue processes it, so a PO
or recipient change that did not pass through ``purchase.order.write`` still
cannot release a stale document. The native outcome is mirrored back onto the
request only after transport records it.

Linda mails are handed to native sending one at a time, each right after its
attempt marker is recorded, so an abort mid-batch never marks a mail that was
not attempted. Only the queue path (``auto_commit=True``) makes the marker
durable before SMTP; a manual "Send Now" keeps native transactional semantics.

An issue mail is held, untouched and still outgoing, while an earlier
cancellation notice to the same party is pending outside this batch, so a
reissue never overtakes the notice; the next queue run picks it up.
"""

import smtplib

from odoo import models

LOGISTICS_REQUEST = "plasticos.logistics.request"


class MailMailInherit(models.Model):
    _inherit = "mail.mail"

    def send(self, auto_commit=False, raise_exception=False, post_send_callback=None):
        # sudo: transport bookkeeping must see every Linda request and mail whatever user runs
        # the queue; it only cancels or annotates Linda's own mail.
        requests = self.env[LOGISTICS_REQUEST].sudo()
        withheld, linda_mails, held = requests._guard_mails_before_send(self.sudo())
        options = {
            "auto_commit": auto_commit,
            "raise_exception": raise_exception,
            "post_send_callback": post_send_callback,
        }
        # Withheld and held mails stay out of the native batch, whose connection-failure
        # path rewrites every mail it was given to "exception".
        others = self - withheld - linda_mails - held
        res = super(MailMailInherit, others).send(**options) if others else True
        # Native order: the queue sends by ascending id.
        for mail in linda_mails.sorted("id"):
            requests._mark_attempt(mail)
            if auto_commit is True:
                # Persist the marker before SMTP, as the native queue commits per mail;
                # otherwise a crash mid-send would roll it back and the cron would resend.
                self.env.cr.commit()
            try:
                super(MailMailInherit, self.browse(mail.id)).send(**options)
            except smtplib.SMTPServerDisconnected:
                # The session dropped mid-send: the message may have been delivered.
                requests._mark_interrupted(mail)
                raise
        return res

    def _postprocess_sent_message(self, success_pids, success_emails, failure_reason=False, failure_type=None):
        res = super()._postprocess_sent_message(
            success_pids,
            success_emails,
            failure_reason=failure_reason,
            failure_type=failure_type,
        )
        # sudo: same bookkeeping scope as send(); mirrors only the native outcome of these mails.
        self.env[LOGISTICS_REQUEST].sudo()._reconcile_mails(self.exists(), failure_type=failure_type)
        return res
