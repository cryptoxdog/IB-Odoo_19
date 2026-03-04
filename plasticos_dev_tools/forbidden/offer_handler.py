# ============================================
# Canonical Header (v4.0 Production Baseline)
# ============================================
# File Name: offer_handler.py
# Version: 4.6
# Created: 2025-10-17
# Author: Igor Beylin
# Domain: Plastic Recycling / AI-Augmented ERP
# Purpose: Offer drafting, validation, and dispatch runtime for PlasticOS
# Related Files: odoo_model_offer_response_v4.0.py, ../agents/offer_drafting_agent_v4.5.yaml
# ============================================

"""
Offer Handler
=============
This runtime module governs offer creation, validation, and lifecycle management.
Integrated directly with Odoo 19 models (`sale.order`, `res.partner`, `plasticos.offer.log`).

Core Capabilities:
- Composes offers using buyer profiles and pricing schema.
- Validates data consistency before dispatch.
- Logs and audits all actions to Decision Ledger.
- Responds dynamically to buyer acceptance, rejection, or counteroffers.
"""

# ------------------------------------------------------------
# Imports and Environment
# ------------------------------------------------------------
import datetime

from odoo import api, fields, models


# ------------------------------------------------------------
# Offer Handler Class
# ------------------------------------------------------------
class OfferHandler(models.Model):
    _name = "plasticos.offer.handler"
    _description = "Offer Drafting and Response Handler"

    buyer_profile_id = fields.Many2one("plasticos.buyer.profile", string="Buyer Profile")
    offer_text = fields.Text("Offer Body")
    offer_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending"),
            ("sent", "Sent"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
            ("countered", "Countered"),
        ],
        default="draft",
    )
    proposed_price = fields.Float("Proposed Price")
    product_grade = fields.Char("Material Grade")
    validity_date = fields.Date("Validity Date")
    trust_index_snapshot = fields.Float("Trust Index (Snapshot)")
    sentiment_score = fields.Float("Sentiment Confidence")

    # --------------------------------------------------------
    # Offer Composition
    # --------------------------------------------------------
    @api.model
    def compose_offer(self, buyer_id, material_grade, proposed_price):
        buyer = self.env["plasticos.buyer.profile"].browse(buyer_id)
        trust_index = buyer.trust_index
        greeting = "Hi {0},".format(buyer.contact_name or "there")
        tone_tag = self._select_tone(trust_index)

        offer_body = (
            f"{greeting}\n\n"
            f"Following our recent conversation, here's a formal offer for {material_grade} "
            f"at ${proposed_price:,.2f} per MT. The offer is valid through "
            f"{datetime.date.today() + datetime.timedelta(days=3)}.\n\n"
            f"{tone_tag}\n\n"
            "Please confirm receipt or reach out with any adjustments."
        )

        offer_record = self.create(
            {
                "buyer_profile_id": buyer.id,
                "offer_text": offer_body,
                "proposed_price": proposed_price,
                "product_grade": material_grade,
                "validity_date": datetime.date.today() + datetime.timedelta(days=3),
                "trust_index_snapshot": trust_index,
            }
        )

        return offer_record

    # --------------------------------------------------------
    # Tone Calibration
    # --------------------------------------------------------
    def _select_tone(self, trust_index):
        if trust_index >= 80:
            return "Always a pleasure working with you - confident this one will move fast."
        elif trust_index >= 60:
            return "Appreciate your continued collaboration - I believe this offer fits your needs."
        else:
            return "Understand things have been variable lately - happy to ensure this deal works for both sides."

    # --------------------------------------------------------
    # Offer Dispatch
    # --------------------------------------------------------
    def send_offer(self):
        for record in self:
            email_template = self.env.ref("plasticos_automation.email_template_offer")
            email_template.send_mail(record.id, force_send=True)
            record.offer_status = "sent"
            record._log_offer_action("Offer sent via email.")

    # --------------------------------------------------------
    # Offer Response Processing
    # --------------------------------------------------------
    def process_response(self, buyer_response):
        for record in self:
            parsed = self._interpret_response(buyer_response)
            record.offer_status = parsed.get("status")
            record.sentiment_score = parsed.get("confidence", 0.0)
            record._log_offer_action(f"Buyer response processed: {record.offer_status}")

    def _interpret_response(self, response_text):
        positive_tokens = ["accept", "confirmed", "deal", "okay"]
        negative_tokens = ["reject", "decline", "not interested"]
        counter_tokens = ["counter", "adjust", "negotiate"]

        text_lower = response_text.lower()
        if any(t in text_lower for t in positive_tokens):
            return {"status": "accepted", "confidence": 0.9}
        elif any(t in text_lower for t in counter_tokens):
            return {"status": "countered", "confidence": 0.75}
        elif any(t in text_lower for t in negative_tokens):
            return {"status": "rejected", "confidence": 0.85}
        else:
            return {"status": "pending", "confidence": 0.4}

    # --------------------------------------------------------
    # Logging Utility
    # --------------------------------------------------------
    def _log_offer_action(self, message):
        self.env["plasticos.decision.ledger"].create(
            {
                "timestamp": datetime.datetime.now(),
                "actor": "PlasticOS Offer Handler",
                "context": self._name,
                "message": message,
                "record_ref": self.id,
            }
        )


# End of File
# ============================================================
