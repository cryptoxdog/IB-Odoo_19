# GMP-129 — Close PR 324 by extracting the useful remainder

Workspace: `feat/close-324-crosswalk-docs` from `origin/Staging` `2dc516aa`.

## What landed

- Campaign documents that exist on PR 324 and are absent from Staging. Private blob extracts were not included.
- The approved VanillaSoft contact crosswalk is now the packaged fallback in `plasticos_crm_sync` `19.0.1.9.13`. An empty system parameter reads that file. A set parameter still replaces it. A blank `erp_ct_id` stays a CRM lead.
- Census pinned to the shipped file: SHA256 `9aa6fcd0eee9fedf106c23090fa32b24c2faacc1576531c4f4fcc846663b72c1`, 759 VanillaSoft ids, 691 ERP ids.
- Pull-request bodies fill `.github/pull_request_template.md` when that file is present.
- Root `reports/` remains retired.

## Already on Staging, so not recopied

CRM material identity and salesperson mapping, including `plasticos_partner_import/erp/mapping.py`. The four local files that already matched Staging were left as they are.

## Memory

`MEMORY_PREFETCH:` namespace `ib-odoo-19`, snapshot_digest `362cc24543c5e38b0d8f2dd9ba9e122df2cc9f823d3720a305af556cc1578fb1`, checked_record_count 61, conflicts 0, policy_version `memory-phase-lock/v2`.

## Tests

`pytest tests/` — 1873 passed, 6 skipped, then 4 publication failures because a fixture repo has no template. Fallback added. `pytest tests/test_make_pr_publication.py` — 58 passed. Focused crosswalk, template, campaign-dependency, and repo-index tests passed.

## Finalize

Governance `precommit-repo` compares `origin/main`. This clone has no `origin/main`. The extraction commit is `6da47127`. Publication continues with the Staging `make pr` path.
