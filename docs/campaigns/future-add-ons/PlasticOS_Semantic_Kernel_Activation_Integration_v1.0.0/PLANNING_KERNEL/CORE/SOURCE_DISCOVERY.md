# Recursive blast-radius discovery | the minimum complete source closure

**Purpose:** implement the user's POS-INV-26 planning standard without confusing a reachable module with a proven runtime consumer, without inspecting the world, and without leaving known consequences for the coding agent to discover. This protocol is **read-only** until a separate implementation grant.

## 1. Bind a coherent source epoch

- Resolve branch/PR identities, `Staging` HEAD, exact WIP base/head/merge base, current file blobs, source-registry and applicable original business decisions. Pin an immutable ref for all repo reads; do not mix different SHAs into one supposed state.
- On rebase or merge, compare source/blob changes, update scope-specific effects and regenerate the case digest. Current branch names alone are not source coordinates.
- `SOURCES/REPO_SOURCE_LOCK.json` is a **2026-10-29 snapshot**, not a live source resolver. The CLI refuses a case target SHA different from both this lock and the provided manifest snapshot. For later SHA: inspect and recreate **both** at one revision (case-specific `--snapshot` and `--source-lock`); never just modify the case SHA to force green.
- `docs/reports/repo-index/` may reduce search cost but is generated and potentially stale. Confirm against live tracked source, Odoo registry and manifests; regenerate through the repo's authorized generator when necessary, not a second plan-owned index.

## 2. Traverse the actual module graph

Start with the real changed model/file/module owner (`source_census.root_modules`). For each root calculate all reverse dependents from `__manifest__.py`: `changed module <- direct addon that depends on it <- transitive addons`. The included script does only that:

```sh
python3 tools/impact_modules.py --roots plasticos_documents plasticos_logistics
```

**Important:** reverse dependency means *possible install/registry impact*, not necessarily actual behavioral impact. Every candidate module receives an inspected `EDIT/CREATE`, evidence-backed `NO_CHANGE`, or proven independent exclusion in `source_census.module_dispositions`. The list is a **screening universe**; it does not automatically require changing each dependent addon. On a newly created addon, add its prospective manifest dependencies and check the future graph for cycles and collision; the snapshot cannot know future importers.

For a changed source field or API also traverse the actual **forward** dependencies and importers. Trace relational definitions/`_inherit` and `@api.depends`, computed/search fields, QWeb, XML `ref`/`inherit_id`, `ir.model.access`, record rules, `sudo`, SQL/read-group domains, native Sale/Purchase/Stock, mail and cron consumers. A new model being unused in `__manifest__` consumers does not prove nobody invokes it dynamically.

## 3. Inspect non-manifest consumers

| Reachability class | Source and observation required | Frequent false omission |
| --- | --- | --- |
| ORM / Python | `_name`/`_inherit`, `fields.Many2one`, `@api.depends`, model methods and direct/indirect callers, import laziness | Adding a new hard field dependency across a lower-layer module, or replacing it with a semantically unsafe integer |
| Security / company | ACL CSV, `ir.rule`, role hierarchy in `plasticos_security_base`, actual company source, record rules and `sudo()` justification | Assuming a company rule covers SQL dashboard queries |
| UI / reporting | XML form/search/list, action/context, buttons, QWeb, PDF templates, SQL views and dashboards | Render path still assumes buyer/SO, leaks partner identity |
| Notifications / workflows | Linda request source-kind, native mail `mail.mail`, reply threading, `base.automation`, `ir.actions.server`, `ir.cron`, templates, inbound aliases | Second sender or stale cron still emits packets |
| Commercial/physical/finance | Native PO/SO, Stock reservations/pickings, Transaction/Load, Accounting posting, document verification; source and replay identity | One evidence row silently creates a payment, buyer, inventory or dispatch |
| Native/Enterprise | Installed model and fields, feature entitlement, document original, requests, stock/account/mobile, real ACL/automation | Guessing a native Odoo Enterprise field/API from a doc or an older edition |
| Data and lifecycle | NULL counts, duplicates, company conflicts, orphan refs, historical status, old XMLIDs, migration version and filestore | Backfill promotes historical unverified evidence to current truth |
| External integration | Gate/CEG/EIE source contracts, CRM portals, web forms, external mail, provider API and callbacks | Restoring a retired local intelligence engine or duplicate transport sender |
| Tests / release | All affected tests, fake/negative paths, concurrency/races, feature toggles, version bump, module upgrade, rollback and backup | A green unit test treated as an installed Enterprise or production receipt |

