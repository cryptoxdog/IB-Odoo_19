"""Mark deleted local-intelligence modules uninstalled (Staging dump cleanup).

Physical mothball deleted plasticos_buyer_match_engine / plasticos_inference_engine
from the addons tree, but Staging DBs can still have ir_module_module.state=installed.
That yields continuous registry ERROR and blocks tip upgrades. Additive only — no
DROP TABLE; retained match/enrichment audit tables stay owned by Gate shells.
"""

import logging

_logger = logging.getLogger(__name__)

_DELETED_LOCAL_INTELLIGENCE = (
    "plasticos_buyer_match_engine",
    "plasticos_inference_engine",
)

_PHANTOM_STATES = (
    "installed",
    "to upgrade",
    "to remove",
    "to install",
)


def migrate(cr, version):
    _logger.info(
        "plasticos_base 19.0.1.1.6: mark deleted local-intelligence modules uninstalled",
    )
    cr.execute(
        """
        UPDATE ir_module_module
           SET state = 'uninstalled'
         WHERE name = ANY(%s)
           AND state = ANY(%s)
        """,
        [list(_DELETED_LOCAL_INTELLIGENCE), list(_PHANTOM_STATES)],
    )
    updated = cr.rowcount
    cr.execute(
        """
        DELETE FROM ir_module_module_dependency
         WHERE name = ANY(%s)
        """,
        [list(_DELETED_LOCAL_INTELLIGENCE)],
    )
    deleted_deps = cr.rowcount
    _logger.info(
        "plasticos_base 19.0.1.1.6: modules_uninstalled=%s dependency_rows_removed=%s",
        updated,
        deleted_deps,
    )
