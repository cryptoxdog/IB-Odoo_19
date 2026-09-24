"""Gates M1 / M2 -- Mack internal review one-winner properties (PR 190).

Not a pytest module and deliberately not collected: needs a live Odoo 19
registry and a live PostgreSQL server (see this directory's README).

M1  Two sessions submit the identical review request -- same company, same
    idempotency key, same caller material -- at the same time. Afterwards
    exactly one receipt row exists, one activity and one audit note were
    posted on the intake, and BOTH callers hold that row's id. The loser is
    proven to have taken the collision path rather than dodged it: its INSERT
    waited on the unique index, took the UniqueViolation, and -- because Odoo
    cursors are REPEATABLE READ and the winner's row is invisible to its
    snapshot -- raised ConcurrencyError so the RPC layer re-ran the request
    on a fresh snapshot (``attempts == 2``). A loser that "converged" in one
    attempt means timing skipped the race, so the gate fails on that too
    (README rule 3).

M2  Two sessions activate two different routing configs for the same company
    at the same time. The partial unique index ``(company_id) WHERE active``
    lets exactly one commit; the other receives the ValidationError the RPC
    layer derives from the IntegrityError. Application-level
    ``@api.constrains`` alone let both through (that is F190-02).

Verified failing without the fix (README rule 5), against the module at
8bcc22c48ac61bff3132dd22405fff3ef21dcb32 (with only the ``check_company``
crash removed so a request could be created at all): M1's loser escaped after
one attempt with ``ValidationError('The operation cannot be completed: An
internal review request already exists for this company and idempotency
key.')`` and never received the receipt; M2 committed two active rows for one
company (``active rows: [(9,), (10,)]``).

    SEAM_DB=<db with plasticos_mack_workbench installed> SEAM_PG_HOST=/tmp \\
      SEAM_PG_PORT=5433 SEAM_PG_USER=odoo \\
      /opt/odoo-venv/bin/python tests/runtime_gates/run_mack_review_concurrency.py
"""

import os
import sys
import threading
import time
from datetime import date, timedelta

import odoo
import odoo.modules.module
from odoo.tools import config

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _runtime_env import bind_config  # noqa: E402

bind_config(config)
odoo.modules.module.initialize_sys_path()

from _mack_runtime import (  # noqa: E402
    Contender,
    ensure_route,
    indep,
    make_intake,
    race,
    report,
    require_models,
    superuser_call,
)

from odoo.exceptions import ValidationError  # noqa: E402

require_models("plasticos.mack.internal.review", "plasticos.mack.workbench.config", "plasticos.intake")

TAG = time.strftime("%Y%m%d%H%M%S") + f"-{os.getpid()}"
HOLD_SECONDS = 1.5  # how long the winner keeps its transaction open once the loser has started
results: dict[str, bool] = {}


def hold_open(started: threading.Event, other_started: threading.Event):
    """Winner-side hook: publish that the row is in, wait for the loser, then hold."""

    def _hold():
        started.set()
        other_started.wait(30)
        time.sleep(HOLD_SECONDS)

    return _hold


def wait_then_announce(other_started: threading.Event, mine: threading.Event):
    """Loser-side hook: do not open a cursor until the winner's row is in (uncommitted)."""

    def _wait():
        if not other_started.wait(30):
            raise RuntimeError("winner never announced its uncommitted insert")
        mine.set()

    return _wait


# ── M1: identical review request from two sessions ──────────────────────────
print("Gate M1: two sessions, one idempotency key")


def setup_m1(env):
    company = env.ref("base.main_company")
    ensure_route(env, company.id)
    return company.id, make_intake(env, TAG)


company_id, intake_id = superuser_call(setup_m1)
KEY = f"mack-gate-m1-{TAG}"
REQUEST = {
    "intake_id": intake_id,
    "cwi_ref": f"cwi_gate_{TAG}",
    "cwi_revision": 1,
    "decision_snapshot_hash": "b" * 64,
    "candidate_action": "request_internal_review",
    "reason": "Concurrency gate M1: identical request from two sessions.",
    "risk_codes": ["GATE_M1"],
    "evidence_refs": [f"odoo:intake:{intake_id}@v1"],
    "priority": "1",
    "deadline": (date.today() + timedelta(days=1)).isoformat(),
    "idempotency_key": KEY,
}


