# Campaign acceptance | No substitute for a recovered system

**SM-ODOO-DR-CAMPAIGN-001 | v1.3.0**

## Release algebra and honesty

A mandatory contract has exactly one disposition: `NOT_STARTED`, `ACTIVE`, `PASS`, `FAIL`, or `BLOCKED_EXTERNAL`. A task cannot be `PASS` while a required test or expected configuration is `UNKNOWN`, `NOT_RUN`, deferred, unowned or under a TODO. `BLOCKED_EXTERNAL` requires a source-bound, verifiable external dependency (e.g. provider incapability, missing operator sign-in or licensing grant), what was proved impossible, who can resolve it and exact requested action. It is **not** a successful contract and it **never** makes the campaign DONE. Implement all independently safe parts before reporting a blocked boundary.

`CAMPAIGN_DONE` is true ONLY IF every `00..06` contract is `PASS`, all acceptance gates below have dated, exact-source receipts, the operator has demonstrated real emergency custody, and actual remote source code and live AWS state are reconciled. Missing evidence never defaults to true. No automated agent can waive a mandatory gate by changing this pack or narrating a workaround.

## Mandatory exact-DONE predicates

| Gate | Required witness to mark PASS | No-go examples |
|---|---|---|
| D00 Blast radius and source rights | Current Odoo.sh Production, Repo Staging SHA, actual AWS account/region, Infisical project/path, 1Password vault capability, Enterprise rights and exact files/resources/permission matrix accounted before coding | Untested AWS account, unauthorized production access, unowned file/secret/permission |
| D01 Native Odoo | Actual native daily backups healthy with source timestamps; one supported manual backup; verified native restoration in isolated target with filestore and no outbound effects | Only backup-list screenshots, unexercised restore or platform-managed policy falsely 'configured' |
| D02 AWS trust boundary | Dedicated independent account IAM; encrypted, private, versioned, object-locked S3; safe KMS emergency decrypt; real writer deny tests; cost/alerts observed; new secrets in Infisical; safe IaC/state | Same creds can delete backups; key missing or state in Git; dormant alarms |
| D03 Independent recovery | Genuine complete Odoo Production DB+filestore checkpoint in S3 with version/hash/source-time provenance, exact code/licenses/config; AWS-only restore running correct Odoo Enterprise with data/attachment checks | Upload alone, wrong source revision, needing Odoo.sh/Infisical to recover |
| D04 Incremental schedule | Two or more fresh distinct real Production source points restored; controlled changed/deleted transaction and attachment semantics verified in disposable Odoo through the same recovery mechanism (no Production test mutation); dedup and source transfer savings measured; 11/13/15/17 weekday scheduler tested; one scheduled checkpoint restored; 365-day availability plus hot/cold retention closure; source RPO measured | Four uploads of same daily file, no supported 2h source, stale restore or dedup chunks pruned |
| D05 Emergency 1Password pack | First a real baseline recovery Document immediately after 03, then refreshed after 04; restricted vault with all mandatory current-recovery material; minimal emergency items; independent account bootstrap/MFA; separate retrieval SHA256 and runbook rehearsal without Mac/Infisical/Odoo.sh | Baseline restore worked but no operator pack; agent says item created but cannot retrieve; stale pack after 04; secret ZIP left on Dropbox |
| D06 Final independent rehearsal | Representative Odoo outage + Infisical outage + worker unavailable; clean-room restore from S3 & 1Password, no side effects, correct complete data; RPO/RTO measured; alert receipt; operator handoff; source/terraform state/PR actual identities | Test-fixture-only PASS; unremediated findings; no operator can execute process |

## RPO and practical caveat

- Target: 120 **operating** minutes. Four 11/13/15/17 starts do NOT guarantee 120-minute worst-case RPO, because capture and upload take time. Model source checkpoint time and admission latency, especially the 09:00-11:00 start window, job failures and Friday-to-Monday gaps. Native Odoo platform protection continues at all times.
- If supported fresh two-hour source access is unavailable at the existing Odoo.sh tier, report `BLOCKED_EXTERNAL` with precise required Odoo provider entitlement/support answer, complete daily independent recovery and its restore as a **partial milestone**, but DO NOT mark this campaign DONE. Do not silently increase frequency or run outside the locked schedule.
- Restored recovery data can still be poisoned before the snapshot if compromised: detection/last-known-clean selection and preserved older immutable versions remain required.
- A real-time guarantee, compromise of the independent AWS account/KMS administrator and total outage of AWS/1Password remain residual failure classes unless separately covered; do not claim 'total security'.

## Files and execution effects required at close

- Pinned source revisions, exact plan/source inventories, root invariant pointer (smallest safe), actual IaC, secret inventory (references only), native configuration procedure, backup source mechanism, restore tooling, identity/retention/alert policies and monitored automation all live and reproducible.
- Every contract's receipt identifies exact Git HEAD/diff/PR (if applicable), AWS resource inventory, testing evidence IDs/time, negative results, private Infisical/1Password item references, operational cost owner, last-good checkpoint source time and expiry/rotation, observed RTO/RPO, cleanup and remaining Unknowns.
- No production writes to Odoo records, unauthorized AWS edits, invented Odoo platform endpoint, arbitrary Odoo Enterprise license duplication, non-verified `make pr`, secret leakage, cross-project repo code drift or unfinished test follow-up.

## Final release adjudication

A single 06 closeout ledger must explicitly mark each contract PASS and cite its independent verification reference, compute all D00-D06 as TRUE and name the human operator who successfully retrieved and followed the emergency pack in a clean session. Actual Odoo/AWS/Infisical/1Password infrastructure observations are required. If any are missing, final status is `NOT_DONE`, with exact next authorized action. Never replace an unmet business objective with a smaller unapproved success definition.

## Scope-correct partial milestones and release independence

- `EARLY_INDEPENDENT_DAILY_PROTECTION` is a **milestone**, not a new permissive campaign completion state. It requires 01 native source PASS, 02 vault PASS, 03 real complete S3 restore PASS and 05 **real baseline operator custody PASS**. It is false if the 1Password pack is only drafted or source backup is stale. It may remain true even if 04 is `BLOCKED_EXTERNAL`; the full `CAMPAIGN_DONE` remains FALSE.
- A full campaign PASS also requires evidence that **the deployed executable recovery code, its exact build dependencies/Enterprise rights and infrastructure rehydration state** are independently protected and can be retrieved when GitHub/the unmerged PR/original Mac are all inaccessible. The operator cannot rely on a developer's unmerged local checkout at disaster time.
- Before 06 PASS, any source, schedule, IAM/KMS, software, provider rights or secret change since baseline triggers a renewed Contract 05 pack, digest verification and operator clean-room rehearsal. A historical 05 PASS receipt with stale identities is invalid.
- The account and spending boundary must be explicit even if a new dedicated AWS member account is needed. Source proof cannot infer consent to make irreversible AWS-account or Object Lock retention changes from the presence of API credentials alone.

- No recovery milestone may be PASS if the regular backup writer can alter last-good or self-publish an admitted source checkpoint. Verify explicit separate admission authority, candidate integrity, immutable version IDs and unsuccessful self-promotion attack before final closeout.
