"""Direction, Supersacs, and the REPRO and LOOSE form retirements.

ADR-134 sections 5 and 6. A fresh install already has the seed names and no
rows to backfill, so this runs only on an upgrade. The body reports counts
and does not delete a profile.
"""


def migrate(cr, version):
    if not version:
        return
    from odoo.addons.plasticos_material_profile.vocabulary_migration import migrate_vocabulary  # noqa: PLC0415

    migrate_vocabulary(cr)
