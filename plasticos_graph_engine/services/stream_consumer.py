"""Kafka stream consumer for graph events.

IMPORTANT: The ``process_batch`` method is designed to be called from
an Odoo ir.cron job.  It polls Kafka for a bounded batch of messages
and returns — it must NEVER block the Odoo worker thread.
"""

import json
import logging

from kafka import KafkaConsumer

from odoo import api, models

_logger = logging.getLogger(__name__)

# Maximum messages to process per cron invocation
_BATCH_LIMIT = 500
# Kafka poll timeout in milliseconds (non-blocking)
_POLL_TIMEOUT_MS = 5000


class StreamConsumer(models.AbstractModel):
    _name = "plasticos.graph.stream.consumer"
    _description = "Kafka Graph Stream Consumer"

    def _get_consumer(self):
        return KafkaConsumer(
            "graph_events",
            bootstrap_servers="localhost:9092",
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            group_id="neo4j_graph_writer",
            consumer_timeout_ms=_POLL_TIMEOUT_MS,
        )

    @api.model
    def process_batch(self):
        """Poll Kafka for a bounded batch of events (cron-safe)."""
        consumer = self._get_consumer()
        driver = self.env["plasticos.neo4j.cluster.driver"]
        shard_router = self.env["plasticos.shard.router"]
        processed = 0

        try:
            for message in consumer:
                if processed >= _BATCH_LIMIT:
                    break

                event = message.value
                event_id = event.get("event_id")
                if not event_id:
                    _logger.warning("Kafka message missing event_id, skipping")
                    consumer.commit()
                    continue

                if self.env["plasticos.graph.idempotency"].search([("event_id", "=", event_id)], limit=1):
                    consumer.commit()
                    continue

                model = event.get("model")
                data = event.get("data", {})

                facility_id = data.get("facility_id") or data.get("partner_id")
                db = shard_router.get_shard_db(facility_id) if facility_id else shard_router.CONTROL_DB

                self._process_event(driver, db, model, data)

                self.env["plasticos.graph.idempotency"].create({"event_id": event_id})
                consumer.commit()
                processed += 1
        finally:
            consumer.close()

        _logger.info("Stream consumer processed %d events", processed)
        return processed

    # Keep backward-compatible alias
    start = process_batch

    def _process_event(self, driver, db, model, data):
        if model == "plasticos.transaction":
            query = """
            MERGE (t:Transaction {txn_id:$id})
            SET t.volume=$volume, t.date=date($date)
            """
            driver.execute_on_db(
                db,
                query,
                {
                    "id": data.get("id"),
                    "volume": data.get("volume"),
                    "date": data.get("date"),
                },
            )

        if model == "plasticos.material.profile":
            query = """
            MERGE (m:MaterialProfile {profile_id:$id})
            SET m.measured_mfi=$mfi
            """
            driver.execute_on_db(
                db,
                query,
                {
                    "id": data.get("id"),
                    "mfi": data.get("measured_mfi"),
                },
            )
