"""PlasticOS test base class and shared fixtures.

Provides PlasticosTestCase with pre-created master data (partner, polymer, form, etc.)
to avoid NOT NULL and UniqueViolation failures across plasticos test modules.
"""

from __future__ import annotations

# Odoo 19 guard: importing odoo.tests outside --test-enable logs an ERROR at
# startup and causes Odoo.sh to mark the build as failed.
# We use odoo.tools.config to detect test mode and fall back to unittest.TestCase
# so this module is safely importable during normal module loading.
try:
    import odoo.tools.config as _odoo_config

    _test_mode = _odoo_config.get("test_enable") or _odoo_config.get("test_file")
except Exception:
    _test_mode = False

if _test_mode:
    from odoo.tests.common import TransactionCase
else:
    from unittest import TestCase as TransactionCase  # type: ignore[assignment]


class PlastOSTestFactoryMixin:
    """Unified factory mixin for creating PlastOS test records.

    Provides consistent record creation helpers. All methods search for existing
    records first to avoid duplicates (UniqueViolation) in test databases.
    """

    @classmethod
    def _create_partner(cls, name="Test Partner", **kw):
        """Create or find a partner record."""
        vals = {"name": name, "is_company": True}
        vals.update(kw)
        return cls.env["res.partner"].create(vals)

    @classmethod
    def _get_or_create_polymer(cls, code="HDPE", name=None):
        """Get existing or create new polymer record."""
        if "plasticos.polymer" not in cls.env:
            return None
        existing = cls.env["plasticos.polymer"].search([("code", "=", code)], limit=1)
        if existing:
            return existing
        return cls.env["plasticos.polymer"].create({"name": name or code, "code": code})

    @classmethod
    def _get_or_create_form(cls, code="pellet", name=None):
        """Get existing or create new material form record."""
        if "plasticos.material.form" not in cls.env:
            return None
        existing = cls.env["plasticos.material.form"].search([("code", "=", code)], limit=1)
        if existing:
            return existing
        return cls.env["plasticos.material.form"].create({"name": name or code.title(), "code": code})

    @classmethod
    def _get_or_create_color(cls, code="natural", name=None):
        """Get existing or create new material color record."""
        if "plasticos.material.color" not in cls.env:
            return None
        existing = cls.env["plasticos.material.color"].search([("code", "=", code)], limit=1)
        if existing:
            return existing
        return cls.env["plasticos.material.color"].create({"name": name or code.title(), "code": code})

    @classmethod
    def _get_or_create_source_type(cls, code="post_consumer", name=None):
        """Get existing or create new source type record."""
        if "plasticos.source.type" not in cls.env:
            return None
        existing = cls.env["plasticos.source.type"].search([("code", "=", code)], limit=1)
        if existing:
            return existing
        return cls.env["plasticos.source.type"].create({"name": name or code.replace("_", " ").title(), "code": code})

    @classmethod
    def _create_intake(cls, partner=None, polymer=None, form=None, **kw):
        """Create an intake record with sensible defaults."""
        if "plasticos.intake" not in cls.env:
            return None
        partner = partner or cls._create_partner("Intake Partner")
        polymer = polymer or cls._get_or_create_polymer()
        form = form or cls._get_or_create_form()
        if not polymer or not form:
            return None
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
        """Create a transaction record."""
        if "plasticos.transaction" not in cls.env:
            return None
        vals = {"name": name} if name else {}
        vals.update(kw)
        return cls.env["plasticos.transaction"].create(vals)

    @classmethod
    def _create_claim(cls, transaction=None, **kw):
        """Create a claim record linked to a transaction."""
        if "plasticos.claim" not in cls.env:
            return None
        transaction = transaction or cls._create_transaction(name="TX-TEST-CLM")
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
        """Create an offer record."""
        if "plasticos.offer" not in cls.env:
            return None
        buyer = buyer or cls._create_partner("Offer Buyer", customer_rank=1)
        vals = {"buyer_partner_id": buyer.id}
        if intake and "intake_id" in cls.env["plasticos.offer"]._fields:
            vals["intake_id"] = intake.id
        vals.update(kw)
        return cls.env["plasticos.offer"].create(vals)

    @classmethod
    def _create_load(cls, transaction=None, **kw):
        """Create a load record."""
        if "plasticos.load" not in cls.env:
            return None
        vals = {"state": "draft"}
        if transaction and "transaction_id" in cls.env["plasticos.load"]._fields:
            vals["transaction_id"] = transaction.id
        vals.update(kw)
        return cls.env["plasticos.load"].create(vals)

    @classmethod
    def _create_web_lead(cls, lead_id=None, **kw):
        """Create a web lead record."""
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
        """Create a material profile record."""
        if "plasticos.material.profile" not in cls.env:
            return None
        partner = partner or cls._create_partner("Profile Partner")
        polymer = polymer or cls._get_or_create_polymer()
        vals = {"partner_id": partner.id, "polymer_id": polymer.id}
        vals.update(kw)
        return cls.env["plasticos.material.profile"].create(vals)

    @classmethod
    def _skip_if_model_missing(cls, *models):
        """Skip test if any of the specified models are not installed."""
        import unittest

        for model in models:
            if model not in cls.env:
                raise unittest.SkipTest(f"{model} not installed")


class PlasticosTestCase(TransactionCase, PlastOSTestFactoryMixin):
    """Base test case for PlasticOS modules with shared fixtures.

    setUpClass pre-creates common master data (partner, polymer, form, etc.)
    to avoid NOT NULL and UniqueViolation failures. Subclasses get:
    - cls.default_partner: res.partner for NOT NULL partner_id
    - cls.default_polymer: plasticos.polymer (HDPE) if model exists
    - cls.default_form: plasticos.material.form (pellet) if model exists
    - cls.default_color: plasticos.material.color (natural) if model exists
    - cls.default_source_type: plasticos.source.type (post_consumer) if model exists
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.default_partner = cls.env["res.partner"].create({"name": "PlasticOS Test Partner", "is_company": True})
        if "plasticos.polymer" in cls.env:
            cls.default_polymer = cls._get_or_create_polymer("HDPE")
        else:
            cls.default_polymer = None
        if "plasticos.material.form" in cls.env:
            cls.default_form = cls._get_or_create_form("pellet")
        else:
            cls.default_form = None
        if "plasticos.material.color" in cls.env:
            cls.default_color = cls._get_or_create_color("natural")
        else:
            cls.default_color = None
        if "plasticos.source.type" in cls.env:
            cls.default_source_type = cls._get_or_create_source_type("post_consumer")
        else:
            cls.default_source_type = None
