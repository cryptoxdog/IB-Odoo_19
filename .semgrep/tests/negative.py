# filename: .semgrep/tests/negative.py
"""Negative Semgrep fixtures for PlasticOS IB-Odoo_19.

These examples demonstrate accepted patterns and should produce no blocking
findings from the hardened Semgrep rules.
"""

import yaml
from odoo import api, fields, models


class PlasticosSemgrepNegativeFixture(models.Model):
    _name = "plasticos.semgrep.negative.fixture"
    _description = "Semgrep Negative Fixture"

    name = fields.Char(help="Fixture name for Semgrep negative controls.", tracking=True)

    name_unique = models.Constraint(
        "UNIQUE(name)",
        "Name must be unique.",
    )

    @api.depends("name")
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.name or "negative fixture"

    def action_specific_exception(self):
        try:
            return self.env["res.partner"].search([], limit=1)
        except ValueError:
            return self.env["res.partner"]

    def action_safe_yaml(self, yaml_text):
        return yaml.safe_load(yaml_text)

    def action_parameterized_sql(self, partner_id):
        self.env.cr.execute(
            "SELECT id FROM res_partner WHERE id = %s",
            [partner_id],
        )
        return self.env.cr.fetchone()

    def action_guarded_env_ref(self):
        return self.env.ref("base.main_company", raise_if_not_found=False)

    def action_model_access(self):
        return self.env["res.partner"].search([], limit=1)
