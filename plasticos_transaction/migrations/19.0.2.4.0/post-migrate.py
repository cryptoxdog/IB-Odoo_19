"""Copy the historical single dock rule onto the pickup side.

ADR-135 §3. Existing transactions and purchase orders keep ``delivery_term`` and
gain the same value in ``pickup_dock_rule`` where that column is still empty.
A second run updates nothing. Loads are copied by the logistics migration.
"""

import importlib.util
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)
_VERSION = "19.0.2.4.0"


def _copy():
    path = Path(__file__).resolve().parents[2] / "dock_rule.py"
    spec = importlib.util.spec_from_file_location("plasticos_transaction_dock_rule", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.copy_pickup_dock_rule


def migrate(cr, version):
    if not version:
        return
    copy_pickup_dock_rule = _copy()
    for table in ("plasticos_transaction", "purchase_order"):
        stats = copy_pickup_dock_rule(cr, table)
        _logger.info("plasticos_transaction %s pickup_dock_rule copy %s", _VERSION, stats)
