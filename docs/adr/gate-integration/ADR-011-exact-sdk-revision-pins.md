# ADR-011: Runtime dependencies use exact proven SDK revisions

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

Gate_SDK defines the transport contract shared by Odoo, Gate, and EIE. If those
services silently install materially different SDK revisions, they can produce
and reject each other's packets while every repository's own CI is green.

## Options Considered

### Option A: Exact commit pins, upgraded on evidence (chosen)
- Pros: reproducible; an upgrade is a reviewable event with a diff and a test
  run; the release set can be reasoned about.
- Cons: upgrades are manual and can lag.

### Option B: Track `main` / a floating branch
- Pros: always current; no upgrade toil.
- Cons: the wire contract changes without any repository changing; a Gate_SDK
  merge can break production Odoo with no Odoo commit. **Rejected.**

### Option C: Version range (`>=x,<y`)
- Pros: allows patch uptake.
- Cons: for a git-sourced transport contract this is a floating pin with extra
  steps; two services can still resolve different commits.

## Decision

Production dependencies must use exact, reproducible Gate_SDK
versions/revisions. Do not depend on `main`, `latest`, a floating git branch,
or an unbounded development revision for coordinated production behavior.

Before changing the pinned Gate_SDK revision: inspect the exact diff; run the
SDK tests; prove dependency resolution; prove installed-package behavior; prove
cross-repository packet compatibility.

## Consequences

- **Release-set rule:** Odoo, Gate, and EIE must not be assumed compatible
  merely because each installs *some* version of Gate_SDK. Compatibility must
  be executable.
- The pin's transitive constraints are part of the contract: the SDK's own
  dependency floors (for example its `cryptography` window) can crash the host
  runtime and must be resolved in the consumer's dependency set, not worked
  around at import time.
