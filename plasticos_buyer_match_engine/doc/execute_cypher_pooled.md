<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# provide an alternate version that uses Neo4jConnectionPool + MetricsCollector instead of creating a driver per call

Here is the alternate `execute_cypher_query` wired to your `Neo4jConnectionPool` and `MetricsCollector`, assuming:

- `Neo4jConnectionPool` lives in `plasticos_graph.services.graph.connection_pool`.
- `get_metrics()` lives in `plasticos_graph.services.monitoring`.

```python
# -*- coding: utf-8 -*-
import logging

from odoo import api, models
from odoo.exceptions import UserError

from neo4j.exceptions import Neo4jError, ServiceUnavailable

from odoo.addons.plasticos_graph.services.graph.connection_pool import (
    Neo4jConnectionPool,
)
from odoo.addons.plasticos_graph.services.monitoring import get_metrics

_logger = logging.getLogger(__name__)


class PlasticosGraphService(models.AbstractModel):
    _name = "plasticos.graph.service"
    _description = "PlastOS Graph Engine Service"

    # -------------------------------------------------------------------------
    # INTERNAL: CONFIG + SHARED POOL
    # -------------------------------------------------------------------------

    def _get_config(self):
        """Return Neo4j connection config as a dict."""
        ICP = self.env["ir.config_parameter"].sudo()
        return {
            "uri": ICP.get_param("plasticos_graph.neo4j_uri", ""),
            "user": ICP.get_param("plasticos_graph.neo4j_user", ""),
            "password": ICP.get_param("plasticos_graph.neo4j_password", ""),
            "pool_size": int(ICP.get_param("plasticos_graph.neo4j_pool_size", "25")),
            "connection_timeout": int(
                ICP.get_param("plasticos_graph.neo4j_connection_timeout", "30")
            ),
            "max_lifetime": int(
                ICP.get_param("plasticos_graph.neo4j_max_connection_lifetime", "3600")
            ),
            "cb_threshold": int(
                ICP.get_param("plasticos_graph.neo4j_cb_failure_threshold", "5")
            ),
            "cb_timeout": int(
                ICP.get_param("plasticos_graph.neo4j_cb_timeout", "60")
            ),
        }

    def _get_pool(self):
        """Return a shared Neo4jConnectionPool instance (singleton per uri/user)."""
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

        pool = Neo4jConnectionPool(
            uri=uri,
            username=user,
            password=password,
            pool_size=cfg["pool_size"],
            connection_timeout=cfg["connection_timeout"],
            max_lifetime=cfg["max_lifetime"],
            circuit_breaker_threshold=cfg["cb_threshold"],
            circuit_breaker_timeout=cfg["cb_timeout"],
        )
        return pool

    # -------------------------------------------------------------------------
    # PUBLIC: EXECUTE CYPHER (WITH POOL + METRICS)
    # -------------------------------------------------------------------------

    def execute_cypher_query(self, query, params=None, metadata=None):
        """Execute a Cypher query with shared pool + metrics.

        :param query: Cypher query string.
        :param params: Optional dict of parameters.
        :param metadata: Optional dict (e.g. {"name": "sync_facility"}).
        :return: list of dict rows from Neo4j.
        """
        self.ensure_one()
        params = params or {}
        metadata = metadata or {}
        op_name = metadata.get("name", "neo4j.query")

        metrics = get_metrics()
        pool = self._get_pool()

        _logger.info(
            "Neo4j query start: %s | metadata=%s",
            op_name,
            metadata,
        )

        try:
            with metrics.measure(op_name):
                with pool.session() as session:
                    result = session.run(query, params)
                    rows = [record.data() for record in result]

            metrics.increment(f"{op_name}.rows", len(rows))
            _logger.info(
                "Neo4j query ok: %s | rows=%d",
                op_name,
                len(rows),
            )
            return rows

        except ServiceUnavailable as exc:
            metrics.increment(f"{op_name}.service_unavailable")
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
            metrics.increment(f"{op_name}.neo4j_error")
            _logger.error(
                "Neo4j error: %s | metadata=%s",
                exc,
                metadata,
                exc_info=True,
            )
            raise UserError(
                "Neo4j query failed:\n%s" % (getattr(exc, "message", str(exc)))
            ) from exc

        except Exception as exc:  # noqa: BLE001
            metrics.increment(f"{op_name}.unexpected_error")
            _logger.exception(
                "Unexpected error while executing Neo4j query | metadata=%s",
                metadata,
            )
            raise UserError(
                "Unexpected error while communicating with Neo4j. "
                "Check Odoo logs for details."
            ) from exc
```
