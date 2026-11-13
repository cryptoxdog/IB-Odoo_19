"""Shared escalation routing: one manager resolver and one routing write for every PlasticOS addon.

An unresolved exception is routed to manager-level personnel. It is never routed to the
salesperson, to the cron service user, or to whoever happens to run the code, and it is never
dropped silently: with no eligible manager the caller's record carries one chatter note and
the server log carries an error.
"""

import logging

from odoo import SUPERUSER_ID, api, models

_logger = logging.getLogger(__name__)

SYSTEM_CRON_USER_XMLID = "plasticos_base.user_system_cron"
NOT_ROUTED_PREFIX = "Not routed:"


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _plasticos_escalation_manager_in_group(self, group, company=None):
        """Return the one eligible manager of ``group``, or an empty recordset.

        Eligible: active, internal (``share`` is false), not the system cron user and not the
        superuser. Implied membership counts. With a company, the manager must be allowed in
        that company. The lowest id wins, so the pick is deterministic.
        """
        if not group or group._name != "res.groups":
            return self.browse()
        excluded = [SUPERUSER_ID]
        cron_user = self.env.ref(SYSTEM_CRON_USER_XMLID, raise_if_not_found=False)
        if cron_user:
            excluded.append(cron_user.id)
        domain = [
            ("all_group_ids", "in", group.ids),
            ("active", "=", True),
            ("share", "=", False),
            ("id", "not in", excluded),
        ]
        if company:
            domain.append(("company_ids", "in", company.ids))
        # A cron run and a user who cannot read other users' access rights must resolve the same owner.
        elevated = self.sudo()  # sudo: read-only group membership lookup, returns one user id
        return self.browse(elevated.search(domain, order="id ASC", limit=1).id)

    @api.model
    def _plasticos_escalation_manager(self, group_xmlid, company=None):
        """Resolve ``group_xmlid`` and return its eligible manager, or an empty recordset.

        The group is named by XML id so that a module below the group's owner can call this.
        An unknown XML id, or one that names another model, has no manager.
        """
        group = self.env.ref(group_xmlid, raise_if_not_found=False) if group_xmlid else None
        return self._plasticos_escalation_manager_in_group(group, company)

    @api.model
    def _plasticos_note_unrouted_escalation(self, record, label, reason):
        """Log an unrouted escalation and note it once on ``record``. Return whether the note was posted.

        ``label`` names the obligation in plain words. It is the idempotency key: a record
        carries one note per label however often the escalation is retried.
        """
        record.ensure_one()
        marker = f"{NOT_ROUTED_PREFIX} {label}."
        _logger.error("%s %s %s (%s id=%s)", marker, reason, record.display_name, record._name, record.id)
        already = self.env["mail.message"].search_count(
            [("model", "=", record._name), ("res_id", "=", record.id), ("body", "ilike", marker)],
            limit=1,
        )
        if already:
            return False
        record.message_post(
            body=f"{marker} {reason}",
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )
        return True

    @api.model
    def _plasticos_escalate_to_manager(self, record, group_xmlid, summary, note, label, companies=None, one_open=True):
        """Assign one escalation Activity on ``record`` to the eligible manager.

        ``companies`` is the record's established legal company: empty resolves any eligible
        manager, one scopes the manager to it, and several conflict and resolve nobody.
        With ``one_open`` an open Activity carrying the same summary is kept and no second
        one is created. With nobody eligible nothing is assigned: the escalation is logged
        and noted once on the record. Returns the user who owns the open Activity, or an
        empty recordset when it was not routed.
        """
        record.ensure_one()
        if one_open:
            existing = self.env["mail.activity"].search(
                [("res_model", "=", record._name), ("res_id", "=", record.id), ("summary", "=", summary)],
                order="id ASC",
                limit=1,
            )
            if existing:
                return existing.user_id
        if companies and len(companies) > 1:
            manager = self.browse()
            reason = "The record belongs to more than one company, so no manager owns it."
        else:
            manager = self._plasticos_escalation_manager(group_xmlid, companies or None)
            reason = "No active manager is eligible" + (f" in {companies.display_name}." if companies else ".")
        if not manager:
            self._plasticos_note_unrouted_escalation(record, label, f"{reason} Assign it manually.")
            return manager
        record.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=manager.id,
            summary=summary,
            note=note,
        )
        return manager
