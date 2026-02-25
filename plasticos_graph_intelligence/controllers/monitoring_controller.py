from odoo import http
from odoo.http import request


class GraphMonitoringController(http.Controller):
    @http.route("/graph/kpis", type="json", auth="user")
    def kpis(self):
        service = request.env["plasticos.graph.monitoring.service"].sudo()
        return service.kpis()
