# ADR-012: Installed and runtime proof is required

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

Source inspection and CI are weak evidence for an integration rail whose
failure modes are packaging and runtime import. A repository can be internally
consistent, fully type-checked, and green in CI while the module fails to
import on the target host — which is precisely the class of failure that takes
the whole Odoo registry down.

## Options Considered

### Option A: Installed-package and real-runtime proof required (chosen)
- Pros: exercises the failure modes that actually occur — dependency
  resolution, import order, registry load; proof is reproducible.
- Cons: needs a real Odoo 19 environment and a Gate endpoint; slower than unit
  tests; may be unavailable in some execution environments.

### Option B: CI green is sufficient
- Pros: fast, always available.
- Cons: mocked SDKs and uncollected tests have both previously reported green
  against a rail that could not import. **Rejected.**

## Decision

Required release evidence includes, as applicable: clean package installation;
real Odoo module import; real Odoo 19 execution; real PostgreSQL where
persistence semantics matter; installed Gate_SDK; canonical packet
construction; Gate ingress; Gate-derived worker packet; EIE runtime validation;
canonical response; Odoo mapper.

**Rejected proxies** — these do not constitute complete runtime proof: a mocked
SDK; a mocked Odoo; unit tests only; CI green without Odoo collection; editable
package source-path substitution; `--no-deps` installation; source review; PR
merge.

## Consequences

- Where an environment cannot supply a piece of this evidence, the report must
  distinguish `PASS` from `NOT_EXECUTED`. A mock is never labelled real-runtime
  proof (ADR-015).
- A release may be locally correct and still `PROOF_PENDING`.

## Invariant

```yaml
id: INV-REAL-ODOO-GATE-PROOF
statement: >
  The canonical Odoo-to-Gate execution path must be proven using
  the installed SDK and a real supported Odoo runtime before canary.
severity: release_blocking
```
