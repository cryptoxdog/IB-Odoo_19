"""Move the six former forms onto material grades on intakes.

The intake form is required, so a former form becomes ``OTHER``.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    from odoo.addons.plasticos_material_profile.grade_migration import move_former_forms  # noqa: PLC0415

    env = api.Environment(cr, SUPERUSER_ID, {})
    move_former_forms(env, "plasticos.intake", notes_field="intake_notes", replacement_form_code="OTHER")
    env.flush_all()
