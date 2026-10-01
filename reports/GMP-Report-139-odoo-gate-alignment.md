# GMP-139: Odoo ↔ Gate Alignment (GAR-ODOO-GATE-ALIGNMENT-001)

**ID:** GMP-139 | **Task:** Final Odoo ↔ Gate ownership alignment | **Tier:** RUNTIME_TIER | **Date:** 2026-10-01 | **Status:** ✅ COMPLETE

| Field | Value |
|-------|-------|
| **Contract** | GAR-ODOO-GATE-ALIGNMENT-001 |
| **R1 correction** | GAR-ODOO-GATE-ALIGNMENT-001-R1 — exact SDK SHA, three manifest bumps, external-state refresh |
| **Repository** | cryptoxdog/IB-Odoo_19 @ `Staging` |
| **Observed baseline** | `2260f1e63e9b834e329ef3a05136d06a528d3c0e` (matches contract; `origin/Staging` had not moved at Phase 0) |
| **Gate_SDK proven runtime revision** | `7ec6cdf5e26c837057ca35b7324a88de4d499ea3`, version `1.2.0` |
| **Constellation.Gate main** | `cfeb81fa4d11eb8c106314fa27310f660a1dfad7` |
| **Gate caller-policy landing** | PR #27 `69588a16a7d86b2269333c31568a3b37b97f4746` |
| **Gate SDK-lock refresh** | PR #28 `cfeb81fa4d11eb8c106314fa27310f660a1dfad7` |
| **Cognitive.Engine.Graphs main** | `7925c79080167913cbaafcfa36f71012fcbb9698` |
| **CEG participation remediation landing** | PR #308 `7925c79080167913cbaafcfa36f71012fcbb9698` |
| **Enrichment.Inference.Engine main** | `eab524cb812990149df0d6fccde36b0817a4af76` |
| **Local code commit** | `a572a9a9338f87760925c188ef7be50eb1ca80c2` on `Staging` (not pushed at Phase 6) |
| **Mode** | bounded realization of already-converged architecture; no redesign |

---

## TODO PLAN

### Phase 0 — ground truth (T-001, no mutation)

