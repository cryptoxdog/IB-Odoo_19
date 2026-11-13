"""Classify every existing evidence row as legacy (Export campaign S3, RP-07-E095).

No operation revision, coverage, known quantity or unit is inferred from an
old covered_quantity or checksum. New operation rows begin only from an
attributed association. The accepted actor, time and source digest must equal
the pre-migration census; otherwise the upgrade stops. Re-running is a no-op.

The classified count is the number of rows that are ``legacy`` after this step,
not the rows this UPDATE touched: the ORM adds the required ``obligation_kind``
column with its ``legacy`` default before this script runs, so on a real upgrade
the UPDATE usually matches nothing (Export campaign S6, finding D1). When a
census was recorded, that count must equal the census row total.
"""

import importlib.util
import json
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)


def _pre_module():
    path = Path(__file__).with_name("pre-migrate.py")
    spec = importlib.util.spec_from_file_location("plasticos_documents_s3_pre_migrate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def migrate(cr, version):
    if not version:
        return
    pre = _pre_module()
    cr.execute(
        """
        UPDATE plasticos_document
           SET obligation_kind = 'legacy'
         WHERE obligation_kind IS NULL OR obligation_kind = ''
        """
    )
    updated = cr.rowcount
    cr.execute("SELECT COUNT(*) FROM plasticos_document WHERE obligation_kind = 'legacy'")
    classified = cr.fetchone()[0]
    cr.execute(
        """
        SELECT id
          FROM plasticos_document
         WHERE obligation_kind = 'legacy'
           AND (operation_revision_key IS NOT NULL OR coverage_key IS NOT NULL
                OR quantity_known IS TRUE OR evidence_uom_id IS NOT NULL)
         ORDER BY id
         LIMIT 50
        """
    )
    inferred = [row[0] for row in cr.fetchall()]
    if inferred:
        raise RuntimeError(f"plasticos_documents: legacy rows carry operation scope: {inferred}")
    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (pre.CENSUS_KEY,))
    row = cr.fetchone()
    if not row:
        _logger.info("plasticos_documents: no census recorded (already migrated); %s rows classified", classified)
        return classified
    cr.execute("SELECT COUNT(*) FROM plasticos_document WHERE obligation_kind <> 'legacy'")
    if cr.fetchone()[0]:
        raise RuntimeError("plasticos_documents: an upgrade cannot create operation-scoped evidence rows.")
    before = json.loads(row[0])
    if classified != before[0]:
        raise RuntimeError(
            f"plasticos_documents: the census recorded {before[0]} evidence rows but {classified} are classified legacy."
        )
    cr.execute(pre.CENSUS_SQL)
    total, accepted, decided, digest = cr.fetchone()
    after = [total, accepted, decided, digest]
    if after != before:
        raise RuntimeError(f"plasticos_documents: evidence provenance changed during upgrade: {before} -> {after}")
    cr.execute("DELETE FROM ir_config_parameter WHERE key = %s", (pre.CENSUS_KEY,))
    _logger.info(
        "plasticos_documents: %s rows classified legacy (%s set here, %s by the column default); provenance unchanged (%s)",
        classified,
        updated,
        classified - updated,
        after,
    )
    return classified
