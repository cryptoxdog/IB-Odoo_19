"""Send-time guard for Linda supplier mail (WP01b, plan section 5 steps 5-6).

A queued Linda mail is rechecked when the native queue processes it, so a PO
or recipient change that did not pass through ``purchase.order.write`` still
cannot release a stale document. The native outcome is mirrored back onto the
request only after transport records it.

Linda mails are handed to native sending one at a time. The attempt marker is
recorded inside ``_send``, after Odoo has applied personal-server throttling,
and the queued request row is claimed so a second worker cannot send it too.
Only the queue path (``auto_commit=True``) makes that claim durable before
SMTP; a manual "Send Now" keeps native transactional semantics.

An issue mail is held, untouched and still outgoing, while an earlier
cancellation notice to the same party is pending outside this batch, so a
reissue never overtakes the notice; the next queue run picks it up.
"""

import smtplib

from odoo import models

LOGISTICS_REQUEST = "plasticos.logistics.request"
REQUEST_TABLE = "plasticos_logistics_request"


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
            try:
                # Native Odoo selects the sending batch, including personal-server
                # throttling, before calling _send; only _send marks a real attempt.
                super(MailMailInherit, self.browse(mail.id)).send(**options)
            except smtplib.SMTPServerDisconnected:
                # The session dropped mid-send: the message may have been delivered.
                requests._mark_interrupted(mail)
                raise
        return res

    def _linda_claim_outgoing(self, mail):
        """Decide whether this worker may hand one outgoing mail to native SMTP.

        ``claimed`` means this worker won the single queued Linda request and
        has recorded the attempt. ``send`` means the mail is not Linda's.
        ``skip`` means another worker already claimed it, or it is Linda mail
        that is no longer a fresh queued attempt. The row lock is what stops
        two queue workers from both passing ``_guard_mails_before_send`` and
        both reaching SMTP.
        """
        requests = self.env[LOGISTICS_REQUEST].sudo()
        if requests._table != REQUEST_TABLE:
            raise RuntimeError("Linda request storage name drifted")
        requests.flush_model()
        self.env.cr.execute(
            """
            SELECT id, send_attempt_count
              FROM plasticos_logistics_request
             WHERE mail_id = %s
               AND state = %s
             FOR UPDATE
            """,
            (mail.id, "queued"),
        )
        rows = self.env.cr.fetchall()
        if not rows:
            return "skip" if requests.search([("mail_id", "=", mail.id)], limit=1) else "send"
        if len(rows) != 1 or rows[0][1]:
            return "skip"
        request_id, attempt_count = rows[0]
        request = requests.browse(request_id)
        request.invalidate_recordset(["send_attempt_count", "state"])
        # Same field write as _mark_attempt, bound to the locked row.
        request.write({"send_attempt_count": attempt_count + 1})
        return "claimed"

    def _send(
        self,
        auto_commit=False,
        raise_exception=False,
        smtp_session=None,
        alias_domain_id=False,
        mail_server=False,
        post_send_callback=None,
    ):
        """Mark actual Linda attempts only after Odoo's personal-server throttle.

        Native mail.mail.send() calls _split_by_delayed_batch() before _send(),
        so a deferred outgoing message has never reached an SMTP attempt.
        Personal-server ACL failures are left to native _send and are not
        recorded as attempts. Other mail.mail messages do not acquire Linda
        attempt markers.
        """
        if self.env["ir.mail_server"]._disable_send():
            return super()._send(
                auto_commit=auto_commit,
                raise_exception=raise_exception,
                smtp_session=smtp_session,
                alias_domain_id=alias_domain_id,
                mail_server=mail_server,
                post_send_callback=post_send_callback,
            )
        if mail_server and not self._filter_mail_mail_servers(mail_server):
            return super()._send(
                auto_commit=auto_commit,
                raise_exception=raise_exception,
                smtp_session=smtp_session,
                alias_domain_id=alias_domain_id,
                mail_server=mail_server,
                post_send_callback=post_send_callback,
            )

        allowed = self.browse()
        for mail in self:
            if mail.state != "outgoing":
                allowed |= mail
                continue
            decision = self._linda_claim_outgoing(mail)
            if decision == "skip":
                continue
            if decision == "claimed" and auto_commit is True:
                # Persist the claim before SMTP. A crash mid-send leaves the
                # marker committed and the mail rolled back to outgoing; the
                # next queue run records unknown instead of sending again.
                self.env.cr.commit()
            allowed |= mail
        if not allowed:
            return True
        return super(MailMailInherit, allowed)._send(
            auto_commit=auto_commit,
            raise_exception=raise_exception,
            smtp_session=smtp_session,
            alias_domain_id=alias_domain_id,
            mail_server=mail_server,
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
        self.env[LOGISTICS_REQUEST].sudo()._reconcile_mails(self.exists(), failure_type=failure_type)
        return res
