# 06 — Gate + EIE Deploy Runbook (converge-first) — OPS HANDOFF

Owner: platform/ops. Scope: bring the **converge** path live end-to-end so
`plasticos_gate` on Odoo staging can route `action=converge` → Constellation.Gate → EIE.
CEG / `action=match` is a follow-up (see §8).

> Status at handoff (2026-09): **code side complete.** EIE `handle_converge`
> is merged to `main` and green; the EIE image is published; the Gate routing
> table already owns `converge`. What remains is **runtime**: nothing is
> deployed yet and there is no live cluster.

---

## 1. Verified current state (evidence)

| Fact | Evidence |
|---|---|
| EIE converge handler merged to `main`, CI green (45/45) | PR #168 (superseded stale PR #128) merged `7d9e092c` |
| EIE image published | `Build & Push Image` success → `ghcr.io/quantum-l9/enrichment.inference.engine:main` |
| Trivy/SBOM main CI green | PR #169 (lowercase OCI ref) merged; `docker-build` on `main` fully green |
| Gate routes converge → EIE | `constellation-gate/src/constellation_gate/routing/action_ownership.py`: `CANONICAL_ACTION_OWNERS = {"converge": "eie", ...}` (ADR + tests) |
| Odoo consumer wired | `plasticos_gate` emits `action=converge`; `plasticos_enrichment` tries Gate → local fallback (default ON, auto-writeback ON) |
| Odoo staging reachable | SSH `36097692@cryptoxdog-ib-odoo-19-staging-36097692.dev.odoo.com` → `SSH_OK` |
| **No Gate/EIE/CEG deployed** | C1 (`46.62.243.82`) runs only `graphiti-mcp-cursor` + `graphiti-neo4j-cursor` behind Caddy (`memory.quantumaipartners.com`). No gate/eie/ceg containers, no on-disk checkouts. |
| **No live cluster** | `k3s` present but `inactive` on C1; no `~/.kube/config`; no `KUBECONFIG` secret in the EIE/Gate repos |

Because nothing is deployed, there is **no Gate hub URL** to set as `plasticos.gate.url` yet. Deploy first, then §6–§7.

---

## 2. Choose a deploy target

The repos ship a `k8s-deploy.yml` (Helm, `workflow_dispatch`, needs `secrets.KUBECONFIG`) **and** a `deploy/docker-compose.yml`. Two supported paths:

- **Path A — docker-compose on C1** (lowest friction; C1 already has docker + Caddy + the OpenAI/SDK secrets). Recommended for converge-first.
- **Path B — k3s/Helm** (activate `k3s` on C1 or provision a cluster, export `KUBECONFIG`, add it as a repo secret, then dispatch `k8s-deploy.yml`). Use if you want the full Helm path/parity with prod.

The rest of this runbook documents **Path A** (converge-first). Path B is a straight `gh workflow run k8s-deploy.yml -f environment=staging` once `KUBECONFIG` exists.

---

## 3. Prerequisites / secrets

Gather on the deploy host (C1) into an env file (never commit):

- `OPENAI_API_KEY` — already present on C1 (`~/.cursor/graphiti.env`), or supply a service key.
- Gate SDK token — EIE/Gate repo secret `SDK_TOKEN` (used by `constellation-node-sdk`).
- Neo4j creds — C1 already runs neo4j (`graphiti-neo4j-cursor`, `bolt://127.0.0.1:7687`); EIE may reuse or get its own instance.
- Postgres/Redis for EIE — provision alongside (EIE tests use pg16 + redis7).

Confirm the exact required env by reading each repo's `deploy/docker-compose.yml` and `scripts/entrypoint.sh` before bring-up.

---

## 4. Bring up the Gate hub (C1, docker-compose)

```bash
ssh -i ~/.ssh/Hetzner-C1-nopass root@46.62.243.82
git clone https://github.com/Quantum-L9/Constellation.Gate /opt/constellation-gate
cd /opt/constellation-gate/constellation-gate
# populate .env from §3, then:
docker compose -f deploy/docker-compose.yml up -d
# Gate listens on :9000 (HOST=0.0.0.0). Verify:
curl -fsS http://127.0.0.1:9000/healthz || docker compose logs --tail=100
```

