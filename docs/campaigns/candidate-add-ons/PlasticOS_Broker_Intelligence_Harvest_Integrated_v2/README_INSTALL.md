# PlasticOS Broker Intelligence v2 - Installation and Use

**Delivery:** Four optional Odoo 19 addons bundled in a single ZIP. **Status:** Source implementation with offline checks; Odoo 19 Enterprise registry/ORM installation NOT observed. Do not deploy directly to Production.

## Inputs and authority

- Only repository: `cryptoxdog/IB-Odoo_19`, branch `Staging`, resolved at `c2c72bc36d6201d4114531a8f666c411db612f64` (2026-11-11 check). At that check, GitHub returned zero open PRs.
- Only source archive: `PlasticOS_Broker_Intelligence_Semantic_Harvest_v1.zip`, SHA-256 `2c0220acdc45c95ffe184da4e3b13dee58ec426a3b6d571aeae97bc02277062a`.
- No earlier standalone-v1 source ZIP exists among the authorized inputs. This package therefore implements the four-addon target afresh. The original 38 legacy standalone seeds and its exact `broker-advice/v1` callable signature were **not** independently available, so preservation/compatibility cannot be guaranteed.
- The reference repository was only read. No commit, PR, deploy, configuration mutation, or database operation was performed.

## The four addon roots

| Addon | Requires | Scope |
|---|---|---|
| `plasticos_broker_intelligence` | `base`, `mail`, `plasticos_intake` | Candidate knowledge, review lifecycle, source-bound approval, deterministic `broker-advice/v2` (and provisional v1 wrapper), intake advice, append-only outcome observations |
| `plasticos_broker_intelligence_mack` | Core, `mail` | Native **Mack: Broker Advice** intake button, verified optional chatter-source identity, immutable consultation snapshots and authenticated replay |
| `plasticos_broker_intelligence_web_leads` | Core, `plasticos_web_leads` | Read-only Web Lead Advice button and optional **shadow-only** advice context in the native `_qualification_signals` seam |
| `plasticos_broker_intelligence_rejections` | Core, `plasticos_offer`, `plasticos_matching` | Read-only Offer and Match Result rejection advice, source-bound raw statement and candidate feedback; no exclusions or state changes |

Every addon sets `installable=True`, `auto_install=False`. The core is a prerequisite for the optional addons; none installs without an explicit operator action. No external LLM, matching engine, mail sender, vector store, scheduler, or cron is created.

## Installation on an isolated Odoo 19 Enterprise validation database

1. Extract this ZIP, preserving each of the four addon directories. Place the four directories in a configured custom `addons_path` available to the Odoo instance **alongside** existing PlasticOS addons from the pinned `Staging` revision. The `source_catalog`, `tests_offline`, and `tools` folders are delivery evidence, not Odoo modules.
2. Confirm all existing dependencies are installed and current: `plasticos_intake` plus the optional owners `plasticos_web_leads`, `plasticos_offer`, `plasticos_matching` as applicable. In Odoo, update the Apps list, then **explicitly install** `plasticos_broker_intelligence` first. Observe registry installation success, XML view inheritance, ACL/rule loading, and source-draft import; if these fail, do not proceed.
3. Install optional addons one by one only when the underlying owner module is installed. Check the Intake button **Broker Advice**, the **Mack: Broker Advice** button, the Web Lead button, and both rejection-source form buttons.
4. Before allowing knowledge approval, designate an internal reviewer by assigning **Broker Knowledge Reviewer** to the appropriate internal user. All 106 imported candidates are drafts. A reviewer must inspect the original evidence, supply reviewed meaning, scope, prerequisites, source support, rationale and a nonempty readable Odoo attachment on the **same** knowledge revision, and attest before the **Approve Reviewed Revision** button will succeed. Regulated/specification/pricing/SOP claims additionally require an authoritative evidence reference. Review is never automatic.
5. **Web-lead integration is off by default.** To evaluate it, explicitly set system parameter `plasticos_broker_intelligence_web_leads.mode` to `shadow_only` **only on a test database** and keep the native `plasticos.web.lead.config` qualification mode at `shadow`. This appends advisory-only context to the existing single economic evaluation. In `legacy`, `live`, missing knowledge, or `off`, the extension returns the native signals without modification. It does not select or alter HOT/REVIEW/COLD.
6. In the same test environment, exercise exact source-message replay, company isolation, approval/retirement concurrency, duplicate-safe upgrades, historical data migration, and source-specific rejection security. Do not assume this package is deployable until all owner-native runtime gates pass.

**Suggested environment-side acceptance command:** use your already-configured Odoo 19 Enterprise test runner against a disposable copy of the applicable database; enable tests when installing the four addons. The command depends on your project's actual Odoo.sh/container runtime and is not guessed in this package.

## Broker user workflow

