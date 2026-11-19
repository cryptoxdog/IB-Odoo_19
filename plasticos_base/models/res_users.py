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
# Context key carrying the ids of users who may not own an escalation (the record's own user and
# the acting user). Passed by context so the resolver's ``(group_xmlid, company)`` signature holds.
EXCLUDE_CONTEXT_KEY = "plasticos_escalation_exclude_user_ids"


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _plasticos_escalation_domain(self, group, company=None):
        """Return the search domain of the users eligible to own an escalation of ``group``.

        Eligible: active, internal (``share`` is false), not the system cron user, not the
        superuser and not a user named in the ``EXCLUDE_CONTEXT_KEY`` context. Implied membership
        counts. With a company, the manager must be allowed in that company.
        """
        excluded = [SUPERUSER_ID, *self.env.context.get(EXCLUDE_CONTEXT_KEY, ())]
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
        return domain

    @api.model
    def _plasticos_escalation_manager_in_group(self, group, company=None):
        """Return the one eligible manager of ``group``, or an empty recordset.

        Eligibility is ``_plasticos_escalation_domain``. The lowest id wins, so the pick is
        deterministic.
        """
        if not group or group._name != "res.groups":
            return self.browse()
        # A cron run and a user who cannot read other users' access rights must resolve the same owner.
        elevated = self.sudo()  # sudo: read-only group membership lookup; the returned user is not sudo
        found = elevated.search(self._plasticos_escalation_domain(group, company), order="id ASC", limit=1)
        return self.browse(found.ids)

    @api.model
    def _plasticos_escalation_owner_is_eligible(self, user, group_xmlid, companies=None):
        """Return whether ``user`` may keep an open escalation of ``group_xmlid`` on a record of ``companies``.

        A record of several companies has no eligible owner. An activity left by an older routing
        (the salesperson, the buyer, the acting user) is not eligible and is reassigned.
        """
        if not user or (companies and len(companies) > 1):
            return False
        group = self.env.ref(group_xmlid, raise_if_not_found=False) if group_xmlid else None
        if not group or group._name != "res.groups":
            return False
        domain = [("id", "=", user.id), *self._plasticos_escalation_domain(group, companies or None)]
        return bool(self.sudo().search_count(domain, limit=1))  # sudo: read-only membership check

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
    def _plasticos_escalate_to_manager(
        self, record, group_xmlid, summary, note, label, companies=None, one_open=True, exclude_users=None
    ):
        """Assign one escalation Activity on ``record`` to the eligible manager.

        ``companies`` is the record's established legal company: empty resolves any eligible
        manager, one scopes the manager to it, and several conflict and resolve nobody.
        ``exclude_users`` are the record's own users (salesperson, buyer, responsible user):
        they never own its escalation, nor does the acting user, even when they are managers.
        With ``one_open`` an open Activity carrying the same summary is kept and no second
        one is created; one whose owner is no longer eligible (left by an older routing) is
        reassigned to the manager. With nobody eligible nothing is assigned: the escalation is
        logged and noted once on the record. Returns the user who owns the open Activity, or an
        empty recordset when it was not routed.
        """
        record.ensure_one()
        excluded = (exclude_users or self.browse()) | self.env.user
        users = self.with_context(**{EXCLUDE_CONTEXT_KEY: excluded.ids})
        existing = self.env["mail.activity"]
        if one_open:
            existing = existing.search(
                [("res_model", "=", record._name), ("res_id", "=", record.id), ("summary", "=", summary)],
                order="id ASC",
                limit=1,
            )
            if existing and users._plasticos_escalation_owner_is_eligible(existing.user_id, group_xmlid, companies):
                return existing.user_id
        if companies and len(companies) > 1:
            manager = self.browse()
            reason = "The record belongs to more than one company, so no manager owns it."
        else:
            manager = users._plasticos_escalation_manager(group_xmlid, companies or None)
            reason = "No active manager is eligible" + (f" in {companies.display_name}." if companies else ".")
        if not manager:
            self._plasticos_note_unrouted_escalation(record, label, f"{reason} Assign it manually.")
            return self.browse()
        if existing:
            existing.write({"user_id": manager.id})
            return self.browse(manager.id)
        record.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=manager.id,
            summary=summary,
            note=note,
        )
        return self.browse(manager.id)
