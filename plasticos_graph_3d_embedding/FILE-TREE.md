# CompoundE3D KGE — Repo-like file tree

Layout follows the **Integration Pack Manifest** (see `docs/KG Embedding - Compound 3D-3.md`).

```
3D KG Embedding - HyperGraphs/
├── FILE-TREE.md              # This file
├── requirements_kge.txt      # Python deps (torch, numpy, scipy)
│
├── memory/
│   └── kge/
│       ├── __init__.py       # Module exports (CompoundE3D, AffineOperator3D, BeamSearch, etc.)
│       ├── transformations.py   # 3D affine operators (T, S, R, F, H)
│       ├── compound_e3d.py   # CompoundE3D model class
│       ├── beam_search.py    # Variant discovery (beam search)
│       ├── ensemble.py       # WDS + rank fusion
│       └── checkpoints/
│           └── .gitkeep      # Model checkpoints directory
│
├── orchestrator/
│   └── kge_orchestrator_integration.py   # WebSocket bridge, kge.predict / kge.discover
│
├── migrations/
│   ├── 0023_init_kge_schema.sql   # Entity/relation embeddings + predictions (pgvector)
│   └── rollback_kge_schema.sql    # Rollback: DROP KGE tables
│
├── config/
│   └── l9/
│       ├── kge_worldmodel_config.yaml   # Worldmodel kernel KGE config
│       ├── kge_safety_config.yaml       # Approval + circuit breaker
│       └── kge_observability_config.yaml # KGE metrics/spans
│
├── tests/
│   └── memory/
│       └── kge/
│           ├── __init__.py
│           └── test_compound_e3d.py     # 36+ tests, beam/ensemble/orchestrator
│
├── docs/                     # Deliverable docs + harvest report
│   ├── final-deliverable-summary.md
│   ├── index-deliverable-pack.md
│   ├── evidence-report.md
│   ├── phases-2-6-consolidated.md
│   ├── HARVEST-REPORT.md
│   ├── KG Embedding - Compound 3D-1.md
│   ├── KG Embedding - Compound 3D-2.md
│   └── KG Embedding - Compound 3D-3.md
│
└── harvested/                 # Sed-extracted originals (reference only)
    └── (same SQL/YAML/Python as above, flat)
```

## Path reference (index-deliverable-pack)

| File | Path |
|------|------|
| Beam search | `memory/kge/beam_search.py` |
| Ensemble | `memory/kge/ensemble.py` |
| Tests | `tests/memory/kge/test_compound_e3d.py` |
| Orchestrator | `orchestrator/kge_orchestrator_integration.py` |

## Run tests

From this folder (or repo root if integrated):

```bash
pytest tests/memory/kge/test_compound_e3d.py -v
```
