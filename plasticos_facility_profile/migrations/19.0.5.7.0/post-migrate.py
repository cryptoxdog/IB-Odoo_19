"""Move equipment, templates' stored shape, and accepted polymers (ADR-134 §9).

Runs after 19.0.5.7.0 removes the fields from the model. The retired columns
are still in the database. This reads them, writes capabilities grouped by
type and In profiles, records the review list, then drops the columns and the
retired tables. A second run finds the columns gone and changes nothing.
Counts are logged.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

MIGRATION = "19.0.5.7.0"
_PROFILE = "plasticos_facility_profile"


def migrate(cr, version):
    from odoo.addons.plasticos_facility_profile.capability_migration import plan_migration

    if not _table_exists(cr, _PROFILE) or "process_type" not in _columns(cr, _PROFILE):
        _logger.info("facility capability migration %s: retired columns already gone; counts unchanged", MIGRATION)
        return
    env = api.Environment(cr, SUPERUSER_ID, {"active_test": False, "tracking_disable": True})
    snapshots = _snapshots(cr)
    existing_profiles, _two_sided = _existing_profiles(cr)
    done = _done_keys(cr)
    known_forms = set(env["plasticos.material.form"].search([("active", "=", True)]).mapped("code"))
    plan = plan_migration(
        snapshots,
        known_forms=known_forms,
        existing_profiles=existing_profiles,
        existing_capabilities=done,
    )
    _apply(env, cr, plan)
    _drop_retired(cr)
    counts = plan.counts()
    counts["facilities_seen"] = len(snapshots)
    counts["two_sided_blank"] = sum(1 for row in existing_profiles if row.two_sided_blank)
    _logger.info("facility capability migration %s counts: %s", MIGRATION, counts)


def _columns(cr, table):
    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = %s
        """,
        (table,),
    )
    return {row[0] for row in cr.fetchall()}


