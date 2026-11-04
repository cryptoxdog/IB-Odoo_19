# Mack-only Odoo 19 acceptance matrix

## Prerequisite: target-native isolated test environment

The current `mack`/`Development` Makefile is **older than Staging**. `make test-module` exists but **does not guard clone ownership**. A named DB (`odoo_test_*`) is not sufficient to prove safety. Before any installation or test, verify (1) locally hosted test PostgreSQL instance, (2) explicit operator-selected DB identity and current ownership comment, (3) it is a fresh non-production disposable Odoo 19 database, (4) `plasticos_mack_workbench` and dependencies installed at known versions, and (5) the test does not connect to any Odoo.sh Staging/Production instance. Preserve its identity and current source SHA in the receipt. Do not let an automated script drop a database it did not create and own.

The generated `_runtime_env.py` enforces `SEAM_DB=odoo_test_mack_<id>`, local PostgreSQL host/socket, same repo root, current local Odoo 19 source, and **reads the actual PostgreSQL database COMMENT** before the scripts execute. A recognized owner-stamped clone has `role=clone owner=...` (as in the newer repo's test-env scheme), or `mack_owned_disposable=1 owner=...` on a specifically designated Mack-only disposable clone. Prepare/verify one of these comment formats through the *authorized test DB provisioner*. Missing comment, missing Postgres/Odoo source, remote host, unknown name or no permissions means **BLOCKED**, not “just set an env variable.”

Do not transplant `scripts/test_env.sh` from `Staging` to this branch. An equivalent approved external test environment is acceptable only after its provenance, module installation, and marker are verified.

## Mechanical checks (non-Odoo)

| Check | Invocation | Required result |
|---|---|---|
| Original anchor guard | `python3 <pack>/scripts/build_repair.py --repo <mack-root> --output /tmp/mack-197-repair.patch` | Correct worktree SHA, file SHA, clean root, `git apply --check` |
| Offline guard behavior | `python3 -m unittest discover -s <pack>/tests -v` | No failed test; synthetic fixture does NOT claim live-app pass |
| Syntax | `python3 -m py_compile <mack-root>/plasticos_mack_workbench/models/internal_review.py <mack-root>/plasticos_mack_workbench/tests/test_internal_review.py <mack-root>/tests/runtime_gates/_runtime_env.py` | All compile successfully |
| Branch-local static | `make pr-check` in the `mack` checkout | Pass with no waived check. Its old Makefile is NOT a release publisher or runtime test harness |
| Module version | inspect `plasticos_mack_workbench/__manifest__.py` | strictly `19.0.1.1.1` after change; installed version transition observed on test clone |

## Odoo native registered tests

The addon registry at `plasticos_mack_workbench/tests/__init__.py` registers `test_internal_review` and `test_chat_intent`. From a verified, owned **fresh clone** of Odoo 19 at the exact patched Mack SHA, exercise an actual install and a scoped module upgrade with test enable. The old Makefile's `make test-module m=plasticos_mack_workbench ODOO_TEST_DB=<proven_clone>` can be used only after independently verifying its actual Docker service/DB target. It is *not safe by virtue of the command name*. Test that the module exists and that both native `TransactionCase` classes were collected; `_skip_if_model_missing` is not evidence of passing.

Required model assertions: hash padding/uppercase rejected and no receipt/activity left behind; exact valid digest accepted; one activity/note for first review only; replay without duplicate; route unchanged after config mutation; server-owned provenance rejects forgery; company scope and ACL, immutable rows, activity lifecycle, chat message binding/attachment references and replay after source intake changes.

## Separate genuine concurrency gates (NOT pytest)

Both scripts are **not collected by the pytest suite**. On the separately verified owned clone, after setting actual environment paths and choosing the Odoo Python interpreter whose registry installed Mack:

```bash
SEAM_DB=odoo_test_mack_<owned_clone> \
SEAM_PG_HOST=/tmp SEAM_PG_PORT=5433 SEAM_PG_USER=odoo \
SEAM_ODOO_SRC=<verified_odoo19_source_root> \
<verified_odoo_python> tests/runtime_gates/run_mack_review_concurrency.py

SEAM_DB=odoo_test_mack_<owned_clone> \
SEAM_PG_HOST=/tmp SEAM_PG_PORT=5433 SEAM_PG_USER=odoo \
SEAM_ODOO_SRC=<verified_odoo19_source_root> \
<verified_odoo_python> tests/runtime_gates/run_mack_chat_intent_concurrency.py
```

`<...>` are **placeholders** that must be bound from the live verified environment before execution; do not paste them literally. Exact environment-specific arguments are not known from GitHub source. Exit 77 = **SKIPPED**, exit nonzero = **FAILED**, all required named gate assertions with exit 0 = candidate PASS on the tested DB/revision. Inspect script output and independent SQL observations; a zero caused by a Python import/shell error is not a gate pass.

| Gate | Proof required |
|---|---|
| M1 | concurrent identical review requests: exactly one receipt + one activity + one intake note; both callers same receipt; loser takes collision/retry path |
| M2 | two route activations for same company: PostgreSQL partial unique index permits exactly one |
| I1 | concurrent same chatter message: exactly one immutable receipt and both callers converge through actual retry path |
| I2 | later separately committed intake edit does not change idempotent replay or its historical `canonical_write_date` |

## In-app-only delivery check

The repository deliberately schedules `mail.activity` and posts an internal chatter note, not a direct outbound email. Odoo's mail configuration can nonetheless send notifications. Independently verify, with the approved test mail sink and instance settings, that Mack review creation remains in-app-only and does not dispatch an external email. Configuration evidence is mandatory before asserting delivery behavior.

## State and test evidence

For each run record: Git SHA, module installed version, Odoo build, Postgres version, database name and comment marker, test registration/collected count, observed non-skipped pass/fail, logs saved outside repository or in approved evidence location, transaction/replay counts, and relevant negative controls. There is no live runtime proof in this ZIP; local synthetic generator tests cannot satisfy it.
