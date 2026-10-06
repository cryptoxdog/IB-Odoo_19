"""ERP source layer (Odoo-free).

Reads ERP SQL from ``plasticos_partner_import/erp_extracted_data/``
and, when those files contain no ``INSERT`` rows, the frozen grid extract
under ``plasticos_partner_import/erp_extracted_data/bulk/``. Records stay keyed by stable ERP
identifiers.

This package imports **no Odoo symbols** so every rule in it is exercised by the
pure-Python CI tier (``ci.yml`` job ``pure-python-tests``) against the real
payload. Odoo-side mapping lives in
``plasticos_partner_import/models/erp_import_service.py``.
"""

from . import header_forensics, mapping, mapping_status, reader, report, source_index, summary

__all__ = ["header_forensics", "mapping", "mapping_status", "reader", "report", "source_index", "summary"]
