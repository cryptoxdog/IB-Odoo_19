"""Enrichment post-migrate 19.0.2.0.0 — preserve audit; disable local crons (M5)."""


def migrate(cr, version):
    """Retain enrichment audit; force local intelligence crons inactive."""
    cr.execute(
        """
        INSERT INTO ir_config_parameter (key, value, create_uid, create_date, write_uid, write_date)
        VALUES (
            'plasticos.mothball.enrichment.authority',
            'gate_only',
            1, NOW() AT TIME ZONE 'UTC', 1, NOW() AT TIME ZONE 'UTC'
        )
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value,
            write_uid = 1, write_date = NOW() AT TIME ZONE 'UTC'
        """
    )
    # Ensure enrichment crawl/inference crons stay inactive (idempotent).
    cr.execute(
        """
        UPDATE ir_cron AS c
           SET active = FALSE
          FROM ir_model_data AS d
         WHERE d.model = 'ir.cron'
           AND d.res_id = c.id
           AND d.module = 'plasticos_enrichment'
        """
    )
