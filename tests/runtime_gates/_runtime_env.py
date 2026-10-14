"""Shared runtime binding for the launch gates.

Every gate needs the same four facts — where PostgreSQL is, which database to
drive, where Odoo's addons live, and where this checkout is — and each script
used to hardcode them. That pinned an Odoo build number
(`odoo-19.0.post20260831`) into four files, so a runtime rebuilt from
`nightly.odoo.com` at any later date silently stopped matching and every one of
those gates failed on an unimportable addon rather than on its own assertion.

Resolving the source directory by glob instead of by pinned version is the fix:
the runbook installs whatever nightly currently serves, and the gates should
follow it. `scripts/setup_local_runtime.sh` builds exactly this layout.

Defaults are the previous hardcoded values, so an existing invocation with no
environment set behaves as before.
"""

from __future__ import annotations

import glob
import os
import re
import subprocess
import sys

DB = os.environ.get("SEAM_DB") or os.environ.get("F1_DB") or "c1c6_test"
PG_HOST = os.environ.get("SEAM_PG_HOST") or os.environ.get("F1_PG_HOST") or "/tmp"
PG_PORT = int(os.environ.get("SEAM_PG_PORT") or os.environ.get("F1_PG_PORT") or "5433")
PG_USER = os.environ.get("SEAM_PG_USER") or os.environ.get("F1_PG_USER") or "odoo"

REPO = os.environ.get("SEAM_REPO") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def odoo_source() -> str:
    """Newest Odoo 19 source tree, or "" when none is installed."""
    explicit = os.environ.get("SEAM_ODOO_SRC")
    if explicit:
        return explicit
    matches = sorted(glob.glob(os.environ.get("SEAM_ODOO_SRC_DIR", "/opt/odoo-src") + "/odoo-19.0*"))
    return matches[-1] if matches else ""


def odoo_addons() -> str:
    src = odoo_source()
    return os.path.join(src, "odoo", "addons") if src else ""


def addons_path() -> str:
    """`addons_path` for odoo.tools.config: core addons plus this checkout."""
    return f"{odoo_addons()},{REPO}"


_F1_DB_RE = re.compile(r"^odoo_test_f1_[a-z0-9_]{1,40}$")


def require_f1_disposable_database(name: str) -> str:
    """Stub CRM commits may land only on a dedicated disposable clone.

    Integration clones (``odoo_test_crm*`` and every other ``odoo_test_*`` name)
    are refused before ``scripts/test_env.sh`` is asked to look at them. The F1
    gate retires its ``odoo_test_f1_*`` clone through that script's ``drop``.
    """
    if not isinstance(name, str) or _F1_DB_RE.fullmatch(name) is None:
        raise SystemExit(
            f"refusing stub CRM gate on {name!r}: commits are allowed only on a disposable "
            "odoo_test_f1_* clone, which the gate drops before exit"
        )
    if "prod" in name or "staging" in name:
        raise SystemExit(f"refusing stub CRM gate on {name!r}: production and staging names are never disposable")
    return name


def bind_config(config) -> None:
    """Apply the resolved runtime to an odoo.tools.config, before any addon import."""
    config["db_host"] = PG_HOST
    config["db_port"] = PG_PORT
    config["db_user"] = PG_USER
    config["addons_path"] = addons_path()


def invoke_test_env(*args: str, runner=None) -> int:
    """Run ``scripts/test_env.sh``. ``runner`` is the test seam; production passes through."""
    if runner is not None:
        return int(runner(list(args)))
    script = os.path.join(REPO, "scripts", "test_env.sh")
    completed = subprocess.run(["bash", script, *args], check=False)
    return int(completed.returncode)


def prove_owned_f1_clone(name: str, *, runner=None) -> str:
    """Name gate, then ``assert-clone``. Nothing is registered for deletion here."""
    require_f1_disposable_database(name)
    code = invoke_test_env("assert-clone", name, runner=runner)
    if code != 0:
        raise SystemExit(code or 2)
    return name


def retire_owned_f1_clone(name: str, *, runner=None) -> None:
    """Retire through ``test_env.sh drop`` (database and filestore). Non-zero fails the gate."""
    require_f1_disposable_database(name)
    code = invoke_test_env("drop", name, runner=runner)
    if code != 0:
        raise SystemExit(code or 1)


def execute_owned_f1(name: str, body, *, runner=None) -> int:
    """Prove ownership, run ``body``, then retire. A cleanup failure is never success.

    ``body`` is not called when the name gate or ``assert-clone`` refuses.
    Retirement still runs when ``body`` returns non-zero or raises.
    """
    prove_owned_f1_clone(name, runner=runner)
    body_code = 1
    cleanup = 0
    try:
        body_code = int(body(name) or 0)
    except SystemExit as exc:
        body_code = exc.code if isinstance(exc.code, int) else 1
        body_code = int(body_code or 0)
    finally:
        try:
            retire_owned_f1_clone(name, runner=runner)
        except SystemExit as exc:
            cleanup = exc.code if isinstance(exc.code, int) else 1
            cleanup = int(cleanup or 1)
            print(f"owned clone retirement failed: {name} status {cleanup}", file=sys.stderr)
    if cleanup:
        raise SystemExit(cleanup)
    if body_code:
        raise SystemExit(body_code)
    return 0
