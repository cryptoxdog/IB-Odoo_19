from odoo import models


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
            valid_docs = docs.filtered(lambda d: d._currently_eligible())

            if not valid_docs:
                missing.append(rule.tag_id.code)

        return missing

    def is_compliant(self, res_model, res_id, purpose=None):
        missing = self.get_missing_documents(res_model, res_id, purpose=purpose)
        return len(missing) == 0
