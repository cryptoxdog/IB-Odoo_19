# v0.1.0 → v0.2.0 transition | consciously incompatible schema

**Breaking case format change:** v0.1 `plasticos.addon-planning-case/v0.1` is not mechanically compatible with v0.2. Do not silently fill missing constitutional cases with fabricated evidence or reinterpret previous candidate rows as admitted law.

| v0.1 field | v0.2 field / conversion requirement |
| --- | --- |
| `invariant_applicability` (26 draft IDs and BAN001) | `invariants.constitutional` (19 current repo numbered reference keys plus BAN001), **must be re-assessed against the active v2.2.0 source**. Draft applicability becomes `invariants.candidate_screening` (screen-only, no promotion). |
| v0.1 `target.constitution.authority_class=CANONICAL` | v0.2 `target.constitution.authority_class=CONSTITUTIONAL`, exact repo blob version and SHA, verified in source lock. |
| v0.1 `target.revision` | Immutable current revision, matching **both** fresh source lock and full module manifest snapshot. |
| `source_census` search strings | New root modules, reverse-manifest `module_dispositions`, extra/dynamic consumers, scope limits; manually inspect actual code and rerun discovery. |
| v0.1 `effects[].source` | Existing file must have exact bound revision + source Git blob where applicable; retained effect IDs, business owners and change paths where still correct. Add `security_impact`. |
| v0.1 WIP baseline optional object | v0.2 NEW omit WIP; WIP requires explicit actual base/head, per-capability preserve/correct decision and falsifying test. |
| `operator_plan_acceptance` / `coding_grant` | Same separation in v0.2, but offline precode **never** authorizes execution even with fake JSON declaration. |
| v0.1 reduced-subset JSON validation | v0.2 full JSON Schema Draft2020-12 using `jsonschema`; missing library is fail-closed. |

A migration **cannot be automatic without user-supplied source and constitutional evidence**. Start a v0.2 case and transplant only unchanged, verified business decisions, real source facts and effects. The v0.1 manifest is in `SOURCES/PREDECESSOR_MANIFEST_v0.1.0.json` so previous artifacts remain traceable; original ZIP remains separate and unchanged. No v0.1 case conversion or project code migration has been run.
