from datetime import datetime

from odoo import http
from odoo.http import request


class GraphMatchController(http.Controller):
    @http.route("/graph/match/<int:intake_id>", type="json", auth="user", methods=["POST"], csrf=False)
    def match_intake(self, intake_id, mode="strict"):
        env = request.env.sudo()
        service = env["plasticos.realtime.match.service"]

        start = datetime.utcnow()

        try:
            match_request_id = service.execute(intake_id=intake_id, mode=mode)

            results = env["plasticos.match.result"].search(
                [("match_request_id", "=", match_request_id)], order="final_score desc"
            )

            latency_ms = (datetime.utcnow() - start).total_seconds() * 1000

            return {
                "status": "success",
                "match_request_id": match_request_id,
                "latency_ms": latency_ms,
                "count": len(results),
                "results": [
                    {
                        "facility_id": r.facility_id.id,
                        "facility_name": r.facility_id.name,
                        "grade_id": r.grade_id,
                        "scores": {
                            "final": r.final_score,
                            "structural": r.structural_score,
                            "similarity": r.similarity_score,
                            "reinforcement": r.reinforcement_score,
                            "confidence": r.confidence_score,
                        },
                        "explainability_id": r.explainability_id.id if r.explainability_id else None,
                    }
                    for r in results
                ],
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}
