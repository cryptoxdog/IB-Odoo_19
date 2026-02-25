from odoo import models


class FederatedQueryService(models.AbstractModel):
    _name = "plasticos.graph.federation.query"

    def execute(self, query):
        router = self.env["plasticos.graph.federation.router"]
        guard = self.env["plasticos.graph.federation.guard"]
        driver = self.env["plasticos.neo4j.cluster.driver"]

        guard.validate(query)

        results = []
        for db in router.get_all_dbs():
            results.extend(driver.execute_on_db(db, query))

        return results
