"""Copy each load's delivery dock rule onto its pickup dock rule.

ADR-135 §3. Rows that already have ``pickup_dock_rule`` are left alone, so a
replay is a no-op. Transactions and purchase orders are copied by
plasticos_transaction 19.0.2.4.0.
"""

import importlib.util
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)
_VERSION = "19.0.1.15.0"


def _copy():
    path = Path(__file__).resolve().parents[3] / "plasticos_transaction" / "dock_rule.py"
    spec = importlib.util.spec_from_file_location("plasticos_transaction_dock_rule", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.copy_pickup_dock_rule


def migrate(cr, version):
    if not version:
        return
    stats = _copy()(cr, "plasticos_load")
    _logger.info("plasticos_logistics %s pickup_dock_rule copy %s", _VERSION, stats)
