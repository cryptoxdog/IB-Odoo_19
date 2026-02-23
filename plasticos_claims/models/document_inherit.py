from odoo import api, models


class PlasticosDocumentInherit(models.Model):
    _inherit = "plasticos.document"

    @api.model_create_multi
    def create(self, vals_list):
        """Override to trigger claim auto-creation on document upload.

        Uses @api.model_create_multi for Odoo 19 compatibility.
        """
        records = super().create(vals_list)
        for record in records:
            record._check_claim_trigger()
        return records

    def _check_claim_trigger(self):
        """Auto-create claim when Claim Pics document is uploaded."""
        self.ensure_one()

        if not self.tag_id:
            return

        claim_codes = ("claim_pics", "claim_photo", "claim")
        if self.tag_id.code.lower() not in claim_codes:
            return

        # Find transaction via load or direct link
        tx = None
        if self.res_model == "plasticos.load":
            tx = self.env["plasticos.transaction"].search([("load_id", "=", self.res_id)], limit=1)
        elif self.res_model == "plasticos.transaction":
            tx = self.env["plasticos.transaction"].browse(self.res_id)

        if not tx:
            return

        # Create claim
        Claim = self.env["plasticos.claim"]
        existing = Claim.search(
            [
                ("source_document_id", "=", self.id),
            ],
            limit=1,
        )
        if existing:
            return

        claim = Claim.create(
            {
                "transaction_id": tx.id,
                "source_document_id": self.id,
                "case_type": "buyer_claim",
                "severity": "medium",
                "notes": f"Auto-created from document: {self.name}",
            }
        )

        # Notify sales rep and quality manager
        claim._send_claim_notification()

    def _send_claim_notification(self):
        """Send email notification for auto-created claim.

        Uses the claim notification template if available.
        Falls back to activity creation if template not found.
        """
        self.ensure_one()
        template = self.env.ref(
            "plasticos_claims.email_template_claim_created",
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=False)
        else:
            # Fallback: create activity for sales rep
            tx = self.env["plasticos.transaction"].search([("id", "=", self.transaction_id.id)], limit=1)
            if tx and tx.user_id:
                self.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary="New Claim Created",
                    note=f"Claim {self.name} auto-created from document upload.",
                    user_id=tx.user_id.id,
                )
