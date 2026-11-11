# Regression Guard: Source and Runtime Separation

Portable source checks from an extracted release root (use a system Python with stdlib):

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests_offline -v
python -B tools/validate_package.py --verify-manifest
```

The ZIP builder reruns the portable suite and static checks, then verifies complete manifest member SHA-256 digests and ZIP CRC. The build is a **source** gate only.

Preserve these cases: no admission without evidence; immutable review and feedback; unknown is not zero; MFI requires its test conditions; no economic claims; no invented rejection alias; cross-company source authorization; source ID parsing; approved guidance still needs applicable current source scope; incomplete knowledge retrieval must be visible; ambiguous approved rejection references must abstain; Web Lead `off` must preserve parent signals and `shadow_only` cannot decide HOT/REVIEW/COLD.

Runtime checks MUST use the actual pinned repository's configured Odoo 19 Enterprise test harness and a disposable test database, then inspect installation and upgrades. No deployment commands or fabricated runtime receipts are provided.

**Expected:** 49 portable unit tests pass on this revised source, recorded afresh in `BUILD_MANIFEST.json`; the native Odoo tests are authored but remain **NOT RUN** in this environment.

## Architecture-alignment guards

The portable tests now additionally assert feedback identity is deterministic, distinguishes legal-company contexts and rejects ambiguous delimiter encodings. On a disposable Odoo 19 database, the knowledge tests assert that edited review inputs clear attestation, company-scoped lookup uses only the source company, and source IDs are not coerced from booleans/floats. The latter are authored tests, **not run** in this source-only environment. Verify rollback-safe optional shadow queries with an actual DB error.
