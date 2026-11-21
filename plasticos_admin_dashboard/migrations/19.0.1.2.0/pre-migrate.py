"""Give every existing Admin KPI record a company before company_id becomes required (DEC-008).

Before 19.0.1.2.0 the KPI record had no company and was shared. Existing rows
are assigned to the main company (base.main_company, else the lowest company
id). No row is deleted. When more than one record would land on that company
the upgrade stops with the record ids instead of leaving the one-per-company
constraint uninstalled. Repeatable: the column is added only when absent and
only rows without a company are updated.
"""

import logging

_logger = logging.getLogger(__name__)

TABLE = "plasticos_admin_kpi"


def _main_company_id(cr):
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
         WHERE module = 'base' AND name = 'main_company' AND model = 'res.company'
        """
    )
    row = cr.fetchone()
    if row:
        return row[0]
    cr.execute("SELECT MIN(id) FROM res_company")
    return cr.fetchone()[0]


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass(%s)", (TABLE,))
    if cr.fetchone()[0] is None:
        return
    cr.execute("ALTER TABLE plasticos_admin_kpi ADD COLUMN IF NOT EXISTS company_id integer")
    company_id = _main_company_id(cr)
    cr.execute(
        """
        SELECT COUNT(*) FILTER (WHERE company_id IS NULL),
               COUNT(*) FILTER (WHERE company_id = %s)
          FROM plasticos_admin_kpi
        """,
        (company_id,),
    )
    unassigned, assigned = cr.fetchone()
    if unassigned + assigned > 1:
        # Fail closed, deleting nothing: the one-record-per-company invariant (UNIQUE(company_id))
        # must hold after this upgrade. The rows carry only last_refresh; KPIs compute on read.
        cr.execute(
            "SELECT id FROM plasticos_admin_kpi WHERE company_id IS NULL OR company_id = %s ORDER BY id", (company_id,)
        )
        ids = [row[0] for row in cr.fetchall()]
        raise RuntimeError(
            f"plasticos_admin_dashboard 19.0.1.2.0: {len(ids)} Admin KPI records {ids} would belong to company "
            f"{company_id}, but there must be one per company. Keep one (they hold only last_refresh), delete "
            "the others with an authorized operation, then re-run the upgrade."
        )
    cr.execute("UPDATE plasticos_admin_kpi SET company_id = %s WHERE company_id IS NULL", (company_id,))
    _logger.info("plasticos_admin_dashboard: assigned %s KPI record(s) to company %s", cr.rowcount, company_id)
