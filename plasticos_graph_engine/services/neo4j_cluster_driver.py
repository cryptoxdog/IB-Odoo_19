"""Neo4j cluster driver with routing and connection pooling.

Reuses a single ``neo4j.Driver`` per Odoo database, configured for
bolt+routing protocol.  Supports multi-database execution for the
sharded graph topology.
"""

import logging
import threading

from neo4j import GraphDatabase

from odoo import models

_logger = logging.getLogger(__name__)

_cluster_lock = threading.Lock()
_cluster_cache: dict = {}  # keyed by db_name


class Neo4jClusterDriver(models.AbstractModel):
    _name = "plasticos.neo4j.cluster.driver"
    _description = "Neo4j Cluster Driver (Routing Enabled)"

    def _get_driver(self):
        """Return a cached routing-enabled driver."""
        db_name = self.env.cr.dbname
        if db_name not in _cluster_cache:
            with _cluster_lock:
                if db_name not in _cluster_cache:
                    config = self.env["plasticos.neo4j.config"].sudo().search([], limit=1)
                    if not config:
                        raise ValueError("No Neo4j configuration found")
                    _cluster_cache[db_name] = GraphDatabase.driver(
                        config.uri,  # bolt+routing://core_1:7687
                        auth=(config.username, config.password),
                        max_connection_pool_size=200,
                    )
                    _logger.info("Neo4j cluster driver created for db=%s", db_name)
        return _cluster_cache[db_name]

    def execute_on_db(self, database, query, params=None, max_retries=2):
        """Execute a Cypher query on a specific Neo4j database with retry."""
        driver = self._get_driver()
        last_exc = None
        for attempt in range(1, max_retries + 2):
            try:
                with driver.session(database=database) as session:
                    return session.run(query, params or {}).data()
            except Exception as exc:
                last_exc = exc
                _logger.warning(
                    "Neo4j cluster query attempt %d/%d on db=%s failed: %s",
                    attempt, max_retries + 1, database, exc,
                )
                if attempt > max_retries:
                    raise
        raise last_exc  # pragma: no cover
