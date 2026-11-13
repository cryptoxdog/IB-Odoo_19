"""Verify the load company repair after the registry has the explicit field.

Runs after ``19.0.1.14.6/post-migrate.py`` in the same upgrade, so the single
parent link ``plasticos_load.transaction_id`` exists here. It verifies, and does
not create:

* every load has a company, and none disagrees with its sale order or parent
  transaction (the pre step's census finds nothing left to repair or refuse);
* each load has at most one parent transaction, and that parent's sale order
  company equals the load company;
* the J1/J2 tables exist. They start empty: no journey is inferred from a legacy
  trailer, seal or container string. Existing rows are left untouched.

The Logistics SQL dashboard is rebuilt by its own ``init`` during the module
update. A rerun asserts the same facts and changes nothing.
"""

import importlib.util
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)


def _pre():
    path = Path(__file__).with_name("pre-migrate.py")
    spec = importlib.util.spec_from_file_location("plasticos_logistics_load_company_pre_1911420", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def discrepancies(cr):
    """Rows that break the repaired load-company invariants. Writes nothing."""
    pre = _pre()
    found = []
    repairs, refusals = pre.census(cr)
    found.extend(("unrepaired_load_company", load_id, company_id, source) for load_id, company_id, source in repairs)
    found.extend(("refused_load_company", load_id, reason, detail) for load_id, reason, detail in refusals)
    if pre.has_column(cr, "plasticos_load", "transaction_id"):
        cr.execute(
            """
            SELECT l.id, l.company_id, so.company_id
              FROM plasticos_load l
              JOIN plasticos_transaction t ON t.id = l.transaction_id
              JOIN sale_order so ON so.id = t.sale_order_id
             WHERE so.company_id IS DISTINCT FROM l.company_id
             ORDER BY l.id
            """
        )
        found.extend(
            ("parent_company_mismatch", load_id, company, tx_company) for load_id, company, tx_company in cr.fetchall()
        )
    return found


def migrate(cr, version):
    if not version:
        return
    pre = _pre()
    if not pre.has_table(cr, "plasticos_load"):
        return
    for table in ("plasticos_iso_journey", "plasticos_iso_journey_source"):
        if not pre.has_table(cr, table):
            raise RuntimeError(f"{table} is missing after the logistics upgrade.")
    found = discrepancies(cr)
    if found:
        raise RuntimeError(f"plasticos load company migration did not hold after upgrade. Rows: {found}")
    cr.execute("SELECT count(*) FROM plasticos_iso_journey")
    journeys = cr.fetchone()[0]
    already = pre.migration_done(cr)
    pre.mark_migration_done(cr)
    _logger.info(
        "plasticos_logistics post-migrate verified load companies (%s); %s container journeys present",
        "rerun, unchanged" if already else "first run",
        journeys,
    )
