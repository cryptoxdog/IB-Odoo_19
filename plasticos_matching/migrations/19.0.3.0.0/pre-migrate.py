"""Matching pre-migrate 19.0.3.0.0 — snapshot retained audit counts (M5)."""

# Static count queries only — table identifiers are not interpolated.
_COUNT_SQL = {
    "plasticos_match_run": "SELECT COUNT(*) FROM plasticos_match_run",
    "plasticos_match_result": "SELECT COUNT(*) FROM plasticos_match_result",
    "plasticos_match_exclusion": "SELECT COUNT(*) FROM plasticos_match_exclusion",
}


def migrate(cr, version):
    """Inventory retained match audit tables; never DELETE/DROP."""
    for table, count_sql in _COUNT_SQL.items():
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
        cr.execute(count_sql)
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
