# filename: .semgrep/tests/positive.py
"""Positive Semgrep fixtures for PlasticOS IB-Odoo_19.

These examples intentionally contain banned patterns and must produce findings
when scanned with .semgrep/odoo-patterns.yml. This file is a rule fixture only;
it is not application code.
"""

import pickle
import yaml
from odoo import api, models


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
        raise NotImplementedError("fixture should trigger zero-stub rule")

    def action_hardcoded_secret(self):
        api_key = "sk_test_1234567890abcdef"
        return api_key
