from neo4j import GraphDatabase

from odoo import models


class Neo4jDriver(models.AbstractModel):
    _name = "plasticos.neo4j.driver"

    def _get_driver(self):
        config = self.env["plasticos.neo4j.config"].search([], limit=1)
        return GraphDatabase.driver(config.uri, auth=(config.username, config.password))

    def execute(self, query, params=None):
        driver = self._get_driver()
        with driver.session() as session:
            return session.run(query, params or {}).data()