Expose via Caddy (append to `/etc/caddy/Caddyfile`, then `systemctl reload caddy`):

```
gate.quantumaipartners.com {
    encode gzip
    reverse_proxy 127.0.0.1:9000
}
```

(Ensure DNS `gate.quantumaipartners.com` → C1 before the TLS handshake.)

---

## 5. Bring up EIE and register it with the Gate

```bash
# On C1: run the published image (or clone + compose)
docker pull ghcr.io/quantum-l9/enrichment.inference.engine:main
# Provide EIE env: OPENAI_API_KEY, SDK_TOKEN, GATE_URL=http://127.0.0.1:9000,
# postgres/redis/neo4j DSNs. EIE registers with the Gate advertising
# supported_actions=["converge"], owner=eie (matches CANONICAL_ACTION_OWNERS).
docker run -d --name eie --env-file /opt/eie.env \
  ghcr.io/quantum-l9/enrichment.inference.engine:main
```

Confirm registration on the Gate (routing is registration-based):

```bash
# Gate should now show a node owning "converge". Check Gate logs / admin route:
docker logs constellation-gate 2>&1 | grep -i "converge\|register\|eie"
```

---

## 6. Point Odoo staging at the Gate

```bash
ssh 36097692@cryptoxdog-ib-odoo-19-staging-36097692.dev.odoo.com
# In the Odoo.sh staging shell:
odoo shell -d <staging_db> <<'PY'
icp = env['ir.config_parameter'].sudo()
icp.set_param('plasticos.gate.url', 'https://gate.quantumaipartners.com')
# Phase-1 defaults already seeded by plasticos_gate:
#   plasticos.gate.enrichment_enabled = 1   (converge live)
#   plasticos.gate.enrichment_action  = converge
#   plasticos.gate.auto_writeback     = 1
#   plasticos.gate.matching_enabled   = 0   (leave OFF until CEG is live)
print('gate.url =', icp.get_param('plasticos.gate.url'))
env.cr.commit()
PY
```

---

## 7. End-to-end validation (converge)

1. Pick a partner with blank allowlisted fields on staging.
2. Trigger a `plasticos.enrichment.run` for it (UI action or `action_execute`).
3. Expected on success: `engine_used == "gate"`, `state == "injected"`, provenance
   rows `source_sentence = gate_converge:<packet_id>`, and only blank allowlisted
   fields backfilled (merge-not-overwrite).
4. Cross-check the Gate + EIE logs show the `converge` packet round-trip.

### Failure matrix (all must degrade safely, never corrupt data)

| Condition | Expected Odoo behavior |
|---|---|
| Gate URL unreachable | Exception caught → **local enrichment fallback**; no false "injected" |
| EIE returns non-`ok` status | `_run_gate_converge` returns False → **local fallback** |
| EIE returns `ok` but no writable allowlisted fields | returns False → **local fallback** (no empty "injected") |
| `auto_writeback=0` | proposal stored, `state=review`, awaits human |

---

## 8. Follow-up: CEG / `action=match`

Same pattern: deploy CEG (owner `ceg`, `supported_actions=["match","sync","outcomes"]`),
confirm Gate registration, then flip `plasticos.gate.matching_enabled=1` on staging and
validate the matcher's Gate→local fallback. Keep matching OFF until CEG is verified.

---

## 9. Open infra asks (blockers for whoever runs this)

- Decide Path A (docker-compose/C1) vs Path B (k3s/Helm + `KUBECONFIG` secret).
- DNS for `gate.quantumaipartners.com` (and `eie.*` if externally exposed) → deploy host.
- EIE datastore provisioning (postgres/redis; neo4j reuse vs dedicated).
- Confirm which OpenAI/SDK credentials the deployed services should use.
