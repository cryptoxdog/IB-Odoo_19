

A️⃣ PRODUCTION READINESS CHECKLIST
Create:

Plasticos/docs/PRODUCTION_READINESS.md

# PlasticOS Production Readiness Checklist

## 1. Database
- [ ] Postgres version ≥ 14
- [ ] Autovacuum enabled
- [ ] WAL archiving configured
- [ ] Daily backup verified (restore test completed)
- [ ] Indexes present:
    - l9_trace_run.run_id
    - l9_trace_run.correlation_id
    - plasticos_intake.partner_id
    - plasticos_intake.polymer
    - plasticos_intake.form

## 2. Odoo
- [ ] All Plasticos modules installed cleanly
- [ ] No module in "to upgrade" state
- [ ] No missing access rules
- [ ] Test suite passes green
- [ ] Replay test executed successfully

## 3. L9 Adapter
- [ ] l9.endpoint_url configured
- [ ] l9.api_key configured
- [ ] l9.environment configured
- [ ] Idempotency enforced
- [ ] Normalization gate enforced
- [ ] Packet_version locked

## 4. Trace System
- [ ] Trace runs created per adapter call
- [ ] Span count > 0
- [ ] Error events logged properly
- [ ] Health cron active

## 5. Documents
- [ ] Missing docs dashboard working
- [ ] Critical doc gating tested
- [ ] POD flow tested

## 6. Linda
- [ ] Dispatch lifecycle transitions tested
- [ ] State changes traced
- [ ] No silent transitions

## 7. Accounting
- [ ] Invoice gating rules verified
- [ ] Vendor bill matching tested
- [ ] No auto-posting without required docs

## 8. CI
- [ ] Pre-commit hooks active
- [ ] GitHub CI passing
- [ ] No forbidden network calls outside adapter

## 9. Replay Validation
- [ ] Full transaction replay test executed
- [ ] Matrix material test executed
- [ ] Ranked buyers returned
- [ ] Score range validated (0-1)

## 10. Final Gate
- [ ] Production database snapshot taken
- [ ] Schema freeze tag created
- [ ] Git tag pushed (v1.0-prod)
B️⃣ LIVE HEALTH DASHBOARD MODULE
New module:
