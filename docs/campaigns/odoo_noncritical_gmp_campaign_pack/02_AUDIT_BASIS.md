# Audit Basis and Locked Conclusions

This pack was derived from the live `Staging` tree observed during planning and from the repository's own audit/governance surfaces.

## Locked conclusions

### 1. The ~980 Moderate count is not a work-item count

The extended audit emits Moderate findings from a small number of heuristic families. A large portion is expected to be assurance-tool noise rather than application defects.

### 2. Weak-test ownership is duplicated, and the scopes do not match

`scripts/audit/test_audit.py` and `ci/weak_test_fixer.py` use different definitions. The CI checker already recognizes bare `assert` and `pytest.raises` more accurately. It does not recognize `raise AssertionError(...)`. It treats non-assertion helper prefixes (`check_`, `_check_`, `validate_`, `_run_`, `_safe_`) as evidence. It walks only the repository `tests/` tree. The extended audit walks every `tests/test_*.py`, including addon trees.

### 3. Static model-name search is not runtime test coverage

`get_models_without_tests()` infers coverage from literal `self.env["model"]` references. This must not be treated as factual Odoo runtime coverage.

### 4. The two state checks ask different questions

`ci/check_state_guard_bypass.py` flags `.write({'state': ...})` on models that define `_validate_state_transition` when `bypass_state_guard` is absent, including XML server actions. The extended `STATE_BYPASS` heuristic flags `self.write({'state': ...})` on any model with a Selection `state` or `status`, outside `action_*`, pipeline methods, and methods whose context contains "State transitions." The CI check is the better owner of the guard. It is not a superset of the Moderate heuristic. Delete `STATE_BYPASS` only after a containment proof.

### 5. `sudo()` policy exists, but its audit is shallow

Repository law requires explicit same-line justification for privilege elevation. The Moderate scanner looks for a comment containing `sudo` on one of the three lines above the call, so a same-line justification does not count, and its suggested fix is to add a comment. A comment is not authorization. A justified elevation may remain. `UNKNOWN` blocks closure and does not authorize a silencing comment.

### 6. `UNBOUNDED_SEARCH` cannot be repaired by blindly adding `limit=1`

Search boundedness is a business-semantic property. Some complete searches are correct and must remain complete. The current heuristic also excuses queries by variable-name spelling, a nearby `batch` comment, and any `'in'` domain. Those exemptions are not an intent model. Replace them inside `check_unbounded_searches` only. Leave `check_n_plus_one_queries` to the High scanner slice.

### 7. XPath checker guidance conflicts with canonical repo law

Canonical repo guidance requires named anchors and forbids positional selectors. The checker suggests `//notebook[1]` and `//sheet/notebook[1]`, and its safe-pattern list treats `//notebook[1]` as already safe. Guidance and that whitelist change together. `UNSCOPED_LIST_FIELD` is a `//list/field[@name=...]` scoping repair, not a notebook anchor. High class-based positional guidance stays sealed and is reported, not repaired here.

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
