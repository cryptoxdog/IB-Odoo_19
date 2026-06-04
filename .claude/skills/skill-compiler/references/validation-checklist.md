<!--
--- SKILL_META ---
skill_schema: 1
origin: strict-skill-compiler
layer: reference
role: validation_contract
tags: [skill, validation, quality_gates, zero_stub, packaging]
owner: igor_beylin
status: active
version: 1.2.0
updated: 2026-06-04
--- /SKILL_META ---

Purpose:
Defines the validation gates required before a Skill pack may be presented, rebuilt, or packaged.
-->

# Validation Checklist

## Required Files

- [ ] `SKILL.md` exists.
- [ ] `SKILL.md` frontmatter includes `name`, `description`, and audit fields (`skill_schema`, `layer`, `role`, `tags`, `owner`, `status`, `version`, `updated`).
- [ ] No duplicate `SKILL_META` HTML comment on `SKILL.md`.
- [ ] Optional folders exist only when useful.
- [ ] Initializer-generated example files are absent.
- [ ] **No** `agents/openai.yaml` or `agents/` folder created.

## Repo Wiring (PlasticOS — mandatory for new skills)

- [ ] Row added to `.claude/README.md` Skills table.
- [ ] Row added to `AGENTS.md` Agent Skills table.
- [ ] Relevant `.claude/agents/*.md` updated with `skills:` preload if subagents should delegate with it.
- [ ] `name` in frontmatter matches directory name.
- [ ] Subagent preload decision documented if no subagent was updated.

Load `references/repo-wiring.md` for full contract.

## Frontmatter

- [ ] `SKILL.md` frontmatter contains only `name` and `description` for ChatGPT-compatible Skills.
- [ ] `name` is lowercase.
- [ ] `name` is short.
- [ ] `name` is hyphen-separated.
- [ ] `description` is lowercase.
- [ ] `description` explains what the Skill does.
- [ ] `description` explains when the Skill should trigger.
- [ ] Trigger logic is not hidden only in the body.

## Metadata

- [ ] Reference files include HTML-comment metadata unless format cannot support comments.
- [ ] Any metadata sidecar clearly identifies the asset it describes.
- [ ] Every metadata block includes all required fields.
- [ ] `layer` matches file location and purpose.
- [ ] `role` matches file behavior.
- [ ] Tags improve search.
- [ ] Purpose is short and accurate.
- [ ] Metadata contains no secrets.
- [ ] Metadata identifies the file instead of storing large doctrine.

## SKILL.md Body

- [ ] Instructions are operational.
- [ ] Workflow is compact.
- [ ] Resource navigation is clear.
- [ ] Validation requirements are included.
- [ ] Failure handling is included.
- [ ] Full base protocol is not duplicated outside `references/skill-pack-contract.md`.
- [ ] Kernel content is not copied in full.

## References

- [ ] Every reference file is linked from `SKILL.md`.
- [ ] Each reference has a distinct purpose.
- [ ] Kernels are compressed.
- [ ] Long checklists live in references, not `SKILL.md`.
- [ ] No reference acts as hidden memory.

## Scripts

- [ ] Every script performs deterministic useful work.
- [ ] Every script has a clear invocation path.
- [ ] Every script is testable.
- [ ] No script is present solely because a template generated it.
- [ ] No script is used for ordinary text reasoning.

## Assets

- [ ] Assets are reusable output materials only.
- [ ] Assets are not hidden instructions.
- [ ] Assets are linked or explained by the control plane or references.
- [ ] Large assets stay within package limits.
- [ ] Assets that cannot contain metadata have sidecar metadata.

## Zero-Stub Gates

Reject the Skill if it contains:

- [ ] incomplete required files
- [ ] unfinished-task markers
- [ ] dummy scaffolds
- [ ] pretend scripts
- [ ] unsupported capability claims
- [ ] invented connectors
- [ ] invented file paths
- [ ] unused example files
- [ ] unlinked references
- [ ] bloated control plane
- [ ] partial artifact delivery
- [ ] `agents/openai.yaml` created (use `SKILL.md` metadata + repo wiring instead)

## Packaging Readiness

- [ ] Scope is bounded.
- [ ] Source intent is preserved.
- [ ] Complexity is justified.
- [ ] Required files are present.
- [ ] Validation gates pass.
- [ ] Archive root contains exactly one Skill folder.
- [ ] Final archive can be named `skill.zip`.
