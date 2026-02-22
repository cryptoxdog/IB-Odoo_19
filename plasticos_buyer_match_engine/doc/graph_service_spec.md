<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Draft the actual Odoo 19 plasticos.graph.service AbstractModel skeleton (fields, methods, and method signatures only) \&

Write the first Neo4j Cypher query template that exactly matches this schema (ready to paste into Neo4j Browser)... except all will be done inside odoo not using an outside browser

Here’s a concise, production-style skeleton for the **`plasticos.graph.service`** AbstractModel and a matching **Cypher query template** you can execute from Odoo (via the Neo4j driver), not the browser.

***

## `plasticos.graph.service` AbstractModel skeleton

```python
# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PlasticosGraphService(models.AbstractModel):
    """Core Neo4j graph orchestration service for PlastOS."""

    _name = "plasticos.graph.service"
    _description = "PlastOS Graph Engine Service"

    # -------------------------------------------------------------------------
    # CONFIG FIELDS (computed or helper accessors, not DB columns)
    # -------------------------------------------------------------------------

    # These are helper accessors; in practice you’ll likely read from
    # ir.config_parameter inside methods instead of storing fields here.
    # Shown as fields for clarity of the service “interface”.
    neo4j_uri = fields.Char(readonly=True)
    neo4j_user = fields.Char(readonly=True)
    neo4j_password = fields.Char(readonly=True)

    # -------------------------------------------------------------------------
    # LOW-LEVEL HELPERS (signatures only)
    # -------------------------------------------------------------------------

    def _get_config(self):
        """Return dict with Neo4j + scoring config (uri, auth, weights, etc.)."""
        self.ensure_one()
        # return {
        #   "neo4j_uri": str,
        #   "neo4j_user": str,
        #   "neo4j_password": str,
        #   "max_distance_km": float,
        #   "score_weights": {...},
        # }
        raise NotImplementedError()

    def _get_driver(self):
        """Return a Neo4j driver or pooled client instance."""
        self.ensure_one()
        raise NotImplementedError()

    def _execute_cypher(self, query, params=None, *, metadata=None):
        """Execute a Cypher query and return raw results.

        :param query: Cypher query string.
        :param params: dict of parameters.
        :param metadata: optional dict for logging/metrics.
        :return: list of dict rows.
        """
        self.ensure_one()
        raise NotImplementedError()

    # -------------------------------------------------------------------------
    # SCHEMA / BOOTSTRAP
    # -------------------------------------------------------------------------

    def initialize_schema(self):
        """Create constraints and indexes in Neo4j if missing."""
        self.ensure_one()
        raise NotImplementedError()

    # -------------------------------------------------------------------------
    # SYNC ENTRYPOINTS (PUBLIC API)
    # -------------------------------------------------------------------------

    def sync_all(self, trigger="manual"):
        """Full graph sync: facilities, materials, transactions.

        :param trigger: 'manual' | 'cron' | 'test' | other free text.
        """
        self.ensure_one()
        raise NotImplementedError()

    def sync_facility_nodes(self, trigger="manual"):
        """Upsert Facility nodes from res.partner / plasticos.facility.profile."""
        self.ensure_one()
        raise NotImplementedError()

    def sync_material_nodes(self, trigger="manual"):
        """Upsert MaterialProfile nodes and HAS_MATERIAL edges."""
        self.ensure_one()
        raise NotImplementedError()

    def sync_transaction_edges(self, trigger="manual"):
        """Upsert TRANSACTED_WITH edges between facilities."""
        self.ensure_one()
        raise NotImplementedError()

    # -------------------------------------------------------------------------
    # SYNC HELPERS (SIGNATURES ONLY)
    # -------------------------------------------------------------------------

    def _build_facility_payloads(self):
        """Return list of dicts representing Facility nodes to sync.

        Each payload dict MUST match the Cypher param schema:
        {
            "facility_id": int,
            "partner_id": int,
            "name": str,
            "is_buyer": bool,
            "is_supplier": bool,
            "lat": float | None,
            "lon": float | None,
            "city": str | None,
            "state": str | None,
            "country": str | None,
            "can_remove_metal": bool,
            "can_filter_fr": bool,
            "min_lot_size_lbs": float | None,
            "max_lot_size_lbs": float | None,
        }
        """
        self.ensure_one()
        raise NotImplementedError()

    def _build_material_payloads(self):
        """Return list of dicts for MaterialProfile nodes.

        {
            "material_id": int,
            "facility_id": int,
            "polymer": str,
            "form": str,
            "color": str | None,
            "min_density": float | None,
            "max_density": float | None,
            "contamination_tolerance": float | None,
            "moisture_tolerance": float | None,
        }
        """
        self.ensure_one()
        raise NotImplementedError()

    def _build_transaction_payloads(self):
        """Return list of dicts for TRANSACTED_WITH edges.

        {
            "from_facility_id": int,
            "to_facility_id": int,
            "tx_count": int,
            "total_weight_lbs": float,
            "avg_margin_pct": float | None,
            "last_tx_date": str (ISO date),
        }
        """
        self.ensure_one()
        raise NotImplementedError()

    # -------------------------------------------------------------------------
    # BUYER MATCHING (CALLED FROM plasticos.intake)
    # -------------------------------------------------------------------------

    def match_buyers_for_intake(self, intake):
        """Run graph-based buyer matching for a single intake.

        :param intake: plasticos.intake record (single).
        :return: list of match dicts (buyer_id, score, debug info, etc.).
        """
        self.ensure_one()
        raise NotImplementedError()

    def _intake_to_match_params(self, intake):
        """Map intake record to Cypher params for buyer match.

        Returns dict matching the buyer-match Cypher template:
        {
            "polymer": str,
            "form": str,
            "color": str | None,
            "has_metal": bool,
            "has_fr": bool,
            "contamination_pct": float | None,
            "moisture_pct": float | None,
            "lot_size_lbs": float | None,
            "lat": float | None,
            "lon": float | None,
            "max_distance_km": float,
            "preferred_packaging": str | None,
        }
        """
        self.ensure_one()
        raise NotImplementedError()

    # -------------------------------------------------------------------------
    # LOGGING / AUDIT
    # -------------------------------------------------------------------------

    def _create_sync_log(self, sync_type, status, stats=None, error_message=None):
        """Create plasticos.graph.sync.log entry.

        :param sync_type: 'facility' | 'material' | 'transaction' | 'full'.
        :param status: 'success' | 'failed' | 'partial'.
        :param stats: optional dict (records_processed, duration, etc.).
        :param error_message: optional error string.
        """
        self.ensure_one()
        raise NotImplementedError()

    def _log_match_run(self, intake, matches, status="success", error_message=None):
        """Audit buyer match run for governance/analytics."""
        self.ensure_one()
        raise NotImplementedError()
```

