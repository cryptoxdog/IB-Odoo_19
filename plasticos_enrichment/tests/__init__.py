# plasticos_enrichment/tests/__init__.py

from . import test_module_install
# Tests disabled for Odoo.sh deployment - require seed data not available during CI
# Re-enable for local testing with full database
# from . import test_normalization
# from . import test_injection
