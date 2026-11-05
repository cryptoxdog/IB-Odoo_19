# FINAL_FINDINGS.md — IB-Odoo_19 shadow-SDK elimination

Execution report for the Claude Code execution contract *"Eliminate Shadow Gate
SDK / Make Gate_SDK the Transport Authority"*, evaluated at the exact final
HEAD below. Findings describe what is in the tree, not what was intended.

---

# Executive Verdict

The Odoo → Gate rail is a Gate_SDK **consumer** in every respect the SDK's
public API permits. All Odoo-owned transport *policy* found at the start of
this work has been removed: the substring-based transport error taxonomy, the
payload-digest replay identity, and the Odoo-chosen packet destination and
classification. One boundary remains, and it is not removable from inside this
repository.

**Gate_SDK exposes no application-facing execute operation.** Its only outbound
surface is `GateClient.send_to_gate(packet)`, which *requires the caller to
pre-build a `TransportPacket`*. `create_transport_packet` therefore still runs
inside Odoo. Under ADR-016 that single fact means
`manual_packet_creation_in_odoo` cannot be reported `false`, and the honest
verdict is `PARTIALLY_ELIMINATED` / `BLOCKED_EXTERNAL_SDK_CAPABILITY` — not
"eliminated", and not "mostly".

This was verified against the SDK at Odoo's pinned commit **and** at current
`Gate_SDK` `main`; their `src/` trees are byte-identical, so no SDK bump can
close the gap. The exact minimal external delta is specified under **External
SDK Capability Gaps**.

Three of the four fractures the contract's prior audit reported (§5A, §5B,
§5D) **did not reproduce** against this checkout and required no repair. They
are documented below rather than silently dropped.

---

# Repository / Branch / Final HEAD

| Field | Value |
|---|---|
| Repository | `cryptoxdog/IB-Odoo_19` |
| Authoritative branch | `Staging` |
| Working branch | `claude/ib-odoo-adr-gate-integration-ys0t8u` |
| Base HEAD (start) | `ce8ff00a51fffc73119160df99a9bca9af39b6c6` |
| **Final code HEAD** | **`828e4b372b4b6aa11c82b0c4315c581759282c00`** |

`828e4b3` is the last commit carrying source, test, or ADR changes, and is the
tree every finding and every test result below was measured against. This
report is committed on top of it: a report cannot record the hash of the commit
that introduces it, so the code HEAD is the meaningful anchor and is stated
rather than approximated.
| Python (analysis tier) | 3.11.15 |
| Python (SDK/runtime tier) | 3.12.3 — the SDK requires `>=3.12` |
| Odoo version target | 19 |

---

# Gate_SDK Version Used

| Field | Value |
|---|---|
| Pinned in `requirements.txt` | `92279da4c01d3cb9be806c60690c21d736103826` |
| `Gate_SDK` `main` at analysis time | `d09fe58a6cd68ef8aa883896c68badc95f96e090` |
| `git diff <pin>..main -- src/` | **empty** — public API identical |
| Installed distribution | `constellation-node-sdk` 1.0.1 |
| Install provenance | `direct_url.json` → `commit_id: 92279da4…` (exact pin verified) |

The pin was **not** changed. Nothing in `main` supplies the missing capability,
so a bump would add risk and buy nothing (pack ADR-011).

Public API surface actually used by Odoo:

- `constellation_node_sdk.GateClient`
- `constellation_node_sdk.GateClientConfig`
- `constellation_node_sdk.create_transport_packet`
- `constellation_node_sdk.TransportError` (exception classification only)

---

# Initial Shadow-SDK Inventory

Repository-wide classification of every transport symbol in production code
(tests, docs and CI tooling excluded).

