"""Delete leftover Gate connection ICPs.

URL and signing key id are no longer connection authority. The SDK reads
GATE_URL + L9_* from the process environment. Capability ICPs stay.
"""

import logging

_logger = logging.getLogger(__name__)

_DELETE_KEYS = (
    "plasticos.gate.url",
    "plasticos.gate.signing_key_id",
)


def migrate(cr, version):
    _logger.info("plasticos_gate 19.0.1.9.3: remove connection-plane ICP rows")
    cr.execute(
        "DELETE FROM ir_config_parameter WHERE key = ANY(%s)",
        (list(_DELETE_KEYS),),
    )
    _logger.info("plasticos_gate connection ICP rows deleted: %s", cr.rowcount)
