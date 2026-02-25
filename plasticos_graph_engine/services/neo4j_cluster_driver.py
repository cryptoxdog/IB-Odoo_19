from neo4j import GraphDatabase

from odoo import models


class Neo4jClusterDriver(models.AbstractModel):
    _name = "plasticos.neo4j.cluster.driver"
    _description = "Neo4j Cluster Driver (Routing Enabled)"

    def _get_driver(self):
        config = self.env["plasticos.neo4j.config"].search([], limit=1)
        return GraphDatabase.driver(
            config.uri,  # bolt+routing://core_1:7687
            auth=(config.username, config.password),
            max_connection_pool_size=200,
        )

    def execute_on_db(self, database, query, params=None):
        driver = self._get_driver()
        with driver.session(database=database) as session:
            return session.run(query, params or {}).data()