| Classification | Findings |
|---|---|
| `SDK_PUBLIC_API` | `gate_client.py` — `GateClient`, `create_transport_packet`; `gate_config.py` — `GateClientConfig` |
| `ODOO_CONFIGURATION` | `gate_config.py` — Gate URL, local node, org id, timeout budget, capability flags |
| `ODOO_DOMAIN` | `gate_builders.py` (request building), `gate_mappers.py` (response mapping), `gate_contracts.py` (internal dataclasses), `gate_allowlists.py` (writeback allowlist) |
| `SHADOW_SDK` | **3 findings** — see *Deleted Shadow Responsibilities* |
| `TEST_ONLY` | Gate tests under `tests/` and `plasticos_enrichment/tests/` |
| `STALE_DEAD_CODE` | 1 finding — see *Remaining Non-Blocking Defects* |
| `DOCUMENTATION` | `semantic_payloads.py` `_TRANSPORT_FORBIDDEN` — a **denylist** that keeps transport fields out of semantic payloads; the inverse of a shadow SDK, retained deliberately |

Structural facts at start, all still true at final HEAD:

- `/v1/execute` in Odoo production code: **0**
- Odoo-owned HTTP to Gate: **0**
- Manual transport hashing / signing / validation: **0**
- Peer (EIE) URLs, hostnames or ports: **0**
- Odoo transport retry loops: **0**
- SDK import sites: **2**, both inside `plasticos_gate/services/`

## The contract's prior audit, reproduced

The contract (§5) instructed reproduction rather than acceptance. Result:

| §5 | Claim | Verdict |
|---|---|---|
| A | `build_idempotency_key` called but not defined | **Did not reproduce.** Defined at `gate_builders.py`; imported and called correctly. |
| B | `send_converge_action` does not accept `idempotency_key` | **Did not reproduce.** The parameter exists and is threaded to the packet. |
| C | Manual packet assembly with Odoo-populated transport concerns | **Reproduced.** Repaired as far as the SDK allows; residue is SDK-GAP-1. |
| D | `_odoo_entity_id` set without canonical `entity.id` | **Did not reproduce.** Both are set to the same value at `gate_builders.py`. |

---

# Deleted Shadow Responsibilities

### 1. Substring-based transport error taxonomy — **removed**

`classify_transport_failure` scanned `str(exc)` against `_RETRYABLE_TOKENS` /
`_PERMANENT_TOKENS` (`"502"`, `"timeout"`, `"401"`, …). Both tables are gone.
Classification is now structural: HTTP status carried on the exception, SDK
`TransportError` types, httpx connection/timeout types, and `ValueError` for
pre-send Gate policy violations and malformed canonical responses.

Two defects the old approach carried, both now closed:

- it misclassified any message that merely *mentioned* a status code;
- it could not classify httpx timeouts at all — those stringify to empty, and a
  timeout is the single most likely real Gate failure.

### 2. Payload-digest replay identity — **removed**

`build_idempotency_key(payload, odoo_ctx)` mixed a SHA-256 digest of the
serialized payload into the transport key. Replaced by
`build_operation_id(odoo_ctx)`, keyed only on durable run identity. It takes no
payload parameter at all, which makes the ADR-006 property structural rather
than merely observed.

### 3. Odoo-chosen packet destination and classification — **removed**

`create_transport_packet(..., destination_node="gate", classification="internal")`
restated values the SDK already defaults, while `GateClientConfig(allowed_gate_destination="gate")`
and `validate_outbound_gate_packet` already *enforce* Gate-only egress. Odoo
naming the destination was routing policy in domain code. Both arguments are
deleted; the SDK's defaults and its validator now carry the invariant, and a
test asserts Odoo does not name a destination.

---

# Remaining Odoo Gate Responsibilities

All domain or configuration; none transport policy.

| Responsibility | Location |
|---|---|
| Gate URL, local node, org id, capability flags, caller budget | `gate_config.py` |
| Odoo → `EnrichRequest` / `MatchRequest` mapping | `gate_builders.py` |
| Canonical `entity.id` construction | `gate_builders.py` |
| Logical operation identity (ADR-006) | `gate_builders.build_operation_id` |
| Async→sync bridging for Odoo workers | `gate_client._run_async` |
| One SDK invocation call | `gate_client.send_action` |
| SDK exception → Odoo operator category | `gate_client.classify_transport_failure` |
| `EnrichResponse` → Odoo proposal | `gate_mappers.py` |
| Writeback allowlist, merge-not-overwrite, review state | `gate_allowlists.py`, `enrichment_run.py` |

