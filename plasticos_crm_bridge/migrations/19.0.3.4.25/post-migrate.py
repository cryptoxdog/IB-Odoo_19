"""Install PlasticOS CRM Sync on a database that already has its dependencies.

``auto_install`` installs a module only while one of its dependencies is moving
to installed. Staging already has those dependencies, so the flag alone leaves
``plasticos_crm_sync`` uninstalled. Marking it here lets the same upgrade load it.
An already installed copy is left as it is.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE ir_module_module
           SET state = 'to install'
         WHERE name = 'plasticos_crm_sync'
           AND state = 'uninstalled'
        """
    )
    if cr.rowcount:
        _logger.info("Marked plasticos_crm_sync to install.")
