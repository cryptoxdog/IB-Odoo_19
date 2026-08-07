# Staging Ladder — Docker Before Odoo.sh

## Promotion sequence

```text
1. Local Docker install-smoke PASS (this skill)
2. make pr-check (includes smoke + pytest + audit)
3. PR → Staging (capital S)
4. Odoo.sh Staging rebuild — expect build 19.0 success
5. Only if still red: plasticos-odoo-sh-deploy SSH → update.log
6. Production promote from green Staging — never feature → Production
```

## Why Docker first

- Odoo.sh build cards show `At least one test failed when loading the modules (X)`
  with little XML detail.
- Local smoke reproduces `-i` / upgrade load with full logs in `/tmp`.
- Module-order drift (Gate shells excluded locally but auto_install on Staging)
  is invisible without Docker smoke using `--all-installable`.

## Branch names

`Staging` / `Production` (capitalized). macOS case-fold can mask lowercase
checkouts — always verify `git rev-parse --abbrev-ref HEAD`.

## Do not claim green until

| Claim | Evidence required |
|-------|-------------------|
| Local load green | `✅ install-smoke PASSED` + module state list |
| Staging green | Odoo.sh Staging card `build 19.0 success` on tip commit |
| Gate architecture intact | matching/enrichment installed; buyer_match/inference **absent** |

## Related skills / docs

- `plasticos-odoo-sh-deploy` — SSH diagnose after local green
- `docs/runbooks/INSTALL_SMOKE.md` — short operator runbook
- `docs/adr/ADR-002-gate-hub-phased-autonomy.md` — Gate hub topology
