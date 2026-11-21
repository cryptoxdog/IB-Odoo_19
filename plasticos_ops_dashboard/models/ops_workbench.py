"""Operations Manager workbench: one declaration per queue drives its count and its drill (DEC-007).

Presentation and workflow only (DEC-004). Every queue reads records that already exist: the DEC-012
exception activities (``mail.activity`` typed by ``plasticos_documents``), pending Linda approvals
reserved to the Operations Manager (DEC-011), escalated or overdue claims, and held digitized
vendor bills. Nothing here stores a queue row, copies a business record or ranks anything.

A count is ``search_count`` of the same domain the drill opens, so the two cannot disagree. Record
rules and ``mail.activity``'s own access filter keep another company's items out of both.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

MAIL_ACTIVITY = "mail.activity"
LINDA_APPROVAL = "plasticos.linda.approval"
PLASTICOS_CLAIM = "plasticos.claim"
OPERATIONS_GROUP_XMLID = "plasticos_security_base.group_operations_manager"

# DEC-011 OPT-A: Linda held-command classes the Operations Manager keeps.
OPERATIONS_LINDA_COMMANDS = (
    "correct_fact",
    "record_container_tare",
    "record_verified_gross_mass",
    "record_regulatory_parties",
)
OPERATIONS_LINDA_EDGE_CASES = ("correction", "value_conflict", "unit_mismatch", "refusal_retry")

# Queue key -> (label, model). The domain of each key is built by ``_kpi_domain``.
WORKBENCH_KPIS = {
    "my_exceptions": ("My Exceptions", MAIL_ACTIVITY),
    "team_exceptions": ("Operations Team Exceptions", MAIL_ACTIVITY),
    "unassigned_exceptions": ("Unassigned Exceptions", MAIL_ACTIVITY),
    "overdue_exceptions": ("Overdue Operations Exceptions", MAIL_ACTIVITY),
    "classification_reviews": ("Classification Reviews", MAIL_ACTIVITY),
    "document_gaps": ("Document Gaps", MAIL_ACTIVITY),
    "held_vendor_bills": ("Held Vendor Bills", MAIL_ACTIVITY),
    "linda_operations": ("Linda Approvals for Operations", LINDA_APPROVAL),
    "claims_attention": ("Escalated or Overdue Claims", PLASTICOS_CLAIM),
}


def _router_api():
    """The plasticos_documents exception router constants. Cross-addon imports stay in functions."""
    from odoo.addons.plasticos_documents.models import exception_router

    return exception_router


class PlasticosOpsWorkbench(models.AbstractModel):
    _name = "plasticos.ops.workbench"
    _description = "Operations Manager Workbench (presentation only)"

    @api.model
    def _type_ids(self, *exception_classes):
        """Ids of the module-owned activity types of ``exception_classes`` (all classes when empty)."""
        router = _router_api()
        classes = exception_classes or tuple(router.EXCEPTION_CLASSES)
        ids = []
        for exception_class in classes:
            xmlid = router.EXCEPTION_CLASSES[exception_class]["type"]
            activity_type = self.env.ref(xmlid, raise_if_not_found=False)
            if activity_type:
                ids.append(activity_type.id)
        return ids

    @api.model
    def _operations_owned(self):
        """Activities owned by an Operations Manager. Logistics-owned work is never duplicated here."""
        group = self.env.ref(OPERATIONS_GROUP_XMLID, raise_if_not_found=False)
        return [("user_id.all_group_ids", "in", group.ids if group else [])]

    @api.model
    def _kpi_domain(self, key):
        """The one domain that both counts and drills queue ``key``."""
        router = _router_api()
        exceptions = [("activity_type_id", "in", self._type_ids())]
        today = fields.Date.context_today(self)
        domains = {
            "my_exceptions": [*exceptions, ("user_id", "=", self.env.uid)],
            "team_exceptions": [*exceptions, *self._operations_owned()],
            "unassigned_exceptions": [*exceptions, "|", ("user_id", "=", False), ("user_id.active", "=", False)],
            "overdue_exceptions": [*exceptions, *self._operations_owned(), ("date_deadline", "<", today)],
            "classification_reviews": [("activity_type_id", "in", self._type_ids(router.EXC_CLASSIFICATION_REVIEW))],
            "document_gaps": [
                (
                    "activity_type_id",
                    "in",
                    self._type_ids(
                        router.EXC_MISSING_DOCUMENTS, router.EXC_MISSING_SCALE_TICKET, router.EXC_EVIDENCE_GAP
                    ),
                ),
                *self._operations_owned(),
            ],
            "held_vendor_bills": [("activity_type_id", "in", self._type_ids(router.EXC_BLOCKED_BILL))],
            "linda_operations": [
                ("state", "=", "pending"),
                ("company_id", "in", self.env.companies.ids),
                "|",
                ("command", "in", OPERATIONS_LINDA_COMMANDS),
                ("edge_case", "in", OPERATIONS_LINDA_EDGE_CASES),
            ],
            # DEC-008: a claim has no company; it takes its transaction's sale order company.
            "claims_attention": [
                ("state", "not in", ("resolved", "archived")),
                "|",
                ("state", "=", "escalated"),
                ("is_overdue", "=", True),
                ("transaction_id.sale_order_id.company_id", "in", self.env.companies.ids),
            ],
        }
        return domains[key]

    @api.model
    def kpi_values(self):
        """``{key: count}`` for every queue, each counted on its own drill domain."""
        return {
            key: self.env[model].search_count(self._kpi_domain(key)) for key, (_label, model) in WORKBENCH_KPIS.items()
        }

    @api.model
    def action_open_kpi(self, key):
        """The drill of queue ``key``: the source model with the same domain its count uses."""
        label, model = WORKBENCH_KPIS[key]
        action = {
            "type": "ir.actions.act_window",
            "name": label,
            "res_model": model,
            "domain": self._kpi_domain(key),
            "view_mode": "list,form",
            "context": {"create": False},
        }
        if model == MAIL_ACTIVITY:
            action["views"] = [
                (self.env.ref("plasticos_ops_dashboard.view_ops_activity_list").id, "list"),
                (self.env.ref("plasticos_ops_dashboard.view_ops_activity_form").id, "form"),
            ]
            action["search_view_id"] = self.env.ref("plasticos_ops_dashboard.view_ops_activity_search").id
        return action
