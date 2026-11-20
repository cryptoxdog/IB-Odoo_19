# filename: .semgrep/tests/positive.py
"""Positive Semgrep fixtures for PlasticOS IB-Odoo_19.

These examples intentionally contain banned patterns and must produce findings
when scanned with .semgrep/odoo-patterns.yml. This file is a rule fixture only;
it is not application code.
"""

import json
import pickle

import yaml

from odoo import api, fields, models
from odoo.http import request


class PlasticosSemgrepPositiveFixture(models.Model):
    _name = "plasticos.semgrep.positive.fixture"
    _description = "Semgrep Positive Fixture"

    _sql_constraints = [
        ("name_unique", "unique(name)", "Name must be unique."),
    ]

    @api.one
    def action_legacy_api_one(self):
        return True

    @api.multi
    def action_legacy_api_multi(self):
        return True

    @api.depends("id")
    def _compute_invalid_depends(self):
        for record in self:
            record.display_name = "bad depends"

    def action_bare_except(self):
        try:
            self.env["res.partner"].search([])
        except:
            return False

    def action_eval_exec_compile(self, expression):
        eval(expression)
        exec(expression)
        compile(expression, "<fixture>", "exec")

    def action_pickle_and_yaml(self, blob, yaml_text):
        pickle.loads(blob)
        yaml.load(yaml_text)

    def action_pipeline_import(self):
        from plasticos_inference_engine.pipeline_v2 import run_pipeline

        return run_pipeline({})

    def action_env_get(self):
        return self.env.get("res.partner")

    def action_sql_injection_examples(self, partner_id, table_name):
        self.env.cr.execute(f"SELECT * FROM res_partner WHERE id = {partner_id}")
        self.env.cr.execute("SELECT * FROM {}".format(table_name))
        self.env.cr.execute("SELECT * FROM res_partner WHERE id = %s" % partner_id)
        self.env.cr.execute("SELECT * FROM " + table_name)

    def action_raw_sql_review(self):
        self.env.cr.execute("SELECT id FROM res_partner LIMIT 1")

    def action_unprotected_env_ref(self):
        return self.env.ref("base.main_company")

    def action_not_implemented(self):
        raise NotImplementedError("fixture should trigger the production guard")

    def action_hardcoded_secret(self):
        api_key = "sk_test_1234567890abcdef"
        return api_key

    # TODO: fixture marker for plasticos-production-todo-implement
    # self.env["res.partner"].search([])
    x_legacy_id = fields.Boolean()
    is_vendor = fields.Boolean()

    def action_indirect_sql(self, table, partner_id, query):
        built = f"SELECT * FROM {table}"
        self.env.cr.execute(built)
        formatted = "SELECT * FROM {}".format(table)
        self.env.cr.execute(formatted)
        percent = "SELECT id FROM res_partner WHERE id = %s" % (partner_id,)
        self.env.cr.execute(percent)
        concatenated = "SELECT * FROM " + table
        self.env.cr.execute(concatenated)
        self.env.cr.execute(query % (partner_id,))
        self.env.cr.execute(query.format(table))

    def action_request_sql_and_domain(self):
        self.env.cr.execute(request.params.get("query"))
        raw = request.httprequest.get_data(as_text=True)
        statement = json.loads(raw)
        self.env.cr.execute(statement)
        body = json.loads(request.httprequest.get_data(as_text=True) or "")
        request.env["res.partner"].search(body)
        request.env["res.partner"].search(request.params.get("domain"))

    def action_destructive_migration_fixture(self):
        statement = "DROP TABLE plasticos_semgrep_fixture"
        return statement


class PlastosSemgrepDrift(models.Model):
    _name = "plasticos.semgrep.drift"
    _description = "Namespace drift fixture"
