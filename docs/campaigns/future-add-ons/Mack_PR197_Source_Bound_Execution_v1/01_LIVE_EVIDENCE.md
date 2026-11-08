# Source and GitHub review evidence | 2026-10-15

## Exactly observed

- Repository `cryptoxdog/IB-Odoo_19`, default `Staging` at `3c24976576185c7a59b10ff7a837dd1ed93344ee`. **Not Mack's base.**
- PR [#197](https://github.com/cryptoxdog/IB-Odoo_19/pull/197) OPEN, non-draft, currently GitHub-mergeable, 23 added files, 6 commits, 2,410 additions. `mack@7dcada49fd301d3b5dafb30405d0242667915fbe` -> `Development@3318fa646a9f33aed55b9ea8f8596316e30684da`. `Production` also currently at `3318fa...` but is *not* this PR's authorized destination.
- #197 comment by repository operator dated 2026-09-30: **DO NOT MERGE**. This remains a hard human hold independent of GitHub mergeability.
- Codex review at `7dcada4` has exactly **two unresolved non-outdated threads** as observed:
  1. `tests/runtime_gates/run_mack_chat_intent_concurrency.py:47`: missing `tests/runtime_gates/_runtime_env.py`; `_mack_runtime.py` imports its DB/PG constants and both runners import `bind_config`. Confirmed absent from Mack and Development branch. Present on modern Staging at blob `7370d9cd4cdbf44b48dd11fd95f9408173cbc056`; Staging's helper includes unrelated F1-specific logic, so do not transplant wholesale.
  2. `plasticos_mack_workbench/models/internal_review.py:228`: `_check_request_shape()` evaluates regex against `(record.decision_snapshot_hash or "").strip()` but stores the unstripped value. A padded digest may be stored as an invalid literal SHA-256. Fix at existing validator owner, not in downstream consumers.
- #197 check-run result observed for the exact head: Pure Python, Static Analysis, Ruff, Secret Detection, GitGuardian success; **Enable Auto-Merge failure**. The check list did not demonstrate live Odoo module or Mack concurrency execution. CodeRabbit skipped automatic review because its branch selection did not include `Development`; do not count it as substantive approval.
- `plasticos_mack_workbench/__manifest__.py`: `19.0.1.1.0`; requires `mail` and `plasticos_intake`; no Enterprise Documents dependency. `models/__init__.py` and `tests/__init__.py` register Mack files/test classes.
- `tests/runtime_gates/run_mack_review_concurrency.py`: gates M1 same-idempotency-key race and M2 one active route per company, relies on `_mack_runtime.py` and `_runtime_env.py`.
- `tests/runtime_gates/run_mack_chat_intent_concurrency.py`: I1 same native message race and I2 receipt replay after later intake edit, same missing helper.
- `mack` and `Development` Makefile blob `2d72ca167fa59f514737c745b5ca4a57fe6d15da` has `make push`, `make pr-check`, `make test-module`; **no `make pr`**. The present Staging Makefile is different. Odoo's modern `make pr` semantics are not retroactively available on Mack's old branch.

## Source bindings used by the proposed local repair

| Repo path | Exact current blob SHA | Repair |
|---|---|---|
| `plasticos_mack_workbench/models/internal_review.py` | `d17eba9c3599aeaa077b7cdd28d87c3667bc3890` | Exact regex validation, no trimming |
| `plasticos_mack_workbench/tests/test_internal_review.py` | `c8bf98419ce8528e2707ecb03adf846cc44223d0` | Literal SHA-256 negative cases |
| `tests/runtime_gates/_runtime_env.py` | **absent** on Mack head | New smallest missing helper only |
| `plasticos_mack_workbench/__manifest__.py` | `7ce7e542af8ec4f9d2bb6976cdcff66d342d4148` | Monotonic module version `19.0.1.1.1` |

The generator demands the branch/head/blobs/clean state before emitting a patch, and Git checks application to the current worktree. It does not say GitHub was updated.

## Unknown / not yet proven

- Actual target-native Odoo model tests on PR #197's exact head or patched revision, as distinct from GitHub's pure-Python checks.
- Two-session concurrency gates M1/M2 and I1/I2 after the missing helper is installed, including real DB commits and rollback/visibility.
- Whether the operator-approved local test DB already exists and is fresh, isolated, and correctly provisioned. Naming alone is not ownership proof.
- Native Odoo activity delivery being **in-app only** under the target mail configuration.
- Current required-check policy for `Development`, and an authorized, non-legacy publication path from Mack's older Makefile. Do not invent it.
- Whether a later PR push changes review findings or reveals new tests/CI failures. Requery after each authorized publication.

## Links

PR #197: https://github.com/cryptoxdog/IB-Odoo_19/pull/197

Exact Mack source: https://github.com/cryptoxdog/IB-Odoo_19/tree/7dcada49fd301d3b5dafb30405d0242667915fbe

Development source: https://github.com/cryptoxdog/IB-Odoo_19/tree/3318fa646a9f33aed55b9ea8f8596316e30684da

Current Staging (inspection only): https://github.com/cryptoxdog/IB-Odoo_19/tree/3c24976576185c7a59b10ff7a837dd1ed93344ee
