# Gate wiring runbook: PlasticOS Odoo → Constellation.Gate (tenant `scrapmanagement`)

**Status:** operator runbook, 2026-11-11. An agent wrote it; the operator applies it. Nothing here has been applied to any running system.
**Goal:** Odoo calls EIE's `converge` and CEG's `match` through Constellation.Gate for tenant `scrapmanagement`.
**Code state:** done. Gate_SDK is pinned to `@v1` (`requirements.txt:69`, resolves to `constellation-node-sdk` 1.3.2), and PRs #415 and #416 are merged into `Staging`. Only configuration is left.

Each claim below names a file and line. "Verified" means the agent read the code. "Gate (fragment)" means the agent saw only a code-search excerpt of `Quantum-L9/Constellation.Gate`, because that repository could not be attached to the session that wrote this runbook. Check those items against Gate's source before applying them.

---

## 0. How the pieces fit

```
Odoo (consumer, node "odoo")
  ── signs a TransportPacket with Odoo's private key (L9_SIGNING_KEY, key id L9_SIGNING_KEY_ID)
  ── POST /v1/admission   (once per Gate URL + key id + tenant: "may I call match + converge?")
  ── POST execute         (action converge | match, tenant scrapmanagement)
Gate
  ── verifies Odoo's signature with Odoo's PUBLIC key   (Gate: L9_VERIFYING_KEYS_JSON[<odoo key id>])
  ── authorizes key → node/kind/tenants/actions          (Gate: L9_KEY_ALLOWED_ACTIONS_JSON[<odoo key id>])
  ── routes converge → enrichment-engine, match → graph (CEG)
  ── signs its reply with Gate's key
Odoo
  ── verifies the admission receipt with Gate's PUBLIC key (Odoo: L9_VERIFYING_KEYS_JSON[<gate key id>])
```

- Admission always runs before execute, and it asks for both actions. `_ODOO_REQUIRED_ACTIONS = ("match", "converge")` is in `plasticos_gate/services/gate_client.py:39`, and `ensure_admitted` is at `:136`. If Gate's policy grants only one of the two actions, admission fails with `action_not_permitted`, so both must be granted.
- The SDK refuses an admission receipt unless a key in Odoo's `L9_VERIFYING_KEYS_JSON` signed it, and that key may not be Odoo's own key id (Gate_SDK `gate/client.py` `activate`, around line 516). Odoo therefore needs Gate's verifying key even when `L9_REQUIRE_SIGNATURE` is off.

---

## 1. Key choice: ed25519 for Odoo's consumer key

**Decision:** Odoo signs with **ed25519**. Odoo gets its own key pair and never shares a secret with Gate.

Evidence:

| Fact | Source |
|---|---|
| The SDK client accepts `hmac-sha256` and `ed25519` | Gate_SDK 1.3.2 `security/signing.py` `sign_transport_packet` (line 77; ed25519 branch at line 99) |
| An ed25519 private key may be a PEM block or base64 of the 32-byte raw seed | Gate_SDK `security/signing.py` `_coerce_bytes` (line 17) and `_load_ed25519_private_key` (line 29) |
| A public key in a verifying map may be PEM or base64 of the 32 raw bytes | Gate_SDK `transport/hop_trace.py` `_load_ed25519_public_key` (line 70) |
| `L9_SIGNING_ALGORITHM` has no default in the client config. A key without it is refused: admission reports "a signing key is configured without an algorithm", and execute raises `GateConfigurationError` | Gate_SDK `gate/config.py:209` and `admission_problems` (`:114`); `gate/client.py` `_maybe_sign` |
| In staging and prod Gate refuses `hmac-sha256` for its own signing and signs with `ed25519` | Gate (fragment) `docs/contracts/score-operator-route.md` |
| Gate's deploy compose still runs dev with `hmac-sha256` and a shared secret | Gate (fragment) `constellation-gate/deploy/docker-compose.yml` |

Why ed25519:
1. Gate stores only Odoo's **public** key, so a leak of Gate's environment cannot forge Odoo traffic. HMAC would put the same secret in both places.
2. It matches Gate's own staging and prod posture, so one algorithm runs across the hub.
3. The SDK already supports it on both sides. No code change is needed.

**Open, Gate-side:** whether Gate's staging or prod configuration *refuses* an `hmac-sha256` **consumer** key. The excerpts confirm the refusal only for Gate's own key. ed25519 is correct in either case. If Gate does not refuse HMAC consumer keys, the reason above is security, not a requirement.

