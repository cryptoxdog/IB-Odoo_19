"""Partner classification tags on companies, sites and people (ADR-131 Decision B).

The one owner of three rules:

* **Trade Role from ranks.** A company's Buyer / Supplier tags follow its native
  ``customer_rank`` / ``supplier_rank`` (both ranks -> both tags). The ranks are
  the source of truth. The first rank increase is an ORM write
  (``account`` ``_increase_rank``), so ``write`` sees it.
* **Mirror.** When a company's tags change, its sites and people get its
  Company Type tags, and its sites get its Trade Role and lead-status tags
  (the Status group without DNC, which stays per record). Every other tag a
  child carries (ERP Contact Role, DNC, ...) is left as it is. Child writes
  carry a context key, so they do not mirror again.
* **DNC.** When the Status tag DNC (``plasticos_base.tag_do_not_contact``) is set on a record, its
  email address(es) go to ``mail.blacklist`` and its phone numbers to
  ``phone.blacklist`` (when ``phone_validation`` is installed). Nothing is ever
  removed from a blacklist here.
"""

import logging

from odoo import Command, api, models, tools

from ..classification import mirrored_tag_ids, newly_tagged, synced_trade_tag_ids
from .res_partner_category import COMPANY_TYPE_XMLID, DO_NOT_CONTACT_XMLID, STATUS_XMLID, TRADE_ROLE_XMLID

_logger = logging.getLogger(__name__)

MIRROR_CONTEXT = "plasticos_classification_mirror"
RANK_FIELDS = ("customer_rank", "supplier_rank")
PHONE_FIELDS = ("phone", "mobile")


class ResPartner(models.Model):
    _inherit = "res.partner"

    # ── Trade Role from ranks ──────────────────────────────────────────
    def _plasticos_sync_trade_role_tags(self):
        members = self.env["res.partner.category"]._plasticos_group_members(TRADE_ROLE_XMLID)
        if not members:
            return
        for company in self.filtered(lambda partner: partner.company_type == "company"):
            current = set(company.category_id.ids)
            target = synced_trade_tag_ids(current, members, company.customer_rank, company.supplier_rank)
            if target != current:
                company.write({"category_id": [Command.set(sorted(target))]})

    # ── Mirror onto sites and people ───────────────────────────────────
    def _plasticos_mirror_classification(self):
        if self.env.context.get(MIRROR_CONTEXT):
            return
        categories = self.env["res.partner.category"]
        company_type = set(categories._plasticos_group_members(COMPANY_TYPE_XMLID).values())
        trade_role = set(categories._plasticos_group_members(TRADE_ROLE_XMLID).values())
        # DNC is set per record (its blacklist rule); the mirror never adds or removes it.
        dnc = self.env.ref(DO_NOT_CONTACT_XMLID, raise_if_not_found=False)
        lead_status = set(categories._plasticos_group_members(STATUS_XMLID).values()) - {dnc.id if dnc else 0}
        if not company_type and not trade_role and not lead_status:
            return
        quiet = self.with_context(**{MIRROR_CONTEXT: True})
        for company in self.filtered(lambda partner: partner.company_type == "company"):
            company_ids = company.category_id.ids
            for child in quiet.search([("id", "child_of", company.id), ("id", "!=", company.id)]):
                current = set(child.category_id.ids)
                target = mirrored_tag_ids(current, company_ids, company_type)
                if child._plasticos_is_site():
                    target = mirrored_tag_ids(target, company_ids, trade_role)
                    target = mirrored_tag_ids(target, company_ids, lead_status)
                if target != current:
                    child.write({"category_id": [Command.set(sorted(target))]})

    # ── DNC -> blacklists ────────────────────────────────────
    def _plasticos_blacklist_contact_points(self):
        # The blacklists are restricted to mail/phone admins; tagging DNC must still record it.
        mail_blacklist = self.env["mail.blacklist"].sudo()  # sudo: blacklist ACL is admin-only; add-only use here
        phone_blacklist = (
            self.env["phone.blacklist"].sudo()  # sudo: blacklist ACL is admin-only; add-only use here
            if "phone.blacklist" in self.env
            else None
        )
        message = self.env._("Added by PlasticOS: the contact is tagged DNC.")
        for partner in self:
            for email in tools.email_split(partner.email or ""):
                if tools.email_normalize(email):
                    mail_blacklist._add(email, message=message)
            if phone_blacklist is None:
                continue
            for field in PHONE_FIELDS:
                number = partner[field] if field in partner._fields else False
                if number and self.env.user._phone_format(number=number):
                    phone_blacklist.add(number, message=message)

    def _plasticos_tags_before(self, vals):
        return {partner.id: set(partner.category_id.ids) for partner in self} if "category_id" in vals else {}

    def _plasticos_after_tag_write(self, before):
        dnc = self.env.ref(DO_NOT_CONTACT_XMLID, raise_if_not_found=False)
        if dnc:
            tagged = self.filtered(
                lambda partner: newly_tagged(before.get(partner.id, ()), partner.category_id.ids, dnc.id)
            )
            if tagged:
                tagged._plasticos_blacklist_contact_points()
        self._plasticos_mirror_classification()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered("category_id")._plasticos_after_tag_write({})
        # Goes through write, which runs the tag rules for what it changes.
        records.filtered(lambda partner: any(partner[name] for name in RANK_FIELDS))._plasticos_sync_trade_role_tags()
        return records

    def write(self, vals):
        before = self._plasticos_tags_before(vals)
        res = super().write(vals)
        if any(name in vals for name in RANK_FIELDS):
            self._plasticos_sync_trade_role_tags()
        if "category_id" in vals:
            self._plasticos_after_tag_write(before)
        return res
