"""Run F1–F3 inside ``odoo shell`` under ``scripts/test_env.sh run``.

The runner has already proved the clone and holds its lease until this process
exits. This file does not drop the database. The caller drops it with
``scripts/test_env.sh drop`` after the lease is released, and writes the CRM
acceptance receipt only when that drop returns 0 and these assertions passed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_MOUNTED_GATE_DIR = "/mnt/extra-addons/tests/runtime_gates"


def _gate_dir() -> str:
    here = globals().get("__file__")
    if here:
        return os.path.dirname(os.path.abspath(here))
    if os.path.isdir(_MOUNTED_GATE_DIR):
        return _MOUNTED_GATE_DIR
    raise SystemExit("F1 gate directory is not on the guarded addons mount")


def _addons_path(config) -> str:
    raw = config["addons_path"]
    if isinstance(raw, list | tuple):
        return ",".join(str(part) for part in raw if part)
    return str(raw or "")


def assertions_passed(text: str) -> bool:
    """True only when the gate printed its table and every row passed.

    A launcher that exits 0 without that table is not an F1 pass. ``FAIL``
    inside Odoo log lines does not match the table prefix.
    """
    passes: list[str] = []
    fails = 0
    for line in text.splitlines():
        if line.startswith("  PASS  "):
            passes.append(line)
        elif line.startswith("  FAIL  "):
            fails += 1
    return fails == 0 and any(line.startswith("  PASS  F1") for line in passes)


def write_receipt(log_text: str, database: str, dest: str, head: str) -> None:
    """Write the acceptance receipt. The caller has already dropped the clone."""
    if not assertions_passed(log_text):
        print("F1 assertions did not pass; no acceptance receipt", file=sys.stderr)
        raise SystemExit(2)
    passes = [line.strip() for line in log_text.splitlines() if line.startswith("  PASS  ")]
    payload = {
        "gate": "F1-F3",
        "passed": True,
        "retired": True,
        "database": database,
        "head": head,
        "pass_count": len(passes),
        "fail_count": 0,
        "results": passes,
    }
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def accept_receipt(path: str, head: str) -> int:
    """Return 0 when ``path`` is a pass for ``head``. Otherwise 2 (unproven)."""
    receipt = Path(path)
    if not receipt.is_file():
        print("F1 unproven: no acceptance receipt", file=sys.stderr)
        return 2
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("F1 unproven: acceptance receipt is not readable", file=sys.stderr)
        return 2
    if payload.get("head") != head:
        print(f"F1 unproven: receipt is for {payload.get('head')}, not {head}", file=sys.stderr)
        return 2
    proven = (
        payload.get("gate") == "F1-F3"
        and payload.get("passed") is True
        and payload.get("retired") is True
        and payload.get("fail_count") == 0
        and payload.get("pass_count")
    )
    if not proven:
        print("F1 unproven: receipt is not a pass", file=sys.stderr)
        return 2
    print(f"F1 accepted at {head} ({payload['pass_count']} assertions, database {payload.get('database')})")
    return 0


def _release_shell_startup_lock(env) -> None:
    """Drop the idle advisory session ``odoo shell`` leaves behind.

    ``server.start(stop=True)`` holds one lock whose last statement is
    ``SELECT 'granted-…'``. F2 counts every advisory lock on the database and
    requires none after a rejected floor. That session is not the gate. A
    lock the gate itself leaks does not match this statement and stays.
    """
    env.cr.execute(
        """
        SELECT DISTINCT a.pid
          FROM pg_locks AS l
          JOIN pg_stat_activity AS a ON a.pid = l.pid
         WHERE l.locktype = 'advisory'
           AND a.pid <> pg_backend_pid()
           AND a.query LIKE 'SELECT ''granted-%'
        """
    )
    for (pid,) in env.cr.fetchall():
        env.cr.execute("SELECT pg_terminate_backend(%s)", [pid])


def main() -> int:
    """Execute the gate body. Ownership was proved by ``test_env.sh run``."""
    env = globals().get("env")
    if env is None:
        raise SystemExit("no Odoo environment (run inside `odoo shell`)")
    name = getattr(getattr(env, "cr", None), "dbname", "") or ""
    gate_dir = _gate_dir()
    if gate_dir not in sys.path:
        sys.path.insert(0, gate_dir)
    import importlib

    runtime = importlib.import_module("_runtime_env")
    runtime.require_f1_disposable_database(name)
    import odoo

    config = odoo.tools.config
    os.environ["SEAM_DB"] = name
    os.environ["SEAM_PG_HOST"] = str(config["db_host"])
    os.environ["SEAM_PG_PORT"] = str(config["db_port"])
    os.environ["SEAM_PG_USER"] = str(config["db_user"])
    os.environ["SEAM_PG_PASSWORD"] = str(config["db_password"] or "")
    os.environ["F1_ADDONS_PATH"] = _addons_path(config)
    _release_shell_startup_lock(env)
    # Host, port, and user are bound when `_runtime_env` is imported. The name
    # gate above had to run first, so re-read them before the gate body imports.
    importlib.reload(runtime)
    gate = importlib.import_module("run_f1_f3_full_import")
    return int(gate._run(name))


if __name__ == "__main__":
    sys.exit(main())