---

# Gate_SDK-Owned Responsibilities

`TransportPacket` model and construction; packet defaults; transport hashing and
integrity; signing and signature verification; outbound and inbound packet
validation; Gate-only destination enforcement; hop, lineage and provenance
mechanics; correlation and causation mechanics; the idempotency header
representation; HTTP execution to Gate; HTTP timeout implementation; response
decoding and validation; transport error types.

Verified executably, not by reading: `test_transport_integrity_is_computed_by_the_sdk`
recomputes `compute_transport_hash(packet)` with the installed SDK and asserts
it equals the packet's own `security.transport_hash`, while asserting the bridge
source contains no hashing or signing call.

---

# Canonical EnrichRequest Contract

Emitted by `build_converge_request`:

```json
{
  "entity": { "id": "res.partner:<id>", "_odoo_entity_id": "res.partner:<id>", "...": "allowlisted snapshot" },
  "object_type": "plasticos",
  "objective": "Full entity enrichment and inference",
  "max_variations": 5,
  "kb_context": "plasticos",
  "idempotency_key": "odoo:enrichment:<db>:plasticos.enrichment.run:<id>",
  "odoo": { "model": "...", "record_id": 0, "company_id": 0, "user_id": 0, "db_name": "...", "correlation_id": "..." }
}
```

The rejected dialect (`entity_snapshot`, top-level `entity_id`, `status`,
`final_fields`, `writeback`) is **absent**, and a negative test asserts it stays
absent.

Response consumption reads canonical `state` and `fields`. `ConvergeResponse`
exposes an internal `status` **derived** from `state` + `failure_reason` and an
internal `final_fields` aliasing canonical `fields`. Both are Odoo-internal
dataclass attributes read from the canonical wire — permitted by contract §7,
and explicitly not a second external contract.

---

# Canonical Identity

`entity.id = "res.partner:<database-id>"`, with `_odoo_entity_id` carrying the
identical value as compatibility metadata. Not derived from name, email, phone,
payload hash, or any mutable CRM content.

---

# Logical Idempotency State

One identity, generated once, reaching both replay boundaries:

```
odoo:enrichment:<db_name>:<model>:<record_id>
```

`build_converge_request` generates it and sets it on the request; it rides in
the canonical `EnrichRequest.idempotency_key` field (an EIE-owned field, so
this is domain propagation rather than a new dialect); `enrichment_run` passes
`request.idempotency_key` to the transport header. The consumer derives no
second value, and a test asserts it cannot.

Behaviour matrix, all covered by tests:

| Situation | Result |
|---|---|
| same durable run, retried | same id |
| same partner, new run | different id |
| different partner | different id |
| different database | different id |
| repeated calls | byte-identical (no clock, no randomness) |
| unknown run identity | `None` — un-keyed, never guessed |

**Accepted consequence, stated plainly.** The prior digest-based key made a
retry-after-edit a *different* operation, which prevented a deduplicating
downstream from serving an earlier answer for changed input. ADR-006 knowingly
trades that away: a durable run is the unit of business identity, so retrying
one is the same operation, and an operator needing a materially new request
creates a new run. This is a deliberate behaviour change, not an oversight —
recorded here because it is the one place this work changes runtime semantics
rather than ownership.

---

# Timeout State

One validated budget. `resolve_gate_timeout_seconds` enforces
`0 < timeout <= 30.0`, rejecting out-of-range values rather than clamping.
`build_gate_client_config` puts it on `GateClientConfig.timeout_seconds`, which
bounds the real HTTP call; the packet's advertised `timeout_ms` is derived from
that same object.

`test_caller_budget_reaches_the_packet_and_the_client_config` asserts the
equality against a real packet built by the installed SDK — not a source
assertion.

Restating `timeout_ms` at the call site is SDK-GAP-3: the SDK hardcodes 30000
and does not derive the packet budget from the client config.

---

# Retry State

No Odoo transport retry layer. No `tenacity`, no `backoff`, no retry loop, no
`max_retries` around a Gate call — asserted by
`test_odoo_wraps_gate_in_no_retry_layer`.

