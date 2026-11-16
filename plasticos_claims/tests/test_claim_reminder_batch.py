"""The SLA cron looks up today's reminder activities once for every open claim it reminds."""

from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

from .common import create_claims_manager


@tagged("post_install", "-at_install", "cron", "claims")
class TestClaimReminderBatch(PlasticosTestCase):
    def _activity_count(self, claim):
        return self.env["mail.activity"].search_count(
            [
                ("res_model", "=", "plasticos.claim"),
                ("res_id", "=", claim.id),
                ("summary", "=", f"Open Claim Reminder: {claim.name}"),
                ("date_deadline", "=", fields.Date.today()),
            ]
        )

    def test_two_open_claims_get_one_reminder_each_from_one_activity_lookup(self):
        claim_model = self.env["plasticos.claim"]
        # Unassigned claims are reminded to a claims manager, never to the cron runner.
        create_claims_manager(self.env, login="claims_reminder_batch_manager")
        opened = fields.Datetime.to_datetime("2000-01-01 00:00:00")
        first = self._create_claim(
            transaction=self._create_transaction(name="TX-TEST-REM-1"), opened_at=opened, state="in_progress"
        )
        second = self._create_claim(
            transaction=self._create_transaction(name="TX-TEST-REM-2"), opened_at=opened, state="in_progress"
        )
        ahead = claim_model.search_count(
            [
                ("state", "in", ("pending", "in_progress", "escalated")),
                ("id", "not in", (first | second).ids),
                ("last_reminder_at", "=", False),
                ("opened_at", "<=", opened),
            ]
        )
        self.assertLess(ahead, 298, f"plasticos.claim reminder prefix already has {ahead} rows; limit is 300")
        activity_cls = type(self.env["mail.activity"])
        real_search_read = activity_cls.search_read
        lookups = []

        def counting_search_read(model, *args, **kwargs):
            lookups.append(args[0] if args else kwargs.get("domain"))
            return real_search_read(model, *args, **kwargs)

        with patch.object(activity_cls, "search_read", counting_search_read):
            claim_model._cron_check_sla()
        self.assertEqual(len(lookups), 1, lookups)
        self.assertEqual(self._activity_count(first), 1)
        self.assertEqual(self._activity_count(second), 1)
        self.assertTrue(first.last_reminder_at)
        self.assertTrue(second.last_reminder_at)
        (first | second).write({"last_reminder_at": False})
        claim_model._cron_check_sla()
        self.assertEqual(self._activity_count(first), 1)
        self.assertEqual(self._activity_count(second), 1)
