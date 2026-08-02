# Mothball Data Map — Local Intelligence Retirement (M5)

## Purpose

Inventory which Odoo-side records are **retained** as business/audit evidence versus
which local-intelligence surfaces are **catalogued for later physical retirement**.

M5 does **not** drop business audit records, does **not** delete legacy source
directories, and does **not** perform automatic production uninstall.

## Retained (must preserve)

| Model | Table (typical) | Why retained |
|---|---|---|
| `plasticos.match.run` | `plasticos_match_run` | Gate match-run audit trail |
| `plasticos.match.result` | `plasticos_match_result` | Gate match results / writeback |
| `plasticos.match.result.link` | `plasticos_match_result_link` | Result linkage |
| `plasticos.match.exclusion` | `plasticos_match_exclusion` | Operator exclusion policy |
| `plasticos.enrichment.run` | `plasticos_enrichment_run` | Gate enrichment-run audit |
| `plasticos.enrichment.provenance` | `plasticos_enrichment_provenance` | Provenance / writeback audit |
| `plasticos.enrichment.extraction` | `plasticos_enrichment_extraction` | Extraction audit |
| `plasticos.enrichment.source` | `plasticos_enrichment_source` | Configured sources |

## Discardable catalog (not dropped in M5)

These are **catalogued only**. Physical uninstall is a later, separately approved
operator action after verified backup + restore rehearsal.

| Surface | Notes |
|---|---|
| `plasticos.buyer.matcher` | Local BME matcher — authority retired |
| `plasticos.match.result.writer` | Local writer path |
| `plasticos.graph.service` / `plasticos.graph.sync.log` | Local graph helpers (CEG owns Neo4j) |
| `plasticos.enrichment.service` local crawl/extract/inference methods | Fail-closed in M4; code retained until uninstall |
| `plasticos_buyer_match_engine` / `plasticos_inference_engine` addons | Source directories retained until physical retirement |

## Migration markers

Written by pre/post-migrate scripts (when upgrading into target versions):

- `plasticos.mothball.pre.<table>.count` — pre counts
- `plasticos.mothball.matching.authority=gate_only`
- `plasticos.mothball.enrichment.authority=gate_only`

## Coordinator

```bash
python3 scripts/migrations/mothball_local_intelligence.py inventory
python3 scripts/migrations/mothball_local_intelligence.py dry-run
python3 scripts/migrations/mothball_local_intelligence.py uninstall-preflight \
  --backup-receipt-digest sha256:…
```

`--execute` is refused. Uninstall is never automatic.