This skeleton keeps the **service interface explicit**: config, sync entrypoints, payload builders, buyer-match API, and logging hooks. You can drop this into `models/graph_service.py` and then fill implementations.

***

## Matching Neo4j Cypher query template

Below is a **facility upsert** Cypher template that exactly matches the `*_payloads` schema above. You will run it from Odoo using parameters, *not* from Neo4j Browser, but it’s valid to paste into the browser too if needed.

### 1) Facility node upsert (batch)

```cypher
// EXPECTED PARAMS (from Odoo):
// $facilities :: LIST<MAP> where each map has:
//   facility_id: INTEGER
//   partner_id:  INTEGER
//   name:        STRING
//   is_buyer:    BOOLEAN
//   is_supplier: BOOLEAN
//   lat:         FLOAT or NULL
//   lon:         FLOAT or NULL
//   city:        STRING or NULL
//   state:       STRING or NULL
//   country:     STRING or NULL
//   can_remove_metal: BOOLEAN
//   can_filter_fr:    BOOLEAN
//   min_lot_size_lbs: FLOAT or NULL
//   max_lot_size_lbs: FLOAT or NULL

UNWIND $facilities AS f
MERGE (fac:Facility {facility_id: f.facility_id})
ON CREATE SET
    fac.partner_id        = f.partner_id,
    fac.name              = f.name,
    fac.is_buyer          = coalesce(f.is_buyer, false),
    fac.is_supplier       = coalesce(f.is_supplier, false),
    fac.can_remove_metal  = coalesce(f.can_remove_metal, false),
    fac.can_filter_fr     = coalesce(f.can_filter_fr, false),
    fac.min_lot_size_lbs  = f.min_lot_size_lbs,
    fac.max_lot_size_lbs  = f.max_lot_size_lbs,
    fac.city              = f.city,
    fac.state             = f.state,
    fac.country           = f.country,
    fac.created_at_utc    = datetime(),
    fac.updated_at_utc    = datetime()
ON MATCH SET
    fac.partner_id        = f.partner_id,
    fac.name              = f.name,
    fac.is_buyer          = coalesce(f.is_buyer, fac.is_buyer),
    fac.is_supplier       = coalesce(f.is_supplier, fac.is_supplier),
    fac.can_remove_metal  = coalesce(f.can_remove_metal, fac.can_remove_metal),
    fac.can_filter_fr     = coalesce(f.can_filter_fr, fac.can_filter_fr),
    fac.min_lot_size_lbs  = f.min_lot_size_lbs,
    fac.max_lot_size_lbs  = f.max_lot_size_lbs,
    fac.city              = f.city,
    fac.state             = f.state,
    fac.country           = f.country,
    fac.updated_at_utc    = datetime()
WITH fac, f
// Geo point (optional if lat/lon provided)
CALL {
    WITH fac, f
    WITH fac, f
    WHERE f.lat IS NOT NULL AND f.lon IS NOT NULL
    SET fac.location = point({latitude: f.lat, longitude: f.lon})
    RETURN fac
}
RETURN count(fac) AS facilities_upserted;
```


