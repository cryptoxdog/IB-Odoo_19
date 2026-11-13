"""Census legacy evidence before operation scope is added (Export campaign S3, RP-07-E094).

Refuses an unsupported baseline before anything changes: the installed module
must be 19.0.2.1.17 or 19.0.2.1.18 (Staging #487 released 19.0.2.1.18), and the
19.0.2.1.9 scale-ticket flag move must be present on plasticos_load. A database
that already ran this step under the campaign build 19.0.2.1.19 is left alone.

The script first shipped under 19.0.2.1.18. Staging released 19.0.2.1.18 without
it, so a database on that release would skip a 19.0.2.1.18 folder. It therefore
runs under 19.0.2.1.20 (PlasticOS Export single merge, 2026-11-13).

Refuses contradictory accepted evidence. Records a census
of the accepted decision provenance so the post-migration can prove that
classifying rows as legacy changed no actor, time or source digest.
"""

import json
import logging

_logger = logging.getLogger(__name__)

SUPPORTED_BASELINES = ("19.0.2.1.17", "19.0.2.1.18")
# The campaign build that already classified evidence under the first folder name.
ALREADY_MIGRATED = ("19.0.2.1.19",)
CENSUS_KEY = "plasticos_documents.s3_legacy_evidence_census"

# One digest over every accepted decision. The post-migration recomputes it.
CENSUS_SQL = """
    SELECT COUNT(*),
           COUNT(*) FILTER (WHERE association_state = 'accepted'),
           COUNT(*) FILTER (WHERE verified IS TRUE OR override IS TRUE),
           COALESCE(md5(string_agg(
               concat_ws('|', id, association_state, associated_by, associated_at, source_reference,
                         source_revision, subject_company_id, covered_quantity, verified, verified_by,
                         verified_at, override, override_by, override_at, evidence_digest,
                         evidence_attachment_id, res_model, res_id, transaction_id, load_id),
               ',' ORDER BY id)), '')
      FROM plasticos_document
"""


def _has_column(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return cr.fetchone() is not None


def _version_tuple(version):
    return tuple(int(part) for part in str(version).split(".") if part.isdigit())


def migrate(cr, version):
    if not version:
        return
    installed = _version_tuple(version)
    if installed in {_version_tuple(done) for done in ALREADY_MIGRATED}:
        _logger.info("plasticos_documents: evidence already classified at %s; census skipped", version)
        return
    if installed not in {_version_tuple(base) for base in SUPPORTED_BASELINES}:
        raise RuntimeError(
            f"plasticos_documents 19.0.2.1.20 upgrades only from {' or '.join(SUPPORTED_BASELINES)}; "
            f"installed is {version}. Upgrade to a reconciled baseline first."
        )
    for column in ("scale_ticket_reminder_sent", "scale_ticket_escalated"):
        if not _has_column(cr, "plasticos_load", column):
            raise RuntimeError(f"plasticos_load.{column} is missing: the 19.0.2.1.9 scale-ticket move is not applied.")
    cr.execute("SELECT to_regclass('public.plasticos_document')")
    if cr.fetchone()[0] is None:
        return
    # Contradictory source: an accepted decision bound to a checksum other than its association's.
    cr.execute(
        """
        SELECT id
          FROM plasticos_document
         WHERE association_state = 'accepted'
           AND (verified IS TRUE OR override IS TRUE)
           AND source_revision IS NOT NULL
           AND evidence_digest IS NOT NULL
           AND source_revision <> evidence_digest
           AND association_review_required IS NOT TRUE
         ORDER BY id
         LIMIT 50
        """
    )
    contradictory = [row[0] for row in cr.fetchall()]
    if contradictory:
        raise RuntimeError(
            "plasticos_documents: accepted decisions contradict their association checksum and are not "
            f"marked for review. Resolve these documents first: {contradictory}"
        )
    if _has_column(cr, "plasticos_document", "obligation_kind"):
        # Re-run after a partial upgrade: the census is already recorded.
        return
    cr.execute(CENSUS_SQL)
    total, accepted, decided, digest = cr.fetchone()
    # [rows, accepted, decided, provenance digest]
    census = json.dumps([total, accepted, decided, digest])
    cr.execute(
        """
        INSERT INTO ir_config_parameter (key, value, create_uid, write_uid, create_date, write_date)
        VALUES (%s, %s, 1, 1, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC')
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, write_date = EXCLUDED.write_date
        """,
        (CENSUS_KEY, census),
    )
    _logger.info(
        "plasticos_documents census: %s rows, %s accepted, %s decided, digest %s", total, accepted, decided, digest
    )
