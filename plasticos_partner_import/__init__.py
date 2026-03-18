from . import models
from . import wizards


def post_init_hook(env):
    """Auto-import partners from CSV on first module install."""
    import logging
    import os

    _logger = logging.getLogger(__name__)

    # Check if partners already imported (look for external ID marker)
    marker = env.ref("plasticos_partner_import.auto_import_complete", raise_if_not_found=False)
    if marker:
        _logger.info("Partner auto-import already completed, skipping")
        return

    module_path = os.path.dirname(os.path.abspath(__file__))
    corporate_csv = os.path.join(module_path, "1. Counterparties - Parent - CORPORATE-Ready To Import.csv")
    facility_csv = os.path.join(module_path, "2. Counterparties - Child - FACILITY LOCATIONS.csv")

    if not os.path.exists(corporate_csv) or not os.path.exists(facility_csv):
        _logger.warning("Partner CSV files not found, skipping auto-import")
        return

    _logger.info("Starting automatic partner import from CSV files...")

    try:
        service = env["plasticos.partner.import.service"]
        result = service.run_csv_import(corporate_csv, facility_csv)
        _logger.info("Auto-import complete: %s", result)

        # Create marker to prevent re-import
        env["ir.model.data"].create(
            {
                "name": "auto_import_complete",
                "module": "plasticos_partner_import",
                "model": "ir.model.data",
                "res_id": 1,  # Dummy reference
                "noupdate": True,
            }
        )
        env.cr.commit()

    except Exception as e:
        _logger.error("Partner auto-import failed: %s", e)
        # Don't raise - allow module install to continue
