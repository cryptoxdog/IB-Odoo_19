"""Shared plumbing for the Mack workbench concurrency gates.

Not a gate itself. The Mack gates (`run_mack_review_concurrency.py` for
PR 190, `run_mack_chat_intent_concurrency.py` for PR 191) prove the same
class of property -- two independent Odoo sessions driving one idempotent
call converge on exactly one committed row and both callers receive that
row -- so the session plumbing lives here once.

Why the retry loop is Odoo's own and not a hand-rolled one: every Odoo
cursor runs at REPEATABLE READ, so a session that loses an insert race
cannot see the winner's row in its own snapshot no matter how it re-queries.
The model therefore raises ``odoo.exceptions.ConcurrencyError`` and the
RPC layer (``odoo.service.model.retrying``) restarts the request on a fresh
snapshot. A gate that bypassed ``retrying`` would either prove nothing about
the real RPC path or reinvent it; using the real function keeps the gate
honest about what production does.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

import psycopg2

import odoo
from odoo.api import Environment
from odoo.service.model import retrying

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _runtime_env import DB, PG_HOST, PG_PORT, PG_USER  # noqa: E402

SKIP_EXIT = 77


def indep(sql: str, args: tuple = ()) -> list[tuple]:
    """Read through a session Odoo does not own (README rule 1)."""
    connection = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, dbname=DB)
    connection.set_session(autocommit=True)
    with connection.cursor() as cursor:
        cursor.execute(sql, args)
        rows = cursor.fetchall()
    connection.close()
    return rows


def registry():
    return odoo.modules.registry.Registry(DB)


def require_models(*model_names: str) -> None:
    """Exit 77 (SKIPPED, never PASS) when the module under test is not installed here."""
    with registry().cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        missing = [name for name in model_names if name not in env]
    if missing:
        print(f"SKIPPED  {', '.join(missing)} not in registry {DB!r}; install plasticos_mack_workbench and re-run.")
        sys.exit(SKIP_EXIT)


def superuser_call(fn: Callable[[Environment], Any]) -> Any:
    """Run ``fn(env)`` as the superuser in its own committed cursor."""
    with registry().cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        result = fn(env)
        cr.commit()
        return result


def ensure_route(env: Environment, company_id: int) -> int:
    """Return the active Mack routing config for ``company_id``, creating one if absent."""
    Config = env["plasticos.mack.workbench.config"]
    config = Config.search([("company_id", "=", company_id), ("active", "=", True)], limit=1)
    if config:
        return config.id
    admin = env.ref("base.user_admin")
    return Config.create({"name": "Mack gate route", "company_id": company_id, "internal_reviewer_id": admin.id}).id


def make_intake(env: Environment, tag: str) -> int:
    """Create a canonical intake the gate can bind requests to."""
    partner = env["res.partner"].create({"name": f"Mack gate partner {tag}", "is_company": True})
    polymer = env["plasticos.polymer"].search([], limit=1)
    form = env["plasticos.material.form"].search([], limit=1)
    if not polymer or not form:
        raise RuntimeError("plasticos_intake seed data (polymer/form) missing from this database")
    return (
        env["plasticos.intake"]
        .create(
            {
                "partner_id": partner.id,
                "polymer_id": polymer.id,
                "form_id": form.id,
                "quantity_per_load_lbs": 40000,
            }
        )
        .id
    )


class Contender(threading.Thread):
    """One session driving one call the way the RPC layer would.

    Without ``before_commit`` the call goes through
    ``odoo.service.model.retrying`` exactly as a JSON-RPC request does: on
    ``ConcurrencyError`` the transaction is rolled back and the call re-runs
    on a fresh snapshot; on ``IntegrityError`` it becomes a
    ``ValidationError`` without retry; on success ``retrying`` itself
    commits. ``attempts`` counts how many times the call actually ran, so a
    gate can assert that the collision path fired rather than that timing
    happened to avoid it.

    With ``before_commit`` the session is the *winner* whose transaction must
    stay open while the other contender runs into it. ``retrying`` commits on
    success, so a held-open winner cannot go through it: the call is driven
    directly (call, flush, hold, commit) -- the shape of a request whose
    commit is merely delayed. The loser is always the session whose
    semantics the gate is proving, and it always takes the real path.
    """

    def __init__(
        self,
        label: str,
        call: Callable[[Environment], Any],
        *,
        uid: int = odoo.SUPERUSER_ID,
        context: dict | None = None,
        before_start: Callable[[], None] | None = None,
        before_commit: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(name=label, daemon=True)
        self.label = label
        self._call = call
        self._uid = uid
        self._context = context or {}
        self._before_start = before_start
        self._before_commit = before_commit
        self.attempts = 0
        self.result: Any = None
        self.error: BaseException | None = None
        self.elapsed = 0.0

    def run(self) -> None:
        started = time.monotonic()
        try:
            if self._before_start:
                self._before_start()
            with registry().cursor() as cr:
                env = Environment(cr, self._uid, self._context)

                def attempt():
                    self.attempts += 1
                    self.result = self._call(env)

                if self._before_commit is None:
                    retrying(attempt, env)  # commits on success, like the RPC layer
                else:
                    attempt()
                    env.cr.flush()
                    self._before_commit()
                    # leaving the cursor context commits the held transaction
        except BaseException as exc:  # noqa: BLE001 - the gate reports whatever escaped
            self.error = exc
        finally:
            self.elapsed = time.monotonic() - started


def race(winner: Contender, loser: Contender, timeout: float = 60.0) -> None:
    winner.start()
    loser.start()
    winner.join(timeout)
    loser.join(timeout)
    if winner.is_alive() or loser.is_alive():
        raise RuntimeError("contenders did not finish inside the gate timeout; a lock wait is stuck")


def report(results: dict[str, bool]) -> int:
    print("\n" + "=" * 66)
    for key, value in results.items():
        print(f"  {'PASS' if value else 'FAIL'}  {key}")
    print("=" * 66)
    return 0 if all(results.values()) else 1
