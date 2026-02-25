import json

from kafka import KafkaConsumer

from odoo import models


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
        )

    def start(self):
        consumer = self._get_consumer()
        driver = self.env["plasticos.neo4j.cluster.driver"]
        shard_router = self.env["plasticos.shard.router"]

        for message in consumer:
            event = message.value
            event_id = event["event_id"]

            if self.env["plasticos.graph.idempotency"].search([("event_id", "=", event_id)]):
                consumer.commit()
                continue

            model = event["model"]
            data = event["data"]

            facility_id = data.get("facility_id") or data.get("partner_id")
            db = shard_router.get_shard_db(facility_id) if facility_id else shard_router.CONTROL_DB

            self._process_event(driver, db, model, data)

            self.env["plasticos.graph.idempotency"].create({"event_id": event_id})
            consumer.commit()

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