### 2) How you’ll call this from Odoo

In your `PlasticosGraphService._execute_cypher` implementation (pseudo-code):

```python
def sync_facility_nodes(self, trigger="manual"):
    self.ensure_one()
    payloads = self._build_facility_payloads()
    query = """
        UNWIND $facilities AS f
        MERGE (fac:Facility {facility_id: f.facility_id})
        ON CREATE SET
            fac.partner_id        = f.partner_id,
            fac.name              = f.name,
            fac.is_buyer          = coalesce(f.is_buyer, false),
            fac.is_supplier       = coalesce(f.is_supplier, false),
            fac.can_remove_metal  = coalesce(f.can_remove_metal, false),
            fac.can_filter_fr     = coalesce(f.can_filter_fr, false),
            fac.min_lot_size_lbs  = f.min_lot_size_lbs,
            fac.max_lot_size_lbs  = f.max_lot_size_lbs,
            fac.city              = f.city,
            fac.state             = f.state,
            fac.country           = f.country,
            fac.created_at_utc    = datetime(),
            fac.updated_at_utc    = datetime()
        ON MATCH SET
            fac.partner_id        = f.partner_id,
            fac.name              = f.name,
            fac.is_buyer          = coalesce(f.is_buyer, fac.is_buyer),
            fac.is_supplier       = coalesce(f.is_supplier, fac.is_supplier),
            fac.can_remove_metal  = coalesce(f.can_remove_metal, fac.can_remove_metal),
            fac.can_filter_fr     = coalesce(f.can_filter_fr, fac.can_filter_fr),
            fac.min_lot_size_lbs  = f.min_lot_size_lbs,
            fac.max_lot_size_lbs  = f.max_lot_size_lbs,
            fac.city              = f.city,
            fac.state             = f.state,
            fac.country           = f.country,
            fac.updated_at_utc    = datetime()
        WITH fac, f
        CALL {
            WITH fac, f
            WHERE f.lat IS NOT NULL AND f.lon IS NOT NULL
            SET fac.location = point({latitude: f.lat, longitude: f.lon})
            RETURN fac
        }
        RETURN count(fac) AS facilities_upserted
    """
    rows = self._execute_cypher(query, {"facilities": payloads})
    # rows[^0]["facilities_upserted"] → use for logging
```

If you’d like, next step I can add **the matching Material node + HAS_MATERIAL edge Cypher** that lines up with `_build_material_payloads()`, or the **buyer match query** template that uses `_intake_to_match_params()`.
<span style="display:none">[^1][^10][^11][^12][^13][^14][^15][^16][^17][^18][^19][^2][^20][^3][^4][^5][^6][^7][^8][^9]</span>

<div align="center">⁂</div>

[^1]: https://lindacoach.odoo.com/slides/odoo-18-new-features-12/tag/sales-6

[^2]: https://lightlab.odoo.com/shop/1031-hourglass-37

[^3]: https://nanochronia.odoo.com

[^4]: https://notchnco1.odoo.com/contactus

[^5]: https://petnology3.odoo.com/qtt-1

[^6]: https://horgi-cattery.odoo.com/puppy-deposit

[^7]: https://geosigmoid-group.odoo.com/contactus

[^8]: https://deltawds.odoo.com/windows

[^9]: https://repmex.odoo.com/contactus

[^10]: https://tortoise.odoo.com/en/jobs

[^11]: https://www.cybrosys.com/blog/overview-of-abstract-models-in-odoo-19

[^12]: https://www.linkedin.com/posts/muhammed-aslam-817327106_odoo-odoodevelopment-erp-activity-7428843019946090496-gjuq

[^13]: https://www.cybrosys.com/blog/a-complete-overview-of-models-in-odoo-19

[^14]: https://home.mycbms.com/tag/abstraction-models/

[^15]: https://dev.to/guewen/introduction-to-odoo-components-bn0

[^16]: https://stackoverflow.com/questions/42397773/neo4j-what-is-the-syntax-to-set-cypher-query-parameters-in-the-browser-interfac

[^17]: https://stackoverflow.com/questions/43469884/inherit-abstract-model-and-add-new-field

[^18]: https://github.com/neo4j/neo4j-documentation/blob/dev/cypher/cypher-docs/src/docs/dev/syntax/parameters.asciidoc

[^19]: https://letscms.com/blog/complete-overview-of-fields-in-odoo-19

[^20]: https://www.youtube.com/watch?v=_-kQRZevbSI
