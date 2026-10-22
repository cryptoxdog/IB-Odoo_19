"""Assign crm.lead.user_id from a VanillaSoft export and the locked owner map.

Run inside ``odoo shell`` after the salesperson logins exist. Set
``VANILLASOFT_OWNER_CSV`` to the export that has ``ContactID`` and
``Contact Owner``. An unresolved owner is counted and does not clear a
salesperson already stored on the lead.

Prints before/after counts of leads whose ``user_id`` is empty, then the
backfill counters.
"""

import os


def _odoo_env():
    env = globals().get("env")
    if env is None:
        raise SystemExit("no Odoo environment (run inside `odoo shell`)")
    return env


def main() -> int:
    from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator
    from odoo.addons.plasticos_crm_sync.services.owner_crosswalk import owner_pairs_from_csv

    path = os.environ.get("VANILLASOFT_OWNER_CSV", "").strip()
    if not path:
        raise SystemExit("VANILLASOFT_OWNER_CSV is required")
    env = _odoo_env()
    leads = env["crm.lead"].with_context(active_test=False)
    before_empty = leads.search_count([("user_id", "=", False), ("vanillasoft_id", "!=", False)])
    before_total = leads.search_count([("vanillasoft_id", "!=", False)])
    orch = SyncOrchestrator(env)
    counts = orch.backfill_owners(owner_pairs_from_csv(path))
    after_empty = leads.search_count([("user_id", "=", False), ("vanillasoft_id", "!=", False)])
    print(
        {
            "vanillasoft_leads": before_total,
            "empty_salesperson_before": before_empty,
            "empty_salesperson_after": after_empty,
            **counts,
        }
    )
    env.cr.commit()
    if counts["failed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
