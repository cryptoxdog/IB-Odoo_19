from odoo import api, models


class GraphOutboxConsumer(models.AbstractModel):
    _name = "plasticos.graph.outbox.consumer"

    @api.model
    def process_queue(self):
        outbox = self.env["plasticos.graph.outbox"].search([("status", "=", "pending")], limit=200)
        driver = self.env["plasticos.neo4j.driver"]

        for event in outbox:
            try:
                handler = getattr(self, f"_handle_{event.model_name.replace('.','_')}", None)
                if handler:
                    handler(event.res_id)
                event.mark_processed()
            except Exception as e:
                event.mark_failed(str(e))

    # MATERIAL PROFILE SYNC
    def _handle_plasticos_material_profile(self, res_id):
        record = self.env["plasticos.material.profile"].browse(res_id)
        driver = self.env["plasticos.neo4j.driver"]

        driver.execute(
            """
        MERGE (m:MaterialProfile {profile_id:$id})
        SET m.measured_mfi=$mfi
        """,
            {"id": record.id, "mfi": getattr(record, "measured_mfi", None)},
        )

    # FACILITY SYNC
    def _handle_res_partner(self, res_id):
        record = self.env["res.partner"].browse(res_id)
        driver = self.env["plasticos.neo4j.driver"]

        driver.execute(
            """
        MERGE (f:Facility {facility_id:$id})
        SET f.geo_point =
            CASE WHEN $lat IS NULL THEN f.geo_point
            ELSE point({latitude:$lat, longitude:$lon}) END
        """,
            {"id": record.id, "lat": record.partner_latitude, "lon": record.partner_longitude},
        )

    # TRANSACTION SYNC
    def _handle_plasticos_transaction(self, res_id):
        record = self.env["plasticos.transaction"].browse(res_id)
        driver = self.env["plasticos.neo4j.driver"]

        driver.execute(
            """
        MERGE (t:Transaction {txn_id:$id})
        SET t.volume=$volume, t.date=date($date)
        """,
            {"id": record.id, "volume": record.volume, "date": str(record.date)},
        )
