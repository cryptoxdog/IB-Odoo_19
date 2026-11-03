# v1.1 improvements over v1.0

1. **Five Enterprise clone runs -> one combined CRM lane** using the runner's proven comma-separated scope; only isolate failed tests when diagnostic value justifies the extra clone. Historical transaction/PR303 tests are not transplanted.
2. **Correct native receipt semantics:** repo's JSON receipt does not contain image/PG/Enterprise identity or method census. Require independent image/DB pre/post attestation and parsed method IDs from raw logs.
3. **No unsafe `status` assumption:** `test_env.sh status` performs `compose up` and `compose build`. A preexisting Docker image does not prove cache-only behavior. Harden preflight to fail closed if no-mutation assurance is unprovable.
4. **Native guarded real import invocation:** confirmed `test_env.sh run <clone> -- make import-vanillasoft ODOO_DB_NAME=<clone> VANILLASOFT_CALL_FLOOR=... VANILLASOFT_CONTACT_FLOOR=...`, rather than an unguarded `make import-vanillasoft` that can hit a different DB/runtime.
5. **Source gap containment:** historical `/Contacts` restriction blocks full-census acceptance only; static, pure and independent ORM probes can still complete. A provider sample is not a full source inventory.
6. **Actual user intent separation:** approved 96-field dispositions vs 44 pending, canonical multi-material profiles, existing ERP-person integrity, owner login, full-history identities and run-status truth. Zero authorization to remap optional fields.
7. **Bounded execution + two verdicts:** one independent discovery pass and one verification pass; output distinguishes `DIAGNOSTIC` from `CRM_PROMOTION` (source completeness and business correctness).
8. **Run-ready structural validator:** `validate_results.py` checks all original behavior IDs, statuses, evidence locators, missing proofs, and source ledger shape without claiming tests actually ran. Nothing is silently marked green.
9. **Privacy hardened:** local raw logs and private ID joins stay private, exported material uses HMAC tokens, a redacted report, and explicit secret/PII inspection before sharing.