Verified against the SDK checkout at `7ec6cdf5` (Gate_SDK 1.2.0). Phase 0 also read Constellation.Gate at `4f8baa5` and Cognitive.Engine.Graphs at `ffa5ac1` (merge of PR #298). Those two heads are historical observations; the current coordinates are the header table above.

| Required API | Location in Gate_SDK v1 | Status |
|---|---|---|
| `GateClientError.retryable` property | `gate/errors.py:25-27`; `True` on `GateConnectionError` (`:78-80`), `GateTimeoutError` (`:99-101`), status-derived on `GateHTTPError` (`:130-134`); `False` on `GateAuthorizationError`, `GateConfigurationError`, `GateSecurityError`, `GateResponseError`, `GatePolicyError` | present |
| `get_gate_client_config_from_env(**overrides)` | `gate/config.py:185-229`; rejects unknown fields (`:194-196`); reads `GATE_URL`, `L9_NODE_NAME`, `L9_SIGNING_KEY`, `L9_SIGNING_KEY_ID`, `L9_SIGNING_ALGORITHM`, `L9_VERIFYING_KEYS_JSON`, `L9_REQUIRE_SIGNATURE` | present, accepts overrides |
| `GateClient.activate(required_actions, tenant, timeout_ms)` | `gate/client.py:460-537`; raises `GateConfigurationError` on `admission_problems()` (`:487-489`), `GateAuthorizationError(403, code=action_not_permitted)` on a missing grant (`:524-536`) | present |
| `GateClientConfig.admission_problems()` | `gate/config.py:114-138` | present |
| `GateClient.execute` | `gate/client.py:104-176` | present |
| `/v1/admission` | SDK `gate/admission.py:22`; Gate `api/main.py:126-137` | present on both sides |
| Top-level exports | `constellation_node_sdk.__init__`: `GateClient`, `GateClientError`, `GateAuthorizationError`, `get_gate_client_config_from_env` | present |

Cross-repo facts bound (read-only):
- Gate scopes keys through `L9_KEY_ALLOWED_ACTIONS_JSON`; an out-of-scope action is `403 action_not_permitted`; an unknown key or bad signature is `400 invalid_transport_packet` (Constellation.Gate `api/errors.py:39-162`, `boundary/ingress_validator.py`, observed at Phase 0 head `4f8baa5`). Current Gate caller policy (PR #27, `69588a16a7d86b2269333c31568a3b37b97f4746`) binds a verified key to node, kind, tenants, and actions. Odoo already supplies its resolved tenant to `GateClient.activate()` and business packets, so tenant ownership is not an architectural Unknown.
- The CEG Odoo E2E rail asserts `activate(required_actions=("converge","match"))` → `admitted`, requiring `sync` → `GateAuthorizationError` with `retryable is False`, HMAC-SHA256 signing, and Gate replies verified via the Gate key (`tests/e2e/constellation_odoo/scripts/odoo_driver.py:614-676`). In SDK-participation mode it still applies `patches/{ceg,eie}-sdk-adoption.diff`.
- The #299 participation remediation is reachable from CEG main through PR #308 (`7925c79080167913cbaafcfa36f71012fcbb9698`).

`CODE_GRAPH_BASELINE: BLOCKED` — `code_graph_gmp_baseline.sh` exited 1 ("Index unhealthy — run code_graph_batch_index.sh"); the `code-graph-rag-mcp` binary is not installed in this container, so indexing cannot run. Substitute importer analysis by grep (full repo, excluding reports/docs):
- `classify_transport_failure` / `TransportFailureClass` importers: `plasticos_matching/models/match_orchestrator.py`, `plasticos_enrichment/models/enrichment_run.py`, `scripts/check_external_intelligence_readiness.py`, `tests/test_gate_sdk_invocation.py`, `tests/contracts/test_external_intelligence_contract_parity.py`.
- `resolve_gate_signing` / `_parse_verifying_keys` / `gate_signing_configured` / `_copy_supported_overrides` / `_sdk_config_from_env`: no importer outside `gate_config.py`.
- `_maybe_activate` / `_activated_ok`: no importer outside `gate_client.py`.
- `GateIntegrationError.failure_class` consumers (contract unchanged): both downstream models, matching receipt tests, runtime gates C7–C10, `tests/e2e/four_repo/run_odoo_driver.py`.

`MEMORY_PREFETCH:` namespace `ib-odoo-19` · snapshot_digest `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` · checked_record_count 0 · conflicts 0 · policy_version `memory-phase-lock/v2` (hydrate: NO_HITS; evidence only, not write authority).

### Locked TODOs

| ID | Phase | File | Operation | Anchor | Description | Deps |
|---|---|---|---|---|---|---|
| T-001 | 0 | — | Verify | — | Bind Staging baseline, Gate_SDK v1 SHA, required SDK APIs (table above). No mutation. | — |
| T-002 | 2 | `plasticos_gate/services/gate_client.py` | Replace | lines 1–267 (module header through `_run_async`) | Remove httpx exception taxonomy, HTTP status tables, SDK exception grouping and `classify_transport_failure`. Add `failure_class_for(exc)`: SDK `GateClientError` → `exc.retryable` projected onto Odoo `retryable`/`permanent`; non-SDK → `None`. Keep `TransportFailureClass` solely as the Odoo durable-category vocabulary. Strict SDK import (`GateClient`, `GateClientError`, `GateAuthorizationError`). | T-001 |
| T-003 | 2 | `plasticos_gate/services/gate_config.py` | Replace / Delete | lines 1–10 (docstring), 14 (`import json`), 25–31 (unused `ENV_*`), 320–485 (`_parse_verifying_keys` … `build_gate_client_config`) | Delete the shadow signing/env parser, zero-argument compatibility shim and manual `GateClientConfig` reconstruction. `build_gate_client_config` calls `get_gate_client_config_from_env(local_node="odoo", timeout_seconds=<validated>, max_timeout_ms=30000, allowed_gate_destination="gate")` and projects SDK `ValueError` onto `GateIntegrationError(permanent)`. Retain the 30 s ceiling validation, tenant resolution, capability toggles, availability presentation, insecure-http dev policy. | T-001 |
| T-004 | 2 | `plasticos_gate/services/gate_client.py` | Replace | `_maybe_activate` (lines 188–226) and its call site in `send_action` (line 291) | `ensure_admitted(client, config, tenant)`: `GateClient.activate(required_actions=("match","converge"), tenant=<resolved tenant>)` is authoritative. Receipts keyed by `(gate_url, local_node, signing_key_id, tenant, required_actions)`, never an unkeyed boolean; invalidated when `execute` raises `GateAuthorizationError`. No soft skip for a missing `activate`, a 404 on `/v1/admission` or unprovable identity. | T-002 |
| T-005 | 2 | `plasticos_matching/models/match_orchestrator.py` | Replace | lines 167–170, 266, 308 | Consume `exc.failure_class`; the generic boundary keeps `unknown`/`degraded`. No reclassification. | T-002 |
| T-005 | 2 | `plasticos_enrichment/models/enrichment_run.py` | Replace | lines 354, 409, 424 | Same for the enrichment persistence shell. | T-002 |
| T-006 | 3 | `scripts/check_external_intelligence_readiness.py` | Replace | lines 84–100 | Drop the classifier requirement; assert the ownership boundary statically. | T-002, T-003 |
| T-007 | 3 | `tests/test_gate_sdk_invocation.py` | Replace | fixture 125–135; classification 263–318; signing 324–387 | Signed fixture over an `httpx.MockTransport` seam with Gate-signed admission echo; V2/V3/V4 proofs; negative guards. | T-002, T-003, T-004 |
| T-007 | 3 | `tests/test_gate_canonical_env.py` | Insert | after line 85 | SDK-free negative guards for every recurrence listed in contract §16 T-007. | T-002, T-003 |
| T-007 | 3 | `tests/contracts/test_external_intelligence_contract_parity.py` | Replace | lines 14–17, 85–141 | Ownership-boundary parity replaces classifier parity. | T-002 |
| T-008 | 2 | `docs/track_b/05_external_authority_readiness.md` | Replace | lines 11, 14 | Statements that became false; admission and SDK-owned parsing stated. | T-004 |
| T-008 | 2 | `docs/handoffs/eie-gate-consumer-handoff.md` | Replace | lines 179–191 | Call sequence gains admission; failure projection; config snippet gains `max_timeout_ms`. | T-003, T-004 |
| T-009 | 6 | `reports/GMP-Report-139-odoo-gate-alignment.md` | Create | — | This evidence report. | all |

Not modified on purpose (verified by reading): `tests/test_gate_canonical_contract.py` (its source assertions remain satisfied), `plasticos_matching/tests/test_match_run_receipts.py` and `plasticos_enrichment/tests/test_gate_enrichment_fallback.py` (they drive the bridge seam with `GateIntegrationError(failure_class=…)` and a bare `RuntimeError`; both contracts are unchanged). `workflow_state.md` exists at the repo root but is outside the contract's modification lock and was left untouched.

### Modification lock

MAY modify: the eleven implementation/test surfaces in contract §14 plus the two active docs. MUST NOT modify: everything in §15. Protected-core rule 90: no protected path targeted. Enforced result: see VERIFICATION.

---

## PHASES

| Phase | Status | Evidence |
|---|---|---|
| 0 PLAN | ✅ | SDK authority table, cross-repo facts, importer analysis, memory receipt, locked TODOs above |
| 1 BASELINE | ✅ READY | Every TODO file existed; every anchor resolved uniquely in the Phase 0 reads; no protected path; acyclic deps. Baseline targeted suite (3.12 + SDK): 144 passed / 3 skipped |
| 2 IMPLEMENT | ✅ | T-002…T-005, T-008 applied; commit `a572a9a` |
| 3 ENFORCE | ✅ | T-006 readiness boundary checks; T-007 tests (SDK tier and SDK-free tier) |
| 4 VALIDATE | ✅ | VALIDATION table below |
| 5 RECURSIVE VERIFY | ✅ VERIFIED | VERIFICATION below |
| 6 FINALIZE | ✅ | this report |

## CHANGES

Before → after ownership map:

| Concern | Before (Staging `2260f1e`) | After (`a572a9a`) | Owner |
|---|---|---|---|
| Transport retryability | Odoo `classify_transport_failure`: httpx exception types, 408/429/5xx tables, SDK subclass grouping | `failure_class_for(exc)` reads `GateClientError.retryable`; non-SDK exceptions return `None` | Gate_SDK |
| Durable failure vocabulary | `TransportFailureClass` + `GateIntegrationError.failure_class` | unchanged (`retryable` / `permanent` / `unknown`) | Odoo |
| httpx knowledge | `import httpx`, six exception classes named | none | Gate_SDK |
| Signing / env parsing | `resolve_gate_signing`, `_parse_verifying_keys`, Odoo `hmac-sha256` default, Odoo-derived `require_signature` | `get_gate_client_config_from_env(...)` reads and validates `L9_*` | Gate_SDK |
| Config overrides | signing posture + node + budget + destination + conditional `max_timeout_ms` | `local_node="odoo"`, `timeout_seconds` (validated ≤ 30 s), `max_timeout_ms=30000`, `allowed_gate_destination="gate"` | Odoo |
| Zero-argument SDK shim | `_copy_supported_overrides`, `_sdk_config_from_env`, `TypeError` fallback, manual `GateClientConfig(...)` | deleted | — |
| Admission | `_maybe_activate`: feature-detected, skipped on missing identity / 404, unkeyed `_activated_ok` | `ensure_admitted`: `activate(required_actions=("match","converge"), tenant)` always asked; receipts keyed by Gate/node/key/tenant/actions; dropped on `GateAuthorizationError` from execute | Gate decides; SDK asks; Odoo persists outcome |
| SDK version posture | `hasattr(GateClient, "execute")` | `execute` and `activate` both required (fail-closed message) | Odoo |
| Downstream shells | `exc.failure_class or classify_transport_failure(exc)`; generic `except` classified | `exc.failure_class or "unknown"`; generic `except` → `unknown`/`degraded` | Odoo |
| Readiness script | requires `classify_transport_failure` | requires `failure_class_for`, `ensure_admitted`, `("match","converge")`; forbids httpx / status tables / shadow parser / shim / unkeyed flag | Odoo |

Files changed (10, commit `a572a9a`; +796 / −616):

| File | Intent |
|---|---|
| `plasticos_gate/services/gate_client.py` | bridge: projection + authoritative keyed admission |
| `plasticos_gate/services/gate_config.py` | config: SDK builder with Odoo-owned overrides only |
| `plasticos_matching/models/match_orchestrator.py` | consumer: no reclassification |
| `plasticos_enrichment/models/enrichment_run.py` | consumer: no reclassification |
| `scripts/check_external_intelligence_readiness.py` | readiness: ownership boundary |
| `tests/test_gate_sdk_invocation.py` | SDK-tier proofs V2/V3/V4 |
| `tests/test_gate_canonical_env.py` | SDK-free negative guards |
| `tests/contracts/test_external_intelligence_contract_parity.py` | boundary parity |
| `docs/track_b/05_external_authority_readiness.md` | invariants that became false |
| `docs/handoffs/eie-gate-consumer-handoff.md` | call sequence and config snippet |

Behavioral consequence to state plainly: an **unsigned** Odoo deployment (no `L9_SIGNING_KEY` / `L9_SIGNING_KEY_ID` / `L9_VERIFYING_KEYS_JSON`) can no longer execute through Gate. `activate()` refuses up front with a permanent, operator-visible configuration failure, because Gate verifies a consumer by its signing key id and the receipt must be verifiable with the Gate key. This is GATE-11/GAP-05 as contracted, and it matches the CEG E2E rail's signed Odoo identity.

## TODO → CHANGE MAP

| TODO | Change | Lines (after) |
|---|---|---|
| T-001 | no mutation; SDK table + cross-repo facts recorded | — |
| T-002 | `gate_client.py`: strict import block, `TransportFailureClass`, `failure_class_for`, `_require_sdk`; `send_action` except-block | 1–96, 207–262 |
| T-003 | `gate_config.py`: docstring, imports, `ENV_GATE_URL` only, `build_gate_client_config` | 1–30, 302–329 |
| T-004 | `gate_client.py`: `_ADMISSION_RECEIPTS`, `_ADMISSION_LOCK`, `_admission_key`, `_forget_admission`, `ensure_admitted`; call in `send_action`; invalidation on authorization refusal | 98–152, 184 |
| T-005 | `match_orchestrator.py` import + two except blocks; `enrichment_run.py` import removal + two except blocks | 163–167, 262–270, 305–307; 354–359, 408–413, 423–427 |
| T-006 | `check_external_intelligence_readiness.py`: `check_contract_symbols`, `_BOUNDARY_*`, `_code_text`, `check_ownership_boundary`, wired into `main` | 84–163, 212 |
| T-007 | three test files as described | whole files / appended block |
| T-008 | two docs | as anchored |
| T-009 | this report | — |

## VALIDATION

Validation interpreter: the SDK requires Python ≥ 3.12; the container's default is 3.11. A scratchpad venv on `/usr/bin/python3.12` with Gate_SDK `7ec6cdf5` (1.2.0), `pytest==8.3.5`, `pytest-timeout==2.4.0`, `requests`, `ruff==0.16.0` stands in for CI's `gate-sdk-tests` job; a 3.11 venv without the SDK stands in for the `pure-python-tests` tier.

| Check | Result |
|---|---|
| `ruff check` (0.16.0) on the 8 Python files | Passed |
| `ruff format --check` | Passed (after formatting two test files) |
| `python -m py_compile` | Passed |
| pytest, 3.12 + SDK, the ten Gate-related test files | **226 passed, 3 skipped** (owner-schema parity skips: `~/l9-constellation-repos` absent) |
| pytest, 3.12 + SDK, full `tests/` tree (minus runtime_gates/integration/e2e) | **934 passed, 6 skipped** |
| pytest, 3.11 without SDK (CI pure-Python tier) | **123 passed, 42 skipped** (SDK-tier module skips by design) |
| `pre-commit run --files <changed>` | 34 hooks Passed; `mypy` Passed after the `attr-defined` narrowing fix |
| `semgrep --config .semgrep/odoo-patterns.yml` on changed Python | 0 findings |
| `scripts/check_odoo_patterns.sh` | all passed |
| `make audit-baseline` | no new findings, no regression (10 known suppressed, 5 stale) |
| `scripts/check_module_wiring.py`, `ci/check_circular_deps.py`, `ci/check_orphan_model_refs.py` | Passed |
| `scripts/check_external_intelligence_readiness.py --owner-root <CEG> --owner-root <EIE>` | **PASS** (new boundary checks included) |
| `OPEN_PR=0 PR_REMEDIATE=0 PR_BASE=origin/Staging make -C $GOV pr WS=$PWD` | **RESULT: PASS — local PR gate clean (changed files only)**, exit 0. Kernel hook OK; pre-commit writers and readers clean; locked ruff writer (repo `.venv` ruff 0.16.0, 8 files) "All checks passed!"; semgrep `p/secrets` + `l9-pr.yml` PASS (8 files); security gate PASS; ci-parity `a572a9a9` vs `2260f1e6`: lanes=4 blocking=0 advisory=0 skipped=1 (semgrep-pro); governance pytest registry skipped (consumer workspace — repo pytest results are the rows above); `OPEN_PR=0` skipped the GitHub PR open |
| Odoo runtime tests (`plasticos_matching/tests`, `plasticos_enrichment/tests`, runtime gates C7–C10) | **NOT RUN** — no Odoo/PostgreSQL runtime in this container. Their seams (`send_*_action` patched; `GateIntegrationError(failure_class=…)`; bare `RuntimeError`) are unchanged by this change |
| Code-graph GMP baseline | **BLOCKED** — tooling absent (see Phase 0) |

Contract validation layers:

- **V1 structural boundary** — `test_gate_single_egress.py` (all 14 guards), `test_gate_canonical_env.py::test_bridge_holds_no_transport_taxonomy_of_its_own`, `::test_bridge_has_no_shadow_signing_or_compatibility_shim`, `::test_admission_is_authoritative_and_keyed`, `::test_downstream_shells_do_not_reclassify_gate_transport`; readiness `check_ownership_boundary`. Passed.
- **V2 canonical SDK config** — `test_config_is_the_sdk_env_builder_plus_odoo_owned_overrides_only`, `test_a_shorter_icp_budget_is_applied_and_the_ceiling_stays`, `test_a_budget_above_the_ceiling_is_rejected_before_any_network_call`, `test_malformed_verifying_keys_fail_visibly_through_the_sdk`, plus `test_gate_canonical_contract.py` ceiling tests. Passed.
- **V3 admission** — `test_send_asks_gate_for_admission_before_executing`, `test_admission_is_keyed_by_identity_not_a_process_global_boolean`, `test_denied_admission_is_permanent_and_nothing_executes` (`code == action_not_permitted`, `retryable is False`), `test_unknown_key_is_rejected_as_permanent`, `test_a_gate_without_the_admission_endpoint_is_not_skipped`, `test_an_authority_refusal_on_execute_drops_the_cached_receipt`, `test_unsigned_identity_cannot_be_admitted`; `sync` never requested (AST guard in `test_gate_canonical_env.py`). Passed.
| **V4 failure projection** — `test_sdk_typed_errors_project_onto_odoo_categories_by_their_own_verdict` asserts exactly the contract table (`GateConnectionError`/`GateTimeoutError` → retryable; `GateAuthorizationError`/`GateConfigurationError`/`GateSecurityError`/`GateResponseError`/`GatePolicyError` → permanent), `test_http_status_retryability_is_the_sdks_not_odoos`, `test_non_sdk_exceptions_are_not_transport_outcomes`, `test_a_programming_error_at_the_boundary_is_not_labelled_a_gate_failure`. Passed.
- **V5 existing behavior** — unchanged seams proven by the unchanged runtime test files; `test_one_operation_identity_reaches_the_transport_header`, `test_operator_retry_is_a_new_logical_operation`, writeback allowlist tests in `test_gate_canonical_contract.py`, disabled-state and degraded-mode source guards (`test_matching_degraded_mode.py`, `test_launch_invariants_crm_enrichment.py`). Passed where runnable; Odoo-runtime cases NOT RUN as stated above.
- **V6 repo gates** — table above.

Governance ceremony notes: the `make pr` preflight required a local L4 release receipt (`l4_local.py begin --contract-id GAR-ODOO-GATE-ALIGNMENT-001` → `authorize-release`) and a kernel apply receipt (`.l9/autonomy/kernel-apply.md`, recorded `l9.kernel_receipt.v2`) even in `OPEN_PR=0` diagnosis mode. Both are gitignored local receipts; nothing was pushed and no PR was opened. The kernel receipt was recorded against the authored change set (the ten files vs `origin/Staging`); the `.claude/skills/*` symlink churn written by the SessionStart governance bootstrap (repo-relative → machine-absolute targets, six deletions) is foreign dirt, excluded from the commit and recorded as kernel finding F-04.

Two gate runs before the passing one failed for environment reasons, not for this change: (a) the gate's locked ruff writer resolved to the governance venv's ruff 0.16.1 while this repo pins `required-version == 0.16.0` — fixed by building the repo's own `.venv` with the documented `make venv` (gitignored; the gate prefers `$WS/.venv/bin/ruff`); (b) the STOP-LOOPING failure receipt (`.l9/pr/gate-failure.json`, `failure_class: unknown`, no failed nodes/hooks/paths) keyed on the unchanged tree and could not observe the toolchain fix, so that one stale, gitignored latch receipt was archived to the scratchpad and removed before the full gate re-ran end to end. No gate was weakened and no tracked file changed for either.

Durable memory: the `memory.write_agent` decision record for this alignment was **refused** (`namespace did not match any write grant` for principal `claude-code-mobile-memory-client` on `ib-odoo-19`). Reported as a gap per the agent write contract; not rerouted.

## VERIFICATION

Phase 5 recursive verification of the committed tree against the locked plan:

- `git diff --name-only 2260f1e a572a9a` = exactly the ten planned paths. No other file changed. `git diff --name-only HEAD` (excluding `.claude/skills`) is empty.
- Must-not-modify probe (`plasticos_crm_sync/`, `plasticos_transaction/`, `plasticos_partner_import/`, `tests/runtime_gates/`, `data/`, `migrations/`, `__manifest__.py`, `requirements.txt`, `Dockerfile`, `docker-compose*`, `odoo.conf`, `config/`, `.github/`, `Makefile`): **none**.
- Residual references to `classify_transport_failure`, `resolve_gate_signing`, `_parse_verifying_keys`, `gate_signing_configured`, `_copy_supported_overrides`, `_sdk_config_from_env`, `_activated_ok`, `_maybe_activate` in code, scripts, tests, YAML: **none** (only as forbidden strings inside the new guards and the readiness script).
- No new runtime module, no new ADR, no new helper framework. `TransportFailureClass` retained solely as the Odoo durable vocabulary.
- Matching/enrichment domain semantics untouched: rollback-before-second-cursor, durable receipts, operation identity, attempt counters, writeback allowlist and disabled states are the same code paths; only the category source changed.
- Status: **VERIFIED** — no scope drift.

Remaining Unknowns:
- Runtime compatibility of the final exact release set is unproven. That set is Gate_SDK `7ec6cdf5e26c837057ca35b7324a88de4d499ea3`, Constellation.Gate `cfeb81fa4d11eb8c106314fa27310f660a1dfad7`, Enrichment.Inference.Engine `eab524cb812990149df0d6fccde36b0817a4af76`, Cognitive.Engine.Graphs `7925c79080167913cbaafcfa36f71012fcbb9698`, and the IB-Odoo_19 SHA that lands from this PR. The proof is the downstream native-head constellation Odoo E2E rail.

## Downstream proof obligation (not part of this change)

After this Odoo alignment lands on `Staging`, freeze that Odoo SHA together with Gate_SDK `7ec6cdf5e26c837057ca35b7324a88de4d499ea3`, Constellation.Gate `cfeb81fa4d11eb8c106314fa27310f660a1dfad7`, Enrichment.Inference.Engine `eab524cb812990149df0d6fccde36b0817a4af76`, and Cognitive.Engine.Graphs `7925c79080167913cbaafcfa36f71012fcbb9698`, then rerun the CEG Odoo cross-repo E2E rail (`Cognitive.Engine.Graphs/tests/e2e/constellation_odoo/`) against native repository heads. The #299 participation remediation is reachable from CEG main through PR #308. The final run must not depend on `patches/ceg-sdk-adoption.diff` or `patches/eie-sdk-adoption.diff` for behavior already native in those repositories. This is a deployment-convergence gate, not part of this code-change scope.

## R1 remediation (GAR-ODOO-GATE-ALIGNMENT-001-R1)

The Phase 5 must-not-modify probe below records the original contract: `requirements.txt` and `__manifest__.py` were untouched in `a572a9a`. R1 authorizes those files and only these corrections:

- `requirements.txt` pins `constellation-node-sdk` to Gate_SDK `7ec6cdf5e26c837057ca35b7324a88de4d499ea3` (version 1.2.0). The floating `@v1` ref and the stale 1.1.0 pin comment are replaced.
- Manifest patch bumps, with no migration directories: `plasticos_gate` `19.0.1.9.4` → `19.0.1.9.5`; `plasticos_matching` `19.0.3.1.1` → `19.0.3.1.2`; `plasticos_enrichment` `19.0.2.5.0` → `19.0.2.5.1`.

## DECLARATION

Odoo owns domain semantics; Gate_SDK owns Gate transport semantics; Gate owns authorization. Odoo asks for `match` + `converge` only, uses SDK configuration parsing and SDK retryability, holds no httpx taxonomy, parses no Gate signing configuration, never silently skips admission, retains durable operator outcomes, and remains Gate-only and fail-closed. Targeted tests pass; runnable repo gates pass; no out-of-scope file changed. No readiness percentage, no production-readiness claim, no claim about VanillaSoft or LegacyERP imports.

Phases 0-6 complete. No assumptions. No drift.
