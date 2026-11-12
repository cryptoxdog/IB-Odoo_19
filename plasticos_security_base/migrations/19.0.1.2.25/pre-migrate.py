"""Refuse to tighten load company rules before Logistics has proven every load company.

ADR-130. This version removes the ``company_id = False`` escape from the global
``plasticos.load`` rule and adds a global company rule to the SQL Load
dashboard. Tightening a rule over rows that still have no company would hide
live loads from every user, so this step checks first and assigns nothing:

* every ``plasticos_load`` row has a company (Logistics 19.0.1.14.20 repaired or
  refused them before this module upgrades);
* the Load dashboard SQL view projects ``company_id``.

Either failure stops the upgrade. Security Base never sets a company, never
changes role membership, and never weakens the filter to make data visible.
It writes nothing, so a rerun is the same check.
"""

import logging

_logger = logging.getLogger(__name__)


def _has_table(cr, table):
    cr.execute("SELECT to_regclass(%s)", (f"public.{table}",))
    return cr.fetchone()[0] is not None


def _has_column(cr, table, column):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s
           AND column_name = %s
        """,
        (table, column),
    )
    return cr.fetchone() is not None


def missing_company_loads(cr):
    if not _has_table(cr, "plasticos_load") or not _has_column(cr, "plasticos_load", "company_id"):
        return []
    cr.execute("SELECT id FROM plasticos_load WHERE company_id IS NULL ORDER BY id")
    return [row[0] for row in cr.fetchall()]


def dashboard_projects_company(cr):
    if not _has_table(cr, "plasticos_load_dashboard"):
        return True
    return _has_column(cr, "plasticos_load_dashboard", "company_id")


def migrate(cr, version):
    if not version:
        return
    missing = missing_company_loads(cr)
    if missing:
        raise RuntimeError(
            "plasticos_security_base refuses to tighten load company isolation: these loads have no "
            f"proven company and would disappear for every user: {missing}"
        )
    if not dashboard_projects_company(cr):
        raise RuntimeError(
            "plasticos_security_base refuses to add the Load dashboard company rule: the dashboard "
            "view does not project company_id. Upgrade plasticos_logistics first."
        )
    _logger.info("plasticos_security_base pre-migrate: every load has a company; dashboard projects company_id")
