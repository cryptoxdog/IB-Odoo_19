"""Replace the partner material unique constraint with a partial unique index.

Partner-owned rows keep one profile per partner, polymer, and form, including
an empty form. Rows with no partner are excluded so a lead-owned facility can
hold its own profiles.
"""

import logging

_logger = logging.getLogger(__name__)

_CONSTRAINT = "plasticos_material_profile_unique_partner_polymer_form"


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        "ALTER TABLE plasticos_material_profile "
        "DROP CONSTRAINT IF EXISTS plasticos_material_profile_unique_partner_polymer_form"
    )
    cr.execute("DELETE FROM ir_model_constraint WHERE name = %s", [_CONSTRAINT])
    _logger.info("Dropped partner material unique constraint %s", _CONSTRAINT)
