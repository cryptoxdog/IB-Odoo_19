import json
import uuid

from kafka import KafkaProducer

from odoo import models


class KafkaProducerService(models.AbstractModel):
    _name = "plasticos.kafka.producer"
    _description = "Graph Event Kafka Producer"

    def _get_producer(self):
        return KafkaProducer(
            bootstrap_servers="localhost:9092",
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            retries=5,
        )

    def publish(self, topic, payload):
        producer = self._get_producer()
        event_id = str(uuid.uuid4())

        envelope = {
            "event_id": event_id,
            "model": payload.get("model"),
            "event": payload.get("event"),
            "timestamp": payload.get("timestamp"),
            "data": payload.get("data"),
        }

        producer.send(topic, envelope)
        producer.flush()
        return event_id
