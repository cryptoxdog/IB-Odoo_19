from odoo import models


class GraphPayloadBuilder(models.AbstractModel):
    _name = "plasticos.graph.payload.builder"
    _description = "Build Canonical Graph Payloads"

    def build_material_profile(self, record):
        return {
            "profile_id": record.id,
            "polymer": record.polymer_id.code,
            "form": record.form_id.code if record.form_id else None,
            "color": record.color_id.code if record.color_id else None,
            "filler": record.filler_type_id.code if record.filler_type_id else None,
            "source": record.source_type_id.code if record.source_type_id else None,
            "attributes": record.material_attribute_ids.mapped("code"),
        }

    def build_facility(self, record):
        return {
            "facility_id": record.id,
            "process_types": [record.process_type] if record.process_type else [],
            "stated_profiles": record.material_profile_ids.mapped("id"),
            "geo": {
                "lat": record.partner_latitude,
                "lon": record.partner_longitude,
            },
        }

    def build_intake(self, record):
        return {
            "intake_id": record.id,
            "profile_id": record.material_profile_id.id,
            "quantity": record.quantity,
        }

    def build_transaction(self, record):
        return {
            "txn_id": record.id,
            "facility_id": record.partner_id.id,
            "grade_id": record.grade_id,
            "volume": record.volume,
            "date": record.date,
        }
