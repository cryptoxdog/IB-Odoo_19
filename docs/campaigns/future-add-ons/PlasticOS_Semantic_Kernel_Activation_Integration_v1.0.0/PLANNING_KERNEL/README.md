# PlasticOS Strategic Addon Development Kernel | v0.2.0

**Classification:** planning-only WORKING CANDIDATE, not an installed skill, Odoo addon, approved PR, constitutional amendment or executable code grant. **Repo snapshot:** `cryptoxdog/IB-Odoo_19`, `Staging@677d734fd88615d673501d91de88734b7150ff50` (2026-10-29). The immutable source lock and all 30 module dependency manifests are indexed under `SOURCES/`.

**Two routes, one source-bound plan:**

- `new_addon`: challenge whether an addon is needed; use native Odoo 19 and existing PlasticOS owners first; design only the missing domain capability.
- `wip_alignment`: bind existing branch/PR(s), preserve proven working behavior, compare against current law/BRS/ADRs, and plan only required corrections across the combined train.

Both routes produce **one per-project `case.json`** with the exact business intent, source authority, active invariants, proposal screening, all material direct/transitive effects, justified no-change decisions, data/ACL/migration/recovery, implementation order, proof obligations and stop conditions. Human-readable briefs and coding contracts are *projections* of that case, not independent editable authorities.

## Most important correction from v0.1

The constitutional source is **`INVARIANTS.md` v2.2.0**, with **19 numbered rules plus BAN001**. The preserved `ODOO_INVARIANTS_v3.4.0_DRAFT_r2.md` has **26 POS-INV candidates plus BAN001** and is **not admitted** into that constitution. The user's exact POS-INV-26 blast-radius requirement is separately active as an **operator-imposed planning rule**, without falsely promoting its draft to constitutional law. BAN001 applies to every tracked byte and tracked path with no exception. `CORE/INVARIANT_ROUTING.md` explains the distinction.

## Read sequence

1. `CORE/PLANNING_KERNEL.md`: operating model, NEW versus WIP, minimum sufficient planning, stop/recheck rules.
2. `CORE/INVARIANT_ROUTING.md`: exact constitutional identity and candidate routing.
3. `CORE/SOURCE_DISCOVERY.md`: recursive code/data/Enterprise reachability and evidence-backed exclusions.
4. `SOURCES/REPO_SOURCE_LOCK.json` and `SOURCES/REPO_MANIFEST_SNAPSHOT.json`: immutable starting-point evidence. **Never silently reuse after a source revision change.**
5. `SOURCES/RECURSIVE_ALIGNMENT_AUDIT.md`: discrepancies found and their corrective placement.
6. `TEMPLATES/`: one case format, separate NEW / WIP working views, implementation handoff derived only after plan acceptance.

## Create and inspect a case

```sh
# External dependency for complete draft-2020-12 schema validation: jsonschema.
python3 -m pip install jsonschema
python3 tools/new_case.py --mode new_addon --id my-addon --out my-addon.case.json
python3 tools/new_case.py --mode wip_alignment --id my-wip --out my-wip.case.json
python3 tools/impact_modules.py --roots plasticos_logistics
python3 tools/validate_case.py my-addon.case.json --gate plan
python3 tools/validate_case.py my-addon.case.json --gate precode
python3 tools/test_negative_controls.py
```

A blank case **must fail**. A source-complete case may receive `DECLARED_ACCOUNTING_PASS`, which checks the declared structure, not whether all true consumers have been found. `--gate precode` **never grants coding**. Local JSON grant fields are not identity-attested: real operator authorization, source-owner interface implementation and execution governance are enforced separately by the actual host. No Odoo code is written by these tools.

## Non-negotiable source discipline

- Before applying a case, refresh `Staging` and WIP HEAD and verify exact repo files, active BRS/ADRs, manifest dependencies, installed Enterprise/native API and relevant runtime DB consumers. The snapshot in this pack is historical evidence, not a live mirror.
- Preserve the **entire protected change set** and all dependent obligations before the first project code/test/migration/configuration edit. Do not plan only the first PR and leave known ripples to improvisation.
- Run the repository's own checks when code is separately authorized: `scripts/check_module_wiring.py`, `ci/check_circular_deps.py`, exact Odoo 19 validation and protected Enterprise Docker fixture tests. They are **not run** by this pack.
- For changed runtime addon files, plan version bump and scoped update. For publication, use only the repo's effective governed `make pr` workflow after explicit authorization. Staging → Production and live mail/cron activation are separate decisions.
- No export/customer originals, secrets, external live messages, migrations, repository changes or PRs are included or performed.

## Packaging and proposed installation

This portable ZIP is **not** an Odoo addon, nor automatically an installable agent skill. If later authorized for native repository installation, its proper domain-owned home is under repo `skills/plasticos-.../`, with `SKILL.md`, manifest registry, `AGENTS.md`, `.claude/README.md`, and discovery symlink as governed by `skills/PLASTICOS_CANONICAL_LAW.md`. Do **not** store the source of truth under `.claude/skills`, make an Odoo manifest, or modify `.cursor/governance` symlinks. See `CORE/REPO_INSTALLATION_ROUTE.md`.

**Evidence limit:** this version reviews immutable GitHub source and its declared addon DAG. Odoo.sh live configuration, installed Enterprise internals, database-defined actions and source-git behavior tests were not executed. No project-specific blast radius is certified closed by a generic kernel.
