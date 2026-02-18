"""
Entry point for partner import from shell or cron.

Usage (Odoo shell) - Dict-based import:
    from plasticos_partner_import.scripts.run_import import run
    result = run(env, corporate=[...], facilities=[...], contacts=[...])

Usage (Odoo shell) - CSV import:
    from plasticos_partner_import.scripts.run_import import run_csv
    result = run_csv(env,
        corporate_csv="/path/to/1. Counterparties - Parent - CORPORATE.csv",
        facility_csv="/path/to/2. Counterparties - Child - FACILITY LOCATIONS.csv"
    )
"""
import logging

_logger = logging.getLogger(__name__)


def run(env, corporate=None, facilities=None, contacts=None):
    """Execute partner import from dict lists and return counts."""
    _logger.info("run_import invoked with %d corporates, %d facilities, %d contacts",
                 len(corporate or []), len(facilities or []), len(contacts or []))

    return env["plasticos.partner.import.service"].run_full_import(
        corporate, facilities, contacts
    )


def run_csv(env, corporate_csv, facility_csv):
    """
    Execute partner import from CSV files.

    Args:
        env: Odoo environment
        corporate_csv: Path to corporate CSV (file 1)
        facility_csv: Path to facility CSV (file 2)

    Returns:
        dict with counts: {corporates, facilities, contacts}

    Example:
        from plasticos_partner_import.scripts.run_import import run_csv
        result = run_csv(env,
            corporate_csv="docs/1. Counterparties - Parent - CORPORATE-Ready To Import.csv",
            facility_csv="docs/2. Counterparties - Child - FACILITY LOCATIONS.csv"
        )
    """
    _logger.info("run_csv invoked with corporate=%s, facility=%s",
                 corporate_csv, facility_csv)

    return env["plasticos.partner.import.service"].run_csv_import(
        corporate_csv, facility_csv
    )
