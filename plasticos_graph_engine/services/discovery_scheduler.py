from odoo import models


class DiscoveryScheduler(models.AbstractModel):
    _name = "plasticos.graph.discovery.scheduler"
    _description = "Graph Discovery Scheduler"

    def run(self):
        detect = self.env["plasticos.graph.community.detection"]
        validate = self.env["plasticos.graph.cluster.validation"]
        synthesize = self.env["plasticos.graph.grade.synthesis"]

        clusters = detect.detect()

        for cluster in clusters:
            density = validate.validate(cluster)

            cluster_rec = self.env["plasticos.graph.emergent.cluster"].create(
                {
                    "cluster_id": str(cluster["cluster_id"]),
                    "size": cluster["size"],
                    "density_score": density,
                    "modularity": 0,
                    "grade_ids": cluster["grades"],
                }
            )

            if density > 0.6:
                cluster_rec.status = "validated"
                synthesize.synthesize(cluster["cluster_id"], cluster["grades"])
            else:
                cluster_rec.status = "rejected"
