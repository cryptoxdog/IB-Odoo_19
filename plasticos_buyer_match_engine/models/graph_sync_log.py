"""Audit log for Neo4j graph sync operations."""

from odoo import fields, models


class PlasticosGraphSyncLog(models.Model):
    _name = "plasticos.graph.sync.log"
    _description = "Graph Sync Audit Log"
    _order = "started_at desc"

    name = fields.Char(string="Sync Run", required=True, index=True)
    sync_type = fields.Selection(
        [
            ("facility", "Facilities"),
            ("material", "Materials"),
            ("transaction", "Transactions"),
            ("taxonomy", "Taxonomy Nodes"),
            ("facility_edges", "Facility Edges"),
            ("material_edges", "Material Edges"),
            ("exclusion", "Exclusion Edges"),
            ("bought_polymer", "Bought Polymer Edges"),
            ("bought_form", "Bought Form Edges"),
            ("co_purchased", "Co-Purchased Edges"),
            ("offer_edges", "Offer Edges"),
            ("compatible_with", "Compatible With Edges"),
            ("profile_similarity", "Profile Similarity Edges"),
            ("full", "Full Sync"),
        ],
        required=True,
        index=True,
    )
    record_count = fields.Integer(string="Records Processed")
    status = fields.Selection(
        [
            ("success", "Success"),
            ("failed", "Failed"),
            ("partial", "Partial"),
        ],
        required=True,
        index=True,
    )
    error_message = fields.Text(string="Error Details")
    started_at = fields.Datetime(required=True)
    finished_at = fields.Datetime()
