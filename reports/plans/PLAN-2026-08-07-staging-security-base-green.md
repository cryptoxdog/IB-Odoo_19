## PLAN: Unblock Staging Odoo.sh green load after mothball + recent merges

### Objective
Clear Staging registry/load failures so tip (through #145/#146) rebuilds green: remove phantom plasticos_buyer_match_engine from live DB state, land PR #146 (module-order + version alignment), and prove plasticos_security_base loads on Odoo.sh Staging.
**Success:**
- PR #146 CI green (CI Gate + Baseline Ratchet)
- Live Staging SSH: plasticos_buyer_match_engine state != installed (uninstalled/absent)
- Live Staging odoo.log has zero ERROR lines for plasticos_buyer_match_engine after rebuild
- Odoo.sh Staging card on tip commit shows build 19.0 success (not failed on plasticos_security_base)
- Local ODOO_ENTERPRISE_MODULES=none make install-smoke still PASS on tip

### Scope
**In:** PR #146 feat/staging-version-align (module order, matching depends, versions, install-smoke), tests/test_mothball_migration.py version assertion drift, Additive migration/hook to mark deleted local-intelligence modules uninstalled on upgrade, Staging SSH verify + Odoo.sh rebuild evidence, plasticos-odoo-docker-testing / INSTALL_SMOKE runbook cross-links if needed
**Out:** Reintroducing plasticos_buyer_match_engine or plasticos_inference_engine, Local matcher/Neo4j Stage-1 scoring, Production promote, Automatic destructive mothball coordinator uninstall, Enterprise-only plasticos_documents_native force-install in Docker smoke

### Pre-Validation (mandatory)
| Check | Command / action | Pass criteria | Status |
|-------|------------------|---------------|--------|
| P0 | SSH Staging 35033335@cryptoxdog-ib-odoo-19-staging-35033335.dev.odoo.com — git log + odoo-bin shell module inventory | Evidence captured: HEAD=87715b2 (#140); buyer_match_engine state=installed but ABSENT on disk; continuous odoo.log ERROR | passed |
| P1 | gh pr view 146 + gh run view failed CI logs | Identify CI blocker test_mothball_migration::test_matching_version_bumped_for_migration expects 19.0.3.0.0 vs manifest 19.0.3.0.1 | passed |
| P2 | Local Docker install-smoke on feat/staging-version-align (prior session) | install-smoke PASSED with 25 modules including matching/enrichment/security_base (fresh DB) | passed |
| P3 | make pr-check on tip (planning bind — not re-run this turn) | Will fail until T1 (mothball test) fixed; treat as known red | failed |

### TODO Plan
| # | Task | Files | Effort | Risk | Deps | Leverage |
|---|------|-------|--------|------|------|----------|
| T1 | Replace hardcoded mothball version pin with >= 19.0.3.0.0 floor using stdlib tuple parse in test_mothball_migration.py | tests/test_mothball_migration.py | S | low |  | 1 |
| T2 | Add additive upgrade migration (prefer plasticos_base early in graph) that SETs ir_module_module.state='uninstalled' for deleted modules plasticos_buyer_match_engine (+ inference if ever installed) and clears stale dependency rows; bump owning module version | plasticos_base/__manifest__.py, plasticos_base/migrations/<new_version>/pre-migrate.py, docs/runbooks/MOTHBALL_LOCAL_INTELLIGENCE.md | M | high | T1 | 2 |
| T3 | Push T1+T2 onto feat/staging-version-align; confirm CI Gate + Baseline Ratchet green; merge #146 into Staging | feat/staging-version-align, PR #146 | S | medium | T1, T2 | 3 |
| T4 | After Staging rebuild: SSH new/live build — verify git tip, buyer_match uninstalled, no buyer_match ERROR in odoo.log, security_base/matching/enrichment/crm_sync installed as expected | .cursor/rules/98-odoo-sh-staging.mdc, .claude/skills/plasticos-odoo-sh-deploy/references/ssh-diagnose.md | S | medium | T3 | 4 |
| T5 | Contingency NotApplicable if tip green after T4; else SSH failed-build update.log within 24h; root-cause fix; re-smoke; push | plasticos_security_base/, plasticos_logistics/, Unknown until traceback | M | high | T4 | 5 |

### Critical Path
T1 -> T2 -> T3 -> T4

### Stress Test
- Disconfirming: Is the Odoo.sh card failure on plasticos_security_base actually caused by the buyer_match phantom, or a separate ParseError only visible on tip upgrade dumps?
- Disconfirming: Would marking buyer_match uninstalled via SQL leave orphan ir.model / ir.model.data that break security_base or matching?
- Disconfirming: Does a fresh Odoo.sh Staging DB (no dump) already pass tip without T2, making T2 Staging-dump-specific only?
- Disconfirming: Could auto_install matching/enrichment on tip pull a dependency that fails security_base attribution incorrectly?
- Blast radius: Staging rebuild + plasticos_base migration on every upgrade environment; incorrect uninstall SQL could strand xmlids or hide real depends; CI pin change affects mothball contract tests
- Rollback: Revert T2 migration commit; Staging can stay on last green build 35033335; do not promote Production; keep buyer_match row if uninstall proves unsafe and instead document rebuild-from-scratch

### Leverage
- Ranked: T1, T2, T3, T4, T5

### Convergence
- status: partial
- next_skill: l9-gmp-protocol
- stop_reason: Recursive Alignment pass: dual-SSOT ownership + critical_path T1-T4; planning-only until Build. U1/U2 remain probe.

_Projection of PLAN_DOCUMENT — validate JSON before treating as ready._
