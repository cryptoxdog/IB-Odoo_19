# filename: .semgrep/tests/negative.py
"""Negative Semgrep fixtures for PlasticOS IB-Odoo_19.

These examples demonstrate accepted patterns and should produce no blocking
findings from the hardened Semgrep rules.
"""

import json

import yaml
from psycopg2 import sql

from odoo import api, fields, models
from odoo.http import request


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

    def action_indirect_sql_safe(self, partner_id, table):
        query = "SELECT id FROM res_partner WHERE id = %s"
        self.env.cr.execute(query, [partner_id])
        self.env.cr.execute(
            "INSERT INTO ir_config_parameter (key, value) VALUES (%s, %s)",
            (f"plasticos.fixture.{table}", "1"),
        )
        static_query = "SELECT id FROM res_partner" + " WHERE id = %s"
        self.env.cr.execute(static_query, [partner_id])
        constant = f"SELECT id FROM res_partner WHERE id = %s"
        self.env.cr.execute(constant, [partner_id])
        self.env.cr.execute(
            sql.SQL("ALTER TABLE {} RENAME COLUMN {} TO {}").format(
                sql.Identifier("res_partner"),
                sql.Identifier("old_name"),
                sql.Identifier("new_name"),
            )
        )

    def action_request_values_are_parameters(self):
        body = json.loads(request.httprequest.get_data(as_text=True) or "")
        self.env.cr.execute(
            "SELECT id FROM res_partner WHERE name = %s",
            [body.get("name")],
        )
        request.env["res.partner"].search([("name", "=", body.get("name"))])
        return request.env["res.partner"].search_read([("name", "=", body.get("name"))], ["name"])

    def action_search_hook_not_implemented(self, operator):
        # Bare raise is the Odoo search-method protocol. The call form is the banned shape.
        if operator not in ("=", "!="):
            raise NotImplementedError
        return []

    tracked_flag = fields.Boolean(help="Ordinary boolean, not a partner role flag.")
