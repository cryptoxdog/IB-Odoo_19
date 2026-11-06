"""
Gate 7 — VanillaSoft 100-contact bounded proof.

SUPERSEDED — Gate 7 now runs via `make import-vanillasoft` from run.sh directly.
The VanillaSoft API key is bound from Infisical (VANILLASOFT_API_KEY) and injected
into the clone ICP param before the import runs. VANILLASOFT_CALL_FLOOR is set to
7 days ago to bound the rehearsal scope.

This file is kept for reference. run.sh no longer pipes it into odoo shell.

Prerequisite (auto-satisfied by run.sh):
  VANILLASOFT_API_KEY must exist in Infisical cursor-governance project.
  It is listed in ~/.cursor-governance/ops/secrets/infisical-cursor-governance.yaml
  root_env_keys and bound via capability_bind.py.

Evidence written to:
  REHEARSAL_EVIDENCE_DIR/06-crm-result.json  (import-vanillasoft machine summary)
  REHEARSAL_EVIDENCE_DIR/06-crm-log.txt      (full stdout/stderr of make import-vanillasoft)
"""
