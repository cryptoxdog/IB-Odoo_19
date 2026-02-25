"""Build canonical graph payloads from Odoo records.

Field references are aligned with the actual Odoo model schemas
defined in model_registry.json.  Uses ``getattr`` with safe defaults
for optional fields to prevent AttributeError on partial records.
"""

from odoo import models


class GraphPayloadBuilder(models.AbstractModel):
    _name = "plasticos.graph.payload.builder"
    _description = "Build Canonical Graph Payloads"

    def build_material_profile(self, record):
        """Build payload for plasticos.material.profile."""
        return {
            "profile_id": record.id,
            "polymer": record.polymer_id.code if record.polymer_id else None,
            "form": record.form_id.code if record.form_id else None,
            "color": record.color_id.code if record.color_id else None,
            "filler_pct": getattr(record, "filler_pct", None),
            "source": record.source_type_id.code if record.source_type_id else None,
            "contamination_pct": getattr(record, "contamination_pct", None),
            "measured_mfi": getattr(record, "measured_mfi", None),
        }

    def build_facility(self, record):
        """Build payload for res.partner (facility)."""
        return {
            "facility_id": record.id,
            "name": record.name,
            "geo": {
                "lat": getattr(record, "partner_latitude", None),
                "lon": getattr(record, "partner_longitude", None),
            },
        }

    def build_intake(self, record):
        """Build payload for plasticos.intake."""
        return {
            "intake_id": record.id,
            "profile_id": record.material_profile_id.id if record.material_profile_id else None,
            "quantity_lbs": getattr(record, "quantity_lbs", None)
            or getattr(record, "quantity_per_load_lbs", None),
        }

    def build_transaction(self, record):
        """Build payload for plasticos.transaction."""
        return {
            "txn_id": record.id,
            "facility_id": record.partner_id.id if record.partner_id else None,
            "quantity_lbs": getattr(record, "quantity_lbs", None),
            "date": str(record.create_date) if record.create_date else None,
        }
