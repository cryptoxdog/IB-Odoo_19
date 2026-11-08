"""Flip seeded auto_writeback=1 → review-only (0).

noupdate=1 on gate_icp_seed.xml leaves previously installed value=1 in place.
Reset only when the ICP row still looks like the install seed (create_date ==
write_date). Rows an operator later edited keep their deliberate value.
"""

import logging

_logger = logging.getLogger(__name__)

_KEY = "plasticos.gate.auto_writeback"


def migrate(cr, version):
    _logger.info("plasticos_gate 19.0.1.2.0: review-only auto_writeback for seeded installs")
    cr.execute(
        """
        UPDATE ir_config_parameter
           SET value = '0',
               write_date = (now() at time zone 'UTC')
         WHERE key = %s
           AND value = '1'
           AND create_date IS NOT NULL
           AND write_date IS NOT NULL
           AND create_date = write_date
        """,
        (_KEY,),
    )
    _logger.info("plasticos_gate auto_writeback seeded rows flipped: %s", cr.rowcount)
