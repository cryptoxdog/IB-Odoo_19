"""Retire Bales as a form on databases that already ran 19.0.5.11.14.

Same idempotent retirement as 19.0.5.11.14 (``bales_retirement``): any profile
still on the Bales form is moved or merged onto packaging Bales, and the Bales
form is archived. A database with no Bales-form profile only logs zero counts.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    from odoo.addons.plasticos_material_profile import bales_retirement  # noqa: PLC0415

    bales_retirement.retire_bales_form(api.Environment(cr, SUPERUSER_ID, {}))
