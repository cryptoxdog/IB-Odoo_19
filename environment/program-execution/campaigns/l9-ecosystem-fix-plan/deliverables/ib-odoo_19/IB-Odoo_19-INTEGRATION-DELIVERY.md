# IB-Odoo_19 Integration Delivery — l9-ecosystem-fix campaign

**Target:** `cryptoxdog/IB-Odoo_19` · **Status:** remaining live work (v1.1.0).
Execute from `origin/Staging` when the operator says run. This file is the
TASK-004 / TASK-006 design. **Not applied.**

TASK-002 (writeback default) is specified in `CAMPAIGN_SOURCE.yaml`. Closed
EIE / CEG / Gate / PR #141 work lives in `history/v1.0.0/` and is not in
this campaign anymore.

- **TASK-004** — Wave 3 match mapper contract break (`results` → `candidates`) +
  DEC-001 identity mapping.
- **TASK-006** — Wave 5 converge request/response mapping (Odoo ⇄ EIE).

Reference implementations (drop-in, adapt imports to the Odoo module):
- `reference/plasticos_ceg_match_mapper.py`
- `reference/plasticos_eie_converge_mapper.py`

---

## 1. DEC-001 — candidate identity (ACCEPTED → OPTION-B)

**Decision:** CEG `candidate.entity_ref` is a **namespaced `<model>:<id>` key**
matching `^[a-z0-9_.-]+:[^\s]+$` — for Odoo buyers, `res.partner:<int>`
(e.g. `res.partner:102`). It **embeds** the `res.partner` integer but is
namespaced and tied to a `SourceRecord{system:odoo, record_ref}` mapping. It is
**NOT** a bare `res.partner` id (OPTION-A) and **NOT** a Neo4j-native node id.

**Odoo consequence:** map to `buyer_partner_id` via an **explicit resolver** that
parses the ref and accepts **only** the `res.partner` model — any other namespace
fails safe (no cross-model mis-attribution). See `resolve_buyer_partner_id()`.

**Evidence (CEG `engine/models/payloads.py`):** `ENTITY_REF_PATTERN` (l.50-51),
`MatchCandidate.entity_ref` (l.164-166), `SourceRecord{system,record_ref}`
(l.262-266); fixture `contracts/payloads/examples/match-response.json`
(`"res.partner:102"`).

