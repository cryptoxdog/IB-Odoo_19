"""Mark every document type set before TASK-070 as human-set (DEC-015).

Before 19.0.1.5.0 no tag derived a ``doc_type``: every value was chosen by a person or an
import. Marking those ``human`` keeps the classification bridge from ever replacing them.
Only empty provenance is filled, so a second run changes nothing (POS-INV-19).
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE documents_document
           SET doc_type_source = 'human'
         WHERE doc_type IS NOT NULL
           AND doc_type_source IS NULL
        """
    )
    _logger.info("plasticos_documents_native 19.0.1.5.0: %d document type(s) marked human-set", cr.rowcount)