`action_retry_enrichment` is an explicit operator action on a durable run, which
ADR-008 permits. Under ADR-006 it now reuses the run's operation identity, so it
is a replay of one operation rather than a new one.

---

# Matching Consumer State

`send_match_action` and `send_converge_action` both delegate to the single
`send_action` core. `test_gate_consumers_share_one_invocation_surface` enforces
this structurally, and `test_only_one_module_builds_gate_packets` asserts
exactly one module in the tree calls `create_transport_packet`.

Matching and enrichment differ in domain payload and action, as intended; they
share one transport implementation. Matching does not currently supply an
operation identity — its replay semantics live in `match_run` lineage and are
out of this contract's scope; noted, not changed.

---

# Enrichment Consumer State

`enrichment_run._run_gate_converge` builds the request, hands
`request.idempotency_key` to the transport, maps the canonical response, and
fails closed on any non-`ok` derived status. Auto-writeback stays off by
default: the proposal is stored `state='review'` with provenance and no partner
write until an operator enables it.

---

# Response Mapping

`map_converge_response` reads canonical `state`, `fields`, `failure_reason` and
carries every `EnrichResponse` field through without loss. `total_cost_usd` and
`writeback_applied` stay explicitly `None` — `EnrichResponse` has no such
fields, and fabricating them was correctly refused. Only an explicit `completed`
state with no `failure_reason` yields `status == "ok"`; a missing or partial
state never manufactures success (pack ADR-015).

---

# Writeback Safety

Unchanged by this work, and re-verified: allowlisted fields only; blank fields
may be populated; populated fields are preserved (merge-not-overwrite);
non-allowlisted fields are never written automatically; provenance is recorded;
auto-writeback is off by default.

---

# Dependency / Installation Evidence

No `--no-deps`, no editable install, no `PYTHONPATH` substitution.

| Evidence | Result |
|---|---|
| Clean venv (Python 3.12) + `requirements.txt` + `constraints.txt` | **PASS** — full set resolved |
| Installed SDK commit matches the pin | **PASS** — `direct_url.json` → `92279da4…` |
| `import constellation_node_sdk` | **PASS** |
| `cryptography` / `pyOpenSSL` pair | **PASS** — 43.0.3 / 24.3.0, `OpenSSL.crypto` imports cleanly (the Odoo.sh registry-crash pin holds) |
| `httpx` | 0.28.1 |
| Boundary + contract + invocation suites in that environment | **PASS** — 77 passed |

The SDK requires Python `>= 3.12`; a 3.11 interpreter cannot install it. The
repository's pure-Python CI tier therefore skips the SDK-dependent module by
mark rather than failing.

---

# Tests Actually Executed

| Suite | Interpreter | Result |
|---|---|---|
| Full `tests/` | 3.11, SDK absent | **531 passed, 18 skipped** |
| Full `tests/` | 3.12 + installed pinned SDK | **540 passed, 9 skipped** |
| Gate boundary + contract + SDK invocation | 3.12, full `requirements.txt` env | **77 passed** |
| `ruff check` (0.16.0, repo `required-version`) | 3.11 | **All checks passed** |
| `ruff format --check` | 3.11 | **126 files already formatted** |
| `mypy` on changed modules | 3.11 | **Success: no issues found** |
| `scripts/check_module_wiring.py` | 3.11 | **PASS** — 30 modules |
| `ci/check_circular_deps.py` | 3.11 | **PASS** |
| `ci/check_odoo19_xml.py` | 3.11 | **PASS** |
| `ci/check_odoo_antipatterns.py` | 3.11 | **PASS** |
| `ci/check_orphan_model_refs.py` | 3.11 | **PASS** |

New tests added: 9 SDK-invocation tests, 7 boundary guards, 9 ADR-006 identity
tests, 2 SDK-ownership tests, 2 structural classification tests.

Tests removed or rewritten because they encoded the rejected architecture
(contract §14) — 4 in total:

