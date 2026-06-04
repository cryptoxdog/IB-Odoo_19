# ADR-007: Deployment Architecture

**Status:** Accepted  
**Date:** 2026-03-17  
**Deciders:** Igor Beylin  
**Scope:** PlasticOS infrastructure and deployment  
**Related:** [ADR-006](ADR-006-module-installation-and-display.md), [ARCHITECTURE.md](../../ARCHITECTURE.md)

## Context

PlasticOS runs on Odoo 19 and needs deployment environments for:

1. **Local development** — Fast iteration, debugging, testing
2. **Staging** — Pre-production validation
3. **Production** — Live customer-facing system

The question: How do we configure and deploy Odoo across these environments, and what controls worker scaling, memory limits, and cron scheduling?

## Decision

**Use Odoo.sh for staging and production. Use Docker Compose for local development only.**

### Environment Architecture

| Environment | Platform | Configuration Source | Worker Control |
|-------------|----------|---------------------|----------------|
| Local Dev | Docker Compose | `docker-compose.yml` | Manual (`--workers=N`) |
| Staging | Odoo.sh | Platform + `odoo.conf` | Odoo.sh dashboard |
| Production | Odoo.sh | Platform + `odoo.conf` | Odoo.sh dashboard |

### Local Development (Docker)

```yaml
# docker-compose.yml controls local behavior
command: >
  --workers=2
  --max-cron-threads=1
  --limit-time-cpu=60
  --limit-time-real=120
  --limit-memory-hard=2684354560
  --limit-memory-soft=2147483648
```

**Process model (5 processes):**

- 1 master process
- 2 HTTP workers (`--workers=2`)
- 1 gevent worker (longpolling)
- 1 cron worker (`--max-cron-threads=1`)

**Database:** Local PostgreSQL container (`postgres:15`)

### Odoo.sh (Staging & Production)

Odoo.sh **ignores** `docker-compose.yml` entirely. It manages:

| Setting | How Controlled |
|---------|---------------|
| Worker count | Odoo.sh dashboard → Settings → Resources |
| Cron threads | Platform-managed based on plan tier |
| Memory limits | Container size per subscription tier |
| Database | Odoo.sh managed PostgreSQL |
| Backups | Automatic daily + manual snapshots |
| SSL/TLS | Automatic via Odoo.sh |

**What Odoo.sh reads from repo:**

- `odoo.conf` (if present) — some settings honored, workers typically overridden
- Module code in addons paths
- `requirements.txt` for Python dependencies

**What Odoo.sh ignores:**

- `docker-compose.yml`
- `Dockerfile`
- Local `.env` files

### Configuration Files

| File | Purpose | Used By |
|------|---------|---------|
| `docker-compose.yml` | Local dev orchestration | Docker only |
| `Dockerfile` | Local container build | Docker only |
| `odoo.conf` | Odoo server settings | Both (limited on Odoo.sh) |
| `config/odoo.conf` | Mounted config for Docker | Docker only |

### Branch → Environment Mapping (Odoo.sh)

| Branch | Environment | Auto-deploy |
|--------|-------------|-------------|
| `Production` | Production | Yes |
| `Staging` | Staging | Yes |
| Feature branches | Development builds | On push |

> Repo canonical branches are **`Staging`** and **`Production`** (capitalized). Odoo.sh project settings must match.

## Consequences

### Positive

1. **Separation of concerns** — Local dev config doesn't affect production
2. **Platform-managed scaling** — Odoo.sh handles worker optimization
3. **Consistent deployments** — Git-based deployment via Odoo.sh
4. **Automatic SSL/backups** — No manual infrastructure management

### Negative

1. **Config divergence** — Local settings may not match production exactly
2. **Limited control** — Can't fine-tune workers beyond Odoo.sh dashboard
3. **Vendor lock-in** — Tied to Odoo.sh platform for hosting

### Mitigations

1. **Test on staging** — Always validate on Odoo.sh staging before production
2. **Document differences** — This ADR captures environment differences
3. **Use `odoo.conf`** — For settings that Odoo.sh does honor

## Verification

### Local (Docker)

```bash
# Start services
docker compose -p odoo19 up -d

# Verify worker count (expect 5)
docker exec odoo19-odoo-1 ps aux | grep odoo | grep -v grep | wc -l

# Check health
curl -s -o /dev/null -w "%{http_code}" http://localhost:8069/web/health
```

### Odoo.sh

1. Check Odoo.sh dashboard → Builds → verify deployment status
2. Check Odoo.sh dashboard → Settings → Resources → verify worker allocation
3. Check Odoo.sh dashboard → Logs → verify no startup errors

## References

- [Odoo.sh Documentation](https://www.odoo.sh/documentation)
- `docker-compose.yml` — Local development configuration
- `config/odoo.conf` — Server configuration template