def submit_review(env):
    return env["plasticos.mack.internal.review"].create(dict(REQUEST)).id


winner_in = threading.Event()
loser_in = threading.Event()
m1_winner = Contender("M1-winner", submit_review, before_commit=hold_open(winner_in, loser_in))
m1_loser = Contender("M1-loser", submit_review, before_start=wait_then_announce(winner_in, loser_in))
race(m1_winner, m1_loser)

rows = indep(
    "SELECT id, reviewer_id, route_policy_revision FROM plasticos_mack_internal_review "
    "WHERE company_id = %s AND idempotency_key = %s",
    (company_id, KEY),
)
activities = indep(
    "SELECT COUNT(*) FROM mail_activity WHERE res_model = 'plasticos.intake' AND res_id = %s",
    (intake_id,),
)[0][0]
notes = indep(
    "SELECT COUNT(*) FROM mail_message WHERE model = 'plasticos.intake' AND res_id = %s "
    "AND message_type = 'comment' AND body::text LIKE '%%Mack internal review request%%'",
    (intake_id,),
)[0][0]
print(f"  winner -> id={m1_winner.result} attempts={m1_winner.attempts} error={m1_winner.error!r}")
print(
    f"  loser  -> id={m1_loser.result} attempts={m1_loser.attempts} error={m1_loser.error!r} elapsed={m1_loser.elapsed:.2f}s"
)
print(f"  rows={rows} activities={activities} audit_notes={notes}")
results["M1: winner committed exactly one receipt"] = m1_winner.error is None and len(rows) == 1
results["M1: loser converged without an error escaping"] = m1_loser.error is None
results["M1: both callers hold the same receipt id"] = bool(rows) and m1_winner.result == m1_loser.result == rows[0][0]
results["M1: loser took the collision path (retried on a fresh snapshot)"] = m1_loser.attempts == 2
results["M1: exactly one activity on the intake"] = activities == 1
results["M1: exactly one audit note on the intake"] = notes == 1
results["M1: loser returned inside the hold window plus retry backoff"] = m1_loser.elapsed < 30

# ── M2: concurrent activation of two routes for one company ─────────────────
print("\nGate M2: two sessions, two routes, one company")


def setup_m2(env):
    company = env["res.company"].create({"name": f"Mack gate company {TAG}"})
    admin = env.ref("base.user_admin")
    Config = env["plasticos.mack.workbench.config"]
    first = Config.create(
        {"name": "gate route one", "company_id": company.id, "internal_reviewer_id": admin.id, "active": False}
    )
    second = Config.create(
        {"name": "gate route two", "company_id": company.id, "internal_reviewer_id": admin.id, "active": False}
    )
    return company.id, first.id, second.id


m2_company_id, first_id, second_id = superuser_call(setup_m2)


def activate(config_id):
    def _activate(env):
        env["plasticos.mack.workbench.config"].browse(config_id).write({"active": True})
        env.flush_all()  # the UPDATE and the Python constraint run here, as they would at RPC flush
        return config_id

    return _activate


winner2_in = threading.Event()
loser2_in = threading.Event()
m2_winner = Contender("M2-winner", activate(first_id), before_commit=hold_open(winner2_in, loser2_in))
m2_loser = Contender("M2-loser", activate(second_id), before_start=wait_then_announce(winner2_in, loser2_in))
race(m2_winner, m2_loser)

active_rows = indep(
    "SELECT id FROM plasticos_mack_workbench_config WHERE company_id = %s AND active IS TRUE ORDER BY id",
    (m2_company_id,),
)
print(f"  winner -> attempts={m2_winner.attempts} error={m2_winner.error!r}")
print(f"  loser  -> attempts={m2_loser.attempts} error={m2_loser.error!r} elapsed={m2_loser.elapsed:.2f}s")
print(f"  active rows for company {m2_company_id}: {active_rows}")
results["M2: exactly one active route committed for the company"] = len(active_rows) == 1
results["M2: the first activation is the winner"] = m2_winner.error is None and active_rows == [(first_id,)]
results["M2: the second activation was refused by the database, not accepted"] = isinstance(
    m2_loser.error, ValidationError
)
results["M2: loser returned inside the hold window"] = m2_loser.elapsed < 30

sys.exit(report(results))
