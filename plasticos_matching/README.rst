PlasticOS matching
##################

Gate match orchestrator and result store for connecting intakes with
potential buyers. Scoring authority is Cognitive.Engine.Graphs (CEG)
via Constellation Gate (``action=match``). This addon does not run a
local matching engine.

**Features:**

* Odoo 19.0 compatible
* Gate-mediated match runs with fail-closed degraded/retry states
* Match result and exclusion persistence for human review

For detailed documentation, see the module's README.md and
``docs/adr/ADR-015-persistence-shells-matching-enrichment.md``.
