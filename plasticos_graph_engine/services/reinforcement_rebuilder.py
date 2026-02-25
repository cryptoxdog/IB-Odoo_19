from neo4j import GraphDatabase


class ReinforcementRebuilder:
    def __init__(self, uri, user, pwd):
        self.driver = GraphDatabase.driver(uri, auth=(user, pwd))

    def rebuild(self):
        with self.driver.session() as s:
            s.run("""
            MATCH (f:Facility)-[r:SUCCESS_WITH]->()
            DELETE r
            """)

            s.run("""
            MATCH (t:Transaction)-[:BETWEEN]->(f)
            MATCH (t)-[:INVOLVES]->(g)
            WITH f, g,
                 count(*) AS txn_count,
                 max(t.date) AS last_txn
            MERGE (f)-[r:SUCCESS_WITH]->(g)
            SET r.score = txn_count,
                r.recency_weight = exp(-duration.inDays(last_txn, date()).days / 90.0)
            """)
