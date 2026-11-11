"""Move profiles that still use the Bales form onto packaging Bales."""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

FORM_BALE = "plasticos_material_profile.form_bale"
PACKAGING_BALES = "plasticos_material_profile.packaging_bales"


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    form = env.ref(FORM_BALE, raise_if_not_found=False)
    packaging = env.ref(PACKAGING_BALES, raise_if_not_found=False)
    if not form or not packaging:
        _logger.warning("Skipped the Bales form move; a master record is missing.")
        return
    profiles = env["plasticos.material.profile"].with_context(active_test=False).search([("form_id", "=", form.id)])
    empty = profiles.filtered(lambda profile: not profile.packaging_type_id)
    if empty:
        empty.write({"packaging_type_id": packaging.id})
    if profiles:
        profiles.write({"form_id": False})
    _logger.info(
        "Cleared the Bales form on %s material profiles; %s gained packaging Bales.",
        len(profiles),
        len(empty),
    )
