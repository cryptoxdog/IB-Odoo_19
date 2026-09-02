# Four-repo end-to-end: IB-Odoo_19 -> Gate_SDK -> Constellation.Gate -> EIE

`run_odoo_driver.py` runs the real `plasticos_gate/services` bridge (the code Odoo
executes) against a real Constellation.Gate and a real Enrichment.Inference.Engine,
with the installed `constellation-node-sdk` doing every packet, signing and HTTP
step. Only the Odoo ORM is replaced by minimal stand-ins. It is not a pytest
module: it needs live services, so it is run by hand or by a scheduled job.

## Prerequisites

* Python 3.12 with this repository's `requirements.txt` SDK pin installed
  (`pip install "$(grep -E '^constellation-node-sdk @ ' requirements.txt)"`).
* Constellation.Gate checked out and installed (`pip install -e constellation-gate`).
* Enrichment.Inference.Engine checked out and installed (`pip install -e .`),
  plus PostgreSQL and Redis reachable by it.
* All three repositories on the same Gate_SDK release commit
  (Gate_SDK `contracts/RELEASE_IDENTITY_LEDGER.json` `consumer_pin.sha`).

## Launch sequence

```bash
# 1. EIE worker (registers itself with Gate; re-registers every 60 s)
cd Enrichment.Inference.Engine
DATABASE_URL=postgresql+asyncpg://enrich:enrich@127.0.0.1:5432/enrich \
REDIS_URL=redis://127.0.0.1:6379/0 \
GATE_URL=http://127.0.0.1:9000 GATE_REGISTRATION_ENABLED=true \
GATE_INTERNAL_URL=http://127.0.0.1:8000 GATE_ADMIN_TOKEN=local-admin \
L9_ENVIRONMENT=local PERPLEXITY_API_KEY=<key-or-mock> \
uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2. Gate (static registry pre-declares the worker; health re-probe every 15 s)
cd Constellation.Gate/constellation-gate
L9_ENVIRONMENT=local GATE_LOCAL_NODE=gate GATE_ADMIN_TOKEN=local-admin \
GATE_NODE_REGISTRY_PATH=src/constellation_gate/config/node_registry.yaml \
GATE_HEALTH_PROBE_INTERVAL_SECONDS=15 GATE_RESPONSE_MARGIN_MS=500 \
sh scripts/entrypoint.sh            # listens on 9000

# 3. Odoo bridge
cd IB-Odoo_19
python tests/e2e/four_repo/run_odoo_driver.py happy http://127.0.0.1:9000 30
```

Exit codes: `0` usable result (Odoo would land in `review`/`injected`), `2`
transport failure surfaced as `GateIntegrationError`, `3` EIE answered but not
with `state="completed"` (Odoo fails closed as `degraded`).

## Scenarios

| Scenario | How | Expected |
|---|---|---|
| Happy path | `happy` | `RESULT: transport OK`, mapped status `ok`, connects only to the Gate host:port |
| Duplicate delivery | run `happy` twice with the same `E2E_RUN_ID` | second answer served from Gate's idempotency cache (same `packet_id`) |
| Operator retry | `E2E_ATTEMPT=2` | new idempotency key `...:attempt-2`, EIE executed again |
| Invalid request | `invalid_request` | `permanent` failure, HTTP 4xx from Gate/EIE |
| Unknown action | `unknown_action` | `permanent` failure, Gate 404 |
| Worker down | stop EIE, run `happy`, start EIE, wait one probe interval, rerun | first run `retryable`/504; second run OK without a Gate restart |
| Timeout margin | `happy ... 2` (2 s budget) against a slow EIE | Gate's 504 arrives before the caller's socket deadline |
| Signed topology | Odoo: `PLASTICOS_GATE_SIGNING_KEY=<k> PLASTICOS_GATE_SIGNING_KEY_ID=odoo-k1 PLASTICOS_GATE_VERIFYING_KEYS_JSON='{"gate-k1":"<k>"}'`; Gate: `L9_REQUIRE_SIGNATURE=true L9_SIGNING_KEY=<k> L9_SIGNING_KEY_ID=gate-k1 L9_VERIFYING_KEYS_JSON='{"odoo-k1":"<k>","eie-k1":"<k>"}'`; EIE: `L9_SIGNING_KEY=<k> L9_SIGNING_KEY_ID=eie-k1 L9_REQUIRE_SIGNATURE=true L9_VERIFYING_KEYS_JSON='{"gate-k1":"<k>"}'` | OK end to end; an unsigned or unknown-key run is rejected by Gate with 400. Odoo needs Gate's verifying key because the SDK verifies every signature it receives. |
| Direct EIE bypass | point the driver at EIE's port | the SDK refuses (`GatePolicyError`/non-canonical response) — no direct path exists |

The `NETWORK CONNECTS` line is the egress proof: only the Gate address may appear.