| Test | Why it was wrong |
|---|---|
| `test_destination_node_is_gate` | Required Odoo to *set* the destination — made routing policy in domain code a requirement. Replaced by the inverse assertion plus a config-pin assertion. |
| `test_idempotency_key_differs_when_the_payload_changed` | Encoded ADR-006's rejected Option B. Replaced by a signature test proving the identity cannot depend on the payload. |
| `test_idempotency_digest_is_128_bits…` / `…is_a_sha256_prefix` / `…ignores_dict_insertion_order` | Pinned a digest that no longer exists. |
| `test_transport_failure_classification` | Asserted `RuntimeError("401 unauthorized")` → PERMANENT, which held only because the classifier scanned the message. Replaced by structural status/type assertions plus a guard that the classifier never reads the message. |

One further test was deleted rather than replaced: the old
`test_packet_is_built_by_the_sdk_with_the_canonical_action` hand-rebuilt the
`create_transport_packet` argument list, so it duplicated the adapter's own code
and could not detect the adapter drifting from it. Its role is now filled by
`tests/test_gate_sdk_invocation.py`, which drives the real adapter.

---

# Real Odoo Runtime Evidence

**NOT_EXECUTED.** No Odoo 19 installation is present in this environment
(`import odoo` fails; no `odoo-bin`; PostgreSQL is present but unused). Per
ADR-012 this is reported as not executed rather than substituted with a mock.

What *was* proven without Odoo: the Gate services are pure Python and were
exercised directly against the installed SDK with a minimal `env` stand-in that
supplies only `ir.config_parameter`, `cr.dbname` and `user.id` — the three
things the adapter actually reads. That is genuine SDK-boundary proof and is
**not** a substitute for module import under a real registry.

Required before canary: `make install-smoke` / `make test-odoo` against Odoo 19
with `plasticos_gate` and `plasticos_enrichment` installed, and one real
enrichment run through the SDK boundary.

---

# Real Gate Runtime Evidence

**NOT_EXECUTED.** `tests/integration/test_gate_external_authority_e2e.py` is a
live harness gated on `PLASTICOS_GATE_LIVE_URL`; no live five-service stack is
reachable from this environment. The harness is present and unmodified.

```
local_runtime:     PASS (installed SDK, adapter boundary)
real_odoo_runtime: NOT_EXECUTED
real_gate_runtime: NOT_EXECUTED
```

No mock in this work is labelled real-runtime proof.

---

# Scope Drift Audit

Changed: `plasticos_gate/services/gate_client.py`,
`plasticos_gate/services/gate_builders.py`,
`plasticos_enrichment/models/enrichment_run.py`, four test modules, and the ADR
pack. Nothing else.

Explicitly **not** done, each because the contract forbids it (§16/§17):

- No EIE contract change, no queue, outbox, scheduler or orchestration layer.
- No new SDK wrapper, no `OdooGateTransport`/`PacketFactory` by any name.
- No SDK pin bump (nothing in `main` closes the gap; a bump would add risk for
  no benefit).
- No writeback semantic change.
- No spread into unrelated CRM modules. In particular, the boundary guard for
  manual HTTP is scoped to Gate rather than to all outbound HTTP: the
  VanillaSoft adapter, the LLM endpoint in `enrichment_service.py`, and lead
  image fetches are legitimate non-constellation calls. A guard failing on
  those would have pushed a shadow-SDK removal into modules it has no business
  touching.

---

# Remaining Blocking Defects

**One**, and it is external.

`manual_packet_creation_in_odoo` is `true` and cannot be made `false` from this
repository. `GateClient.send_to_gate` accepts only a pre-built `TransportPacket`,
so `create_transport_packet` must run in Odoo. Per ADR-013 no local workaround
was written; per ADR-016 the close condition is therefore not satisfied.

The call is held to the minimum the SDK forces. Every remaining argument is a
business input Odoo legitimately owns (`action`, `payload`, `tenant`,
`correlation_id`, `compliance_tags`, `idempotency_key`) or local node identity
from Odoo config (`source_node`, `reply_to`) — except `timeout_ms`, which is
SDK-GAP-3.

---

# Remaining Non-Blocking Defects

