# PlasticOS addon planning kernel | one case, two routes, nine gates

## Mission and scope

**Mission:** create the smallest useful, correct PlasticOS Odoo 19 capability (or align an existing WIP) without duplicate authorities, stale contracts, unplanned transitive consequences, or accidental production effects. Output a **whole-change-set source-bound plan**, not program code. This is a method, not an admitted Odoo/L9 law.

**Scope precedence:** explicit operator constraints; actual constitutional `INVARIANTS.md` v2.2.0 at the bound revision; repo-owned `skills/PLASTICOS_CANONICAL_LAW.md` for skill layout; relevant *accepted and narrowly superseded* ADRs; effective module-local BRS plus ID-specific supersession; source implementation and measured observations; agent/router documents where consistent; archived/draft material only as candidates. Do not impose an unverified global ordering across independent subject-owner domains. A conflicting rule must be resolved at the actual authority owner. `SOURCES/REPO_SOURCE_LOCK.json` lists the specific inspected source classes.

**One source of truth per case:** `case.json` is the working plan's **derived assembly** and has one editable representation for each decision/effect. It is not a replacement for the higher-level authority files, and it cannot promote a proposed API, acceptance result or user approval. The pack's readme, effect tables and coding handoffs are projections of current case data + cited source, not places to author a second business rule.

## The ten permanent planning disciplines

1. **Outcome before addon.** Define who performs which real job and the first falsifiable useful result. Protect any already-working WIP before imagining a rewrite.
2. **Native first and minimum new ownership.** At exact Odoo 19 Community + installed Enterprise, compare `REUSE`, `CONFIGURE`, `EXTEND`, `BRIDGE`, `NEW_ADDON`, `DEFER`. Do not invent an Export-specific identity or parallel workflow in an unrelated addon.
3. **Exact facts and owners.** Identify native/legal source-of-truth writer, business scope, lifecycle, actor/company, event time, version/replay key and consumers. Never infer a real order, buyer, dispatch, stock movement, email success or payment from a convenient field.
4. **Module DAG from real manifests.** Actual `__manifest__.py` `depends` supersedes outdated diagrams. Keep models/fields in their semantic homes. New references and `_inherit` must have dependency wiring; avoid cycles. An untyped `Integer` replacing a relationship is **not** automatically semantically safe.
5. **Protect authoritative contracts.** Cite `INVARIANTS.md`, exact accepted ADR full filenames, local BRS IDs and specific later supersession. An owner is the module/semantic authority, **not** an invented human sign-off committee.
6. **Recursive blast radius, entire change set.** Inspect direct + transitive consumers (both call and dependency directions), registry/ORM, XML/QWeb, SQL, ACL, mail, cron, reports, APIs, data, migration and recovery, Enterprise/DB actions, and tests. A manifest reverse dependent is a **candidate**, not proof of behavioral impact.
7. **Account for every effect.** Record `EDIT`, `CREATE`, `REMOVE`, `NO_CHANGE`, `INDEPENDENT_EXCLUSION` or `NO_ADD` with source, owner, rationale, exact path, before/after, predecessor, migration, recovery and positive/negative proof. `NO_CHANGE` without source evidence is not closure.
8. **Evidence is typed.** Separate observed repository code, observed installed registry, integration test, hosted behavior, routine operation and inferred plan. An imported document, AI classification, lint success or merged PR alone is not a live business outcome.
9. **Plan first, small implementation later.** Know the entire blast radius before any project code or tests. Split execution into ordered small slices after closure; later optional product features must not block the MVP. New discovery invalidates affected closure and corresponding grant, never silently extends scope.
10. **Authorization and release separately controlled.** A candidate plan or local validator cannot authorize code, `make pr`, merge, Odoo.sh deployment, production backup/migration, live mail, or paid API use. Exact code authorization belongs to the operator and actual governance tools; runtime proof follows implementation.

## Nine bounded steps

