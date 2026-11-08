# Rehearsal receipt

- verdict: `failed`
- evidence: `/Users/ib-mac/IB-Odoo_19 (LOCAL)/IB-Odoo_19/tests/production-rehearsal/evidence/2026-11-06_205618`
- log: `/Users/ib-mac/IB-Odoo_19 (LOCAL)/IB-Odoo_19/tests/production-rehearsal/evidence/2026-11-06_205618/rehearsal.log`
- failures: Gate1-branch-identity, Gate5-weblead-e2e, Gate6-erp-import, Gate7-skipped-erp-not-passed

The bearer token log is omitted. Database name and credential assignments are redacted.

## Gate files

### 00-staging-sha.txt

```
branch=Staging
HEAD=9ef95a4b09f5612d0886077d9e1974b65901fb32
origin/Staging=4f571cbd1b8fda3482d6fd9e63aead72476245b0
```

### 01-production-sha.txt

```
origin/Production=3318fa646a9f33aed55b9ea8f8596316e30684da
```

### 02-merge-tree.txt

```
origin/Production=3318fa646a9f33aed55b9ea8f8596316e30684da
origin/Staging=4f571cbd1b8fda3482d6fd9e63aead72476245b0
conflict_markers=0
---
5883be5e75db01a375cedc667384e0123fa23ec7
```

### 03-install-smoke.txt

```
bash scripts/install_smoke.sh
install-smoke evidence matches
install-smoke evidence matches; not upgrading
```

### 04-clone-census.txt

```
partner_census_before_import=0
```

### 04-weblead-health.json

```
{"status": "ok"}
```

### 04-weblead-result.json

```
{"status": "ok", "lead_id": "CG-rehearsal-hot-001", "web_lead_id": 1, "decision": "hot", "intake_id": 1, "partner_id": null, "state": "error", "error": "Expected singleton: res.users()"}
```

### verdict.txt

```
run_ts=2026-11-06_205618
staging_sha=9ef95a4b09f5612d0886077d9e1974b65901fb32
production_sha=3318fa646a9f33aed55b9ea8f8596316e30684da
verdict=failed
failures=Gate1-branch-identity Gate5-weblead-e2e Gate6-erp-import Gate7-skipped-erp-not-passed
```

## Failure lines from the log

```
  ❌ Gate 1 FAILED: not on Staging or ahead of origin
  ❌ Gate 5 FAILED: state=error error=Expected singleton: res.users()
  ❌ Gate 5 FAILED
Traceback (most recent call last):
  File "src/pymssql/_mssql.pyx", line 2005, in pymssql._mssql.maybe_raise_MSSQLDatabaseException
  File "src/pymssql/_mssql.pyx", line 2022, in pymssql._mssql.raise_MSSQLDatabaseException
pymssql._mssql.MSSQLDatabaseException: (18456, b"Login failed for user 'erp_reader'.DB-Lib error message 20018, severity 14:\nGeneral SQL Server error: Check messages from the SQL Server\nDB-Lib error message 20002, severity 9:\nTDS server connection failed (host.docker.internal)\nDB-Lib error message 20002, severity 9:\nTDS server connection failed (host.docker.internal)\n")
Traceback (most recent call last):
pymssql.exceptions.OperationalError: (18456, b"Login failed for user 'erp_reader'.DB-Lib error message 20018, severity 14:\nGeneral SQL Server error: Check messages from the SQL Server\nDB-Lib error message 20002, severity 9:\nTDS server connection failed (host.docker.internal)\nDB-Lib error message 20002, severity 9:\nTDS server connection failed (host.docker.internal)\n")
Traceback (most recent call last):
    raise SourcePayloadError(f"cannot connect to ERP database {source.label}: {type(exc).__name__}") from exc
odoo.addons.plasticos_partner_import.erp.reader.SourcePayloadError: cannot connect to ERP database host.docker.internal/[database]: OperationalError
make: *** [import-erp] Error 1
  ❌ Gate 6 FAILED
verdict=failed
```
