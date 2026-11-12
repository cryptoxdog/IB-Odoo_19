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

An issue mail is held, untouched and still outgoing, until an earlier
cancellation notice to the same party is confirmed sent. Selection in the
same batch is not delivery. Unknown and failed notices keep the hold.

The claim is the logical send authorization (S4, V06). It takes the source row
lock first (the order revision acceptance uses), then the request row, and
re-reads the current source, recipient and payload under both locks. A
revision that won the source lock first leaves the old unclaimed mail canceled
before SMTP; a claim that won first is kept, and the later revision treats it
as in-flight history. Ordinary mail never reaches this path.
"""

import ast
import json
import smtplib

from odoo import fields, models
from odoo.exceptions import LockError
from odoo.tools import email_normalize, email_normalize_all

LOGISTICS_REQUEST = "plasticos.logistics.request"
PLASTICOS_LOAD = "plasticos.load"
# Set on the outgoing notification mail of a carrier dispatch-packet composer (S4, V10).
# Its value names the load ("dispatch_packet:<load id>") and must match the mail's own res_id.
DISPATCH_PACKET_HEADER = "X-Plasticos-Release"
DISPATCH_PACKET_VALUE = "dispatch_packet"
# Context set by the composer only while it sends a release packet.
DISPATCH_PACKET_SEND_CONTEXT = "plasticos_dispatch_packet_send"
REQUEST_TABLE = "plasticos_logistics_request"


class MailMailInherit(models.Model):
    _inherit = "mail.mail"

    def send(self, auto_commit=False, raise_exception=False, post_send_callback=None):
        requests = self.env[LOGISTICS_REQUEST].sudo()  # sudo: queue bookkeeping reads every Linda request
        withheld, linda_mails, held = requests._guard_mails_before_send(
            self.sudo()  # sudo: queue may run as any user; only Linda mail is guarded
        )
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

    def _linda_request_mail_ids(self, mails):
        """Mail ids that already have a Linda request row.

        This is a read of flushed rows only. It does not flush the request
        model and it does not take the row lock. ``_linda_claim_outgoing``
        remains the only path that does either, and only for these ids.
        """
        mail_ids = tuple(mails.ids)
        if not mail_ids:
            return set()
        requests = self.env[LOGISTICS_REQUEST].sudo()  # sudo: queue claim reads Linda rows by mail id
        if requests._table != REQUEST_TABLE:
            raise RuntimeError("Linda request storage name drifted")
        self.env.cr.execute(
            """
            SELECT mail_id
              FROM plasticos_logistics_request
             WHERE mail_id IN %s
            """,
            (mail_ids,),
        )
        return {row[0] for row in self.env.cr.fetchall() if row[0]}

    def _linda_claim_outgoing(self, mail):
        """Decide whether this worker may hand one outgoing mail to native SMTP.

        ``claimed`` means this worker won the single queued Linda request and
        has recorded the attempt. ``send`` means the mail is not Linda's.
        ``skip`` means another worker already claimed it, or it is Linda mail
        that is no longer a fresh queued attempt. The row lock is what stops
        two queue workers from both passing ``_guard_mails_before_send`` and
        both reaching SMTP.
        """
        requests = self.env[LOGISTICS_REQUEST].sudo()  # sudo: queue claim locks the Linda request row
        if requests._table != REQUEST_TABLE:
            raise RuntimeError("Linda request storage name drifted")
        requests.flush_model()
        self.env.cr.execute(
            "SELECT id FROM plasticos_logistics_request WHERE mail_id = %s AND state = %s",
            (mail.id, "queued"),
        )
        candidates = [row[0] for row in self.env.cr.fetchall()]
        if not candidates:
            return "skip" if requests.search([("mail_id", "=", mail.id)], limit=1) else "send"
        if len(candidates) != 1:
            return "skip"
        source_model, source_id = requests.browse(candidates[0])._source_lock_target()
        try:
            with self.env.cr.savepoint():
                # Source before request: the same order revision acceptance uses.
                requests._lock_source(source_model, source_id)
        except LockError:
            # A revision is being accepted on this source; decide on the next queue run.
            return "skip"
        self.env.cr.execute(
            """
            SELECT id, COALESCE(send_attempt_count, 0)
              FROM plasticos_logistics_request
             WHERE mail_id = %s
               AND state = %s
             FOR UPDATE
            """,
            (mail.id, "queued"),
        )
        rows = self.env.cr.fetchall()
        if not rows:
            return "skip"
        if len(rows) != 1 or rows[0][1]:
            return "skip"
        request_id, attempt_count = rows[0]
        request = requests.browse(request_id)
        # Re-read what other transactions committed before the locks were granted.
        self.env.invalidate_all()
        reason = request._current_block_reason()
        if reason:
            # The source moved before this claim: the unclaimed mail never reaches SMTP.
            request._cancel_queued(reason)
            return "skip"
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

        outgoing = self.filtered(lambda mail: mail.state == "outgoing")
        linda_mail_ids = self._linda_request_mail_ids(outgoing)
        allowed = self.browse()
        for mail in self:
            if mail.state != "outgoing" or mail.id not in linda_mail_ids:
                # Ordinary mail never flushes or locks the Linda request table.
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

    @staticmethod
    def _plasticos_header_map(raw):
        """Headers stored on a mail.mail, as a dict; anything unreadable is no header."""
        if not raw:
            return {}
        for parse in (json.loads, ast.literal_eval):
            try:
                value = parse(raw)
            except (ValueError, SyntaxError, TypeError):
                continue
            if isinstance(value, dict):
                return value
        return {}

    def _plasticos_dispatch_packet_loads(self):
        """Loads whose own carrier this packet mail reached.

        The header value must name the mail's own load, and the mail must be addressed to
        that load's carrier: one packet post also mails internal followers, and a follower
        copy reaching "sent" is not the carrier receiving the instruction.
        """
        load_ids = []
        for mail in self:
            if mail.model != PLASTICOS_LOAD or not mail.res_id:
                continue
            marker = self._plasticos_header_map(mail.headers).get(DISPATCH_PACKET_HEADER)
            if marker != f"{DISPATCH_PACKET_VALUE}:{mail.res_id}":
                continue
            load = self.env[PLASTICOS_LOAD].browse(mail.res_id).exists()
            carrier = load.carrier_id
            if not carrier:
                continue
            carrier_email = email_normalize(carrier.email or "")
            addressed = carrier in mail.recipient_ids or (
                carrier_email and carrier_email in email_normalize_all(mail.email_to or "")
            )
            if addressed:
                load_ids.append(load.id)
        return self.env[PLASTICOS_LOAD].browse(load_ids)

    def _plasticos_stamp_dispatch_sent(self):
        """First confirmed send of a dispatch packet starts the acknowledgement clock."""
        for load in self._plasticos_dispatch_packet_loads().filtered(lambda load: not load.dispatch_sent):
            load.write({"dispatch_sent": fields.Datetime.now()})
            load.message_post(body="Dispatch packet confirmed sent to carrier.")

    def _postprocess_sent_message(self, success_pids, success_emails, failure_reason=False, failure_type=None):
        # Read before native post-processing: an auto-delete mail is gone afterwards. The gate is
        # the transport's own verdict (state "sent"): native _send also reports a failure_type such
        # as mail_email_invalid for a mail that still reached its valid recipients.
        sent = self.filtered(lambda mail: mail.state == "sent")
        if sent and sent._plasticos_dispatch_packet_loads():
            sent.sudo()._plasticos_stamp_dispatch_sent()  # sudo: queue workers stamp the sent packet's own load
        res = super()._postprocess_sent_message(
            success_pids,
            success_emails,
            failure_reason=failure_reason,
            failure_type=failure_type,
        )
        # The id lookup is raw SQL, so an ordinary message does not flush the request table.
        existing = self.exists()
        linda_ids = self._linda_request_mail_ids(existing)
        if linda_ids:
            self.env[LOGISTICS_REQUEST].sudo()._reconcile_mails(  # sudo: mirrors only Linda mail after send
                existing.filtered(lambda mail: mail.id in linda_ids),
                failure_type=failure_type,
            )
        return res
