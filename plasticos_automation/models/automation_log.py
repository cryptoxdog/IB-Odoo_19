import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class PlasticosAutomationLog(models.Model):
    _name = "plasticos.automation.log"
    _description = "Automation Execution Log"
    _order = "create_date desc"

    name = fields.Char(required=True)
    model_name = fields.Char(
        string="Model",
        required=True,
        help="Technical model name of the affected record.",
    )
    res_id = fields.Integer(
        string="Record ID",
        required=True,
        help="Database ID of the affected record.",
    )
    action_type = fields.Selection(
        [
            ("approval_flag", "Approval Flag"),
            ("invoice_reminder", "Invoice Reminder"),
            ("contract_alert", "Contract Renewal Alert"),
            ("stock_alert", "Stock Reorder Alert"),
            ("logistics_followup", "Logistics Follow-up"),
            ("logistics_escalation", "Logistics Escalation"),
        ],
        required=True,
        string="Action Type",
    )
    note = fields.Text()
