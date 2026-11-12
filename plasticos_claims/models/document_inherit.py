from odoo import api, models


class PlasticosDocumentInherit(models.Model):
    _inherit = "plasticos.document"

    @api.model_create_multi
    def create(self, vals_list):
        """Trigger claim auto-creation when a Claim Pics document is first stored."""
        records = super().create(vals_list)
        for record in records:
            record._check_claim_trigger()
        return records

    def write(self, vals):
        """A later exact association can create the claim without duplicating it."""
        records = super().write(vals)
        watched = {"tag_id", "res_model", "res_id", "load_id", "transaction_id", "association_state"}
        if watched.intersection(vals):
            for record in self:
                record._check_claim_trigger()
        return records

    def _claim_subject(self):
        """Return the transaction and, only for an exact load document, that load.

        Only legacy evidence rows open a claim. An operation-scoped row on the
        same original is another obligation, not another claim or notification.
        Both the create and the write path come through here.
        """
        self.ensure_one()
        transactions = self.env["plasticos.transaction"]
        loads = self.env["plasticos.load"]
        if (self.obligation_kind or "legacy") != "legacy":
            return transactions.browse(), loads.browse()
        transaction, load = self._legacy_claim_subject()
        if transaction and self.subject_company_id:
            companies, _requires = self._subject_company_candidates(transaction)
            if companies and self.subject_company_id not in companies:
                # The accepted company is not this trade's company: no claim on it.
                return transactions.browse(), loads.browse()
        return transaction, load

    def _legacy_claim_subject(self):
        self.ensure_one()
        transactions = self.env["plasticos.transaction"]
        loads = self.env["plasticos.load"]
        if self._association_conflict_reason():
            self._route_association_conflict()
            return transactions.browse(), loads.browse()
        if self.load_id or self.res_model == "plasticos.load":
            load = self.load_id
            if self.res_model == "plasticos.load" and self.res_id:
                pointed = loads.browse(self.res_id).exists()
                if load and pointed and load != pointed:
                    self._route_association_conflict()
                    return transactions.browse(), loads.browse()
                load = load or pointed
            if not load or not load.transaction_id:
                return transactions.browse(), loads.browse()
            if self.transaction_id and self.transaction_id != load.transaction_id:
                self._route_association_conflict()
                return transactions.browse(), loads.browse()
            return load.transaction_id, load
        if self.res_model == "plasticos.transaction" and self.res_id:
            transaction = transactions.browse(self.res_id).exists()
            if not transaction:
                return transactions.browse(), loads.browse()
            if self.transaction_id and self.transaction_id != transaction:
                self._route_association_conflict()
                return transactions.browse(), loads.browse()
            return transaction, loads.browse()
        if self.transaction_id and not self.load_id:
            return self.transaction_id, loads.browse()
        return transactions.browse(), loads.browse()

    def _check_claim_trigger(self):
        """Create one claim for a Claim Pics document on its exact subject."""
        self.ensure_one()
        if not self.tag_id:
            return
        claim_codes = ("claim_pics", "claim_photo", "claim")
        if self.tag_id.code.lower() not in claim_codes:
            return
        transaction, load = self._claim_subject()
        if not transaction:
            return
        claim_model = self.env["plasticos.claim"]
        existing = claim_model.search([("source_document_id", "=", self.id)], limit=1)
        if existing:
            return
        values = {
            "transaction_id": transaction.id,
            "source_document_id": self.id,
            "case_type": "buyer_claim",
            "severity": "medium",
            "notes": f"Auto-created from document: {self.name}",
        }
        if load:
            values["load_id"] = load.id
        claim = claim_model.create(values)
        claim._send_claim_notification()
