# Harvest Report — 3D KG Embedding HyperGraphs

**Workflow:** harvest-deploy-v1 (sed-only extraction)
**Source docs:** final-deliverable-summary.md, index-deliverable-pack.md, KG Embedding - Compound 3D-1.md, KG Embedding - Compound 3D-2.md, KG Embedding - Compound 3D-3.md, phases-2-6-consolidated.md
**Target dir:** `docs/02-25-2026/3D KG Embedding - HyperGraphs`
**Rule:** Extract only code **not** already in beam_search.py, ensemble.py, kge_orchestrator_integration.py, test_compound_e3d.py.

---

## Files created (CREATES)

| # | Source | Lines | Output file |
|---|--------|-------|-------------|
| 1 | KG Embedding - Compound 3D-3.md | 422-605 | 0023_init_kge_schema.sql |
| 2 | KG Embedding - Compound 3D-3.md | 310-314 | rollback_kge_schema.sql |
| 3 | KG Embedding - Compound 3D-3.md | 168-175 | kge_worldmodel_config.yaml |
| 4 | KG Embedding - Compound 3D-3.md | 182-194 | kge_safety_config.yaml |
| 5 | KG Embedding - Compound 3D-3.md | 201-226 | kge_observability_config.yaml |
| 6 | KG Embedding - Compound 3D-3.md | 238-240 | requirements_kge.txt |
| 7 | KG Embedding - Compound 3D-3.md | 615-648 | memory_kge_init.py |
| 8 | KG Embedding - Compound 3D-3.md | 657-876 | transformations_affine_3d.py |
| 9 | KG Embedding - Compound 3D-3.md | 886-1179 | compound_e3d_model.py |

---

## Validation

| File | Syntax (py_compile) | Note |
|------|---------------------|------|
| 0023_init_kge_schema.sql | N/A | SQL |
| rollback_kge_schema.sql | N/A | SQL |
| kge_*.yaml | N/A | YAML |
| requirements_kge.txt | N/A | Text |
| memory_kge_init.py | Pass | |
| compound_e3d_model.py | Pass | |
| transformations_affine_3d.py | Fail | Source contains markdown refs `[^2]`, `[^3]`, etc.; remove or replace manually for valid Python. |

---

## Extraction method

- All extractions used **sed only**: `sed -n 'start,endp' "KG Embedding - Compound 3D-3.md" > output_file`
- No manual retyping or Write/StrReplace of code from the docs.

---

## Next steps

- Run `/use-harvest` to deploy or refine as needed.
- Fix `transformations_affine_3d.py`: delete or replace `[^2]`, `[^3]`, `,[^2]`, etc., then run `python3 -m py_compile transformations_affine_3d.py`.