1. **Unreachable code in `enrichment_service.crawl_source`** — the function
   raises `UserError` unconditionally (mothball M4), leaving ~30 lines of dead
   crawl logic after the `raise`. Pre-existing, harmless, and outside this
   contract's scope; removing it would widen the diff into unrelated enrichment
   code. Recorded, not fixed.
2. **`_odoo_entity_id` compatibility alias** — retained per ADR-005. Retire once
   no consumer reads it; requires a cross-repository check first.
3. **Matching carries no logical operation identity** — see *Matching Consumer
   State*. Out of scope; noted for a future decision.

---

# External SDK Capability Gaps

Three, in priority order. **SDK-GAP-1 alone determines the verdict.**

### SDK-GAP-1 — no application-facing execute (blocking)

*Present at both the pinned commit and `main`.* The SDK's only outbound surface
requires callers to construct transport objects.

Smallest sufficient delta — one method on `GateClient`:

```python
async def execute(
    self,
    *,
    action: str,
    payload: dict[str, Any],
    tenant: str | dict[str, Any] | TenantContext,
    idempotency_key: str | None = None,
    correlation_id: str | None = None,
    compliance_tags: tuple[str, ...] = (),
) -> TransportPacket:
    """Build, sign, validate, send, and validate the response — one call.

    source_node / reply_to come from self._config.local_node.
    destination_node comes from self._config.allowed_gate_destination.
    timeout_ms is derived from self._config.timeout_seconds.
    """
```

It needs no new transport primitive — only the composition of
`create_transport_packet` and `send_to_gate` that every consumer currently
writes by hand. Consumers keep supplying business inputs and stop supplying
transport arguments entirely.

On release, Odoo deletes its `create_transport_packet` call and SDK-GAP-3 closes
with it; `manual_packet_creation_in_odoo` and
`manual_transport_timeout_implementation_in_odoo` both become `false`, and the
verdict moves to `ELIMINATED`.

### SDK-GAP-2 — httpx exceptions leak through the public API (non-blocking)

`send_to_gate` propagates `httpx` exceptions unwrapped, and
`validate_outbound_gate_packet` raises bare `ValueError`. Consumers cannot
classify a transport failure without naming the SDK's HTTP library. Odoo's
classifier therefore imports `httpx` for its exception *types* — it opens no
socket, but the coupling is real and belongs to the SDK.

Delta: wrap transport faults in SDK-owned types (e.g.
`TransportConnectionError`, `TransportTimeoutError`, `TransportRemoteError`
carrying `status_code`), and raise a typed policy error from
`validate_outbound_gate_packet` instead of `ValueError`.

### SDK-GAP-3 — packet timeout not derived from client config (non-blocking)

`create_transport_packet` hardcodes `timeout_ms=30000` and has no view of
`GateClientConfig.timeout_seconds`, so a caller that configures a different
budget must restate it or advertise a budget it will not honour. Subsumed by
SDK-GAP-1.

---

# Deferred Work

| Item | Trigger |
|---|---|
| Delete the Odoo `create_transport_packet` call | Gate_SDK ships SDK-GAP-1 |
| Drop the `httpx` exception import | Gate_SDK ships SDK-GAP-2 |
| Real Odoo 19 import + enrichment-run proof | Odoo 19 environment |
| Live Gate round-trip | Live five-service stack |
| Retire `_odoo_entity_id` | Cross-repo consumer audit |
| Matching operation identity | Separate decision |

---

# Merge Recommendation

**Merge.** The change is a strict reduction in Odoo-owned transport behaviour,
adds executable ownership gates, and is green across every check available in
this environment. It does not, and does not claim to, complete shadow-SDK
elimination — that requires the Gate_SDK change above.

Reviewers should read the ADR-006 behaviour change in *Logical Idempotency
State* deliberately: it is the one runtime-semantic change in the diff.

---

# Release-Set Recommendation

**PENDING.** Odoo, Gate and EIE must not be assumed compatible because each
installs some Gate_SDK (pack ADR-011). Compatibility is executable, and the
executable proof here stops at the SDK boundary. Do not canary before the real
Odoo 19 and live Gate evidence exists.

