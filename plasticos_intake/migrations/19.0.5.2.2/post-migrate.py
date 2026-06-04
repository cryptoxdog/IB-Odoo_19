import logging

_logger = logging.getLogger(__name__)

_POLYMER_XMLID = "plasticos_material_profile.polymer_other"
_FORM_XMLID = "plasticos_material_profile.form_other"


def _resolve_xmlid(cr, xmlid: str) -> int | None:
    module, name = xmlid.split(".", 1)
    cr.execute(
        "SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s",
        (module, name),
    )
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, version):
    """Add NOT NULL constraints to plasticos_intake.polymer_id and form_id.

    Odoo emits 'Missing not-null constraint' warnings at startup when a
    required=True field exists in Python but the DB column was created
    without NOT NULL (schema drift from a previous upgrade path).

    This migration:
      1. Finds any intake rows with NULL polymer_id / form_id.
      2. Fills them with the 'OTHER' fallback record from the material registry.
      3. Applies SET NOT NULL so Odoo's schema checker no longer warns.
    """
    _logger.info("[5.2.2 migration] Patching NOT NULL constraints on plasticos_intake ...")

    polymer_fallback_id = _resolve_xmlid(cr, _POLYMER_XMLID)
    form_fallback_id = _resolve_xmlid(cr, _FORM_XMLID)

    if not polymer_fallback_id:
        _logger.error(
            "[5.2.2 migration] Cannot resolve %s — aborting NOT NULL patch for polymer_id",
            _POLYMER_XMLID,
        )
        return
    if not form_fallback_id:
        _logger.error(
            "[5.2.2 migration] Cannot resolve %s — aborting NOT NULL patch for form_id",
            _FORM_XMLID,
        )
        return

    # --- polymer_id ---
    cr.execute("SELECT COUNT(*) FROM plasticos_intake WHERE polymer_id IS NULL")
    null_polymer = cr.fetchone()[0]
    if null_polymer:
        _logger.warning(
            "[5.2.2 migration] %d intake rows have NULL polymer_id — backfilling with OTHER (%d)",
            null_polymer,
            polymer_fallback_id,
        )
        cr.execute(
            "UPDATE plasticos_intake SET polymer_id = %s WHERE polymer_id IS NULL",
            (polymer_fallback_id,),
        )
    else:
        _logger.info("[5.2.2 migration] No NULL polymer_id rows found.")

    # --- form_id ---
    cr.execute("SELECT COUNT(*) FROM plasticos_intake WHERE form_id IS NULL")
    null_form = cr.fetchone()[0]
    if null_form:
        _logger.warning(
            "[5.2.2 migration] %d intake rows have NULL form_id — backfilling with OTHER (%d)",
            null_form,
            form_fallback_id,
        )
        cr.execute(
            "UPDATE plasticos_intake SET form_id = %s WHERE form_id IS NULL",
            (form_fallback_id,),
        )
    else:
        _logger.info("[5.2.2 migration] No NULL form_id rows found.")

    # --- apply NOT NULL constraints ---
    cr.execute(
        """
        ALTER TABLE plasticos_intake
            ALTER COLUMN polymer_id SET NOT NULL,
            ALTER COLUMN form_id    SET NOT NULL
        """
    )
    _logger.info("[5.2.2 migration] NOT NULL constraints applied to polymer_id and form_id.")