> ⚠️ Residual (documented in CEG PR #195 / ADR): the **live** CEG match handler
> currently keys candidates on a bare `entity_id` node property
> (`engine/handlers.py:509,616,1497`), client-supplied at sync, **not**
> schema-defined. Until the live path is reconciled to emit the contract
> `entity_ref`, confirm which form your CEG deployment actually returns and
> adjust `resolve_buyer_partner_id()` accordingly. The resolver already fails
> safe on a bare integer (no `<model>:` prefix → skipped, never mis-mapped).

---

## 2. TASK-004 — CEG match response → Odoo buyer-match records

**The break:** the prior Odoo mapper read `payload.get("results")`. The live CEG
`/v1/execute` match response returns rows under **`candidates`** — so every
candidate was silently dropped. Fix: read `payload.get("candidates")`.

### Field mapping (CEG `MatchCandidate` → Odoo buyer-match)

| CEG contract field | Odoo target | Notes |
|---|---|---|
| `entity_ref` (`res.partner:<int>`) | `buyer_partner_id` (int) | via `resolve_buyer_partner_id()` (DEC-001) |
| `score` + `score_scale` | `normalized_score` (0–1) | `0_to_1` as-is; `0_to_100`÷100; `unnormalized_declared` left raw |
| `eligible` | `eligible` | ineligible candidates never carry a rank (contract invariant) |
| `rank` | `rank` | |
| `explanation` | `explanation` | |
| `failed_gates[]` / `feature_contributions[]` / `missing_evidence[]` | carried through | for review UI |
| response `query_id`, `direction`, `total_candidates`, `execution_time_ms`, `domain_spec_version`, `model_version`, `projection_version`, `contract_version`, `domain` | preserved verbatim | lineage |

**Do NOT** add `packet_id`/`correlation_id`/`meta` to the payload mapping — those
are transport-forbidden on CEG payloads; they live on the chassis envelope.

### VAL-004 acceptance (frozen-fixture test) — assert:
1. candidates are **not dropped** (reads `candidates`);
2. buyer ids map correctly **per DEC-001** (`res.partner:102` → `102`);
3. scores **normalize** to [0,1] per `score_scale`;
4. output **sorted descending** by normalized score;
5. a missing/invalid `entity_ref` **fails safe** (lands in `unresolved`, never a
   wrong `res.partner`).

Use the canonical CEG fixture `contracts/match_response.json` (shipped in CEG
PR #195) as the frozen input.

---

## 3. TASK-006 — Odoo ⇄ EIE converge mapping

EIE owns the `converge` action (`POST /v1/execute`). Request = `EnrichRequest`,
response = `EnrichResponse` (EIE `app/models/schemas.py`).

### Request: Odoo → EIE `EnrichRequest`

| Odoo field | EIE `EnrichRequest` | Notes |
|---|---|---|
| `entity_snapshot` | `entity` (dict, required) | Odoo `entity_id` preserved inside `entity._odoo_entity_id` (context, not a Gate transform) |
| `domain` / type | `object_type` (str, required) | |
| `objective` | `objective` (str, required) | defaults to "Full entity enrichment and inference" |
| `max_passes` | `max_variations` | **clamped 1..10** (EIE constraint) |
| `kb_context` | `kb_context` | optional — include only if provided |
| `idempotency_key` | `idempotency_key` | optional |

### Response: EIE `EnrichResponse` → Odoo (no field loss)

Carry through **all** EnrichResponse fields (`fields`, `confidence`, `state`,
`failure_reason`, `quality_tier`, `variation_count`, `pass_count`,
`consensus_threshold`, `uncertainty_score`, `processing_time_ms`,
`inference_version`, `kb_content_hash`, `kb_files_consulted`, `kb_fragment_ids`,
`inferences`, `grade_matches`, `enrichment_payload`, `feature_vector`,
`tokens_used`).

**DNB-006 (hard rule):** EnrichResponse has **no `total_cost_usd`** and converge
performs **no writeback**. The mapper marks both **explicitly UNAVAILABLE
(`None`)** — never fabricated. Cost is `tokens_used` only.

### VAL-006 acceptance — assert against a frozen/real EIE response:
- no `total_cost_usd` or writeback field is fabricated;
- no response field is lost on mapping.

Use the canonical EIE fixtures `contracts/converge_request.json` /
`converge_response.json` (shipped in EIE PR #166) as frozen I/O.

---

## 4. How to apply (only when the operator says run)

See `../../EXECUTION_FROM_ODOO.md`. Bind a fresh worktree from `origin/Staging`.
Do not use the constellation `fix/install-smoke-runtime-gate` clone.

Place the two reference mappers under `plasticos_gate`, adapt imports, then:

- replace `payload.get("results")` with `map_match_response()` / `candidates`
- wire converge request/response through the converge mapper
- add frozen-fixture tests using CEG #195 + EIE #166 canonical fixtures
- flip `plasticos.gate.auto_writeback` default to `0` (TASK-002 remainder)

L4 local commits only. Publish with `PR_REMEDIATE=0 make pr` against
`campaign/l9-ecosystem-fix-plan`. No merge from the controller.

---

## 5. Remaining campaign work

- TASK-002 writeback default.
- These mappers (TASK-004 / TASK-006).
- TASK-007 Wave-6 round-trips after those three land.

Companion artifacts: `../../handoff/CAMPAIGN_HANDOFF.md`,
`../../handoff/handoff.json`. Frozen fixtures: CEG `contracts/match_response.json`,
EIE `contracts/converge_*.json`.
