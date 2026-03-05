"""Shared test utilities and factory mixins for PlastOS test suite.

This module provides reusable factory methods and base classes to reduce
code duplication across test files and ensure consistent test data creation.
"""


class PlastOSTestFactoryMixin:
    """Unified factory mixin for creating PlastOS test records.

    Provides consistent record creation helpers used across all test modules.
    All methods search for existing records first to avoid duplicates in
    test databases with demo data.
    """

    @classmethod
    def _create_partner(cls, name="Test Partner", **kw):
        """Create or find a partner record.

        Args:
            name: Partner name (default: "Test Partner")
            **kw: Additional field values to set

        Returns:
            res.partner record
        """
        vals = {"name": name, "is_company": True}
        vals.update(kw)
        return cls.env["res.partner"].create(vals)

    @classmethod
    def _get_or_create_polymer(cls, code="HDPE", name=None):
        """Get existing or create new polymer record.

        Args:
            code: Polymer code (default: "HDPE")
            name: Polymer name (defaults to code if not provided)

        Returns:
            plasticos.polymer record
        """
        existing = cls.env["plasticos.polymer"].search([("code", "=", code)], limit=1)
        if existing:
            return existing
        return cls.env["plasticos.polymer"].create(
            {
                "name": name or code,
                "code": code,
            }
        )

    @classmethod
    def _get_or_create_form(cls, code="pellet", name=None):
        """Get existing or create new material form record.

        Args:
            code: Form code (default: "pellet")
            name: Form name (defaults to titlecased code if not provided)

        Returns:
            plasticos.material.form record
        """
        existing = cls.env["plasticos.material.form"].search([("code", "=", code)], limit=1)
        if existing:
            return existing
        return cls.env["plasticos.material.form"].create(
            {
                "name": name or code.title(),
                "code": code,
            }
        )

    @classmethod
    def _create_intake(cls, partner=None, polymer=None, form=None, **kw):
        """Create an intake record with sensible defaults.

        Args:
            partner: res.partner record (creates one if not provided)
            polymer: plasticos.polymer record (gets/creates HDPE if not provided)
            form: plasticos.material.form record (gets/creates pellet if not provided)
            **kw: Additional field values to set

        Returns:
            plasticos.intake record
        """
        if "plasticos.intake" not in cls.env:
            return None
        if partner is None:
            partner = cls._create_partner("Intake Partner")
        if polymer is None:
            polymer = cls._get_or_create_polymer()
        if form is None:
            form = cls._get_or_create_form()

        vals = {
            "partner_id": partner.id,
            "polymer_id": polymer.id,
            "form_id": form.id,
            "quantity_per_load_lbs": 40000,
        }
        vals.update(kw)
        return cls.env["plasticos.intake"].create(vals)

    @classmethod
    def _create_transaction(cls, name=None, **kw):
        """Create a transaction record.

        Args:
            name: Transaction name (auto-generated if not provided)
            **kw: Additional field values to set

        Returns:
            plasticos.transaction record
        """
        if "plasticos.transaction" not in cls.env:
            return None
        vals = {}
        if name:
            vals["name"] = name
        vals.update(kw)
        return cls.env["plasticos.transaction"].create(vals)

    @classmethod
    def _create_claim(cls, transaction=None, **kw):
        """Create a claim record linked to a transaction.

        Args:
            transaction: plasticos.transaction record (creates one if not provided)
            **kw: Additional field values to set

        Returns:
            plasticos.claim record
        """
        if "plasticos.claim" not in cls.env:
            return None
        if transaction is None:
            transaction = cls._create_transaction(name="TX-TEST-CLM")

        vals = {
            "transaction_id": transaction.id,
            "case_type": "buyer_claim",
            "severity": "medium",
            "state": "pending",
        }
        vals.update(kw)
        return cls.env["plasticos.claim"].create(vals)

    @classmethod
    def _create_offer(cls, buyer=None, intake=None, **kw):
        """Create an offer record.

        Args:
            buyer: res.partner record for buyer (creates one if not provided)
            intake: plasticos.intake record (optional)
            **kw: Additional field values to set

        Returns:
            plasticos.offer record
        """
        if "plasticos.offer" not in cls.env:
            return None
        if buyer is None:
            buyer = cls._create_partner("Offer Buyer", customer_rank=1)

        vals = {"buyer_partner_id": buyer.id}
        if intake and "intake_id" in cls.env["plasticos.offer"]._fields:
            vals["intake_id"] = intake.id
        vals.update(kw)
        return cls.env["plasticos.offer"].create(vals)

    @classmethod
    def _create_load(cls, transaction=None, **kw):
        """Create a load record.

        Args:
            transaction: plasticos.transaction record (optional)
            **kw: Additional field values to set

        Returns:
            plasticos.load record
        """
        if "plasticos.load" not in cls.env:
            return None
        vals = {"state": "draft"}
        if transaction and "transaction_id" in cls.env["plasticos.load"]._fields:
            vals["transaction_id"] = transaction.id
        vals.update(kw)
        return cls.env["plasticos.load"].create(vals)

    @classmethod
    def _create_web_lead(cls, lead_id=None, **kw):
        """Create a web lead record.

        Args:
            lead_id: Unique lead identifier (auto-generated if not provided)
            **kw: Additional field values to set

        Returns:
            plasticos.web.lead record
        """
        if "plasticos.web.lead" not in cls.env:
            return None
        import uuid

        vals = {
            "lead_id": lead_id or f"WL-{uuid.uuid4().hex[:8]}",
            "decision": "cold",
            "company_name": "Test Co",
            "state": "received",
        }
        vals.update(kw)
        return cls.env["plasticos.web.lead"].create(vals)

    @classmethod
    def _create_material_profile(cls, partner=None, polymer=None, **kw):
        """Create a material profile record.

        Args:
            partner: res.partner record (creates one if not provided)
            polymer: plasticos.polymer record (gets/creates HDPE if not provided)
            **kw: Additional field values to set

        Returns:
            plasticos.material.profile record
        """
        if "plasticos.material.profile" not in cls.env:
            return None
        if partner is None:
            partner = cls._create_partner("Profile Partner")
        if polymer is None:
            polymer = cls._get_or_create_polymer()

        vals = {
            "partner_id": partner.id,
            "polymer_id": polymer.id,
        }
        vals.update(kw)
        return cls.env["plasticos.material.profile"].create(vals)

    @classmethod
    def _skip_if_model_missing(cls, *models):
        """Skip test if any of the specified models are not installed.

        Args:
            *models: Model names to check (e.g., "plasticos.intake")

        Raises:
            unittest.SkipTest if any model is missing
        """
        import unittest

        for model in models:
            if model not in cls.env:
                raise unittest.SkipTest(f"{model} not installed")


