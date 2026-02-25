from neo4j import GraphDatabase


class ConstraintAudit:
    def __init__(self, uri, user, pwd):
        self.driver = GraphDatabase.driver(uri, auth=(user, pwd))

    def run(self):
        with self.driver.session() as s:
            result = s.run("""
            MATCH (mp:MaterialProfile)
            WHERE NOT (mp)-[:HAS_POLYMER]->()
            RETURN count(mp) AS missing_polymer
            """)
            return result.single()["missing_polymer"]