### Generating the key pair (operator workstation only)

Generate the keys outside every repository and every agent session. The private half lives **only** in Infisical project `cursor-governance` under the name `ODOO_GATE_SIGNING_KEY`. That name is new; section 6 covers registering it. Only the public half is printed.

```bash
umask 077
python3 - <<'PY'
import base64, pathlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization as s
k = Ed25519PrivateKey.generate()
raw_priv = k.private_bytes(s.Encoding.Raw, s.PrivateFormat.Raw, s.NoEncryption())
raw_pub = k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)
pathlib.Path("odoo_gate_signing_key.b64").write_text(base64.b64encode(raw_priv).decode())
print("public (base64, safe to share):", base64.b64encode(raw_pub).decode())
PY
# Store the contents of odoo_gate_signing_key.b64 in Infisical as ODOO_GATE_SIGNING_KEY,
# then delete the file:  shred -u odoo_gate_signing_key.b64
```

**Key id:** `odoo-scrapmanagement-v1`. A key id is an identifier, not a secret. Rotation adds `-v2` next to `-v1`, then retires `-v1`.

---

## 2. Settings, by location

### 2a. Gate process environment (Constellation.Gate, `constellation-gate/`)

| Variable | Value | Source |
|---|---|---|
| `L9_VERIFYING_KEYS_JSON` | Add one entry to the existing object: `"odoo-scrapmanagement-v1": "<Odoo public key, base64>"`. Keep every existing entry. | Gate (fragment) `deploy/README_DEPLOY.md`: "Consumers … are admitted by adding their key id to `L9_VERIFYING_KEYS_JSON` and a caller policy record in `L9_KEY_ALLOWED_ACTIONS_JSON`" |
| `L9_KEY_ALLOWED_ACTIONS_JSON` | Add one entry: `"odoo-scrapmanagement-v1": {"node": "odoo", "kind": "consumer", "tenants": ["scrapmanagement"], "actions": ["converge", "match"]}` | Gate (fragment) `src/constellation_gate/config/settings.py` `CallerPolicy`. The handoff states that extra keys are forbidden, `kind` is `consumer` or `worker`, and duplicates are refused. Same shape as the README example `{"odoo-e2e":{"node":"odoo","kind":"consumer","tenants":["plasticos"],"actions":["converge","match"]}}` |
| `L9_REQUIRE_SIGNATURE` | `true` | Gate (fragment) `deploy/README_DEPLOY.md`: one ingress trust boundary must be declared, either `L9_REQUIRE_SIGNATURE=true` with `L9_VERIFYING_KEYS_JSON` or a network boundary with evidence |

Constraints on Gate (fragments of `settings.py`):
- "In staging and prod every verifying key id must have [a policy record]." Adding the verifying key without the policy record makes Gate refuse to start in staging and prod.
- "`L9_KEY_ALLOWED_ACTIONS_JSON` names key ids not in `L9_VERIFYING_KEYS_JSON`" is a startup error. The policy record without the verifying key also fails.
- **Both entries ship in the same Gate deploy.** Neither one can go out alone.
- `"node": "odoo"` must equal Odoo's node name. Odoo forces it to `odoo` (`plasticos_gate/services/gate_config.py:338`, `ODOO_NODE_NAME`), whatever `L9_NODE_NAME` says.

Routing that Gate must already have:
- `converge` → `enrichment-engine`: shipped static registry `src/constellation_gate/config/node_registry.yaml` (fragment), which EIE's own registration overwrites.
- `match` → `graph` (CEG): from CEG's registration (Gate e2e report fragment: `graph` → actions `match, sync, outcomes, resolve`).

### 2b. Odoo system parameters (Settings → Technical → System Parameters, per database)

