<!--
--- SKILL_META ---
skill_schema: 1
origin: strict-skill-compiler
layer: reference
role: zero_stub_kernel
tags: [skill, zero_stub, complete_artifacts, validation, quality]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-05-31
--- /SKILL_META ---

Purpose:
Compresses complete-artifact enforcement rules so generated Skill packs do not contain dummy scaffolds, unwired resources, or partial deliverables.
-->

# Zero-Stub Build Kernel

## Purpose

Use this kernel whenever building, rebuilding, validating, or packaging Skill files.

## Hard Rules

- Produce complete files, not fragments, when full build is requested.
- Remove initializer-generated examples.
- Do not leave dummy scaffolds.
- Do not create pretend scripts.
- Do not claim unsupported tools, connectors, or paths.
- Do not leave unlinked references.
- Do not add files that are not used by the Skill.
- Do not package until validation passes.
- If a script is included, it must perform deterministic work and have a clear invocation path.
- If an asset is included, it must support final output generation.

## File Completeness Tests

A file is complete only if:

- its purpose is clear
- its metadata is present
- it has no unfinished sections
- it is linked or routed from the control plane
- it can be used without hidden context
- it does not require invented resources

## Wiring Tests

- Every reference is named in `SKILL.md`.
- Every script is named in `SKILL.md` or a linked reference.
- Every asset is named in `SKILL.md`, a linked reference, or a sidecar metadata file.
- Every folder exists for a reason.

## Validation Gates

- Required files exist.
- Metadata exists.
- References are linked.
- Scripts, if present, are deterministic.
- Assets, if present, are output materials.
- Package readiness confirmed.
