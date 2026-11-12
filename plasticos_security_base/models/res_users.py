from odoo import api, models

SYSTEM_CRON_USER_XMLID = "plasticos_base.user_system_cron"


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _plasticos_manager_reviewer(self, group_xmlid):
        """Return the one user an unresolved exception is routed to, or an empty recordset.

        The reviewer is the lowest-id active internal user who holds the group
        named by ``group_xmlid`` (directly or through an implying group). The
        system cron user is a technical actor and is never eligible, even when
        it holds the group for ACL reasons. An unknown group, or a group with no
        eligible member, returns an empty recordset: the caller must make that
        visible and must not substitute the current user.
        """
        group = self.env.ref(group_xmlid, raise_if_not_found=False)
        if not group or group._name != "res.groups":
            return self.browse()
        cron_user = self.env.ref(SYSTEM_CRON_USER_XMLID, raise_if_not_found=False)
        # sudo: group membership must resolve the same way for a cron run and for
        # a user who cannot read other users' access rights.
        internal_users = self.sudo().search([("share", "=", False), ("active", "=", True)], order="id ASC")
        for user in internal_users:
            if cron_user and user == cron_user:
                continue
            if user.has_group(group_xmlid):
                return self.browse(user.id)
        return self.browse()
