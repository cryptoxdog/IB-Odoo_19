"""Standalone outbox consumer for external deployment.

This module is designed to run as a separate process outside of Odoo,
polling the outbox table and writing events to Neo4j.  For the
Odoo-integrated consumer, see ``plasticos_graph_engine.services.outbox_consumer``.
"""

import time

from neo4j import GraphDatabase

from .idempotency_registry import IdempotencyRegistry


class OutboxConsumer:
    def __init__(self, odoo_repo, neo_uri, user, pwd):
        self.repo = odoo_repo
        self.driver = GraphDatabase.driver(neo_uri, auth=(user, pwd))
        self.registry = IdempotencyRegistry()

    def run(self):
        while True:
            events = self.repo.fetch_unprocessed_events(limit=100)

            for e in events:
                if self.registry.seen(e["event_id"]):
                    continue

                self.process_event(e)
                self.registry.mark(e["event_id"])
                self.repo.mark_processed(e["id"])

            time.sleep(2)

    def process_event(self, event):
        with self.driver.session() as s:
            s.run(event["cypher"], event["params"])
