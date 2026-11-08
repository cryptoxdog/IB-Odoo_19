# Implementation handoff projection | not the authorization itself

Use this only after completing whole-case source reconciliation and obtaining genuine operator plan acceptance and a **separate authorized code scope** at the actual execution host. Do not create a self-signed approval by setting `granted=true` in JSON. The offline validator deliberately refuses to authenticate any coding grant.

**Exact source identity:** repo / baseline and WIP head SHA / module manifest snapshot / `INVARIANTS.md` blob / applicable accepted ADR full filenames and module BRS IDs / current plan content digest.

**Protected decisions and code:** explicit list from `case.authority.locked_decisions` and `target.wip.capabilities`. Do not rewrite already-accepted behavior or weaken negative regression assertions.

**All affected owners / paths:** project-wide `case.effects`, `source_census.module_dispositions`, `extra_consumers`, including proven NO_CHANGE/NO_ADD/INDEPENDENT_EXCLUSION. No blanket permission to edit all listed addons; each operation is bounded by approved scope.

**Source-owner contracts:** actual installed method/field/schema evidence (proposed method names do not exist merely because a plan uses them). No reverse dependencies, duplicate authorities/writers, fabricated orders/movement, or secondary mail/posting paths.

**Ordered implementation slices:** `delivery.units` with exact effect IDs, predecessor order and expected result. Runtime-changing addon code requires version bump, scoped update, ACL/rules, init/import, manifest XML data, idempotent migration where applicable.

**Proofs and recovery:** positive, adversarial/negative, security/company, concurrency/replay, import/data, business-clock and no-sends/finance guard tests; actual Enterprise registry install, tests with record counts, migration/rollback and DB+filestore restore rehearsal at appropriate stage. `NOT_RUN` stays `NOT_RUN`.

**Publication:** repository's `make pr` only when separately authorized and host verifies it. No raw push/merge/deploy, Odoo.sh production cutover, live communications or paid calls from this pack.

**If new ripple:** stop dependent edits, update full affected closure, recompute case hash and renew actual operator scope. Do not silently expand a child PR.
