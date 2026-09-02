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


def bind_config(config) -> None:
    """Apply the resolved runtime to an odoo.tools.config, before any addon import."""
    config["db_host"] = PG_HOST
    config["db_port"] = PG_PORT
    config["db_user"] = PG_USER
    config["addons_path"] = addons_path()
