# PlasticOS repository installation route | NOT EXECUTED

The current deliverable is a **portable planning pack**. Its `tools/` directory is not an Odoo module and is not a governance plugin or preinstalled agent skill. Nothing in this pack has been committed to `cryptoxdog/IB-Odoo_19`.

If the operator later authorizes **installing this capability as an actual PlasticOS project skill**, conform to the exact current `skills/PLASTICOS_CANONICAL_LAW.md`:

- Canonical skill source `skills/plasticos-addon-planning/` under this repository, with `SKILL.md` and bundled references/validators, not a parallel `.claude/skills` implementation.
- Register `skills/PLASTICOS_SKILLS_MANIFEST.yaml` with `invocation: auto`, `disable-model-invocation: false`, and a clear NEW/WIP trigger route that is **planning-only**.
- Register in `AGENTS.md` and `.claude/README.md` project-skill tables; add a discovery symlink `.claude/skills/plasticos-addon-planning` pointing to `../../skills/plasticos-addon-planning`.
- Never create an Odoo addon `__manifest__.py` or `__init__.py` under `skills/`, and do not copy L9 GlobalCommands packs into this repository.
- Validate `make check-plasticos-skills` and `scripts/check_module_wiring.py`, independent of project-specific plan validation.
- Use only governed `make pr` after explicit operator authorization; no direct push, merge, deploy, or invocation registration is implied by this candidate.

**Do not promote `SOURCES/ODOO_INVARIANTS_v3.4.0_DRAFT_r2.md` to constitutional law** by distributing it with the skill. The active v2.2.0 constitution stays active until a separately authorized amendment and enforcement update. The planning skill may enforce the user-locked POS-INV-26 operator pre-code gate without claiming universal constitutional adoption.

Alternative: keep this package as an external read-only planning reference and give it to the architect at project kickoff. It need not be installed as a skill to be useful. This avoids extra repo/tooling churn while testing the two modes.
