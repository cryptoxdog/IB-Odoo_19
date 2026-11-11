"""Immutable Mack broker advice receipts: only an authenticated source can trigger them."""
import hashlib
import json
import re
import uuid
from html.parser import HTMLParser

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


class _Plaintext(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _plain(html):
    parser = _Plaintext()
    parser.feed(str(html or ""))
    return " ".join(" ".join(parser.parts).lower().split())


class BrokerConsultation(models.Model):
    _name = "plasticos.broker.consultation"
    _description = "Immutable Broker Advice Consultation Receipt"
    _order = "id desc"

    source_model = fields.Selection(
        [("plasticos.intake", "Intake"), ("plasticos.web.lead", "Web Lead"),
         ("plasticos.offer", "Offer"), ("plasticos.match.result", "Match Result")],
        required=True, readonly=True)
    source_id = fields.Integer(required=True, readonly=True)
    source_revision = fields.Char(required=True, readonly=True)
    source_message_id = fields.Many2one("mail.message", readonly=True, ondelete="restrict")
    request_key = fields.Char(required=True, readonly=True)
    question = fields.Text(required=True, readonly=True)
    response_snapshot = fields.Json(required=True, readonly=True)
    actor_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    company_id = fields.Many2one("res.company", required=True, readonly=True, ondelete="restrict")

    _unique_consultation_intent = models.UniqueIndex("(request_key)")
    _unique_source_message = models.UniqueIndex("(source_message_id) WHERE source_message_id IS NOT NULL")

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError("Consultation receipts are created only through action_consult, not direct ORM writes.")

    def write(self, vals):
        raise UserError("Consultation responses are immutable. Make a new consultation.")

    def unlink(self):
        raise UserError("Consultation receipts cannot be deleted.")

    @api.model
    def _verify_source_message(self, source_message_id, source_model, source_id, question):
        if not source_message_id:
            return None
        message = self.env["mail.message"].browse(int(source_message_id)).exists()
        if not message:
            raise UserError("The referenced source message does not exist.")
        message.check_access("read")
        if message.model != source_model or message.res_id != source_id:
            raise AccessError("Source message is not attached to this exact target record.")
        if message.author_id != self.env.user.partner_id or message.message_type != "comment":
            raise AccessError("Only your authenticated Odoo internal message may trigger a Mack consultation.")
        normalized_question = " ".join(question.lower().split())
        if not normalized_question or normalized_question not in _plain(message.body):
            raise AccessError("The request must be present in the verified source message.")
        if message.parent_id and (message.parent_id.model != source_model or message.parent_id.res_id != source_id):
            raise AccessError("Message thread does not belong to the authorized source record.")
        return message

    @api.model
    def action_consult(self, source_model, source_id, question, source_message_id=None):
        """A deterministic consultation. No chatter posting, model call, or business mutation."""
        if self.env.user.share:
            raise AccessError("Only authenticated internal brokers may request Mack advice.")
        question = str(question or "").strip()
        if not question or len(question) > 1500:
            raise UserError("Enter a specific question of at most 1,500 characters.")
        service = self.env["plasticos.broker.advice.service"]
        target = service._authorized_target(source_model, source_id)
        message = self._verify_source_message(source_message_id, source_model, target.id, question)
        key = (hashlib.sha256(f"mack:{message.id}".encode()).hexdigest() if message
               else hashlib.sha256(f"mack:manual:{uuid.uuid4().hex}".encode()).hexdigest())
        existing = self.search([("request_key", "=", key)], limit=1) if message else self.browse()
        if existing:
            if (existing.source_model, existing.source_id, existing.question, existing.actor_id.id) != (
                source_model, target.id, question, self.env.user.id
            ):
                raise AccessError("A source message cannot be reinterpreted into a different consultation.")
            return existing
        advice = service.advise_v2(source_model, target.id, question)
        company = target.company_id if "company_id" in target._fields and target.company_id else self.env.company
        vals = {"source_model": source_model, "source_id": target.id,
                "source_revision": str(target.write_date or target.create_date or "unknown"),
                "source_message_id": message.id if message else False, "request_key": key,
                "question": question, "response_snapshot": json.loads(json.dumps(advice, default=str)),
                "actor_id": self.env.user.id, "company_id": company.id}
        try:
            with self.env.cr.savepoint():
                return super(BrokerConsultation, self).create([vals])
        except IntegrityError:
            concurrent = self.search([("request_key", "=", key)], limit=1)
            if concurrent and concurrent.actor_id == self.env.user and concurrent.question == question:
                return concurrent
            raise UserError("Source message was already consumed by another consultation.") from None