def _table_exists(cr, table):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.tables
         WHERE table_schema = current_schema()
           AND table_name = %s
        """,
        (table,),
    )
    return cr.fetchone() is not None


def _snapshots(cr):
    from odoo.addons.plasticos_facility_profile.capability_migration import FacilitySnapshot

    equipment = _equipment_by_profile(cr)
    polymers = _polymers_by_profile(cr)
    forms = _form_codes(cr)
    cr.execute(
        """
        SELECT id, partner_id, process_type, form_preference_id,
               handles_bales, handles_regrind, handles_pellet, handles_flake, handles_rollstock,
               can_remove_metal, can_reduce_moisture, can_filter_fr, can_screen_fines,
               density_min, density_max, melt_index_min, melt_index_max
          FROM plasticos_facility_profile
         ORDER BY id
        """
    )
    rows = []
    for (
        facility_id,
        partner_id,
        process_type,
        form_id,
        bales,
        regrind,
        pellet,
        flake,
        rollstock,
        metal,
        moisture,
        fr,
        fines,
        density_min,
        density_max,
        melt_min,
        melt_max,
    ) in cr.fetchall():
        rows.append(
            FacilitySnapshot(
                facility_id=facility_id,
                partner_id=partner_id,
                equipment_codes=tuple(equipment.get(facility_id, ())),
                handles={
                    "handles_bales": bool(bales),
                    "handles_regrind": bool(regrind),
                    "handles_pellet": bool(pellet),
                    "handles_flake": bool(flake),
                    "handles_rollstock": bool(rollstock),
                },
                cans={
                    "can_remove_metal": bool(metal),
                    "can_reduce_moisture": bool(moisture),
                    "can_filter_fr": bool(fr),
                    "can_screen_fines": bool(fines),
                },
                process_type=process_type or None,
                form_preference_code=forms.get(form_id),
                polymer_ids=tuple(polymers.get(facility_id, ())),
                density_min=density_min,
                density_max=density_max,
                melt_index_min=melt_min,
                melt_index_max=melt_max,
            )
        )
    return rows


def _equipment_by_profile(cr):
    if not _table_exists(cr, "facility_profile_equipment_rel") or not _table_exists(cr, "plasticos_equipment_type"):
        return {}
    cr.execute(
        """
        SELECT rel.profile_id, equip.code
          FROM facility_profile_equipment_rel rel
          JOIN plasticos_equipment_type equip ON equip.id = rel.equipment_type_id
         ORDER BY rel.profile_id, equip.code
        """
    )
    grouped = {}
    for profile_id, code in cr.fetchall():
        grouped.setdefault(profile_id, []).append(code)
    return grouped


def _polymers_by_profile(cr):
    if not _table_exists(cr, "facility_profile_polymer_rel"):
        return {}
    cr.execute(
        """
        SELECT profile_id, polymer_id
          FROM facility_profile_polymer_rel
         ORDER BY profile_id, polymer_id
        """
    )
    grouped = {}
    for profile_id, polymer_id in cr.fetchall():
        grouped.setdefault(profile_id, []).append(polymer_id)
    return grouped


def _form_codes(cr):
    if not _table_exists(cr, "plasticos_material_form"):
        return {}
    cr.execute("SELECT id, code FROM plasticos_material_form")
    return {form_id: code for form_id, code in cr.fetchall()}


def _existing_profiles(cr):
    from odoo.addons.plasticos_facility_profile.capability_migration import ExistingProfile

    if not _table_exists(cr, "plasticos_material_profile"):
        return [], set()
    forms = _form_codes(cr)
    repro_ids = {form_id for form_id, code in forms.items() if code == "REPRO"}
    two_sided = _two_sided_partners(cr)
    cr.execute(
        """
        SELECT id, partner_id, polymer_id, form_id, material_grade_id, direction,
               density_min, density_max, mfi_min, mfi_max
          FROM plasticos_material_profile
         ORDER BY id
        """
    )
    rows = []
    for profile_id, partner_id, polymer_id, form_id, grade_id, direction, dmin, dmax, mmin, mmax in cr.fetchall():
        rows.append(
            ExistingProfile(
                profile_id=profile_id,
                partner_id=partner_id,
                polymer_id=polymer_id,
                form_code=forms.get(form_id),
                grade_id=grade_id,
                direction=direction or None,
                density_min=dmin,
                density_max=dmax,
                mfi_min=mmin,
                mfi_max=mmax,
                form_is_repro=form_id in repro_ids,
                two_sided_blank=bool(partner_id in two_sided and not direction),
            )
        )
    return rows, two_sided


def _two_sided_partners(cr):
    cr.execute(
        """
        SELECT id
          FROM res_partner
         WHERE COALESCE(customer_rank, 0) > 0
           AND COALESCE(supplier_rank, 0) > 0
        """
    )
    return {row[0] for row in cr.fetchall()}


def _done_keys(cr):
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS plasticos_facility_capability_migration_done (
            facility_id INTEGER NOT NULL,
            type_code VARCHAR NOT NULL,
            detail_key VARCHAR NOT NULL,
            capability_id INTEGER,
            UNIQUE (facility_id, type_code, detail_key)
        )
        """
    )
    cr.execute("SELECT facility_id, type_code, detail_key FROM plasticos_facility_capability_migration_done")
    return set(cr.fetchall())


def _ensure_review(cr):
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS plasticos_facility_capability_migration_review (
            migration VARCHAR NOT NULL,
            facility_id INTEGER,
            profile_id INTEGER,
            reason VARCHAR NOT NULL,
            detail VARCHAR,
            UNIQUE (migration, reason, detail)
        )
        """
    )


def _apply(env, cr, plan):
    _ensure_review(cr)
    types = {rec.code: rec for rec in env["plasticos.capability.type"].search([])}
    by_type = plan.creates_by_type()
    for type_code, rows in by_type.items():
        cap_type = types.get(type_code)
        if cap_type is None:
            for row in rows:
                _review(cr, row.facility_id, None, "unmapped_equipment", f"capability type {type_code} is not seeded")
            continue
        created = env["plasticos.capability"].create(
            [
                {
                    "facility_profile_id": row.facility_id,
                    "capability_type_id": cap_type.id,
                    "sequence": row.sequence,
                    **({"details": row.details} if row.details else {}),
                }
                for row in rows
            ]
        )
        for row, capability in zip(rows, created, strict=True):
            cr.execute(
                """
                INSERT INTO plasticos_facility_capability_migration_done
                    (facility_id, type_code, detail_key, capability_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (row.facility_id, row.type_code, row.detail_key, capability.id),
            )
    forms = {rec.code: rec.id for rec in env["plasticos.material.form"].search([])}
    packaging = {rec.code: rec.id for rec in env["plasticos.packaging.type"].search([])}
    fresh = [row for row in plan.profiles if not row.unchanged]
    if fresh:
        env["plasticos.material.profile"].create(
            [
                {
                    "partner_id": row.partner_id,
                    "polymer_id": row.polymer_id,
                    "form_id": forms.get(row.form_code) or False,
                    "packaging_type_id": packaging.get(row.packaging_code) or False,
                    "direction": row.direction,
                    "density_min": row.density_min or 0.0,
                    "density_max": row.density_max or 0.0,
                    "mfi_min": row.mfi_min or 0.0,
                    "mfi_max": row.mfi_max or 0.0,
                }
                for row in fresh
            ]
        )
    for item in plan.review:
        _review(cr, item.facility_id, item.profile_id, item.reason, item.detail)
    env.flush_all()


