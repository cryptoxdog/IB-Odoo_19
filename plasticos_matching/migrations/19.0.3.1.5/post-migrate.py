"""Replace the intake-keyed result uniqueness with the run-keyed partial index.

Runs on upgrade only. ``plasticos.match.result.intake_id`` is optional from
this version, so the old ``unique(intake_id, buyer_partner_id, run_id)``
constraint no longer protects lot results (NULL intakes compare distinct).
The ORM created ``plasticos_match_result_unique_result_per_run_buyer`` at
load; this step retires the superseded constraint. Rows are not touched.
"""

import logging

_logger = logging.getLogger(__name__)

_OLD_CONSTRAINT = "plasticos_match_result_unique_match_per_run"


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        "SELECT 1 FROM pg_constraint WHERE conname = %s AND conrelid = 'plasticos_match_result'::regclass",
        (_OLD_CONSTRAINT,),
    )
    if not cr.fetchone():
        _logger.info("plasticos_matching 19.0.3.1.5: constraint %s already absent", _OLD_CONSTRAINT)
        return
    from odoo.tools import sql  # noqa: PLC0415

    sql.drop_constraint(cr, "plasticos_match_result", _OLD_CONSTRAINT)
    _logger.info("plasticos_matching 19.0.3.1.5: retired constraint %s", _OLD_CONSTRAINT)