| Key | Value | Reader | Note |
|---|---|---|---|
| `plasticos.gate.org_id` | `scrapmanagement` | `gate_config.py:348` `resolve_tenant` | Seeded empty (`data/gate_icp_seed.xml:24`). When empty, the tenant falls back to the **database name**, which on Odoo.sh is not `scrapmanagement`. It must equal the `tenants` entry in Gate's policy. |
| `plasticos.gate.matching_enabled` | `1` (seeded) | `gate_config.py:164` | `0`/false turns matching off |
| `plasticos.gate.enrichment_enabled` | `1` (seeded) | `gate_config.py:169` | Must be truthy for converge. Keep it `0` until the smoke in §4 passes. |
| `plasticos.gate.matching_action` | `match` (seeded) | `gate_config.py:183` | Do not change |
| `plasticos.gate.enrichment_action` | `converge` (seeded) | `gate_config.py:184` | Do not change |
| `plasticos.gate.timeout_seconds` | `30` (seeded) | `gate_config.py:246` | Must be > 0 and ≤ 30 (`MAX_GATE_TIMEOUT_SECONDS`, `:97`). Any other value raises a permanent error and is not clamped. EIE caps converge at 25 s, which fits. |
| `plasticos.gate.auto_writeback` / `…_operator_approved` | `0` / `0` (seeded) | `gate_config.py:236` | Keep both at 0 so converge results land as `review` proposals. Partner writes need both set to 1. |
| `plasticos.gate.allow_insecure_http` | unset | `gate_config.py:114` | Leave unset. `GATE_URL` must be `https://`. |

Inert parameters: `plasticos.gate.signing_algorithm` (seeded `hmac-sha256`, `gate_icp_seed.xml:39`) and `plasticos.gate.verify_response_signatures` (`:43`) are **not read by any code**. Signing comes only from the process environment (`gate_config.py` module docstring, lines 1–15). Leave them alone, and do not treat them as the algorithm setting.

### 2c. Odoo process environment

Read by Gate_SDK `get_gate_client_config_from_env` (`gate/config.py:185`), which Odoo calls from `build_gate_client_config` (`gate_config.py:318`). Odoo overrides only `local_node`, the timeout, the 30 s ceiling and the destination pin. Gate_SDK reads every other value from the environment.

| Variable | Value | Note |
|---|---|---|
| `GATE_URL` | Gate's public `https://` base URL | Required. Operator supplies it. |
| `L9_NODE_NAME` | `odoo` | Overridden to `odoo` anyway (`gate_config.py:338`). Set it for clarity. |
| `L9_SIGNING_KEY` | Secret `ODOO_GATE_SIGNING_KEY` from Infisical (base64 ed25519 seed) | Never in the repository, a ticket, or chat |
| `L9_SIGNING_KEY_ID` | `odoo-scrapmanagement-v1` | Must equal Gate's map keys in §2a |
| `L9_SIGNING_ALGORITHM` | `ed25519` | **Required.** Without it Odoo cannot sign (see §1) |
| `L9_VERIFYING_KEYS_JSON` | `{"<Gate key id>": "<Gate public key>"}` | **Gate's** key, not Odoo's. The Gate operator supplies the id and public half. In staging and prod Gate signs with ed25519. |
| `L9_REQUIRE_SIGNATURE` | `true` | Also turns on verification of execute responses (`gate/config.py`: `verify_response_signatures` reads the same variable) |

---

## 3. Order of application

1. **Keys.** Generate Odoo's key pair (§1). Store the private half in Infisical. Hand the public half and the key id to the Gate operator, and get Gate's key id and public key in return.
2. **Gate policy.** In **one** Gate deploy, add Odoo's verifying key and its caller policy (§2a). Smoke check G.
3. **Odoo tenant.** Set `plasticos.gate.org_id = scrapmanagement`. Keep `plasticos.gate.enrichment_enabled = 0`.
4. **Odoo environment.** Set the seven §2c variables on the Odoo process and restart it. Smoke check O1.
5. **Admission.** Smoke check O2. This is the first call that crosses to Gate.
6. **Enable.** Set `plasticos.gate.enrichment_enabled = 1`. `matching_enabled` is already 1. Smoke check O3.

Gate refuses Odoo until step 2 has shipped. Odoo stays inert until step 4 is done. `enrichment_enabled` stays 0 until step 6, so no step leaves converge half-configured.

---

## 4. Smoke checks

**G (Gate).** With the Gate operator's access:
- Gate starts, so the policy and verifying-key maps are consistent.
- `GET <GATE_URL>/v1/ready` (Gate fragment `api/main.py`) returns `ready: true`, and its `actions` list resolves `converge` → `enrichment-engine` and `match` → `graph`. The `test_ready_endpoint.py` fragment asserts that shape.

**O1 (Odoo config, offline).** In `odoo-bin shell -d <db>` on the target build:

```python
from odoo.addons.plasticos_gate.services import gate_config as gc
print(gc.resolve_tenant(env))                              # -> scrapmanagement
cfg = gc.build_gate_client_config(env)
print(cfg.local_node, cfg.signing_key_id, cfg.signing_algorithm, sorted(cfg.verifying_keys))
print(cfg.admission_problems())                            # -> []
print(gc.classify_gate_availability(env, capability="matching").as_dict())
```

