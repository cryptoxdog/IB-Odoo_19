from odoo import models


class FederationRouter(models.AbstractModel):
    _name = "plasticos.graph.federation.router"
    _description = "Federation Router"

    def get_all_dbs(self):
        return [t.database_name for t in self.env["plasticos.graph.tenant"].search([("active", "=", True)])]