def _review(cr, facility_id, profile_id, reason, detail):
    cr.execute(
        """
        INSERT INTO plasticos_facility_capability_migration_review
            (migration, facility_id, profile_id, reason, detail)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (MIGRATION, facility_id, profile_id, reason, detail),
    )


_DROP_COLUMN = {
    "process_type": "ALTER TABLE plasticos_facility_profile DROP COLUMN process_type",
    "form_preference": "ALTER TABLE plasticos_facility_profile DROP COLUMN form_preference",
    "handles_bales": "ALTER TABLE plasticos_facility_profile DROP COLUMN handles_bales",
    "handles_regrind": "ALTER TABLE plasticos_facility_profile DROP COLUMN handles_regrind",
    "handles_pellet": "ALTER TABLE plasticos_facility_profile DROP COLUMN handles_pellet",
    "handles_flake": "ALTER TABLE plasticos_facility_profile DROP COLUMN handles_flake",
    "handles_rollstock": "ALTER TABLE plasticos_facility_profile DROP COLUMN handles_rollstock",
    "can_remove_metal": "ALTER TABLE plasticos_facility_profile DROP COLUMN can_remove_metal",
    "can_reduce_moisture": "ALTER TABLE plasticos_facility_profile DROP COLUMN can_reduce_moisture",
    "can_filter_fr": "ALTER TABLE plasticos_facility_profile DROP COLUMN can_filter_fr",
    "can_screen_fines": "ALTER TABLE plasticos_facility_profile DROP COLUMN can_screen_fines",
    "has_horizontal_baler": "ALTER TABLE plasticos_facility_profile DROP COLUMN has_horizontal_baler",
    "has_downstroke_baler": "ALTER TABLE plasticos_facility_profile DROP COLUMN has_downstroke_baler",
    "has_shredder": "ALTER TABLE plasticos_facility_profile DROP COLUMN has_shredder",
    "has_granulator": "ALTER TABLE plasticos_facility_profile DROP COLUMN has_granulator",
    "has_wash_line": "ALTER TABLE plasticos_facility_profile DROP COLUMN has_wash_line",
    "has_extruder": "ALTER TABLE plasticos_facility_profile DROP COLUMN has_extruder",
    "has_sorting_line": "ALTER TABLE plasticos_facility_profile DROP COLUMN has_sorting_line",
    "density_min": "ALTER TABLE plasticos_facility_profile DROP COLUMN density_min",
    "density_max": "ALTER TABLE plasticos_facility_profile DROP COLUMN density_max",
    "melt_index_min": "ALTER TABLE plasticos_facility_profile DROP COLUMN melt_index_min",
    "melt_index_max": "ALTER TABLE plasticos_facility_profile DROP COLUMN melt_index_max",
    "form_preference_id": "ALTER TABLE plasticos_facility_profile DROP COLUMN form_preference_id",
}
_DROP_TABLE = {
    "facility_profile_equipment_rel": "DROP TABLE facility_profile_equipment_rel CASCADE",
    "facility_template_equipment_rel": "DROP TABLE facility_template_equipment_rel CASCADE",
    "facility_profile_polymer_rel": "DROP TABLE facility_profile_polymer_rel CASCADE",
    "plasticos_equipment_type": "DROP TABLE plasticos_equipment_type CASCADE",
    "plasticos_facility_template": "DROP TABLE plasticos_facility_template CASCADE",
}


def _drop_retired(cr):
    present = _columns(cr, _PROFILE)
    for column, statement in _DROP_COLUMN.items():
        if column in present:
            cr.execute(statement)
    for table, statement in _DROP_TABLE.items():
        if _table_exists(cr, table):
            cr.execute(statement)