No line prints a key value. `admission_problems()` must print `[]`.

**O2 (admission, one signed call, no business payload):**

```python
from odoo.addons.plasticos_gate.services import gate_client as gcl, gate_config as gc
from constellation_node_sdk import GateClient
cfg = gc.build_gate_client_config(env)
r = gcl.ensure_admitted(GateClient(cfg), cfg, gc.resolve_tenant(env))
print(r.key_id, r.granted_actions)                         # -> odoo-scrapmanagement-v1, includes converge + match
```

Expected failures and what they mean:
- `GateConfigurationError`: a variable from §2c is missing.
- HTTP 400: Gate does not know the key id, or the signature is bad (wrong public key or algorithm).
- `action_not_permitted`: the policy is missing an action or the tenant.
- "not signed by a trusted Gate key": Odoo's `L9_VERIFYING_KEYS_JSON` holds the wrong Gate key id.

**O3 (end to end).** From the UI, run one converge on a test partner (enrichment) and one match on an Opportunity (`crm.lead.action_match_opportunity`). Expected: a run record with a Gate result. With `auto_writeback = 0` the converge proposal is `review`, and no partner fields change.

---

## 5. Open questions only the operator can answer

1. **How do environment variables reach an Odoo.sh build?** Odoo reads `GATE_URL` and `L9_*` from the process environment only (`gate_config.py:101`, the module docstring, and `plasticos_gate/README.md`: "The Gate URL comes from the process environment"). Odoo.sh's official docs describe no setting for custom process environment variables. The Settings page (`odoo/documentation` 19.0 `content/administration/odoo_sh/getting_started/settings.rst`) has none, and the advanced page documents only `/home/odoo/.config/odoo/odoo.conf` as server configuration (`advanced.rst:183`). `.env.example:60` says "Set the same names on Odoo.sh", but no file shows that this works. Before step 4, establish one of these:
   - (a) the mechanism the project already uses, if Odoo.sh support or the project's settings provide one; or
   - (b) the smallest supported alternative: ask Odoo.sh support whether a build-persistent environment for the Odoo server process exists.
   - If neither exists, the only in-repo alternative is a **code change** to read these values from `odoo.conf` options (`odoo.tools.config`). It would add a second configuration source, which `gate_config.py` deliberately forbids today ("No legacy aliases, no ICP Gate URL"), so it needs an ADR decision before anyone writes it. Do **not** put the key in an `ir.config_parameter`: the database is copied to staging and dev builds.
2. **Who holds Gate's deploy**, and therefore its environment and secret store? That person applies §2a and supplies Gate's key id, Gate's public key, and `GATE_URL`.
3. **Does Gate refuse an HMAC consumer key in staging/prod?** This does not change the decision (§1). Confirm it so the runbook can state it as a requirement.
4. **Which Odoo database(s) get the tenant.** Production and staging builds are separate databases, and each needs `plasticos.gate.org_id` set. A staging database sharing tenant `scrapmanagement` with production would reach the same Gate tenant; decide whether staging gets its own tenant and key.

---

## 6. Repository changes this wiring needs

| Change | Where | Status |
|---|---|---|
| This runbook | `docs/GATE_ODOO_WIRING.md` | This PR |
| `L9_SIGNING_ALGORITHM` passed through to the Odoo container. All three services in `docker-compose.yml` (around lines 70–76, 108–114, 149–155) list every `L9_*` variable except the algorithm, so a local stack cannot sign. Proposed line after each `L9_SIGNING_KEY_ID:` entry: `L9_SIGNING_ALGORITHM: ${L9_SIGNING_ALGORITHM:-}` | `docker-compose.yml` (protected file) | **Proposed, awaiting explicit operator approval** |
| `L9_SIGNING_ALGORITHM=ed25519` after `L9_SIGNING_KEY_ID=` in the Gate block | `.env.example:64` (protected file) | **Proposed, awaiting explicit operator approval** |
| Register `ODOO_GATE_SIGNING_KEY` in `root_env_keys` | Cursor-Governance `ops/secrets/infisical-cursor-governance.yaml` | Separate Cursor-Governance PR |
| Odoo consumer caller policy documented next to the `odoo-e2e` example | Constellation.Gate `deploy/README_DEPLOY.md` | Gate repository; not attachable from this session |
