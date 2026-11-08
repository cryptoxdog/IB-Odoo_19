from odoo import models
from odoo.tools.float_utils import float_compare

# Buyer Receiving is the only quantity-scoped invoice evidence. Aggregation of
# partial receipts is not an admitted rule, so one row must cover the subject.
RECEIVING_TAG_CODE = "RECEIVING"


class PlasticosComplianceService(models.AbstractModel):
    """Document compliance checking service.

    NOTE: AbstractModel = no database table, no ACL needed.
    This is a service class, not a data model. Audit tools may flag
    "MISSING_ACL" but this is a false positive for AbstractModel classes.
    """

    _name = "plasticos.compliance.service"
    _description = "Compliance Service"

    # Gates name the rule flag that scopes them: a rule required for close only must
    # not block invoice posting (plasticos.document.rule required_for_*).
    _PURPOSE_FLAGS = {"invoice": "required_for_invoice", "close": "required_for_close"}

    def get_missing_documents(self, res_model, res_id, purpose=None):
        domain = [("res_model", "=", res_model), ("active", "=", True)]
        if purpose is not None:
            domain.append((self._PURPOSE_FLAGS[purpose], "=", True))
        rules = self.env["plasticos.document.rule"].search(domain)

        missing = []

        # Batch query: fetch all documents for this record with any of the rule tags
        tag_ids = rules.mapped("tag_id").ids
        all_docs = (
            self.env["plasticos.document"].search(
                [
                    ("res_model", "=", res_model),
                    ("res_id", "=", res_id),
                    ("tag_id", "in", tag_ids),
                    ("association_state", "=", "accepted"),
                    "|",
                    ("verified", "=", True),
                    ("override", "=", True),
                ]
            )
            if tag_ids
            else self.env["plasticos.document"]
        )

        # Group docs by tag_id
        docs_by_tag = {}
        for doc in all_docs:
            if doc.tag_id.id not in docs_by_tag:
                docs_by_tag[doc.tag_id.id] = self.env["plasticos.document"]
            docs_by_tag[doc.tag_id.id] |= doc

        for rule in rules:
            docs = docs_by_tag.get(rule.tag_id.id, self.env["plasticos.document"])
            # Historical approval is not current eligibility. Expired, inactive,
            # superseded, replaced, or unbound evidence stays on the record and
            # does not satisfy the rule.
            valid_docs = docs.filtered(
                lambda d, rule=rule: (
                    d._currently_eligible() and self._quantity_covers_subject(d, rule, res_model, res_id)
                )
            )

            if not valid_docs:
                missing.append(rule.tag_id.code)

        return missing

    def _quantity_covers_subject(self, doc, rule, res_model, res_id):
        """One Receiving row covers a transaction only when its own quantity does.

        Partial rows are not summed. An unknown quantity fails closed. Other tags
        are not quantity evidence.
        """
        if not rule.tag_id or rule.tag_id.code != RECEIVING_TAG_CODE:
            return True
        if res_model != "plasticos.transaction":
            return False
        transaction = self.env["plasticos.transaction"].browse(res_id).exists()
        if not transaction or not transaction.quantity or not doc.covered_quantity:
            return False
        return float_compare(doc.covered_quantity, transaction.quantity, precision_digits=2) >= 0

    def is_compliant(self, res_model, res_id, purpose=None):
        """Live eligibility. This read does not store, recompute, or post."""
        return not self.get_missing_documents(res_model, res_id, purpose=purpose)
