"""Retire the material-taxonomy partner tags (C1 lane G1).

``data/material_taxonomy.xml`` loaded 108 ``res.partner.category`` records
(groups Polymers, Material Types, Forms, Source Types, Colors, Grades) that
copied the material vocabulary owned by ``plasticos_material_profile``. No code
read them. 19.0.1.1.15 stops loading the file; this removes the records by their
``plasticos_base`` external ids, which also removes their links from partners.

Before removal it logs, per tag, how many partners carried it (archived partners
and archived tags included). Only records whose external id is in
``RETIRED_TAG_XMLIDS`` under module ``plasticos_base`` are removed; the
Operational and Material Focus tags of ``partner_tags.xml`` are untouched. A
second run finds nothing and changes nothing.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

MODULE = "plasticos_base"
TAG_MODEL = "res.partner.category"

RETIRED_TAG_XMLIDS = (
    "category_polymers",
    "category_material_types",
    "partner_tag_polymer_hdpe",
    "partner_tag_polymer_hmw_hdpe",
    "partner_tag_polymer_ldpe",
    "partner_tag_polymer_lldpe",
    "partner_tag_polymer_pp",
    "partner_tag_polymer_bopp",
    "partner_tag_polymer_pet",
    "partner_tag_polymer_rpet",
    "partner_tag_polymer_ps",
    "partner_tag_polymer_eps",
    "partner_tag_polymer_hips",
    "partner_tag_polymer_pvc",
    "partner_tag_polymer_eva",
    "partner_tag_polymer_abs",
    "partner_tag_polymer_pa",
    "partner_tag_polymer_pc",
    "partner_tag_polymer_pbt",
    "partner_tag_polymer_pom",
    "partner_tag_polymer_pmma",
    "partner_tag_polymer_ppo",
    "partner_tag_polymer_tpe",
    "partner_tag_polymer_tpo",
    "partner_tag_polymer_tpu",
    "partner_tag_polymer_pla",
    "partner_tag_polymer_pp_pe",
    "partner_tag_polymer_pc_pmma",
    "partner_tag_polymer_mixed",
    "partner_tag_polymer_mrp",
    "partner_tag_polymer_ewaste",
    "partner_tag_polymer_metal",
    "partner_tag_polymer_occ",
    "partner_tag_polymer_boxes",
    "partner_tag_polymer_pallets",
    "category_forms",
    "category_source_types",
    "category_colors",
    "form_bag",
    "form_bale",
    "form_chop",
    "form_dens",
    "form_film",
    "form_flake",
    "form_gay",
    "form_log",
    "form_loose",
    "form_pal",
    "form_part",
    "form_patty",
    "form_pell",
    "form_purg",
    "form_reg",
    "form_repro",
    "form_rg",
    "form_roll",
    "form_sheet",
    "form_shred",
    "form_sweep",
    "source_type_clean",
    "source_type_cont",
    "source_type_mixed",
    "source_type_no_value",
    "source_type_off_grade",
    "source_type_off",
    "tag_source_type_post_consumer",
    "source_type_pc",
    "tag_source_type_post_industrial",
    "source_type_pi",
    "source_type_reusable",
    "source_type_reuse",
    "color_black",
    "color_blue",
    "color_blue_white",
    "color_clear",
    "color_dark",
    "color_gray",
    "color_green",
    "color_mixed_color",
    "color_natural",
    "color_orange",
    "color_print",
    "color_red",
    "color_white",
    "color_yellow",
    "category_grades",
    "grade_food_grade",
    "grade_medical_grade",
    "grade_fda_approved",
    "grade_usp_class_vi",
    "grade_prime",
    "grade_wide_spec",
    "grade_off_grade",
    "material_type_clean",
    "material_type_dirty",
    "material_type_dry",
    "material_type_metalized",
    "material_type_mixed",
    "material_type_no_metal",
    "material_type_no_print",
    "material_type_off_grade",
    "material_type_other",
    "material_type_pcr",
    "material_type_pir",
    "material_type_wet",
    "material_type_with_metal",
    "material_type_with_print",
    "material_type_reusable",
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {"active_test": False})
    data = env["ir.model.data"].search(
        [("module", "=", MODULE), ("model", "=", TAG_MODEL), ("name", "in", list(RETIRED_TAG_XMLIDS))]
    )
    tag_ids = data.mapped("res_id")
    tags = env[TAG_MODEL].browse(tag_ids).exists()
    if not tags:
        _logger.info("post-migrate 19.0.1.1.15: no material-taxonomy partner tags to remove")
        return
    cr.execute(
        "SELECT category_id, count(*) FROM res_partner_res_partner_category_rel "
        "WHERE category_id IN %s GROUP BY category_id",
        (tuple(tags.ids),),
    )
    usage = dict(cr.fetchall())
    name_by_id = {row.res_id: row.name for row in data}
    carried = 0
    for tag in tags:
        count = usage.get(tag.id, 0)
        carried += count
        _logger.info(
            "post-migrate 19.0.1.1.15: tag %s.%s (%s) carried by %d partner(s)",
            MODULE,
            name_by_id.get(tag.id),
            tag.name,
            count,
        )
    tags.unlink()
    data.exists().unlink()
    _logger.info(
        "post-migrate 19.0.1.1.15: removed %d material-taxonomy partner tags; %d partner link(s) removed",
        len(tags),
        carried,
    )
