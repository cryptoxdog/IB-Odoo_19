"""CieTrade legacy-ERP source layer (Odoo-free).

Reads the authoritative CieTrade export tracked under
``data/legacy_erp_sm_export/`` and exposes it as deterministic, replay-safe
source records keyed by stable CieTrade identifiers.

This package imports **no Odoo symbols** so every rule in it is exercised by the
pure-Python CI tier (``ci.yml`` job ``pure-python-tests``) against the real
payload. Odoo-side mapping lives in
``plasticos_transaction/models/cietrade_import_service.py``.
"""

from . import header_forensics, mapping, reader, report, source_index

__all__ = ["header_forensics", "mapping", "reader", "report", "source_index"]
