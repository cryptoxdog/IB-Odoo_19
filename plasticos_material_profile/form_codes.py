"""Canonical material-form code registry — single source of truth.

Every layer that references form codes MUST import from here:
  - material_profile.py ``form`` Selection
  - facility_profile.py ``form_preference_id`` (Many2one to material.form)
  - graph_service.py Cypher form-equipment gate
  - matcher.py Gate 2 form comparison
  - tests/test_material_grade_codes.py drift-prevention tests

Adding or removing a form code here will cause drift-prevention tests to
fail until every downstream consumer is updated. Material grades (drums,
totes, pallets) are not forms; they live in ``grade_codes.py``.
"""

# ── Canonical form codes (must match the active records of material_form_data.xml) ──
# Sorted alphabetically for deterministic comparison. UPPERCASE convention.
# Bales are packaging (``plasticos.packaging.type`` code ``bales``), never a form: the
# form ``plasticos_material_profile.form_bale`` is archived and is not a form code.
# REPRO and LOOSE were retired in 19.0.5.14.0 (ADR-134 §6). Repro is the attribute
# ``attr_repro``. Loose is packaging ``loose``. Both form records stay archived.
RETIRED_FORM_CODES: tuple[str, ...] = ("BALES", "LOOSE", "REPRO")
FORM_CODES: tuple[str, ...] = (
    "CHOPPED",
    "CORRUGATED",
    "DENSIFIED",
    "FILM",
    "FLAKE",
    "FLOORSWEEP",
    "FLUFF",
    "LOGS",
    "OTHER",
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
}

# Forms that pass through without equipment checks.
PASSTHROUGH_FORMS: tuple[str, ...] = tuple(code for code in FORM_CODES if code not in EQUIPMENT_GATED_FORMS)

# ── Selection tuples (for Odoo fields.Selection) ────────────────────
FORM_SELECTION: list[tuple[str, str]] = [(code, code.replace("_", " ").title()) for code in FORM_CODES]
