
# ═══════════════════════════════════════════════════════════════
# PlastOS Enrichment — Revised Architecture (Segregated Modules)
# Date: 2026-02-22  |  Revision: 2.0
# ═══════════════════════════════════════════════════════════════

## Design Principle

**No monoliths.** Three independent packages, each with its own
responsibility, testable in isolation, callable by any consumer.

```
┌─────────────────────────────────────────────────────────────┐
│                     CONSUMER LAYER                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ enrichment   │  │ Mack buyer   │  │ Odoo cron /      │  │
│  │ pipeline     │  │ matching     │  │ manual trigger    │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
└─────────┼─────────────────┼───────────────────┼─────────────┘
          │                 │                   │
          ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│           plasticos_inference  (standalone library)          │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────────────┐│
│  │ KB Loader  │ │ Grade Engine │ │ Rule Engine            ││
│  │            │ │ (MFI, dens.) │ │ (property, quality,    ││
│  │ ontology + │ │              │ │  contamination, tier)  ││
│  │ all YAMLs  │ │              │ │                        ││
│  └────────────┘ └──────────────┘ └────────────────────────┘│
│  ┌──────────────────────────────────────────────────────┐  │
│  │          Typed API: infer(InferenceRequest)          │  │
│  │          → InferenceResponse                         │  │
│  │                                                      │  │
│  │  Works on ANY entity: supplier lead, buyer card,     │  │
│  │  intake record, material profile — anything with     │  │
│  │  polymer + optional form/source_type/process fields  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
          │
          │  (no dependency on enrichment or Odoo)
          ▼
┌─────────────────────────────────────────────────────────────┐
│                   kb/  (YAML knowledge bases)               │
│  ontology.yaml, hdpe_*.yaml, ldpe_*.yaml, pp_*.yaml, ...   │
└─────────────────────────────────────────────────────────────┘
```

## Three Packages

### 1. `plasticos_inference/`  (NEW — standalone library)

Pure Python. Zero Odoo dependency. Zero API dependency.
Takes a dict of known fields → returns inferred fields + confidence.

Consumers:
  - Enrichment pipeline (enrich suppliers)
  - Mack buyer matching (score buyer↔material fit)
  - Odoo server action (run inference on any intake/material.profile)
  - CLI one-off (debug / test a single material)
  - n8n webhook (HTTP call → inference JSON)

### 2. `plasticos_enrichment/`  (slimmed — pipeline only)

Sonar client, prompt builder, QA scoring, Odoo writer.
Imports `plasticos_inference` as a dependency.
Does NOT contain any YAML parsing or rule logic.

### 3. `kb/`  (shared data directory)

YAML knowledge bases. Read by `plasticos_inference` at init.
Path injected via config — never hardcoded.


## File Manifest After Separation

```
plasticos_inference/                    # STANDALONE LIBRARY
├── __init__.py                         # Exports: InferenceEngine, infer()
├── models.py                           # InferenceRequest, InferenceResponse,
│                                       #   InferenceResult, QualityTier
├── engine.py                           # Main engine class
├── kb_loader.py                        # YAML loading + indexing
├── grade_engine.py                     # Grade → property inference
├── rule_engine.py                      # Premise→conclusion rule firing
├── tier_engine.py                      # Quality tier classification
├── contamination_engine.py             # Contamination profile matching
├── polymer_aliases.py                  # Normalize "hdpe" → "HDPE" etc.
└── tests/
    ├── test_engine.py
    ├── test_grade_engine.py
    ├── test_rule_engine.py
    └── conftest.py                     # Shared fixtures

plasticos_enrichment/                   # PIPELINE (uses inference)
├── __init__.py
├── config.py
├── schema_loader.py
├── prompt_builder.py
├── sonar_client.py
├── quality_scorer.py                   # Uses inference results for scoring
├── qa_gate.py
├── judge.py                            # Optional LLM second-opinion
├── odoo_writer.py
├── pipeline.py                         # Orchestrator
├── queue.py
├── telemetry.py
└── tests/

kb/                                     # SHARED DATA (path-injected)
├── ontology.yaml
├── hdpe_compounding_recycling_v7.0r.yaml
├── ldpe_compounding_recycling_v7.0r.yaml
├── lldpe_compounding_recycling_v7.0r.yaml
├── pp_compounding_recycling_v7.0r.yaml
├── ps_compounding_recycling_v7.0r.yaml
├── hips_compounding_recycling_v7.0r.yaml
├── pp_supersacs_compounding_recycling_v7.0r.yaml
├── gaylord_boxes_compounding_recycling_v7.0r.yaml
└── kb_blowmolding_standards_certifications_v6.4.md
```

## Dependency Graph (strict unidirectional)

```
kb/  ←────  plasticos_inference  ←────  plasticos_enrichment
             (reads YAMLs)               (calls .infer())
                  ↑
                  │
              Mack module / Odoo / n8n / CLI
              (also calls .infer() directly)
```

plasticos_inference depends on: pyyaml (only)
plasticos_enrichment depends on: plasticos_inference, httpx, pydantic, tenacity

## Key API Contract: `plasticos_inference`

```python
from plasticos_inference import InferenceEngine
from plasticos_inference.models import InferenceRequest

# Init once, reuse across requests
engine = InferenceEngine(kb_dir="/path/to/kb")

# Works for SUPPLIER leads
request = InferenceRequest(
    entity_type="supplier",       # or "buyer", "intake", "material_profile"
    polymer="HDPE",
    form="BALE",
    source_type="PC",
    process_type="blow molding",
    contamination_pct=2.5,
)
response = engine.infer(request)

# Works for BUYER cards
request = InferenceRequest(
    entity_type="buyer",
    polymer="PP",
    process_type="injection molding",
    quality_tier_required="tier2",
)
response = engine.infer(request)

# Both return the same InferenceResponse:
# response.results: list[InferenceResult]
# response.quality_tier: str | None
# response.grade_matches: list[GradeMatch]
# response.applicable_rules: list[RuleFiring]
```
