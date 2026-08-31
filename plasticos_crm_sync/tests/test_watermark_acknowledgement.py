"""I1 — a watermark acknowledges only source data that was durably consumed.

These exercise ``_sync_contacts`` / ``_sync_calls`` directly. Going through
``run_connection`` would drag in its rollback-before-failure-cursor step, and
under Odoo's test mode a rollback unwinds to the test savepoint rather than a
real transaction boundary — a green result there would prove nothing about the
production behavior. The cross-session/rollback invariants (I2/I3/I5) are
therefore real-runtime deployment gates; see docs/runbooks/LAUNCH_GATES.md.
"""

from odoo.addons.plasticos_crm_sync.adapters.base import CanonicalCall, CanonicalLead, CrmAdapterError
from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator
from odoo.tests import TransactionCase, tagged

W0 = "2026-07-01T00:00:00Z"
W1 = "2026-07-02T00:00:00Z"
W2 = "2026-07-03T00:00:00Z"


def _lead(external_id):
    return CanonicalLead(
        provider="vanillasoft",
        external_id=external_id,
        company=f"Co {external_id}",
        first_name="Ada",
        last_name="Lovelace",
        lead_status_raw="New",
    )


def _call(external_id, contact_external_id="wm-1"):
    return CanonicalCall(
        provider="vanillasoft",
        external_id=external_id,
        contact_external_id=contact_external_id,
        call_datetime_utc="2026-07-01T12:00:00Z",
        duration_seconds=30,
    )


class _StubAdapter:
    """Adapter whose pages are scripted; a page may be an exception to raise."""

    provider = "vanillasoft"
    live = True

    def __init__(self, contact_pages=(), call_batches=()):
        self._contact_pages = list(contact_pages)
        self._call_batches = list(call_batches)

    def healthcheck(self):
        return {}

    def iter_contacts(self, *, modified_after, limit=200):
        for page in self._contact_pages:
            if isinstance(page, Exception):
                raise page
            yield page

    def iter_calls(self, *, start, end, limit=500):
        for batch in self._call_batches:
            if isinstance(batch, Exception):
                raise batch
            yield batch

    def iter_table_rows(self, contact_external_id):
        return iter(())


