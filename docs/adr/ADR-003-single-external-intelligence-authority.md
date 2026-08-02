# ADR-003: Single External Intelligence Authority

**Status:** Accepted  
**Date:** 2026-08-02  
**Deciders:** Igor Beylin (operator PROMOTION_APPROVED — TASK-045 / M1)  
**Scope:** Matching and enrichment intelligence authority for PlasticOS Odoo  
**Contract:** PLASTICOS-MOTHBALL-M1-v2.2.0 · TASK-045 · Wave W7  
**Related:** [ADR-002](ADR-002-gate-hub-phased-autonomy.md), [GATE_AUTONOMY_ROADMAP.md](../GATE_AUTONOMY_ROADMAP.md), [ARCHITECTURE.md](../../ARCHITECTURE.md)

> **Filename collision notice (RO-P5):** This file shares the `ADR-003` numeric prefix with
> [`ADR-003-contact-import-configuration.md`](ADR-003-contact-import-configuration.md), which remains
> **Accepted** and **unchanged**. That ADR covers partner CSV import hierarchy only. This mothball
> ADR covers external intelligence authority only. Agents must cite the **full filename**, not the
> numeric prefix alone. Do not overwrite or merge the contact-import ADR.

## Context

ADR-002 established Gate as the mandatory hub and allowed **in-Odoo matching and enrichment as
architectural fallback** when Gate or workers were unavailable. M0 / TASK-046 proved live
Odoo → Gate → worker TransportPacket round-trips for `match` and `converge` (honest class:
`LIVE_TRANSPORT_ROUNDTRIP_PASS`). Wave-7 mothballing requires a successor constitutional stance:
local algorithmic engines are **temporary residue**, not authority.

Operator decision (`approved resume` / `PROMOTION_APPROVED`) authorizes this ADR under
publication ceiling `local_commit` (no push/PR/merge in this contract).

## Decision

### 1. Single external intelligence authority

For buyer matching and partner enrichment intelligence:

| Concern | Authority |
|---------|-----------|
| Matching semantics / scoring | Cognitive.Engine.Graphs (CEG), reached only via Gate |
| Enrichment / converge intelligence | Enrichment.Inference.Engine (EIE), reached only via Gate |
| Transport + hub routing | Gate_SDK `TransportPacket` + Constellation.Gate |
| Odoo role | Gate **consumer** only — when to call, how to map allowlisted CRM fields, audit/UX |

Odoo **must not** treat `plasticos_buyer_match_engine`, local Neo4j matcher paths, or
`plasticos_enrichment` crawl/extract/inference pipelines as the architectural source of truth
for match quality or enrichment intelligence.

### 2. Supersedes ADR-002 §2 (fallback-as-authority)

This ADR **supersedes** ADR-002 §2 (“Odoo local engines are fallback — not the primary path”)
**as architectural authority**. Gate-hub topology, Phase human checkpoints, and “never
Odoo → CEG/EIE direct” from ADR-002 remain binding.

Local engines were **physically retired in M7** (TASK-051): `plasticos_buyer_match_engine` and
`plasticos_inference_engine` source trees are absent from the repository. They must not be cited
as product matching/enrichment design and must not be reintroduced.

- Failures must surface as **classified Gate/worker failures** (or explicit degraded-mode
  policy), not as restoration of local engines as authority.
- M8 (TASK-052) activates **blocking** drift guards in Makefile, pre-commit, CI, and
  `scripts/check_odoo_patterns.sh` via `ci/check_no_local_intelligence.py`.

M2–M6 removed local *authority*; M7 removed local engine *source directories* (verified backup +
restore rehearsal per TASK-050); M8 makes absence + consumer-path drift **blocking** in CI.

### 3. Gate-only egress for intelligence

Unchanged hard rule, restated for agents:

```
Odoo  ──TransportPacket──►  Gate  ──►  CEG / EIE
Odoo  ◄──TransportPacket──  Gate  ◄──
```

- Sole Odoo SDK import seam: `plasticos_gate`.
- Forbidden: direct Odoo → CEG/EIE HTTP or SDK bypass of Gate.
- Web-lead triage remains Odoo-local until a later Phase-3 ADR/roadmap promotion (unchanged).

