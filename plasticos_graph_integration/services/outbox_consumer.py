import time

from idempotency_registry import IdempotencyRegistry
from neo4j import GraphDatabase


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
