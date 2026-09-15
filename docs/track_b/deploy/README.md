# Seam deploy bundle — box `EIE-CEG-GATE`

Single-box Docker Compose for the PlasticOS external intelligence seam:
**Gate hub + CEG (graph) + EIE (enrichment-engine)**, edge-terminated by Caddy.

## Contract (from Constellation.Gate `node_registry.yaml`)
| Service | Node name | Port | Health | Actions |
|---|---|---|---|---|
| gate | gate | 9000 | `/v1/health`* | routes only |
| graph (CEG) | graph | 8000 | `/v1/health` | match, sync, outcomes, resolve |
| enrichment-engine (EIE) | enrichment-engine | 8000 | `/api/v1/health` | converge, enrich, enrich-and-sync |

\* Gate health path assumed `/v1/health` (L9 chassis) — verify on first boot.

## Provisioning (executed at reimage, step c1/c2)
1. Hetzner: rename server label -> `EIE-CEG-GATE`; reimage Ubuntu 24.04 (arm64); re-apply SSH key.
2. `hostnamectl set-hostname EIE-CEG-GATE`
3. Install Docker engine + compose plugin.
4. `mkdir -p /opt/seam && cd /opt/seam` then fresh-clone (main, which now pins SDK `@v1`):
   - `git clone https://github.com/Quantum-L9/Constellation.Gate`
   - `git clone https://github.com/Quantum-L9/Cognitive.Engine.Graphs`
   - `git clone https://github.com/Quantum-L9/Enrichment.Inference.Engine`
5. Copy `docker-compose.yml`, `Caddyfile`, `.env.example` -> `/opt/seam`; fill `.env` from Infisical + generated datastore passwords.
6. `docker compose build --pull --no-cache gate graph enrichment-engine`  (native arm64; `--no-cache` guarantees the moving `@v1` tag is re-pulled)
7. `docker compose up -d`
8. Cloudflare: A record `gate.quantumaipartners.com` -> box IP (Caddy issues LE cert).

## Health / routing verification (step c3/c4)
- `docker compose ps` — all healthy
- CEG: `docker compose exec graph curl -s localhost:8000/v1/health`
- EIE: `docker compose exec enrichment-engine curl -s localhost:8000/api/v1/health`
- Gate registry: confirm `graph` + `enrichment-engine` self-registered (Gate admin/registry endpoint)
- External: `curl https://gate.quantumaipartners.com/v1/health`

## Signatures
All sides run `L9_REQUIRE_SIGNATURE=true` (hmac-sha256) with one shared `SEAM_HMAC_SECRET`.
First-boot fallback for debugging only: set `L9_REQUIRE_SIGNATURE=false` on gate/graph/enrichment-engine
AND leave Odoo unsigned (`plasticos.gate.signing_key_id` empty) + Gate `L9_TRUSTED_INGRESS_BOUNDARY=network`.

## Odoo staging wiring (step c5)
Set on Odoo.sh staging ICP:
- `plasticos.gate.url = https://gate.quantumaipartners.com`
- `plasticos.gate.signing_key_id = odoo-v1`  (+ env `PLASTICOS_GATE_SIGNING_KEY = <SEAM_HMAC_SECRET>`)
- `plasticos.gate.auto_writeback = 1`  (to exercise live converge writeback in §7 e2e)
Then run the §7 end-to-end check in `docs/track_b/04_odoo_gate_consumer_wiring.md`.

## Caveats to verify on first boot
- Gate health path (`/v1/health` assumed).
- `neo4j:5-enterprise` arm64 image availability on aarch64.
- EIE `API_KEY_HASH` format (hash, not raw key).