### 4. Ownership boundaries (unchanged from ADR-002 amendment)

- Gate_SDK / Constellation.Gate / CEG / EIE own their contracts.
- Odoo owns CRM persistence, allowlists, merge-not-overwrite, provenance, and operator UX.

## Consequences

### Positive

- Constitutional docs align with mothball Wave-7: Gate-mediated CEG/EIE is the intelligence authority.
- Clears the path for M2–M6 extraction without re-debating “fallback as design.”
- Preserves contact-import ADR-003 under a distinct filename.

### Negative / constraints

- Docs and residual runtime diverge until M2+ lands — agents must not “fix” that by re-elevating
  local engines as authority.
- ADR numeric prefix collision requires full-path citations forever (or a future renumbering
  ADR outside this contract’s hard-locked path).

### Implementation rules (agents)

1. Cite this ADR (full path) for matching/enrichment **authority**; cite ADR-002 for hub topology
   and phased human checkpoints unless a later ADR supersedes those sections.
2. Do not add direct CEG/EIE calls or second SDK import sites.
3. Do not reintroduce `plasticos_buyer_match_engine` or `plasticos_inference_engine` (M7 retired; M8 guards block).
4. Do not overwrite `ADR-003-contact-import-configuration.md`.



## Retirement evidence (M6–M8)

Wave-7/10 mothball repository evidence (controller ledger under `l9-constellation-control`):

| Phase | Task | Gate | Proof class |
|-------|------|------|-------------|
| M0 | TASK-046 | live transport | `LIVE_TRANSPORT_ROUNDTRIP_PASS` (not full LIVE_INTEGRATION_PASS) |
| M1 | TASK-045 | GATE-047 | `REPOSITORY_TEST_PASS` + PROMOTION_APPROVED |
| M2 | TASK-047 | GATE-051 | `REPOSITORY_TEST_PASS` |
| M3 | TASK-048 | GATE-050 | `REPOSITORY_TEST_PASS` |
| M4 | TASK-049 | GATE-052 | `REPOSITORY_TEST_PASS` |
| M5 | TASK-050 | GATE-053 | `REPOSITORY_TEST_PASS` + A4 + restore-rehearsal receipt |
| M6 | TASK-068 | GATE-056 | `REPOSITORY_TEST_PASS` (constitutional seal) |
| M7 | TASK-051 | GATE-055 | `REPOSITORY_TEST_PASS` — physical module deletion |
| M8 | TASK-052 | GATE-066 | `REPOSITORY_TEST_PASS` — **blocking** drift guards activated |

Drift scanner: `ci/check_no_local_intelligence.py` — **blocking** in CI (`run_check`), pre-commit,
Makefile (`make no-local-intelligence`, `make audit`), and `scripts/check_odoo_patterns.sh`.
Retired module trees must stay absent; consumer-path authority drift fails the build.

## Observation criteria

Production completion of physical retirement is **not** claimed from repository tests alone.
Operators must observe:

1. Enrichment crons remain `active=False` in deployed DBs.
2. Match/enrichment runs show `engine=gate` (or equivalent) with classified degraded/retry states — never silent local scoring.
3. Drift scanner stays green for consumer paths; residue reports shrink only after approved uninstall.
4. No direct Odoo → CEG/EIE egress; sole seam remains `plasticos_gate`.
5. Backup/restore rehearsal evidence exists before any destructive uninstall (`TASK-050-restore-rehearsal`).

Until those observations are recorded for a given environment, mothball status is
**repository_validated**, not production-complete.

## References

- Prerequisite proof: TASK-046 control evidence (Wave-7 ledger)
- Consumer wiring: [`docs/track_b/04_odoo_gate_consumer_wiring.md`](../track_b/04_odoo_gate_consumer_wiring.md)
- Readiness (M0): [`docs/track_b/05_external_authority_readiness.md`](../track_b/05_external_authority_readiness.md)
- External repos: Constellation.Gate, Cognitive.Engine.Graphs, Enrichment.Inference.Engine, Gate_SDK
