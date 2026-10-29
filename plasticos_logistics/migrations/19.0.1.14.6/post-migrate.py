"""Re-check the load parent copy after the registry has the stored field."""

import importlib.util
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)


def _pre():
    path = Path(__file__).with_name("pre-migrate.py")
    spec = importlib.util.spec_from_file_location("plasticos_logistics_load_parent_pre_191146", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def migrate(cr, version):
    if not version:
        return
    pre = _pre()
    pre.migrate(cr, version)
    if not pre._has_column(cr, "plasticos_transaction", "load_id"):
        return
    if not pre._has_column(cr, "plasticos_load", "transaction_id"):
        raise RuntimeError("plasticos_load.transaction_id is missing after the logistics upgrade.")
    conflicts = pre._conflicts(cr)
    if conflicts:
        raise RuntimeError(
            f"plasticos load parent migration refused after upgrade. Rows left unchanged: {conflicts}"
        )
    copied = pre._copy(cr)
    cr.execute(
        """
        SELECT t.id, t.load_id, l.transaction_id
          FROM plasticos_transaction t
          LEFT JOIN plasticos_load l ON l.id = t.load_id
         WHERE t.load_id IS NOT NULL
           AND (l.id IS NULL OR l.transaction_id IS DISTINCT FROM t.id)
         ORDER BY t.id
        """
    )
    missing = cr.fetchall()
    if missing:
        raise RuntimeError(
            f"plasticos load parent migration did not preserve every transaction.load_id row: {missing}"
        )
    _logger.info("plasticos_logistics post-migrate confirmed load parents; copied %s", copied)
