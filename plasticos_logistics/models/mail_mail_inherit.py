"""Send-time guard for Linda supplier mail (WP01b, plan section 5 steps 5-6).

A queued Linda mail is rechecked when the native queue processes it, so a PO
or recipient change that did not pass through ``purchase.order.write`` still
cannot release a stale document. The native outcome is mirrored back onto the
request only after transport records it.
"""

from odoo import models

LOGISTICS_REQUEST = "plasticos.logistics.request"


class MailMailInherit(models.Model):
    _inherit = "mail.mail"

    def send(self, auto_commit=False, raise_exception=False, post_send_callback=None):
        # sudo: transport bookkeeping must see every Linda request whatever user runs the queue.
        requests = self.env[LOGISTICS_REQUEST].sudo()
        if requests._guard_mails_before_send(self) and auto_commit is True:
            # Persist the attempt marker before SMTP, as the native queue commits per mail;
            # otherwise a crash mid-send would roll it back and the cron would resend blindly.
            self.env.cr.commit()
        return super().send(
            auto_commit=auto_commit,
            raise_exception=raise_exception,
            post_send_callback=post_send_callback,
        )

    def _postprocess_sent_message(self, success_pids, success_emails, failure_reason=False, failure_type=None):
        res = super()._postprocess_sent_message(
            success_pids,
            success_emails,
            failure_reason=failure_reason,
            failure_type=failure_type,
        )
        # sudo: same bookkeeping scope as send(); mirrors only the native outcome of these mails.
        self.env[LOGISTICS_REQUEST].sudo()._reconcile_mails(self.exists())
        return res