Run the environment-dependent search in **read-only** mode against the actual disposable Enterprise/odoo.sh clone only if authorized and accessible: `ir_module_module`, `ir_model`/`ir_model_fields`, `ir_rule`, `ir_model_access`, `ir_ui_view`, `ir_cron`, `base_automation`, `ir_actions_server`, `mail_template`, `mail_alias`, and installed native module schema. Discover actual model names/ACL first. Do not disable crons, send mail, alter templates or create a test DB in the name of planning. If inaccessible and material, mark `UNOBSERVED` and block the affected code gate. A grounded nonmaterial exclusion is allowed with a cited source and falsifier.

## 4. Reconcile authority and stale documentation

- Constitutional rules are in current `INVARIANTS.md`. BAN001 applies to every tracked path and byte. All 19 other numbered invariants receive an applicability disposition. `POS-INV-26` stays mandatory as operator planning instruction; POS-INV-01..25 are candidate themes only.
- For Logistics, inspect `plasticos_logistics/business_rules/README.md`, original `BRS-0N`, `SUPERSESSION.md`, `EFFECTIVE_RULES`, relevant `LINDA_BUILD_PLAN.md` and live source. Preserve narrow operator supersession without editing original BRS.
- For Documents, inspect `plasticos_documents/business_rules/README.md`, `BRS-POS-02/03/09`, `EFFECTIVE_RULES`, `OWNERSHIP_AND_INTEROP.md`, `SUPERSESSION.md`, plus latest verified code. The Oct 29 source already contains verification/association fixes; do not rebuild those features from stale Export-era proposals. Repo BRS status may be proposed: distinguish requirements from implementation.
- For intelligence and Gate, use the exact `docs/adr/ADR-003-single-external-intelligence-authority.md`, ADR-009..018 and ADR-019 supersession. The duplicate `ADR-003-contact-import-configuration.md` is independent. Retired local engine names in old `.cursor` overlays are not architectural permission.
- For skill/project layout use `skills/PLASTICOS_CANONICAL_LAW.md`, not `AGENTS.md` narrative alone. For dependency truth inspect manifests, not a stale diagram or layer enumeration. The installed Enterprise revision is a separate source owner; do not infer it from git.

## 5. Account for EVERY material effect

Record one source-bound `effects[]` object per material effect and `source_census.module_dispositions[]` per reverse manifest candidate. Each effect contains: exact consumer/owner, `source.path/revision/git_blob_sha` for existing repo code, cause/reachability, before/after contract, action (`EDIT` / `CREATE` / `REMOVE` / `NO_CHANGE` / `INDEPENDENT_EXCLUSION` / `NO_ADD`), exact file/surface list, change predecessor, migration or justified none, recovery/rollback, company/security consequence, both positive and negative proof IDs, and what source change would invalidate the plan.

Do not write “no impact” based on absence of a grep hit alone when XML/SQL/Enterprise runtime or dynamic routing may still reach it. For every exclusion, state its falsifier: *which discovered reference, business scenario, company/role, state transition or runtime consumer would reverse this decision?* A confirmed no-change is a positive technical decision and must be tested where consequential.

## 6. Plan all slices before coding, verify later

Create the whole-project dependency-ordered `delivery.units` only **after** the union census, with effects assigned exactly once. Small PRs follow those dependencies. Every changed addon has its `__manifest__` version bump, correct `__init__` and manifest data/security/view/test wiring, idempotent and versioned migrations if needed, data-backup/filestore restore strategy, ACL tests, concurrency and replay checks, and native/Enterprise installer/runtime witnesses. Testing plans are pre-code; actual run results are after implementation and never fabricated.

**Repo test safety:** use the declared `config/odoo_module_order.yaml` and `scripts/get_odoo_module_order.py`, `scripts/test_env.sh` owned-clone safety, the canonical Enterprise fixture `config/test_env_fixture.conf`, `make test-module m=<changed>` and designated install-smoke flows. Test runner may have a narrower module roster than installed optional Enterprise addons, so an optional addon needs an exact run plan; do not silently claim it was included. `make update m=<module>` is scoped and **only after authorization**. For publication the repository's current `make pr` is the sole interface; a merged PR is not production deployment.

## 7. Closure and reopen criteria

**Closure candidate:** all listed material effects fully accounted, all reverse manifest candidates disposed, added code/runtime consumers inspected, no known material conflict or decision unexplained, protected behavior and positive/negative tests specified, migrations and recovery planned. This is a *bounded technical planning conclusion*, not a claim that every unknown system has been inspected. If current native Enterprise or DB consumers remain materially unobserved, precode remains blocked for dependent scope.

**Reopen:** branch SHA/blob changed, material interface changed, source-owner BRS supersession arrived, installed EE schema or Odoo.sh settings drifted, DB-defined action discovered, new direct or transitive caller found, forbidden duplicate authority exposed. Stop before unplanned edit, recompute impact/dispositions/digest and obtain fresh execution authorization for expanded changed scope. Do not invalidate unrelated frozen business decisions.
