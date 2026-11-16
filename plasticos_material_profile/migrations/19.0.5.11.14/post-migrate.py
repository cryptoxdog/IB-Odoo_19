"""Retire Bales as a form: Bales-form profiles end with packaging Bales and no form.

Clearing the form can duplicate a profile identity, and a duplicate aborted the
whole upgrade (PR #516 review). ``plasticos_material_profile.bales_retirement``
moves a profile whose form-less key is free, merges a duplicate into the existing
form-less profile (fill empty fields, repoint every reference, delete the
duplicate), logs every pair it cannot resolve and never raises.

Edited in place (PR #516 / #517): Staging already ran this version, and
Production (``plasticos_material_profile`` 19.0.5.11.13) has not run it yet, so
the corrected body is what Production executes. 19.0.5.13.5 runs the same,
idempotent retirement for databases that already passed this version.
"""

from odoo import SUPERUSER_ID, api

FORM_BALE = "plasticos_material_profile.form_bale"
PACKAGING_BALES = "plasticos_material_profile.packaging_bales"


def migrate(cr, version):
    from odoo.addons.plasticos_material_profile import bales_retirement  # noqa: PLC0415

    env = api.Environment(cr, SUPERUSER_ID, {})
    # Both master records must exist; the helper logs and returns when either is missing.
    if env.ref(FORM_BALE, raise_if_not_found=False) and env.ref(PACKAGING_BALES, raise_if_not_found=False):
        bales_retirement.retire_bales_form(env)
