"""Matching post-migrate 19.0.3.0.0 — preserve audit; mark Gate authority (M5)."""


def migrate(cr, version):
    """Retain all match audit rows; record mothball identity marker."""
    # Never DELETE/DROP retained audit tables.
    cr.execute(
        """
        INSERT INTO ir_config_parameter (key, value, create_uid, create_date, write_uid, write_date)
        VALUES (
            'plasticos.mothball.matching.authority',
            'gate_only',
            1, NOW() AT TIME ZONE 'UTC', 1, NOW() AT TIME ZONE 'UTC'
        )
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value,
            write_uid = 1, write_date = NOW() AT TIME ZONE 'UTC'
        """
    )
    cr.execute(
        """
        INSERT INTO ir_config_parameter (key, value, create_uid, create_date, write_uid, write_date)
        VALUES (
            'plasticos.mothball.matching.version',
            '19.0.3.0.0',
            1, NOW() AT TIME ZONE 'UTC', 1, NOW() AT TIME ZONE 'UTC'
        )
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value,
            write_uid = 1, write_date = NOW() AT TIME ZONE 'UTC'
        """
    )
