"""PlasticOS CRM Sync.

Under Odoo, load models + controllers. Under pure pytest (no odoo), leave
the package importable so adapters/client unit tests can load without ORM.
"""

try:
    import odoo  # noqa: F401
except ImportError:
    pass
else:
    from . import controllers
    from . import models