def assert_action_result(test_case, result, expected_model=None, expected_type="ir.actions.act_window"):
    """Assert that an action method returns a valid action dict.

    Args:
        test_case: The TestCase instance
        result: The action result dict to validate
        expected_model: Expected res_model value (optional)
        expected_type: Expected action type (default: "ir.actions.act_window")
    """
    test_case.assertIsInstance(result, dict, "Action should return a dict")
    test_case.assertEqual(result.get("type"), expected_type, f"Action type should be {expected_type}")
    if expected_model:
        test_case.assertEqual(result.get("res_model"), expected_model, f"Action res_model should be {expected_model}")


def assert_state_transition(test_case, record, action_name, expected_state, msg=None):
    """Assert that calling an action method transitions to expected state.

    Args:
        test_case: The TestCase instance
        record: The record to call the action on
        action_name: Name of the action method (e.g., "action_confirm")
        expected_state: Expected state after action
        msg: Optional assertion message
    """
    if hasattr(record, action_name):
        getattr(record, action_name)()
        test_case.assertEqual(
            record.state,
            expected_state,
            msg or f"{action_name} should transition to {expected_state}",
        )
    else:
        test_case.skipTest(f"{action_name} not available on {record._name}")


def assert_message_posted(test_case, record, keyword=None):
    """Assert that a message was posted to the record's chatter.

    Args:
        test_case: The TestCase instance
        record: The record to check messages on
        keyword: Optional keyword to search for in message body
    """
    test_case.assertTrue(record.message_ids, "Expected at least one message to be posted")
    if keyword:
        matching = record.message_ids.filtered(lambda m: keyword.lower() in (m.body or "").lower())
        test_case.assertTrue(matching, f"Expected message containing '{keyword}'")
