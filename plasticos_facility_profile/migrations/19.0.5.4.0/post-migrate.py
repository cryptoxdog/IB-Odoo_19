"""Clear facility form preferences that point at the six former forms.

There is no grade preference field, so the preference is cleared, not moved.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    from odoo.addons.plasticos_material_profile.grade_migration import clear_former_form_links  # noqa: PLC0415

    env = api.Environment(cr, SUPERUSER_ID, {})
    for model_name in ("plasticos.facility.profile", "plasticos.facility.template"):
        clear_former_form_links(env, model_name, "form_preference_id")
    env.flush_all()