---

# Next Straight-Line Move

Open a `Gate_SDK` change implementing **SDK-GAP-1** (`GateClient.execute`),
release it, pin the proven commit here, then delete the Odoo
`create_transport_packet` call. That single change moves `shadow_sdk` to
`ELIMINATED` and `sdk_capability` to `SUFFICIENT`.

---

# Machine-Readable Summary

```yaml
repository: cryptoxdog/IB-Odoo_19
branch: Staging
final_code_head: "828e4b372b4b6aa11c82b0c4315c581759282c00"
final_head_note: "this report is committed on top of final_code_head"
gate_sdk:
  pinned_sha: "92279da4c01d3cb9be806c60690c21d736103826"
  main_sha_at_analysis: "d09fe58a6cd68ef8aa883896c68badc95f96e090"
  src_diff_pin_to_main: none
  api_surface_used:
    - "constellation_node_sdk.GateClient"
    - "constellation_node_sdk.GateClientConfig"
    - "constellation_node_sdk.create_transport_packet"
    - "constellation_node_sdk.TransportError"
  capability: BLOCKED_EXTERNAL_SDK_CAPABILITY
shadow_sdk:
  verdict: PARTIALLY_ELIMINATED
  removed:
    - "substring-based transport error taxonomy (_RETRYABLE_TOKENS/_PERMANENT_TOKENS)"
    - "payload-digest transport replay identity (build_idempotency_key)"
    - "Odoo-chosen packet destination_node and classification"
    - "tests asserting Odoo-owned transport policy as correct"
  remaining:
    - "create_transport_packet called in Odoo — forced by SDK-GAP-1"
    - "timeout_ms restated at the call site — forced by SDK-GAP-3"
    - "httpx exception types imported for classification — forced by SDK-GAP-2"
canonical_contract:
  request: EnrichRequest
  response: EnrichResponse
  entity_identity: "res.partner:<id>"
  rejected_dialect_present: false
transport:
  authority: Quantum-L9/Gate_SDK
  manual_packet_creation_in_odoo: true
  manual_http_in_odoo: false
  manual_transport_validation_in_odoo: false
  manual_transport_signing_in_odoo: false
  manual_transport_hashing_in_odoo: false
  manual_hop_management_in_odoo: false
  manual_gate_routing_in_odoo: false
  duplicate_transport_error_protocol_in_odoo: false
  odoo_retry_layer: false
  gate_only_egress: true
idempotency:
  one_logical_operation_identity: true
  transport_representation_sdk_owned: true
  domain_identity_propagated: true
  form: "odoo:enrichment:<db>:<model>:<record_id>"
timeouts:
  odoo_business_ceiling_seconds: 30
  sdk_transport_owned: true
  packet_budget_restated_by_caller: true
validation:
  static_boundary_tests: PASS
  unit_tests: PASS
  installed_package: PASS
  real_odoo_19: NOT_RUN
  real_gate: NOT_RUN
blocking_defects:
  - "manual_packet_creation_in_odoo cannot be false while Gate_SDK lacks an application-facing execute"
external_blockers:
  - "SDK-GAP-1: GateClient has no execute(action, payload, tenant, idempotency_key, ...) — BLOCKING"
  - "SDK-GAP-2: httpx exceptions and bare ValueError leak through the public API"
  - "SDK-GAP-3: packet timeout_ms not derived from GateClientConfig.timeout_seconds"
deferred:
  - "delete Odoo create_transport_packet call once SDK-GAP-1 ships"
  - "drop httpx exception import once SDK-GAP-2 ships"
  - "real Odoo 19 runtime proof"
  - "live Gate round-trip proof"
  - "retire _odoo_entity_id after cross-repo consumer audit"
  - "matching logical operation identity"
verdict:
  odoo_local: NO_GO
  runtime: PROOF_PENDING
  release_set: PENDING
next_move: "Implement GateClient.execute in Quantum-L9/Gate_SDK (SDK-GAP-1), release, pin, then delete the Odoo packet-construction call."
```
