# L9 governed analysis pipeline — IB-Odoo_19 adoption

These six files are the l9-ci-core v2 governance pack (Python preset,
unmodified from `Quantum-L9/l9-ci-core/presets/python/.github/governance/`),
plus the semgrep identity map. `.github/workflows/l9-analysis.yml` reads them
via `resolve-governance` / `validate-governance`.

**Format gotcha — these are JSON.** The resolver parses each file with
`json.loads`, so they must stay valid JSON: double-quoted keys, no comments,
no trailing commas.

## Why this exists (2026-07 adoption)

This repo already runs a custom, Odoo-aware semgrep check inline in
`ci.yml` (`.semgrep/odoo-patterns.yml`) — that stays the actual blocking
gate for Odoo-specific rules. This pipeline is additive: it runs the
generic `p/python` OWASP/security ruleset through the SDK-normalized,
governed path (canonical finding bundle → GitHub Check), which our own
inline `semgrep --error` call doesn't produce.

## Current mode: advisory-first (deliberate)

- `rule-modes.yaml` defaults `pr_fast`/`merge` to `blocking` — that's the
  *pipeline*-level mode (does the provider run at all).
- `semgrep-policy.yaml` defaults every individual finding's `mode` to
  `advisory` with an empty `rules: {}` map — no specific rule is promoted to
  blocking yet. This means `l9-analysis.yml` runs, publishes a GitHub Check
  with findings, but does **not** fail the PR on its own until specific
  `provider_rule_id`s are promoted here after review (see
  `promotion-policy.yaml`: `shadow → advisory → blocking`, min 20 runs / 7
  days observation before promotion).
- This is intentional for first adoption — do not flip individual rules to
  `blocking` without observing at least one week of PR runs first.

## `l9-ci-sdk` is never referenced directly here — by design

Neither `l9-analysis.yml` nor `baseline-ratchet.yml` has a `uses: Quantum-L9/l9-ci-sdk@...`
line anywhere in this repo, and that's expected, not a gap. `Quantum-L9/l9-ci-sdk` is an
implementation detail of `l9-ci-core`'s own composite actions (`provision-sdk`,
`invoke-sdk`, `validate-bundle`, `route-artifacts`, `build-artifact-manifest`) — those
actions resolve/download/pin the SDK internally. `baseline-ratchet.yml` passes
`sdk-revision: 0779fca8238011f8abea551895f96584676e9d17` as a caller *input* to
`l9-ci-core`'s reusable workflow (a pass-through parameter Core forwards to its own
`provision-sdk` step); `l9-analysis.yml`'s `provision-sdk` step doesn't even take an
`sdk-revision` input, so Core resolves its own default there. In both cases, `l9-ci-sdk`
is consumed *through* Core's action surface, never instantiated in this repo's own
workflow graph — consumer repos are not meant to pin or invoke it directly. If a future
Core version changes that contract (e.g. requires an explicit `sdk-revision` on every
caller), that's a breaking change to review against `l9-ci-core`'s own changelog, not
something to route around locally.

## Pin

`.github/workflows/l9-analysis.yml` pins `Quantum-L9/l9-ci-core` to
`d81a06ed821106a487df2e5ad06d93e347392af6` — the same commit
`.github/workflows/baseline-ratchet.yml` already trusts (GATE-01 adoption).
Bump both pins together; don't let them drift to different Core revisions.

## Upstream reference

`Quantum-L9/l9-ci-core/docs/templates/governance/README.md` has the full
field-by-field contract, the promotion workflow, and the Node/TypeScript
preset comparison.
