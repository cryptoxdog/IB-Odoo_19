"""Canonical material-form code registry — single source of truth.

Every layer that references form codes MUST import from here:
  - material_profile.py ``form`` Selection
  - facility_profile.py ``form_preference_id`` (Many2one to material.form)
  - graph_service.py Cypher form-equipment gate
  - matcher.py Gate 2 form comparison
  - tests/test_form_enum_alignment.py drift-prevention tests

Adding or removing a form code here will cause drift-prevention tests to
fail until every downstream consumer is updated.
"""

# ── Canonical form codes (must match material_form_data.xml) ─────────
# Sorted alphabetically for deterministic comparison. UPPERCASE convention.
FORM_CODES: tuple[str, ...] = (
    "BALES",
    "BOTTLES",
    "BUCKETS",
    "CHOPPED",
    "DENSIFIED",
    "DRUMS",
    "FILM",
    "FLAKE",
    "FLOORSWEEP",
    "LOGS",
    "LOOSE",
    "OTHER",
    "PALLETS",
    "PARTS",
    "PELLETS",
    "POWDER",
    "PURGE",
    "REGRIND",
    "ROLLSTOCK",
    "SHEET",
    "SHRED",
)

# ── Equipment-gated forms ────────────────────────────────────────────
# Forms that require specific facility equipment to process.
# Key = form code, Value = Cypher property that must be ``true``.
EQUIPMENT_GATED_FORMS: dict[str, str] = {
    "REGRIND": "f.handles_regrind",
    "FLAKE": "f.handles_flake",
    "ROLLSTOCK": "f.handles_rollstock",
    "BALES": "(f.has_shredder = true OR f.has_granulator = true)",
}

# Forms that pass through without equipment checks.
PASSTHROUGH_FORMS: tuple[str, ...] = tuple(code for code in FORM_CODES if code not in EQUIPMENT_GATED_FORMS)

# ── Selection tuples (for Odoo fields.Selection) ────────────────────
FORM_SELECTION: list[tuple[str, str]] = [(code, code.replace("_", " ").title()) for code in FORM_CODES]
