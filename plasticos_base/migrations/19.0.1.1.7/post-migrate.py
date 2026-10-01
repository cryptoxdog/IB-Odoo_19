"""Delete leftover CEG/EIE Settings connection ICPs.

These keys are no longer connection authority. Gate is reached via GATE_URL +
L9_* in the process environment. Capability ICPs stay on plasticos_gate.
"""

import logging

_logger = logging.getLogger(__name__)

_DELETE_KEYS = (
    "plasticos.matching_engine.enabled",
    "plasticos.matching_engine.url",
    "plasticos.matching_engine.stubbed",
    "plasticos.inference_engine.enabled",
    "plasticos.inference_engine.url",
    "plasticos.feature_gate.user_message",
)


def migrate(cr, version):
    _logger.info("plasticos_base 19.0.1.1.7: remove microservice Settings ICP rows")
    cr.execute(
        "DELETE FROM ir_config_parameter WHERE key = ANY(%s)",
        (list(_DELETE_KEYS),),
    )
    _logger.info("plasticos_base microservice ICP rows deleted: %s", cr.rowcount)
