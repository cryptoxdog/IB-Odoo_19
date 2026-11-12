"""Point stored selections and profile letters at the quality-tier master.

Runs after the seed exists and after the old columns are gone. A profile
letter A, B, or C wins. Other sub_grade text is appended to freeform_notes.
An empty quality tier stays empty for Prime, Near Prime, Economy, and Unknown.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        SELECT 1
          FROM information_schema.tables
         WHERE table_schema = current_schema()
           AND table_name = 'plasticos_quality_tier_migration'
        """
    )
    if not cr.fetchone():
        return

    from odoo.addons.plasticos_material_profile.quality_tier_codes import (  # noqa: PLC0415
        notes_with_leftover,
        profile_quality_tier,
        template_quality_tier_code,
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    tiers = {tier.code: tier for tier in env["plasticos.material.quality.tier"].search([])}
    cr.execute(
        """
        SELECT res_model, res_id, old_tier, old_sub_grade
          FROM plasticos_quality_tier_migration
        """
    )
    filled = 0
    noted = 0
    for res_model, res_id, old_tier, old_sub_grade in cr.fetchall():
        if res_model == "plasticos.grade.template":
            code = template_quality_tier_code(old_tier)
            leftover = None
            record = env["plasticos.grade.template"].browse(res_id).exists()
        elif res_model == "plasticos.material.profile":
            code, leftover = profile_quality_tier(old_tier, old_sub_grade)
            record = env["plasticos.material.profile"].browse(res_id).exists()
        else:
            continue
        if not record:
            continue
        vals = {}
        tier = tiers.get(code) if code else None
        if tier and not record.quality_tier_id:
            vals["quality_tier_id"] = tier.id
            filled += 1
        if res_model == "plasticos.material.profile":
            notes = notes_with_leftover(record.freeform_notes, leftover)
            if notes is not None:
                vals["freeform_notes"] = notes
                noted += 1
        if vals:
            record.write(vals)
    cr.execute("DROP TABLE plasticos_quality_tier_migration")
    env.flush_all()
    _logger.info("Set %s quality tiers and kept %s leftover sub-grade notes.", filled, noted)
