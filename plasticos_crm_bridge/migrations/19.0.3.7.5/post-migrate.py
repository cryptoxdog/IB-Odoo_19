"""Report profiles that have no owner. Report only: nothing is changed or deleted.

A facility profile is owned by a facility partner or a CRM lead. A material
profile is owned by a facility partner or a lead-owned facility profile. The
base modules no longer declare ``partner_id`` NOT NULL, because lead-owned rows
legitimately have none. A database CHECK on the composed owner rule is not added
until a run of this report on Production shows zero rows without an owner.
"""

import logging

_logger = logging.getLogger(__name__)

_OWNER_RULES = (
    ("plasticos_facility_profile", "partner_id IS NULL AND crm_lead_id IS NULL"),
    ("plasticos_material_profile", "partner_id IS NULL AND facility_profile_id IS NULL"),
)


def _has_columns(cr, table, columns):
    cr.execute(
        """
        SELECT count(*)
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = %s
           AND column_name = ANY(%s)
        """,
        [table, list(columns)],
    )
    return cr.fetchone()[0] == len(columns)


def migrate(cr, version):
    if not version:
        return
    for table, missing_owner in _OWNER_RULES:
        columns = (
            ["partner_id", "crm_lead_id"] if "crm_lead_id" in missing_owner else ["partner_id", "facility_profile_id"]
        )
        if not _has_columns(cr, table, columns):
            _logger.info("%s: owner columns not present; owner report skipped", table)
            continue
        # Table and predicate are module constants above, never input.
        cr.execute(f"SELECT count(*) FROM {table} WHERE {missing_owner}")  # noqa: S608
        count = cr.fetchone()[0]
        if count:
            _logger.warning("%s: %s row(s) have no owner (%s); left unchanged", table, count, missing_owner)
        else:
            _logger.info("%s: every row has an owner", table)
