"""Move the six former forms onto material grades on sale and purchase lines.

The stored material description recomputes; existing line names are not rewritten.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    from odoo.addons.plasticos_material_profile.grade_migration import move_former_forms  # noqa: PLC0415

    env = api.Environment(cr, SUPERUSER_ID, {})
    for model_name in ("sale.order.line", "purchase.order.line"):
        move_former_forms(env, model_name)
    env.flush_all()
