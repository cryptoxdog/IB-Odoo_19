"""Enrichment pre-migrate 19.0.2.0.0 — snapshot retained audit counts (M5)."""


def migrate(cr, version):
    """Inventory retained enrichment audit tables; never DELETE/DROP."""
    retained = (
        "plasticos_enrichment_run",
        "plasticos_enrichment_provenance",
        "plasticos_enrichment_extraction",
        "plasticos_enrichment_source",
    )
    for table in retained:
        cr.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = %s
            )
            """,
            (table,),
        )
        exists = cr.fetchone()[0]
        if not exists:
            continue
        cr.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608 — fixed table list
        count = cr.fetchone()[0]
        cr.execute(
            """
            INSERT INTO ir_config_parameter (key, value, create_uid, create_date, write_uid, write_date)
            VALUES (%s, %s, 1, NOW() AT TIME ZONE 'UTC', 1, NOW() AT TIME ZONE 'UTC')
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value,
                write_uid = 1, write_date = NOW() AT TIME ZONE 'UTC'
            """,
            (f"plasticos.mothball.pre.{table}.count", str(count)),
        )
