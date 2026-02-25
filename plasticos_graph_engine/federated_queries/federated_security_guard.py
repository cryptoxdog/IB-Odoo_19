from odoo import models


class FederatedSecurityGuard(models.AbstractModel):
    _name = "plasticos.graph.federation.guard"
    _description = "Federated Security Guard"

    def validate(self, query):
        if "DETACH DELETE" in query.upper():
            raise Exception("Write operations forbidden in federated mode")
