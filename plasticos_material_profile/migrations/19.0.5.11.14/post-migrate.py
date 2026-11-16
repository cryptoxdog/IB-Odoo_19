"""Move profiles that still use the Bales form onto packaging Bales.

Clearing ``form_id`` changes the profile's identity key. The key is enforced twice:
``plasticos.material.profile._check_unique_triple_before_save`` and the partial
``NULLS NOT DISTINCT`` unique indexes

* ``(partner_id, polymer_id, form_id, material_grade_id) WHERE partner_id IS NOT NULL``
  (``plasticos_material_profile``), and
* ``(facility_profile_id, polymer_id, form_id, material_grade_id)
  WHERE partner_id IS NULL AND facility_profile_id IS NOT NULL`` (``plasticos_crm_bridge``).

A Bales profile whose owner already has a form-less profile with the same polymer
and grade, or that shares that key with another Bales profile, cannot lose its form
without a duplicate, and one such write would abort the whole addon upgrade.
Those profiles keep the Bales form; they only gain packaging Bales when they have
none (packaging is not part of the key). A WARNING names each one and the row it
would collide with, for an operator to resolve. Nothing is deleted, merged, or
reassigned. Every other Bales profile is moved exactly as before. A rerun only
finds the colliding profiles again, so the migration is idempotent.

Edited in place (PR #516 review): Staging already ran this version with no
collision, and Production (``plasticos_material_profile`` 19.0.5.11.13) has not
run it yet, so the corrected body is what Production executes.
"""

import logging

_logger = logging.getLogger(__name__)

FORM_BALE = "plasticos_material_profile.form_bale"
PACKAGING_BALES = "plasticos_material_profile.packaging_bales"

_FACILITY_COLUMN_SQL = """
    SELECT 1 FROM information_schema.columns
     WHERE table_name = 'plasticos_material_profile' AND column_name = 'facility_profile_id'
"""
_ROWS_SQL = """
    SELECT id, partner_id, NULL, polymer_id, material_grade_id, form_id
      FROM plasticos_material_profile
     WHERE form_id = %s OR form_id IS NULL
"""
_ROWS_WITH_FACILITY_SQL = """
    SELECT id, partner_id, facility_profile_id, polymer_id, material_grade_id, form_id
      FROM plasticos_material_profile
     WHERE form_id = %s OR form_id IS NULL
"""


def identity_owner(partner_id, facility_profile_id):
    """Return the owner part of the unique key, or None when no index covers the row."""
    if partner_id:
        return ("partner", partner_id)
    if facility_profile_id:
        return ("facility", facility_profile_id)
    return None


def partition_bales_profiles(bales_rows, formless_rows):
    """Split Bales profiles into those whose form can be cleared and those that collide.

    Each row is ``(id, partner_id, facility_profile_id, polymer_id, material_grade_id)``.
    ``bales_rows`` hold the Bales form; ``formless_rows`` already have no form.
    Returns ``(safe_ids, collisions)`` where ``collisions`` maps a colliding Bales
    profile id to the sorted ids of the rows it would duplicate. A Bales profile is
    safe only when clearing its form duplicates neither an existing row nor another
    Bales profile in this batch; two Bales profiles sharing a target key both stay.
    """
    occupied = {}
    for row_id, partner_id, facility_id, polymer_id, grade_id in formless_rows:
        owner = identity_owner(partner_id, facility_id)
        if owner is not None:
            occupied.setdefault((owner, polymer_id, grade_id or None), []).append(row_id)

    targets = {}
    for row_id, partner_id, facility_id, polymer_id, grade_id in bales_rows:
        owner = identity_owner(partner_id, facility_id)
        key = (owner, polymer_id, grade_id or None) if owner is not None else ("unowned", row_id)
        targets.setdefault(key, []).append(row_id)

    safe_ids = []
    collisions = {}
    for key, ids in targets.items():
        existing = occupied.get(key, []) if key[0] != "unowned" else []
        if not existing and len(ids) == 1:
            safe_ids.append(ids[0])
            continue
        for row_id in ids:
            collisions[row_id] = sorted(existing + [other for other in ids if other != row_id])
    return sorted(safe_ids), collisions


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    form = env.ref(FORM_BALE, raise_if_not_found=False)
    packaging = env.ref(PACKAGING_BALES, raise_if_not_found=False)
    if not form or not packaging:
        _logger.warning("Skipped the Bales form move; a master record is missing.")
        return

    cr.execute(_FACILITY_COLUMN_SQL)
    has_facility = bool(cr.fetchone())
    cr.execute(_ROWS_WITH_FACILITY_SQL if has_facility else _ROWS_SQL, (form.id,))
    bales_rows, formless_rows = [], []
    for row_id, partner_id, facility_id, polymer_id, grade_id, form_id in cr.fetchall():
        target = bales_rows if form_id == form.id else formless_rows
        target.append((row_id, partner_id, facility_id, polymer_id, grade_id))
    safe_ids, collisions = partition_bales_profiles(bales_rows, formless_rows)

    Profile = env["plasticos.material.profile"].with_context(active_test=False)
    profiles = Profile.browse([row[0] for row in bales_rows])
    empty = profiles.filtered(lambda profile: not profile.packaging_type_id)
    if empty:
        empty.write({"packaging_type_id": packaging.id})
    if safe_ids:
        Profile.browse(safe_ids).write({"form_id": False})
    for profile_id in sorted(collisions):
        _logger.warning(
            "Kept the Bales form on material profile %s: clearing it would duplicate the identity of "
            "material profile(s) %s. Resolve the duplicate, then clear the form.",
            profile_id,
            collisions[profile_id],
        )
    _logger.info(
        "Cleared the Bales form on %s material profiles; kept it on %s colliding profiles; %s gained packaging Bales.",
        len(safe_ids),
        len(collisions),
        len(empty),
    )
