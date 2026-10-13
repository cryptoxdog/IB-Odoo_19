"""GMP-NC-D D-09: the batch cron never searches with a nonpositive limit.

The configuration refuses a negative ``batch_limit``; 0 keeps meaning "use
the default of 200". A negative value stored before the constraint existed is
refused by the cron with the same configuration error, before any search.

Every case runs on a test-owned configuration record: ``get_config()`` is
pointed at it, so the XML-seeded singleton is never written, unlinked or
updated.

Runs under ``odoo --test-enable --test-tags /plasticos_intake_normalizer``.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBatchLimit(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Config = cls.env["plasticos.normalizer.config"]
        cls.Intake = cls.env["plasticos.intake"]
        cls.config = cls.Config.sudo().create({"name": "NC-D Batch Limit Test"})

    @contextmanager
    def _cron_uses(self, config):
        """Point the cron's configuration lookup at a test-owned record."""
        with patch.object(type(self.Config), "get_config", autospec=True, return_value=config):
            yield

    def _cron_batch_limit(self):
        """Run the cron through the real ORM search; return the batch search's limit.

        The batch query is the cron's first ``plasticos.intake`` search; any
        later one belongs to per-record processing.
        """
        Intake = type(self.Intake)
        original = Intake.search
        limits = []

        def spy(model, *args, **kwargs):
            limits.append(kwargs.get("limit"))
            return original(model, *args, **kwargs)

        with patch.object(Intake, "search", autospec=True, side_effect=spy):
            self.Intake.cron_batch_normalize()
        self.assertTrue(limits, "the cron issued no batch search")
        return limits[0]

    def _store_without_validation(self, config, value):
        """A value persisted before the constraint existed."""
        self.env.flush_all()
        self.env.cr.execute("UPDATE plasticos_normalizer_config SET batch_limit = %s WHERE id = %s", [value, config.id])
        config.invalidate_recordset(["batch_limit"])

    def test_missing_configuration_uses_the_default(self):
        """When ``get_config`` finds no record, it creates one with the field defaults."""
        Config = type(self.Config)
        original_search = Config.search
        original_create = Config.create
        created = []

        def no_existing_config(model, domain, *args, **kwargs):
            if domain == [] and kwargs.get("limit") == 1:
                return model.browse()
            return original_search(model, domain, *args, **kwargs)

        def record_create(model, *args, **kwargs):
            record = original_create(model, *args, **kwargs)
            created.append(record)
            return record

        with (
            patch.object(Config, "search", autospec=True, side_effect=no_existing_config),
            patch.object(Config, "create", autospec=True, side_effect=record_create),
        ):
            self.assertEqual(self._cron_batch_limit(), 200)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].batch_limit, 200)

    def test_zero_keeps_the_default(self):
        self.config.write({"batch_limit": 0})
        with self._cron_uses(self.config):
            self.assertEqual(self._cron_batch_limit(), 200)

    def test_positive_limit_is_used(self):
        self.config.write({"batch_limit": 7})
        with self._cron_uses(self.config):
            self.assertEqual(self._cron_batch_limit(), 7)

    def test_negative_limit_is_refused_on_write(self):
        with self.assertRaises(ValidationError):
            self.config.write({"batch_limit": -1})

    def test_negative_limit_is_refused_on_create(self):
        with self.assertRaises(ValidationError):
            self.Config.sudo().create({"name": "NC-D Negative", "batch_limit": -5})

    def test_stored_negative_limit_stops_the_cron_before_any_search(self):
        self._store_without_validation(self.config, -5)
        Intake = type(self.Intake)
        with self._cron_uses(self.config), patch.object(Intake, "search", autospec=True) as search:
            with self.assertRaisesRegex(ValidationError, r"batch limit -5"):
                self.Intake.cron_batch_normalize()
        search.assert_not_called()

    def test_cron_never_searches_with_a_nonpositive_limit(self):
        with self._cron_uses(self.config):
            for value in (0, 1, 200):
                self.config.write({"batch_limit": value})
                self.assertGreater(self._cron_batch_limit(), 0)