| Step | Output | Rejection condition |
| --- | --- | --- |
| S0 Bind revision | Exact target branch + SHA, WIP base/head, constitution blob, source lock and current artifact hashes | Changed branch with unreconciled case is stale |
| S1 Recover intent | Locked decisions and explicit exclusions; user/job, near-term proof and competing alternative | Guessing a material business choice |
| S2 Source-owner and native census | Actual installed native/Enterprise capability, existing addon, BRS/ADR and single writer | Parallel subsystem without demonstrated gap; unproven API assumed callable |
| S3 Architecture integrity | Identity/cardinality/state/trust boundaries, prospective addon placement, dependency DAG and external seam | Duplicate writer, reversed dependency, fictitious events |
| S4 Recursive reachability | Changed roots, reverse-manifest candidates, code/data/ACL/SQL/QWeb/mail/cron/native/dynamic consumers and explicit limits | Omitted materially reachable frontier or unsupported exclusion |
| S5 Whole-change plan | Every material effect; edit/add/delete/no-change paths; prior/next stages; migration, recovery, positive/negative tests | Any effect without disposition, owner, source or plan |
| S6 Counterexample/reconciliation | Break-tests against strongest alternatives, drift, WIP preservation, cross-PR interactions, BAN001 and no-code gate | Fixed business decision silently reopened; conditional test treated as proof |
| S7 Declared-plan checks | Schema, exact invariant census, source/manifest SHA lock, full reverse module coverage and negative controls | Structural errors; mechanical success cannot prove source completeness |
| S8 Handoff decision | Operator plan consideration, bounded execution authorization and source-owner implementation obligations | No authenticated grant, unadopted installed API or unresolved material dependency |

The gates are **ordinal states, not percentages**. A structurally complete plan is distinct from implemented code, Enterprise install-smoke, migration replay, restore rehearsal, Odoo.sh deployed behavior and recurring business operations.

## NEW addon mode

First propose the smallest existing **semantic owner** able to deliver the business job. Search standard Odoo models and available Enterprise capabilities, then existing `plasticos_*` addon paths, then a narrow bridge. Admit `NEW_ADDON` only if irreducible ownership demands it, and express exactly what it owns and **does not** own. Build a prospective `depends` DAG, source-compatible interface and event model; future capabilities get bounded seams only, not premature tables and crons. The plan must name new addon tests, security ACL/record rules, deterministic XML IDs/seed rules, manifest version, wiring, migration rules and an install/upgrade/rollback plan. No scaffold before whole-change-set planning.

## WIP alignment mode

Bind **exact WIP head** and merge base; inspect actual code and accepted intent rather than starting from a replacement spec. Per capability choose `PRESERVE`, `ALIGN`, `SPLIT`, `SUPERSEDE` or `RETIRE` and record protecting regression tests. A failing test may reflect a genuine code defect or a stale assertion; do not weaken an assertion without verified requirements. Evaluate the *union* of affected PRs and successor interfaces and resolve cross-branch conflicts at the intended owner. Keep unrelated passing code and source history unchanged. An upstream merged fix is reused, not re-implemented by the plan. A reviewer only judges code; this working pack does not auto-close PRs.

## Completion and no-change policy

Pre-code completeness means: no known material untraced consumer, documented search bounds, all changed root modules' declared reverse dependents disposed, all extra dynamic consumers disposed or evidenced out-of-scope, exact implementation files and order accounted, security/data/migration/recovery and positive/negative tests planned. This is a **bounded evidence-grounded conclusion**, never a promise of omniscience. When runtime access cannot be obtained, identify the missing read-only inspection as `UNKNOWN` and stop only dependent execution. Do not invent source-owner human approvals. `CORE/SOURCE_DISCOVERY.md` defines the concrete census.

## Revalidation after change

A new SHA, manifest, BRS/ADR supersession, installed Enterprise revision, dynamic server action, DB schema, audience rule or newly discovered consumer must trigger *selective re-census* of its reachable impact path. Recompute the plan digest; prior operator plan acceptance and coding grant against the old digest no longer cover changed material scope. Preserve protected unaffected history and already proven facts. Source rebinding to the same unchanged Git blob is possible with explicit evidence, but branch-name identity alone is not proof.
