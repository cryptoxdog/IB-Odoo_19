"""Move the six former forms onto material grades on profiles and grade templates."""

from odoo import SUPERUSER_ID, api

TEMPLATE_GRADES = {
    "grade_plastic_pallets_no_metal": "PALLETS",
    "grade_hdpe_crates": "CRATES",
    "grade_hdpe_drums": "DRUMS",
    "grade_ibc_totes": "IBC_TOTES",
}


def migrate(cr, version):
    from odoo.addons.plasticos_material_profile.grade_migration import (  # noqa: PLC0415
        grades_by_code,
        move_former_forms,
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    grades = grades_by_code(env)
    for xmlid, code in TEMPLATE_GRADES.items():
        template = env.ref(f"plasticos_material_profile.{xmlid}", raise_if_not_found=False)
        if template and not template.material_grade_id:
            template.write({"material_grade_id": grades[code].id})
    move_former_forms(env, "plasticos.grade.template")
    move_former_forms(env, "plasticos.material.profile", notes_field="freeform_notes")
    env.flush_all()
