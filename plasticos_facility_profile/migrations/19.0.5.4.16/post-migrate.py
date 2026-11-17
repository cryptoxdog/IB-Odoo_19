"""Reformat the phones and emails already stored on partners and phone lines.

19.0.5.4.16 formats ``res.partner.phone``, ``res.partner.email`` and
``plasticos.partner.phone.number`` on create and write. This brings the rows
written before that into the same format, in batches of 1000 ids, with tracking
and mail notifications disabled.

A row is written only when its formatted value differs. A phone line whose
formatted number equals another line of the same partner and label is the same
number written twice; the later line is removed so the
``unique(partner_id, label, number)`` constraint holds. Counts are logged:
formatted, unchanged, unparseable, invalid email entries dropped, duplicate
phone lines removed. A second run changes nothing.
"""

import logging
from collections import Counter

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

BATCH = 1000
QUIET = {
    "tracking_disable": True,
    "mail_notrack": True,
    "mail_create_nolog": True,
    "mail_notify_force_send": False,
    "active_test": False,
}


def _country_code(partner):
    """The partner's country, else its commercial company's, else US."""
    codes = (
        partner.country_id.code,
        partner.commercial_partner_id.country_id.code,
        partner.parent_id.commercial_partner_id.country_id.code,
    )
    return next((code for code in codes if code), "US")


def _batches(ids):
    for start in range(0, len(ids), BATCH):
        yield ids[start : start + BATCH]


def _partners(env, fmt, counts):
    partner_model = env["res.partner"].with_context(**QUIET)
    ids = partner_model.search(["|", ("phone", "!=", False), ("email", "!=", False)], order="id").ids
    for chunk in _batches(ids):
        for partner in partner_model.browse(chunk):
            vals = {}
            if partner.phone:
                result = fmt.format_phone_result(partner.phone, _country_code(partner))
                if not result.parsed:
                    counts["unparseable"] += 1
                if (result.value or False) != partner.phone:
                    vals["phone"] = result.value or False
            if partner.email:
                result = fmt.format_emails_result(partner.email)
                counts["invalid_email_dropped"] += result.dropped
                if (result.value or False) != partner.email:
                    vals["email"] = result.value or False
            if vals:
                partner.write(vals)
                counts["formatted"] += 1
            else:
                counts["unchanged"] += 1
        env.flush_all()
        env.invalidate_all()


def _phone_lines(env, fmt, counts):
    line_model = env["plasticos.partner.phone"].with_context(**QUIET)
    ids = line_model.search([], order="partner_id, label, id").ids
    for chunk in _batches(ids):
        for line in line_model.browse(chunk):
            result = fmt.format_phone_result(line.number, _country_code(line.partner_id))
            if not result.parsed:
                counts["unparseable"] += 1
            if not result.value or result.value == line.number:
                counts["unchanged"] += 1
                continue
            twin = line_model.search(
                [
                    ("partner_id", "=", line.partner_id.id),
                    ("label", "=", line.label),
                    ("number", "=", result.value),
                    ("id", "!=", line.id),
                ],
                limit=1,
            )
            if twin:
                line.unlink()
                counts["duplicate_lines_removed"] += 1
                continue
            line.write({"number": result.value})
            counts["formatted"] += 1
        env.flush_all()
        env.invalidate_all()


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.plasticos_facility_profile.services import contact_format as fmt

    counts = Counter()
    _partners(env, fmt, counts)
    _phone_lines(env, fmt, counts)
    _logger.info(
        "post-migrate 19.0.5.4.16 contact format: formatted=%d unchanged=%d unparseable=%d "
        "invalid_email_dropped=%d duplicate_lines_removed=%d",
        counts["formatted"],
        counts["unchanged"],
        counts["unparseable"],
        counts["invalid_email_dropped"],
        counts["duplicate_lines_removed"],
    )
