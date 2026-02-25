from odoo import models


class GNNScheduler(models.AbstractModel):
    _name = "plasticos.graph.gnn.scheduler"

    def train_all(self):
        tenants = self.env["plasticos.graph.tenant"].search([("active", "=", True)])
        export = self.env["plasticos.graph.gnn.export"]
        builder = self.env["plasticos.graph.gnn.dataset.builder"]
        trainer = self.env["plasticos.graph.gnn.training"]

        for tenant in tenants:
            data = export.export(tenant.tenant_code)
            dataset = builder.build(data)
            trainer.train(tenant.tenant_code, dataset)
