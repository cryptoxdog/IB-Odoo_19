"""Give every existing Admin KPI record a company before company_id becomes required (DEC-008).

Before 19.0.1.2.0 the KPI record had no company and was shared. Existing rows
are assigned to the main company (base.main_company, else the lowest company
id). No row is deleted. Repeatable: the column is added only when absent and
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
    cr.execute("UPDATE plasticos_admin_kpi SET company_id = %s WHERE company_id IS NULL", (company_id,))
    _logger.info("plasticos_admin_dashboard: assigned %s KPI record(s) to company %s", cr.rowcount, company_id)
    cr.execute("SELECT company_id, COUNT(*) FROM plasticos_admin_kpi GROUP BY company_id HAVING COUNT(*) > 1")
    for company, count in cr.fetchall():
        _logger.warning(
            "plasticos_admin_dashboard: company %s has %s KPI records; the one-per-company "
            "constraint cannot be added until the extra records are removed",
            company,
            count,
        )
