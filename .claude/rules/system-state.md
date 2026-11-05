---
paths:
  - "docs/**"
  - "config/**"
---
# System State — Living Snapshot

Update when significant changes merge. **Branches:** `Staging` (dev/PR target) · `Production` (prod). Capitalized — not `staging`/`main`.

**Module counts / CI:** see `AGENTS.md` (maintained SSOT).

| Status | Examples |
|--------|----------|
| Production | base, security_base, intake, offer, transaction, logistics, claims |
| Beta | web_leads, enrichment, commission, crm_bridge |
| Dev-only | dev_tools (`installable=False`) |
| Gated | enrichment full wiring (pipeline_v2) · Gate web-lead triage (Phase 3) |

**Known:** mypy advisory in pre-commit · ruff excludes some engine modules · circular dep commission↔transaction intentional.