- **Core:** Open an existing Material Intake and click **Broker Advice**. Ask for missing evidence or verification needs. The service reads only allowlisted fields from the current record under the current user's permissions and retrieves **approved** knowledge. Its result explicitly separates recorded defaults, incomplete observations, unknowns, deferred knowledge, source citations and next human verification actions.
- **Mack:** Open the Intake and click **Mack: Broker Advice**. The deterministic consultation is stored as a new immutable receipt. A source-message ID is optional for manual consultation. If supplied, the source must be an accessible, authenticated Odoo `mail.message` from the same user and exact record/thread, containing that request. Replaying the same source message returns its original receipt and cannot reinterpret the question.
- **Web leads:** Optional read-only action on an existing web lead, with optional shadow-only enrichment. No second LLM request or intake/opportunity is created.
- **Rejections:** Open an existing Offer or Match Result and click **Explain Rejection**. The raw rejection text remains original; an exact canonical code or manually selected code produces only a **candidate** classification. Unresolved aliases abstain. Approved source guidance is only surfaced after the core structured-prerequisite and citation gates. Inapplicable knowledge is shown as deferred, never as an established buyer requirement. A broker may create separate candidate feedback after entering an exact evidence reference. No automated buyer exclusion, matching score, offer transition, or external email.

## Invariants and security

- `POS-INV-01..20` and `BAN001` in the pinned `INVARIANTS.md` are binding. This package claims **source-code intent**, not validated runtime conformance.
- An ACL and record rule cannot substitute for owner-specific access checks. Each source is read with its native permissions; the advisory layer does not `sudo()` the source or commercial owner.
- Knowledge is immutable after approval; retirement creates an immutable event that cannot be forged by a direct ORM `create`, and the next revision begins as a draft. The partial unique index prevents two approved versions of the same stable key in the same company scope, subject to Odoo 19 registry confirmation.
- The 106 candidate records are imported as `noupdate` drafts. The recorded harvest's 867 scenarios and 28 alias conflicts remain evidence inventory, not business facts or approved automation.
- Source outcome evidence has an actor, company, owner record, revision, and digest. The digest protects replay against duplicate candidate observations; actual concurrent ORM behavior remains a runtime gate. `verified_against_source=True` now requires an exact verbatim recorded rejection statement, rejected source state, and a rejection-type observation. It never certifies buyer specifications, material quality, an independently verified counterparty statement, or a successful settlement. Feedback records are readable by their originating operator within an authorized company, not all coworkers in that company; reviewer access to another broker's private source must follow its original Odoo permissions. `company_scope_basis=operator_company` denotes recording context, never verified source-company ownership.

## Validation and limitations

From the extracted bundle root, run:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests_offline -v
python tools/validate_package.py --verify-manifest
```

The `tools/build_release.py` script reruns portable tests, derives the test count from observed results, regenerates a file manifest, and independently verifies the resulting ZIP; use `python tools/build_release.py --output /path/to/revised.zip` to prevent replacing your existing release. The revision is based on the v2 ZIP with SHA-256 `649389e7b3fe163067e68beff6fa48d6518d0fed27f9482b171468eac79fe183`. Neither the static validator nor Python-only tests prove Odoo 19 Enterprise registry installation, record rule behavior, field binary uploads, UI actions, or execution inside the real inbound pipeline. See `VALIDATION_REPORT.md` for the acceptance matrix and `BUILD_RECEIPT.md` for the source binding.


## Recursive Leverage source hardening (revision 19.0.2.0.1)

The current pack is an additive, source-validated revision of the prior Revised ZIP, not a new architecture or production installation.

- All broker source authorization now passes through `plasticos.broker.advice.service._authorized_target` with positive integer IDs, native Odoo read access and company checks; feedback no longer maintains a competing interpretation.
- `broker-advice/v2` includes `knowledge_retrieval.complete` and `candidates_examined`. Where more than 150 current approved knowledge rows could apply, a 151st sentinel prevents a silent completeness claim, keeps `uncertainty=unresolved`, and requests human review. This is **not** a complete search in the truncated case.
- An approved reference includes its human-reviewed `workflow_scope` and `applicability_verified=false`. Reviewer approval of guidance does **not** prove that reference applies to the present lot, material, facility or counterparty.
- Rejection advice abstains instead of picking an arbitrary knowledge reference when multiple approved same-code/scope records are available. No offer, matching or buyer-exclusion state is written.
- `plasticos_broker_intelligence` and the rejection addon bump to `19.0.2.0.1` for the changed source; Mack and Web Lead bridges remain at their prior versions.

**Entrypoints:** Odoo-native buttons and permitted source-bound commands remain separate because they represent distinct authorized user actions. All source authorization is centralized; advice uses the single core advisory service. There is no extra transport, orchestrator or synthetic universal request gateway. This is the explicit single-ingress evaluation: one authorization/advisory ingress, not one invented business lifecycle.

**Release evidence:** `PROVENANCE_MAP.yaml` maps source and change provenance; `REGRESSION_GUARD.md` separates portable and runtime checks; `UNKNOWN_REGISTER.md` records unproven obligations; `CHANGE_SUMMARY.md` records fixes; `FILETREE.md` enumerates members; and `BUILD_MANIFEST.json` remains the authoritative file-hash inventory. No publication or Odoo.sh action occurred.

## Required checks for this alignment revision

When upgrading any previous source candidate, retain existing feedback/audit data and let the actual Odoo module upgrader apply the increased versions in Core, Rejection Advice and Web Lead Shadow. Validate feedback replay against any existing legacy `provenance_digest` rows, and test cross-company isolation with a user allowed to operate in two legal companies. Reviewer attestation must clear after changing a draft's reviewed meaning, scope or attachment. Do not activate the optional shadow path until a database-error injection proves savepoint recovery. These instructions are acceptance criteria, **not** claims of having executed a database migration or installation.
