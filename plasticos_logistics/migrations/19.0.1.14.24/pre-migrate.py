"""S11 (OP11-E01): container journey facts become revisioned, append-only.

Before the registry adds the revision constraint:

* add ``revision`` and set it to 1 on every fact recorded before this version,
  so each existing row is revision 1 of its kind;
* drop the S9 ``UNIQUE(journey_id, fact_kind)`` index, replaced by
  ``UNIQUE(journey_id, fact_kind, revision)``.

No fact value is read, rewritten or deleted. A rerun changes nothing.
"""

import logging

_logger = logging.getLogger(__name__)

TABLE = "plasticos_iso_journey_fact"
OLD_CONSTRAINT = "plasticos_iso_journey_fact_one_fact_per_kind"


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass(%s)", (f"public.{TABLE}",))
    if not cr.fetchone()[0]:
        return
    # justification: schema step before the ORM update; constant identifiers only.
    cr.execute("ALTER TABLE plasticos_iso_journey_fact ADD COLUMN IF NOT EXISTS revision integer")
    cr.execute("UPDATE plasticos_iso_journey_fact SET revision = 1 WHERE revision IS NULL")
    backfilled = cr.rowcount
    cr.execute(
        "SELECT 1 FROM pg_constraint WHERE conrelid = %s::regclass AND conname = %s",
        (TABLE, OLD_CONSTRAINT),
    )
    dropped = bool(cr.fetchone())
    if dropped:
        cr.execute(
            "ALTER TABLE plasticos_iso_journey_fact DROP CONSTRAINT plasticos_iso_journey_fact_one_fact_per_kind"
        )
    _logger.info(
        "S11 journey facts: %s row(s) set to revision 1; %s %s",
        backfilled,
        OLD_CONSTRAINT,
        "dropped" if dropped else "already absent",
    )
