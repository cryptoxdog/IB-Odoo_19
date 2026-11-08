"""Fail closed before removing the HubSpot / Salesforce / Zoho stub providers.

The stub adapter files, registry entries and selection options are removed in
19.0.1.7.0 (odoo-intent-1 ingestion milestone: only VanillaSoft is
implemented). A connection row still referencing a removed provider cannot be
edited or synced after the selection shrinks, so the upgrade refuses rather
than leaving an orphaned connection behind.

If this ever fires on a real database: convert or archive the named
connections, then re-run the upgrade.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        SELECT id, name, provider
        FROM plasticos_crm_connection
        WHERE provider IN ('hubspot', 'salesforce', 'zoho')
        ORDER BY id
        """
    )
    rows = cr.fetchall()
    if rows:
        details = "; ".join(f"id={row[0]} name={row[1]!r} provider={row[2]}" for row in rows[:5])
        raise RuntimeError(
            "plasticos_crm_sync 19.0.1.7.0 removes the HubSpot / Salesforce / Zoho stub providers, "
            f"but connections still reference them ({details}). "
            "Archive or convert those connections before upgrading."
        )
