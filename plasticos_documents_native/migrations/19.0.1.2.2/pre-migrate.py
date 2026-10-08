"""Drop xmlids that still point at Documents models Odoo 19 removed.

Folders are documents.document records. Facets no longer exist, so an upgrade
must not try to update documents.folder or documents.facet rows.
"""

import logging

_logger = logging.getLogger(__name__)

_MODULE = "plasticos_documents_native"
_RETIRED_MODELS = ("documents.folder", "documents.facet")


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE module = %s
          AND model IN %s
        """,
        (_MODULE, _RETIRED_MODELS),
    )
    _logger.info(
        "Removed %s retired Documents xmlids from %s",
        cr.rowcount,
        _MODULE,
    )
