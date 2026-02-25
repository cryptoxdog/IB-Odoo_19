from odoo import models


class GNNEmbeddingWriter(models.AbstractModel):
    _name = "plasticos.graph.gnn.writer"

    def write_embeddings(self, tenant_code, embeddings):
        router = self.env["plasticos.graph.tenant.router"]
        db = router.get_database(tenant_code)
        driver = self.env["plasticos.neo4j.cluster.driver"]

        for idx, emb in enumerate(embeddings):
            driver.execute_on_db(
                db,
                """
            MATCH (g:Grade)
            WHERE id(g) = $id
            SET g.gnn_embedding = $embedding
            """,
                {
                    "id": int(idx),
                    "embedding": emb.tolist(),
                },
            )