@tagged("post_install", "-at_install")
class TestWatermarkAcknowledgement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connection = cls.env["plasticos.crm.connection"].create(
            {
                "name": "Watermark VS",
                "provider": "vanillasoft",
                "project_id": "139705",
                "enabled": False,
            }
        )

    def setUp(self):
        super().setUp()
        self.orch = SyncOrchestrator(self.env)
        self.connection.write({"contact_watermark_utc": W0, "call_watermark_utc": W0})

    # ── contacts ────────────────────────────────────────────────────────────

    def test_malformed_contact_page_leaves_watermark_untouched(self):
        adapter = _StubAdapter(contact_pages=[CrmAdapterError("Contact payload missing contact_id")])
        with self.assertRaises(CrmAdapterError):
            self.orch._sync_contacts(self.connection, adapter, None)
        self.assertEqual(self.connection.contact_watermark_utc, W0)

    def test_failure_after_a_committed_page_preserves_that_page_watermark(self):
        adapter = _StubAdapter(
            contact_pages=[
                ([_lead("wm-1")], W1, True),
                CrmAdapterError("page 2 exploded"),
            ]
        )
        with self.assertRaises(CrmAdapterError):
            self.orch._sync_contacts(self.connection, adapter, None)
        # Page 1's work is acknowledged; page 2's is not.
        self.assertEqual(self.connection.contact_watermark_utc, W1)
        self.assertNotEqual(self.connection.contact_watermark_utc, W2)

    def test_persist_failure_during_a_page_leaves_watermark_untouched(self):
        """A DB-side failure between transform and watermark is still fail-closed."""
        adapter = _StubAdapter(contact_pages=[([_lead("wm-2")], W1, False)])

        def _boom(self_, connection, dto):
            raise CrmAdapterError("upsert failed")

        # BaseCase.patch reverts on cleanup — no manual restore needed.
        self.patch(SyncOrchestrator, "_upsert_lead", _boom)
        with self.assertRaises(CrmAdapterError):
            self.orch._sync_contacts(self.connection, adapter, None)
        self.assertEqual(self.connection.contact_watermark_utc, W0)

    def test_successful_page_advances_the_watermark(self):
        adapter = _StubAdapter(contact_pages=[([_lead("wm-3")], W1, False)])
        self.orch._sync_contacts(self.connection, adapter, None)
        self.assertEqual(self.connection.contact_watermark_utc, W1)

    def test_replayed_page_creates_no_duplicate_lead(self):
        adapter = _StubAdapter(contact_pages=[([_lead("wm-4")], W1, False)])
        self.orch._sync_contacts(self.connection, adapter, None)
        self.orch._sync_contacts(
            self.connection,
            _StubAdapter(contact_pages=[([_lead("wm-4")], W1, False)]),
            None,
        )
        refs = self.env["plasticos.crm.external.ref"].search(
            [("provider", "=", "vanillasoft"), ("external_id", "=", "wm-4")]
        )
        self.assertEqual(len(refs), 1)

    # ── calls ───────────────────────────────────────────────────────────────

    def test_malformed_call_leaves_the_window_watermark_untouched(self):
        adapter = _StubAdapter(
            call_batches=[
                [_call("wm-call-1")],
                CrmAdapterError("Call 10 payload missing contact_id"),
            ]
        )
        with self.assertRaises(CrmAdapterError):
            self.orch._sync_calls(self.connection, adapter, None)
        self.assertEqual(self.connection.call_watermark_utc, W0)

    def test_call_pagination_failure_leaves_the_window_watermark_untouched(self):
        """The blocker this guards: a full page that cannot be paginated past
        used to end the iterator normally, and _sync_calls reads normal
        completion as permission to advance the whole window."""
        adapter = _StubAdapter(
            call_batches=[
                [_call("wm-call-3")],
                CrmAdapterError("Call pagination failed to advance: '...' -> '...' (500 rows at the page limit)"),
            ]
        )
        with self.assertRaises(CrmAdapterError):
            self.orch._sync_calls(self.connection, adapter, None)
        self.assertEqual(self.connection.call_watermark_utc, W0)

    def test_calls_from_a_failed_window_are_still_persisted_and_replayable(self):
        """Yielded batches stay committed; the unchanged watermark makes the
        next run re-read the window and upsert them idempotently (I4)."""
        adapter = _StubAdapter(
            call_batches=[
                [_call("wm-call-4")],
                CrmAdapterError("Full call-history page has no usable pagination timestamp"),
            ]
        )
        with self.assertRaises(CrmAdapterError):
            self.orch._sync_calls(self.connection, adapter, None)
        self.assertEqual(self.connection.call_watermark_utc, W0)
        self.orch._upsert_calls(self.connection, [_call("wm-call-4")], None)
        events = self.env["plasticos.crm.call.event"].search(
            [("provider", "=", "vanillasoft"), ("external_id", "=", "wm-call-4")]
        )
        self.assertEqual(len(events), 1)

    def test_partial_contact_page_without_cursor_leaves_watermark_untouched(self):
        adapter = _StubAdapter(
            contact_pages=[
                CrmAdapterError("VanillaSoft reported partial contact fulfillment without a batch_end cursor"),
            ]
        )
        with self.assertRaises(CrmAdapterError):
            self.orch._sync_contacts(self.connection, adapter, None)
        self.assertEqual(self.connection.contact_watermark_utc, W0)

    def test_replayed_calls_create_no_duplicate_call_event(self):
        batch = [_call("wm-call-2")]
        self.orch._upsert_calls(self.connection, batch, None)
        self.orch._upsert_calls(self.connection, batch, None)
        events = self.env["plasticos.crm.call.event"].search(
            [("provider", "=", "vanillasoft"), ("external_id", "=", "wm-call-2")]
        )
        self.assertEqual(len(events), 1)
