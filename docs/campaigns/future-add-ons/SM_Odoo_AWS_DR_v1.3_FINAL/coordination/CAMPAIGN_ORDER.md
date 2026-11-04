# One campaign, seven bounded, closure-driven contracts

**The two separate provider missions are preserved:** `01` owns Odoo.sh native controls; `02-04` own independent AWS protection. `00` is pre-code proof, `05` is emergency custody and `06` is final assurance. This is not seven competing infrastructure projects.

```text
00 prove exact Odoo.sh, AWS, Infisical, 1Password access + full blast radius
       |
01 Odoo.sh native automatic+manual backup and isolated restore
       |
02 independent AWS vault, KMS/IAM + Infisical + alerting + safe IaC
       |
03 one real Production full backup -> protected S3 -> AWS-only restore
       |
05 initial: 1Password emergency pack and independent retrieval for PROVEN BASELINE
       |
04 fresh, consistent incremental/dedup -> 4 weekday triggers -> restore
       |
05 refresh: same emergency pack, current release and credential proof
       |
06 ransomware/Infisical/Odoo outage drill + all tests + independent operator handoff
       v
  CAMPAIGN_DONE ONLY WHEN ALL MANDATORY GATES PASS
```

## Work units and dependency semantics

- Each slice reads `policy/LOCKED_POLICY.yaml`, `policy/INVARIANTS.md`, this file, `coordination/DEFINITION_OF_DONE.md` and the exact predecessor receipts. At entry confirm external service state has not materially drifted; source revision changes selectively invalidate related prior proofs.
- Do not write implementation code before 00's exact blast-radius plan is source-verified, all material effects/dispositions are owned, file adds/edits/removals/rollbacks known, and fail-closed unresolved dependencies classified. This remains true for new impacts discovered later: re-plan the affected scope before continuing.
- Work may happen in a *single bounded coding campaign with consecutive internal commits* to avoid repeated publication ceremonies; still emit a separate, auditable 00-06 receipt per contract. The native Odoo and AWS external write authorities never merge. If independent PRs are needed, use related stacked branches only when they consume predecessor code; otherwise use integration-base `Staging`. Do not invent merge prerequisites or publish with raw push.
- Every contract closes its own in-scope failures, test fixtures, secrets, IaC changes, cleanup, event/risk alarms and evidence before a successor consumes it. One off-platform real restore must precede optimization. A package or PR alone is never an operation proof.
- AWS creates/changes ONLY newly scoped and verified DR resources. Native Odoo production data remains untouched; supported native manual backup action belongs exclusively to 01. Contract 05 holds user 1Password approval (interactive auth when needed) but must not require Cursor to know the account password.
- A 1Password login, Mac access or cloud permission missing from agent session gets one exact, bounded operator-action request and a `BLOCKED_EXTERNAL` receipt. Cursor continues independently safe work and resumes that contract once permission is supplied. It may not substitute fake credentials, browser scraping or a Dropbox file.
- Every material source-owner update, artifact and code reference has one owner. Safe configuration/infrastructure code belongs under `ops/independent_dr/` (subject to current source inspection). Production receipt material belongs in a private, encrypted vault, not Git.

## Failure contracts

`FAIL`: code or infrastructure is wrong under verified authority; debug and remediate within the slice, rerun regression and real proof. Never accept FAIL as handoff.

`BLOCKED_EXTERNAL`: a provider feature genuinely unavailable, missing independent account/Infisical/1Password grant, Enterprise license constraint, or operator biometric required. Must include observed evidence, exact failed capability, source owner, one actionable permission/capability request, and preserve prior successfully protected data. Status remains NOT_DONE.

`PASS`: all mandatory slice outputs exist, operator/recovery consumers can access them, all negative tests have observed results, no in-scope TODO/UNKNOWN remains, and actual source/provider evidence is attached privately with public-safe hash/ID summary.

## Closeout integrity

The source README is advisory. The actual release gate is `coordination/DEFINITION_OF_DONE.md`. The operator may request a change to requirements, but Cursor may not dilute, waive or relabel a mandatory gate. If the external platform cannot meet four fresh, consistent weekday snapshots, do not invent an API; immediately preserve daily real recovery, get an exact vendor capability answer and request approval for an alternate source method or service tier if genuinely necessary.

## Explicit early protection milestone and durable release

- Contract 05 is executed **once as soon as 03 proves an independent baseline**, and refreshed/retested after 04 to reflect the actual scheduled system. The 05 owner can PASS for the *complete current proven capability*, even if 04 is BLOCKED_EXTERNAL; 06/campaign DONE still require 04 PASS. This breaks the unsafe dependency in which a platform limitation could prevent emergency custody for a genuine daily restore.
- Contract 02 establishes a minimal lawful independently accessible AWS/KMS recovery principal needed for Contract 03's first restore; Contract 05 subsequently publishes the operator-friendly full emergency pack. The 1Password Document itself must not be the sole prerequisite to bootstrap its own upload.
- After each AWS apply, the exact source commit and image/dependency digests required to run recovery must be saved under independent protected release custody, separate from mutable or unmerged Git branches. A later change cannot strand protected backups behind dead code, lost secrets or unexported Terraform state.
- Closeout may not be called PASS based on provider promises. If 04 remains BLOCKED_EXTERNAL, C must still preserve an actually restored baseline + usable 1Password pack, name the requested vendor capability, and report campaign NOT_DONE. Do not leave a bare backlog, silent TODO or fake PASS.
