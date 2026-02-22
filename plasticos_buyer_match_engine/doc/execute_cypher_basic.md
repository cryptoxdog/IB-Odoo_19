<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Implement the full execute_cypher_query method body

Here is a production-style `execute_cypher_query` implementation you can drop into your `plasticos.graph.service` AbstractModel, assuming you use the official Neo4j Python driver and your config lives in `ir.config_parameter`.

```python
# -*- coding: utf-8 -*-
import logging
from contextlib import contextmanager

from odoo import api, models
from odoo.exceptions import UserError

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

_logger = logging.getLogger(__name__)


class PlasticosGraphService(models.AbstractModel):
    _name = "plasticos.graph.service"
    _description = "PlastOS Graph Engine Service"

    # -------------------------------------------------------------------------
    # INTERNAL: CONFIG + DRIVER
    # -------------------------------------------------------------------------

    def _get_config(self):
        """Return Neo4j connection config as a dict."""
        ICP = self.env["ir.config_parameter"].sudo()
        return {
            "uri": ICP.get_param("plasticos_graph.neo4j_uri", ""),
            "user": ICP.get_param("plasticos_graph.neo4j_user", ""),
            "password": ICP.get_param("plasticos_graph.neo4j_password", ""),
            "max_pool_size": int(ICP.get_param("plasticos_graph.neo4j_pool_size", "25")),
            "connection_timeout": int(
                ICP.get_param("plasticos_graph.neo4j_connection_timeout", "30")
            ),
            "max_connection_lifetime": int(
                ICP.get_param("plasticos_graph.neo4j_max_connection_lifetime", "3600")
            ),
        }

    @contextmanager
    def _get_driver(self):
        """Context manager that yields a Neo4j driver and closes it afterward.

        In a high-throughput setup you would replace this with a shared
        connection pool singleton; this is simple and safe for now.
        """
        cfg = self._get_config()
        uri = cfg["uri"]
        user = cfg["user"]
        password = cfg["password"]

        if not uri or not user or not password:
            raise UserError(
                "Neo4j connection is not configured. Set:\n"
                "- plasticos_graph.neo4j_uri\n"
                "- plasticos_graph.neo4j_user\n"
                "- plasticos_graph.neo4j_password"
            )

        driver = None
        try:
            driver = GraphDatabase.driver(
                uri,
                auth=(user, password),
                max_connection_pool_size=cfg["max_pool_size"],
                connection_timeout=cfg["connection_timeout"],
                max_connection_lifetime=cfg["max_connection_lifetime"],
            )
            yield driver
        finally:
            if driver is not None:
                driver.close()

    # -------------------------------------------------------------------------
    # PUBLIC: EXECUTE CYPHER
    # -------------------------------------------------------------------------

    def execute_cypher_query(self, query, params=None, metadata=None):
        """Execute a Cypher query against Neo4j and return list of dict rows.

        :param query: Cypher query string.
        :param params: Optional dict of parameters for the query.
        :param metadata: Optional dict for logging/diagnostics.
        :return: list of dicts, each representing a row from Neo4j.
        """
        self.ensure_one()
        params = params or {}
        metadata = metadata or {}

        # Lightweight log for observability (you can enrich as needed)
        _logger.info(
            "Neo4j query start: %s | metadata=%s",
            metadata.get("name", "unnamed"),
            metadata,
        )

        try:
            with self._get_driver() as driver:
                with driver.session() as session:
                    result = session.run(query, params)
                    rows = [record.data() for record in result]

            _logger.info(
                "Neo4j query ok: %s | rows=%d",
                metadata.get("name", "unnamed"),
                len(rows),
            )
            return rows

        except ServiceUnavailable as exc:
            _logger.error(
                "Neo4j service unavailable: %s | metadata=%s",
                exc,
                metadata,
                exc_info=True,
            )
            raise UserError(
                "Neo4j service is unavailable. Please try again later or "
                "contact your administrator."
            ) from exc

        except Neo4jError as exc:
            _logger.error(
                "Neo4j error: %s | metadata=%s",
                exc,
                metadata,
                exc_info=True,
            )
            # Bubble up as functional error to show to users/admins
            raise UserError(
                "Neo4j query failed:\n%s" % (getattr(exc, "message", str(exc)))
            ) from exc

        except Exception as exc:  # noqa: BLE001
            _logger.exception(
                "Unexpected error while executing Neo4j query | metadata=%s",
                metadata,
            )
            raise UserError(
                "Unexpected error while communicating with Neo4j. "
                "Check Odoo logs for details."
            ) from exc
```

Usage inside the same service for your facility upsert, for example:

```python
def sync_facility_nodes(self, trigger="manual"):
    self.ensure_one()
    payloads = self._build_facility_payloads()
    if not payloads:
        return []

    query = """UNWIND $facilities AS f
               MERGE (fac:Facility {facility_id: f.facility_id})
               // ... rest of Cypher ...
               RETURN count(fac) AS facilities_upserted"""
    return self.execute_cypher_query(
        query,
        params={"facilities": payloads},
        metadata={"name": "sync_facility_nodes", "trigger": trigger},
    )
```

If you want it wired to the more advanced connection pool / metrics components from the earlier phases, I can provide an alternate version that uses `Neo4jConnectionPool` + `MetricsCollector` instead of creating a driver per call.
