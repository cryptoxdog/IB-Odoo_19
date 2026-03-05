from odoo import models


class PlasticosComplianceService(models.AbstractModel):
    """Document compliance checking service.

    NOTE: AbstractModel = no database table, no ACL needed.
    This is a service class, not a data model. Audit tools may flag
    "MISSING_ACL" but this is a false positive for AbstractModel classes.
    """

    _name = "plasticos.compliance.service"
    _description = "Compliance Service"

    def get_missing_documents(self, res_model, res_id):
        rules = self.env["plasticos.document.rule"].search([("res_model", "=", res_model), ("active", "=", True)])

        missing = []

        for rule in rules:
            docs = self.env["plasticos.document"].search(
                [
                    ("res_model", "=", res_model),
                    ("res_id", "=", res_id),
                    ("tag_id", "=", rule.tag_id.id),
                    "|",
                    ("verified", "=", True),
                    ("override", "=", True),
                ]
            )
            # Filter out expired documents so they no longer satisfy compliance
            valid_docs = docs.filtered(lambda d: not d.is_expired)

            if not valid_docs:
                missing.append(rule.tag_id.code)

        return missing

    def is_compliant(self, res_model, res_id):
        missing = self.get_missing_documents(res_model, res_id)
        return len(missing) == 0
