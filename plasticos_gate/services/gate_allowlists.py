"""Field allowlists and mappings for Odoo <-> Gate payloads."""

from __future__ import annotations

PARTNER_SNAPSHOT_FIELD_MAP = {
    "name": "name",
    "website": "website",
    "city": "city",
    "zip": "zip",
    "street": "street",
    "street2": "street2",
    "comment": "comment",
    "email": "email",
    "phone": "phone",
}

PARTNER_WRITEBACK_FIELD_ALLOWLIST = {
    "name",
    "website",
    "city",
    "zip",
    "street",
    "street2",
    "email",
    "phone",
}

WEB_LEAD_SEED_FIELD_MAP = {
    "company_name": "company",
    "contact_name": "contact",
    "contact_email": "email",
    "contact_phone": "phone",
    "material_description": "material_desc",
    "quantity_text": "quantity_text",
    "contaminant_notes": "contaminants",
}

WEB_LEAD_WRITEBACK_FIELD_MAP = {
    "company": "company_name",
    "contact": "contact_name",
    "email": "contact_email",
    "phone": "contact_phone",
    "material_desc": "material_description",
    "quantity_text": "quantity_text",
}

INTAKE_SNAPSHOT_FIELD_MAP = {
    "quantity_per_load_lbs": "quantity_per_load_lbs",
    "contamination_pct": "contamination_pct",
    "mfi_value": "mfi",
    "lat": "lat",
    "lon": "lon",
}

INTAKE_WRITEBACK_FIELD_MAP = {
    "quantity_per_load_lbs": "quantity_per_load_lbs",
    "contamination_pct": "contamination_pct",
    "mfi": "mfi_value",
}

MATCH_RESULT_FIELD_MAP = {
    "buyer_partner_id": "buyer_id",
    "score": "match_score",
    "reason": "match_reason",
    "typical_price": "typical_price",
}
