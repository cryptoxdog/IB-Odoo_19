"""Regression tests for the ODOO006 recordset-is-None detector in ci/check_odoo_antipatterns.py.

The detector must catch search()/browse()/env[...] recordsets in helper and
service functions outside model classes, must not flag ordinary values or
dataclass None checks, and must keep its existing model-class coverage.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import textwrap
from pathlib import Path

CHECKER_PATH = Path(__file__).parents[1] / "ci" / "check_odoo_antipatterns.py"
SPEC = importlib.util.spec_from_file_location("check_odoo_antipatterns", CHECKER_PATH)
assert SPEC and SPEC.loader
checker_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker_module
SPEC.loader.exec_module(checker_module)


def _codes(source: str) -> list[str]:
    source = textwrap.dedent(source)
    tree = ast.parse(source)
    checker = checker_module.OdooAntiPatternChecker("snippet.py", source.splitlines())
    checker.visit(tree)
    return [issue.code for issue in checker.issues]


def test_search_recordset_in_helper_function_is_caught():
    codes = _codes(
        """
        def lookup(env, partner_id):
            records = env["res.partner"].search([("id", "=", partner_id)], limit=1)
            if records is None:
                return False
            return records.id
        """
    )
    assert codes == ["ODOO006"]


def test_browse_recordset_in_service_function_is_caught():
    codes = _codes(
        """
        def resolve(load):
            source = load.env["plasticos.load"].browse(42).exists()
            if source is not None:
                return source.rate_amount
            return 0.0
        """
    )
    assert codes == ["ODOO006"]


def test_env_model_lookup_compared_directly_is_caught():
    codes = _codes(
        """
        def first_partner(env):
            if env["res.partner"].search([], limit=1) is None:
                return None
            return True
        """
    )
    assert codes == ["ODOO006"]


def test_relational_attribute_of_tracked_local_is_caught():
    codes = _codes(
        """
        def carrier_for(load):
            candidate = load.env["plasticos.load"].browse(load.id)
            if candidate.carrier_id is None:
                return None
            return candidate.carrier_id
        """
    )
    assert codes == ["ODOO006"]


def test_dataclass_none_check_outside_model_class_is_not_flagged():
    codes = _codes(
        """
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class FreightContext:
            fingerprint: str

        def build_freight_context(load):
            return FreightContext("abc") if load else None

        def describe(load):
            context = build_freight_context(load)
            if context is None:
                return "missing"
            records = compute_records(load)
            if records is None:
                return "none"
            return context.fingerprint
        """
    )
    assert codes == []


def test_rebinding_a_tracked_local_to_a_plain_value_releases_it():
    codes = _codes(
        """
        def summarize(env):
            rows = env["res.partner"].search([])
            rows = [row.name for row in rows]
            if rows is None:
                return []
            return rows
        """
    )
    assert codes == []


def test_recordset_locals_do_not_leak_between_functions():
    codes = _codes(
        """
        def first(env):
            hits = env["res.partner"].search([])
            return hits

        def second(payload):
            hits = payload.get("hits")
            if hits is None:
                return []
            return hits
        """
    )
    assert codes == []


def test_model_class_relational_field_coverage_is_preserved():
    codes = _codes(
        """
        class PlasticosLoad(models.Model):
            _name = "plasticos.load"

            def check(self):
                if self.partner_id is None:
                    return False
                return True
        """
    )
    assert codes == ["ODOO006"]


def test_model_class_search_local_coverage_is_preserved():
    codes = _codes(
        """
        class PlasticosLoad(models.Model):
            _name = "plasticos.load"

            def check(self):
                found = self.search([("id", "=", self.id)])
                if found is not None:
                    return True
                return False
        """
    )
    assert codes == ["ODOO006"]


def test_model_class_plain_value_is_not_flagged():
    codes = _codes(
        """
        class PlasticosLoad(models.Model):
            _name = "plasticos.load"

            def check(self, weight):
                if weight is None:
                    return False
                return True
        """
    )
    assert codes == []


def test_method_name_alone_is_not_recordset_evidence():
    """re.search()/payload.create() share method names with the ORM but are not recordsets."""
    codes = _codes(
        """
        import re

        def parse(text, client, payload):
            match = re.search(r"\\d+", text)
            if match is None:
                return None
            created = client.create(payload)
            if created is None:
                return None
            if payload.search("x") is None:
                return None
            return match.group(0)
        """
    )
    assert codes == []


def test_tracked_model_variable_receiver_is_recordset_evidence():
    codes = _codes(
        """
        def lookup(env):
            request_model = env["plasticos.freight.quote.request"]
            found = request_model.search([], limit=1)
            if found is None:
                return None
            return found
        """
    )
    assert codes == ["ODOO006"]


def test_env_ref_receiver_is_recordset_evidence():
    codes = _codes(
        """
        def group_for(env):
            group = env.ref("plasticos_security_base.group_logistics", raise_if_not_found=False)
            if group is None:
                return None
            return group
        """
    )
    assert codes == ["ODOO006"]


def test_checker_ignores_scalar_id_locals_outside_model_classes():
    codes = _codes(
        """
        def resolve(matched_id):
            if matched_id is None:
                return None
            return matched_id
        """
    )
    assert codes == []
