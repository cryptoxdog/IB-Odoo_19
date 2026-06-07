<!-- L9_META
skill_schema: 1
parent: plasticos-pr-review-kernel
layer: reference
role: reject_contract
tags: [plasticos, pr, review, block, security]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
/L9_META -->

# Hard Reject Conditions

Reject the PR immediately if any condition is true:

- `plasticos_inference_engine/pipeline_v2.py` imported or activated
- `plasticos_dev_tools` enabled in non-dev config
- Irreversible migration without explicit approval
- Column or table dropped without explicit user approval
- Force push to `Production` or `Staging` without approval
- Credentials, tokens, or secrets in changed files

## Branch Topology

```
Production  ←  Staging  ←  feature/fix branches
```

- PRs into `Staging` = pre-production validation.
- PRs into `Production` = production promotion or low-risk config only.
- Never merge features directly into `Production` without Staging validation.

## pipeline_v2 Guard

```yaml
pipeline_v2_check:
  any_import_of_pipeline_v2: false  # must be false
  ci_check_file: ci/check_pipeline_v2_guard.py
  status: must_pass
```

Exception: `pipeline_v2.py` deferred guard file itself — intentional, not a stub violation.
