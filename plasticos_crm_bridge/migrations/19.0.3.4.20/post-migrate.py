"""Report lineage readiness after the native Opportunity root lands.

Runs on upgrade only. Historical match runs, results and offers keep null
lineage; nothing is backfilled with a guessed opportunity or lot. Opportunities
sharing one source intake would block the new partial unique index, so they
are reported here for an operator decision, never merged.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        SELECT source_intake_id, COUNT(*)
        FROM crm_lead
        WHERE type = 'opportunity' AND source_intake_id IS NOT NULL
        GROUP BY source_intake_id
        HAVING COUNT(*) > 1
        """
    )
    duplicates = cr.fetchall()
    for intake_id, count in duplicates:
        _logger.warning(
            "plasticos_crm_bridge 19.0.3.4.20: source intake %s has %s opportunities; "
            "the one-opportunity-per-source-intake index cannot be created until an operator resolves it",
            intake_id,
            count,
        )
    cr.execute("SELECT COUNT(*) FROM plasticos_match_run WHERE opportunity_id IS NULL")
    legacy_runs = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM plasticos_offer WHERE match_result_id IS NULL")
    legacy_offers = cr.fetchone()[0]
    _logger.info(
        "plasticos_crm_bridge 19.0.3.4.20: %s historical match runs and %s historical offers keep null lineage",
        legacy_runs,
        legacy_offers,
    )
