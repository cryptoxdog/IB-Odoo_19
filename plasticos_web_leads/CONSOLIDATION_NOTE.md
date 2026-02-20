# CONSOL-4: Web Lead AI Triage Consolidation

## Status: DEFERRED — branch `feat/web-lead-ai-triage` not yet merged to staging

## Plan
When PR #17 (`feat/web-lead-ai-triage`) is ready to merge, the separate
`plasticos_web_lead_ai_triage` module should be consolidated INTO this
`plasticos_web_leads` module rather than kept as a standalone addon.

### Files to absorb
- `models/ai_normalizer.py`
- `models/classification_engine.py`
- `models/image_analyzer.py`
- `models/triage_config.py`
- `models/web_lead_triage.py` (inherits `plasticos.web.lead`)
- `controllers/cognito_webhook.py`
- `data/triage_config_data.xml`
- `data/logistics_ir_rules.xml`
- `views/triage_config_views.xml`
- `views/web_lead_triage_views.xml`
- `tests/test_ai_normalizer.py`
- `tests/test_classification_engine.py`

### Rationale
Both modules operate on the same `plasticos.web.lead` model. Keeping them
separate adds a dependency hop and an extra installable module with no
architectural benefit. The AI triage is a feature of web leads, not a
separate domain.
