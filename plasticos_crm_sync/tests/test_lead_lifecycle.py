"""VanillaSoft delete/restore semantics against the real ORM.

`crm.lead.active` is shared state. Sync archives a lead when VanillaSoft
reports the contact deleted, but Odoo users archive leads for their own reasons
and `deleted=false` is the provider's steady state for every live contact — so
mirroring the provider flag onto `active` would reopen every lead a user ever
archived, on the next sync. Reactivation is therefore gated on the provenance
flag `vanillasoft_sync_archived`, which only this sync sets.

These need the ORM (`active_test`, the archive filter, the provenance column),
so they are TransactionCase rather than pure-Python.
"""

from odoo.addons.plasticos_crm_sync.adapters.base import CanonicalCall, CanonicalLead
from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator
from odoo.tests import TransactionCase, tagged


def _lead(external_id, deleted=False):
    return CanonicalLead(
        provider="vanillasoft",
        external_id=external_id,
        company=f"Co {external_id}",
        first_name="Ada",
        last_name="Lovelace",
        lead_status_raw="New",
        deleted=deleted,
    )


@tagged("post_install", "-at_install")
class TestVanillaSoftLeadLifecycle(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connection = cls.env["plasticos.crm.connection"].create(
            {
                "name": "Lifecycle VS",
                "provider": "vanillasoft",
                "project_id": "139705",
                "enabled": False,
            }
        )

    def setUp(self):
        super().setUp()
        self.orch = SyncOrchestrator(self.env)

    def _archived(self, external_id):
        return (
            self.env["crm.lead"].with_context(active_test=False).search([("vanillasoft_id", "=", external_id)], limit=1)
        )

    def test_vanillasoft_deleted_contact_archives_lead(self):
        self.orch._upsert_lead(self.connection, _lead("life-1"))
        self.orch._upsert_lead(self.connection, _lead("life-1", deleted=True))

        lead = self._archived("life-1")
        self.assertTrue(lead, "the archived lead must still be reachable by external id")
        self.assertFalse(lead.active)
        self.assertTrue(lead.vanillasoft_sync_archived, "the archive must record who caused it")

    def test_vanillasoft_restored_contact_reactivates_sync_archived_lead(self):
        created = self.orch._upsert_lead(self.connection, _lead("life-2"))
        self.orch._upsert_lead(self.connection, _lead("life-2", deleted=True))
        self.assertFalse(created.exists() and created.active)

        restored = self.orch._upsert_lead(self.connection, _lead("life-2"))
        self.assertEqual(restored.id, created.id, "restore must reuse the lead, not create a second one")
        self.assertTrue(restored.active)
        self.assertFalse(restored.vanillasoft_sync_archived, "provenance is cleared once the lead is live again")

    def test_manually_archived_odoo_lead_is_not_reactivated_without_sync_provenance(self):
        lead = self.orch._upsert_lead(self.connection, _lead("life-3"))
        lead.active = False  # an Odoo user archived it, for their own reasons
        self.assertFalse(lead.vanillasoft_sync_archived)

        # VanillaSoft reports the contact as it always does: not deleted.
        self.orch._upsert_lead(self.connection, _lead("life-3"))
        self.assertFalse(lead.active, "sync must not reopen a lead it did not archive")

    def test_a_sync_archived_lead_is_matched_rather_than_duplicated(self):
        """Without `active_test=False` the fallback search misses the archived
        lead and creates a second one on the next page that mentions it."""
        first = self.orch._upsert_lead(self.connection, _lead("life-4"))
        self.env["plasticos.crm.external.ref"].search(
            [("provider", "=", "vanillasoft"), ("external_id", "=", "life-4")]
        ).unlink()
        first.write({"active": False, "vanillasoft_sync_archived": True})

        again = self.orch._upsert_lead(self.connection, _lead("life-4"))
        self.assertEqual(again.id, first.id)
        leads = self.env["crm.lead"].with_context(active_test=False).search([("vanillasoft_id", "=", "life-4")])
        self.assertEqual(len(leads), 1)

    def test_calls_attach_to_a_sync_archived_lead_instead_of_buffering_as_orphans(self):
        lead = self.orch._upsert_lead(self.connection, _lead("life-5"))
        self.orch._upsert_lead(self.connection, _lead("life-5", deleted=True))
        self.env["plasticos.crm.external.ref"].search(
            [("provider", "=", "vanillasoft"), ("external_id", "=", "life-5")]
        ).unlink()

        self.orch._upsert_calls(
            self.connection,
            [
                CanonicalCall(
                    provider="vanillasoft",
                    external_id="life-5-call",
                    contact_external_id="life-5",
                    call_datetime_utc="2026-08-01T12:00:00Z",
                    duration_seconds=30,
                )
            ],
            None,
        )
        event = self.env["plasticos.crm.call.event"].search([("external_id", "=", "life-5-call")], limit=1)
        self.assertTrue(event)
        self.assertEqual(event.lead_id.id, lead.id)
        self.assertFalse(
            self.env["plasticos.crm.sync.orphan"].search(
                [("connection_id", "=", self.connection.id), ("external_id", "=", "life-5-call")]
            )
        )
