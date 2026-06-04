<!--
--- SKILL_META ---
skill_schema: 1
origin: strict-skill-compiler
layer: reference
role: output_contract
tags: [skill, outputs, modes, response_contract]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-05-31
--- /SKILL_META ---

Purpose:
Defines output contracts for discuss, design, analyze, build, rebuild, and package modes.
-->

# Output Modes

## Purpose

Use this file to select the right response shape for the user's request.

## Mode Selection

| User intent | Mode |
|---|---|
| asks whether a Skill is worth building | discuss |
| asks for architecture before files | design |
| asks to review an existing Skill | analyze |
| asks to create full contents | build |
| asks to improve or replace an existing Skill | rebuild |
| asks for distributable archive | package |

## Discuss Mode

Return:

- direct recommendation
- tradeoffs
- next action

Keep it short. Do not produce file contents unless requested.

## Design Mode

Return:

- objective
- skill concept
- trigger description
- file plan
- resource map
- validation plan

Do not create files unless requested.

## Analyze Mode

Return:

- strengths
- gaps
- duplication
- trigger quality
- structure risks
- resource misuse
- recommended edits

Prioritize edits by functional impact.

## Build Mode

Return:

- complete folder tree
- complete file contents
- validation checklist with status
- packaging command when packaging is requested or useful

Do not return partial files when full build is requested.

## Rebuild Mode

Return:

- old versus new gap analysis
- revised structure
- revised file contents or archive
- migration notes
- validation checklist

Preserve source intent unless the user explicitly changes it.

## Package Mode

Return:

- `skill.zip`
- manifest
- validation status

Package only after validation passes.

## Next Prompt Discipline

When a next prompt would reduce turns or preserve momentum, provide exactly one highest-leverage next prompt or next action. Do not provide a menu unless the user asks for options.

## Formatting Rules

- Prefer compact sections.
- Prefer YAML for specs and validation status.
- Label assumptions and unknowns.
- Do not include commentary inside artifact files unless it is part of the file contract.
- Keep final responses decision-ready.
