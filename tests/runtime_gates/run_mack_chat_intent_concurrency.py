"""Gates I1 / I2 -- Mack chat-intent receipt one-winner and replay-after-edit (PR 191).

Not a pytest module and deliberately not collected: needs a live Odoo 19
registry and a live PostgreSQL server (see this directory's README).

I1  Two sessions record an intent for the same native chatter message at the
    same time. Afterwards exactly one receipt row exists for (company, source
    message) and BOTH callers hold its id. The loser is proven to have taken
    the collision path rather than dodged it: its INSERT waited on the unique
    constraint, took the UniqueViolation, and -- Odoo cursors being REPEATABLE
    READ, the winner's row invisible to its snapshot -- raised
    ConcurrencyError so the RPC layer re-ran the request on a fresh snapshot
    (``attempts == 2``). A loser that "converged" in one attempt means timing
    skipped the race, so the gate fails on that too (README rule 3).

I2  A later edit to the intake, committed by a separate transaction so that
    ``write_date`` really moves (inside one TransactionCase it cannot: every
    write stamps the same ``cr.now()``), does not invalidate replay of the
    exact same source message: the same receipt comes back, and its stored
    ``canonical_write_date`` is still the original observation, not the
    intake's new ``write_date``. That is the README's "observation only"
    boundary, proven against a real second transaction (F191-01).

Verified failing without the fix (README rule 5), against the module at
4a50816 (PR 191 head merged with PR 190's remediation, chat_intent.py
untouched): I1's loser escaped after one attempt with
``ValidationError('The operation cannot be completed: An intent receipt
already exists for this company and source message.')`` and I2's replay was
refused with ``Source message is already bound to different chat intent
material (canonical_write_date)``.

    SEAM_DB=<db with plasticos_mack_workbench installed> SEAM_PG_HOST=/tmp \\
      SEAM_PG_PORT=5433 SEAM_PG_USER=odoo \\
      /opt/odoo-venv/bin/python tests/runtime_gates/run_mack_chat_intent_concurrency.py
"""

import os
import sys
import threading
import time

import odoo
import odoo.modules.module
from odoo.tools import config

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _runtime_env import bind_config  # noqa: E402

bind_config(config)
odoo.modules.module.initialize_sys_path()

from _mack_runtime import (  # noqa: E402
    Contender,
    hold_open,
    indep,
    make_intake,
    race,
    report,
    require_models,
    superuser_call,
    wait_then_announce,
)

require_models("plasticos.mack.chat.intent.receipt", "plasticos.intake")

TAG = time.strftime("%Y%m%d%H%M%S") + f"-{os.getpid()}"
results: dict[str, bool] = {}


def setup(env):
    """An admin who may record intents, a fresh intake, and admin's own chatter comment on it."""
    admin = env.ref("base.user_admin")
    manager = env.ref("plasticos_mack_workbench.group_mack_workbench_manager")
    if manager not in admin.group_ids:
        admin.write({"group_ids": [(4, manager.id)]})
    company = env.ref("base.main_company")
    intake_id = make_intake(env, TAG)
    intake = env["plasticos.intake"].browse(intake_id)
    message = intake.with_user(admin).message_post(
        body=f"Gate I1 {TAG}: please consult on this lot.",
        message_type="comment",
        subtype_xmlid="mail.mt_note",
    )
    return admin.id, company.id, intake_id, message.id


admin_id, company_id, intake_id, message_id = superuser_call(setup)
CTX = {"allowed_company_ids": [company_id]}  # what a real RPC session carries


def record(env):
    receipt = env["plasticos.mack.chat.intent.receipt"]
    return receipt.record_intent_from_source_message(intake_id, message_id, "consult")["receipt_id"]


def receipt_rows():
    return indep(
        "SELECT id, canonical_write_date FROM plasticos_mack_chat_intent_receipt "
        "WHERE company_id = %s AND source_message_id = %s",
        (company_id, message_id),
    )


# ── I1: identical intent for one message from two sessions ──────────────────
print("Gate I1: two sessions, one source message")
winner_in = threading.Event()
loser_in = threading.Event()
i1_winner = Contender("I1-winner", record, uid=admin_id, context=CTX, before_commit=hold_open(winner_in, loser_in))
i1_loser = Contender(
    "I1-loser", record, uid=admin_id, context=CTX, before_start=wait_then_announce(winner_in, loser_in)
)
race(i1_winner, i1_loser)

rows = receipt_rows()
print(f"  winner -> id={i1_winner.result} attempts={i1_winner.attempts} error={i1_winner.error!r}")
print(
    f"  loser  -> id={i1_loser.result} attempts={i1_loser.attempts} error={i1_loser.error!r} elapsed={i1_loser.elapsed:.2f}s"
)
print(f"  rows={rows}")
results["I1: winner committed exactly one receipt"] = i1_winner.error is None and len(rows) == 1
results["I1: loser converged without an error escaping"] = i1_loser.error is None
results["I1: both callers hold the same receipt id"] = bool(rows) and i1_winner.result == i1_loser.result == rows[0][0]
results["I1: loser took the collision path (retried on a fresh snapshot)"] = i1_loser.attempts == 2
results["I1: loser returned inside the hold window plus retry backoff"] = i1_loser.elapsed < 30

# ── I2: replay after a later, separately committed intake edit ──────────────
print("\nGate I2: intake edited afterwards, same message replayed")
original_snapshot = rows[0][1] if rows else None


def edit_intake(env):
    env["plasticos.intake"].browse(intake_id).write({"quantity_per_load_lbs": 42000})


superuser_call(edit_intake)
intake_write_date = indep("SELECT write_date FROM plasticos_intake WHERE id = %s", (intake_id,))[0][0]

i2_replay = Contender("I2-replay", record, uid=admin_id, context=CTX)
i2_replay.start()
i2_replay.join(60)
rows_after = receipt_rows()
print(f"  intake write_date: {original_snapshot} -> {intake_write_date}")
print(f"  replay -> id={i2_replay.result} attempts={i2_replay.attempts} error={i2_replay.error!r}")
print(f"  rows={rows_after}")
results["I2: intake write_date moved in a separate committed transaction"] = (
    original_snapshot is not None and intake_write_date != original_snapshot
)
results["I2: replay after the edit returns the original receipt"] = (
    i2_replay.error is None and bool(rows) and i2_replay.result == rows[0][0]
)
results["I2: stored canonical_write_date is still the original observation"] = (
    bool(rows_after) and rows_after[0][1] == original_snapshot
)
results["I2: still exactly one receipt for the message"] = len(rows_after) == 1

sys.exit(report(results))
