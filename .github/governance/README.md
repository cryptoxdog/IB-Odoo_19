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

## Cross-workflow concurrency (PR checks)

Wave 1 (max concurrent, fail-open collectors — start together, never
`workflow_run`-chained):

- **CI Gate** Phase 1: `lint` \| `static-checks` \| `pure-python-tests` \|
  `secret-scan` \| `audit-baseline`
- **Baseline Ratchet** collectors (reusable workflow jobs)
- **L9 Analysis** `analyze` (this pack; advisory findings)

Wave 2 (strictest last — aggregators / publish):

- **CI Gate Result** (`needs:` all Phase 1, `if: always()`)
- **Baseline Ratchet / Ratchet Verdict**
- **L9** `publish` (depends on `analyze` only; not a merge blocker while
  advisory-first)

External (not ordered by YAML): **GitGuardian Security Checks** scans the PR
commit range independently. Tip-only secret fixes do not clear GG if an earlier
PR commit still contains the secret — squash/rewrite the feature branch (never
`Staging`/`Production`) or resolve the occurrence in the GG dashboard after
rotation.

`cancel-in-progress: true` is per-workflow (own concurrency group). Stacked
pushes cancel in-flight runs; read the latest **non-cancelled** HEAD run only.
GG does not cancel GHA jobs.

## `l9-ci-sdk` is never referenced directly here — by design

Neither `l9-analysis.yml` nor `baseline-ratchet.yml` has a `uses: Quantum-L9/l9-ci-sdk@...`
line anywhere in this repo, and that's expected, not a gap. `Quantum-L9/l9-ci-sdk` is an
implementation detail of `l9-ci-core`'s own composite actions (`provision-sdk`,
`invoke-sdk`, `validate-bundle`, `route-artifacts`, `build-artifact-manifest`) — those
actions resolve/download/pin the SDK internally. `baseline-ratchet.yml` passes
`sdk-revision: 0c487747b0fcd172edaefe9e843dac818de8fc12` as a caller *input* to
`l9-ci-core`'s reusable workflow (a pass-through parameter Core forwards to its own
`provision-sdk` step); `l9-analysis.yml` provisions via Core's default, then forwards
`steps.sdk.outputs.sdk-revision` into `publish-analysis` so analyze and publish use the
same allowlisted revision. In both cases, `l9-ci-sdk` is consumed *through* Core's
action surface, never instantiated in this repo's own workflow graph — consumer repos
are not meant to pin or invoke it directly. If a future Core version changes that
contract, that's a breaking change to review against `l9-ci-core`'s own changelog, not
something to route around locally.

## Pin

`.github/workflows/l9-analysis.yml` pins `Quantum-L9/l9-ci-core` to
`3a085894895f754a4eab19a88d8449804ba805c3` — the same commit
`.github/workflows/baseline-ratchet.yml` already trusts (GATE-01 adoption).
Bump both pins together; don't let them drift to different Core revisions.
That Core SHA's `publish-analysis.yml` provisions via `provision-sdk@2989db3d…`,
whose `.l9/sdk-compatibility.yaml` allowlists the SDK revision above (fixes the
prior d81a06ed publish path that still called `provision-sdk@d2c2cd7f` and
rejected `0779fca…`).

## Upstream reference

`Quantum-L9/l9-ci-core/docs/templates/governance/README.md` has the full
field-by-field contract, the promotion workflow, and the Node/TypeScript
preset comparison.
