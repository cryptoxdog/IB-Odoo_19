# Audit Basis and Locked Conclusions

This pack was derived from the live `Staging` tree observed during planning and from the repository's own audit/governance surfaces.

## Locked conclusions

### 1. The ~980 Moderate count is not a work-item count

The extended audit emits Moderate findings from a small number of heuristic families. A large portion is expected to be assurance-tool noise rather than application defects.

### 2. Weak-test ownership is duplicated, and the scopes do not match

`scripts/audit/test_audit.py` and `ci/weak_test_fixer.py` use different definitions. The CI checker already recognizes bare `assert` and `pytest.raises` more accurately. It does not recognize `raise AssertionError(...)`. It treats non-assertion helper prefixes (`check_`, `_check_`, `validate_`, `_run_`, `_safe_`) as evidence. It walks only the repository `tests/` tree. The extended audit walks only direct `tests/test_*.py` children, including addon trees, and misses nested suites such as `tests/contracts/`.

### 3. Static model-name search is not runtime test coverage

`get_models_without_tests()` infers coverage from literal `self.env["model"]` references. This must not be treated as factual Odoo runtime coverage.

### 4. State bypass has a stronger existing owner

`ci/check_state_guard_bypass.py` is more semantically specific than the extended audit's `STATE_BYPASS` heuristic and already participates in CI.

### 5. `sudo()` policy exists, but its audit is shallow

Repository law requires explicit justification for privilege elevation. The Moderate scanner only looks for nearby comments and does not establish authorization ownership.

### 6. `UNBOUNDED_SEARCH` cannot be repaired by blindly adding `limit=1`

Search boundedness is a business-semantic property. Some complete searches are correct and must remain complete.

### 7. XPath checker guidance conflicts with canonical repo law

Canonical repo guidance requires named anchors and forbids positional selectors, while the current checker suggests `//notebook[1]` and `//sheet/notebook[1]`.

## Sealed prior campaign

Do not reopen unless a contradiction blocks execution:

- High N+1 runtime remediation
- High performance-scanner remediation
- High sensitive-logging scanner remediation
- transaction stored-profile correctness
- load cardinality
- facility uniqueness
- commission uniqueness
- High baseline contraction
