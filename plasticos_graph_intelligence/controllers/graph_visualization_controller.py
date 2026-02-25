from odoo import http
from odoo.http import request


class GraphVisualizationController(http.Controller):
    @http.route("/graph/intake/<int:intake_id>/subgraph", type="json", auth="user")
    def intake_subgraph(self, intake_id):
        service = request.env["plasticos.graph.visualization.service"].sudo()
        return service.intake_subgraph(intake_id)

    @http.route("/graph/grade/<string:grade_id>/neighborhood", type="json", auth="user")
    def grade_neighborhood(self, grade_id):
        service = request.env["plasticos.graph.visualization.service"].sudo()
        return service.grade_neighborhood(grade_id)
