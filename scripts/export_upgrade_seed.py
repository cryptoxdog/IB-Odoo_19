"""Seed a disposable test clone with synthetic Staging-shaped legacy data (Export campaign S6, F1/F7).

The S6 upgrade proof needs a database that looks like Staging before the Export
slices: installed at the Staging module versions and holding the legacy row shapes
the slice migrations must classify or repair. The admitted fixture is empty, so this
script adds them to an owned clone, with the Staging code still on disk:

* loads with no company: no sale order of their own, so the old stored related
  ``company_id`` is NULL, and exactly one authoritative source through the parent
  transaction (its sale order, or with no sale order its purchase orders);
* multi-load transactions (one parent, several loads);
* the old parent link column ``plasticos_transaction.load_id``. Odoo does not drop a
  removed field's column, so a database that ran Logistics 19.0.1.14.6 still carries
  it beside ``plasticos_load.transaction_id``; the values agree with that link;
* legacy documents with an accepted association and verification decision: actor,
  time and source digest, with the evidence digest equal to the source revision;
* dispatched loads with ``dispatch_sent`` and no acknowledgement. One lane holds more
  than ``LOAD_SWEEP_BATCH`` (200) of them, the F6 measurement volume.

Every name is synthetic (``S6-SYN-...``); no real record, address, e-mail or secret
is written. The rows that a legacy database holds but the current ORM refuses to
create (accepted decisions, dispatched state) are written with fixed SQL statements
after an ORM create, as a legacy import would have left them.

Usage, on an owned clone only (the guard refuses anything else)::

    scripts/test_env.sh run odoo_test_<suffix> -- shell < scripts/export_upgrade_seed.py

The pure functions (plan, guard, summary) are tested in tests/test_export_upgrade_seed.py.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import timedelta

SEED_MARKER = "plasticos_s6.synthetic_upgrade_seed"
NAME_PREFIX = "S6-SYN"
# More than LOAD_SWEEP_BATCH (200) eligible loads in the ACK lane.
DEFAULT_LANE_LOADS = 240
DEFAULT_MULTI_LOAD_TRANSACTIONS = 4
DEFAULT_LOADS_PER_TRANSACTION = 3
DEFAULT_PO_ONLY_TRANSACTIONS = 2
DEFAULT_ACCEPTED_DOCUMENTS = 6
DEFAULT_PENDING_DOCUMENTS = 2

_CLONE_NAME = re.compile(r"^odoo_test_[a-z0-9_]{1,48}$")

# Fixed statements. Only bound parameters vary; no SQL text is composed.
SQL_ADD_LEGACY_PARENT_COLUMN = "ALTER TABLE plasticos_transaction ADD COLUMN IF NOT EXISTS load_id integer"
SQL_SET_LEGACY_PARENT = "UPDATE plasticos_transaction SET load_id = %s WHERE id = %s"
# The current ORM refuses a parent link for a load with no sale order (no company);
# legacy rows carry it because 19.0.1.14.6 copied the old link without that guard.
SQL_LEGACY_PARENT_LINK = "UPDATE plasticos_load SET transaction_id = %s WHERE id = ANY(%s)"
SQL_LEGACY_DISPATCHED = (
    "UPDATE plasticos_load SET state = 'dispatched', dispatch_sent = %s, dispatch_acknowledged = NULL WHERE id = ANY(%s)"
)
SQL_LEGACY_ACCEPTED_DOCUMENT = """
    UPDATE plasticos_document
       SET association_state = 'accepted',
           associated_by = %s,
           associated_at = %s,
           source_revision = %s,
           subject_company_id = %s,
           verified = TRUE,
           verified_by = %s,
           verified_at = %s,
           evidence_digest = %s,
           evidence_attachment_id = %s,
           load_id = %s,
           transaction_id = %s
     WHERE id = %s
"""


def guard_database(dbname):
    """Refuse every database that is not a disposable test clone name."""
    if not isinstance(dbname, str) or not _CLONE_NAME.match(dbname):
        raise SystemExit(f"export_upgrade_seed: '{dbname}' is not a disposable odoo_test_<suffix> clone")
    if dbname.startswith(("odoo_test_tpl_", "odoo_test_bld_")):
        raise SystemExit(f"export_upgrade_seed: '{dbname}' is a template or build database")
    if "prod" in dbname or "staging" in dbname:
        raise SystemExit(f"export_upgrade_seed: '{dbname}' names a production or staging database")
    return dbname


def build_plan(
    lane_loads=DEFAULT_LANE_LOADS,
    multi_load_transactions=DEFAULT_MULTI_LOAD_TRANSACTIONS,
    loads_per_transaction=DEFAULT_LOADS_PER_TRANSACTION,
    po_only_transactions=DEFAULT_PO_ONLY_TRANSACTIONS,
    accepted_documents=DEFAULT_ACCEPTED_DOCUMENTS,
    pending_documents=DEFAULT_PENDING_DOCUMENTS,
):
    """The deterministic seed plan: names and shapes only, no database access."""
    for label, value, minimum in (
        ("lane_loads", lane_loads, 201),
        ("multi_load_transactions", multi_load_transactions, 1),
        ("loads_per_transaction", loads_per_transaction, 2),
        ("po_only_transactions", po_only_transactions, 1),
        ("accepted_documents", accepted_documents, 1),
        ("pending_documents", pending_documents, 0),
    ):
        if not isinstance(value, int) or value < minimum:
            raise ValueError(f"{label} must be an integer >= {minimum} (got {value!r})")
    transactions = []
    for t in range(1, multi_load_transactions + 1):
        loads = [
            # The first load carries the sale order; the others only the parent link,
            # so their stored related company is NULL (the 14.20 repair case).
            {"name": f"{NAME_PREFIX}-L-T{t:02d}-{n}", "own_sale_order": n == 1}
            for n in range(1, loads_per_transaction + 1)
        ]
        transactions.append({"name": f"{NAME_PREFIX}-TX-{t:02d}", "source": "sale_order", "loads": loads})
    for t in range(1, po_only_transactions + 1):
        transactions.append(
            {
                "name": f"{NAME_PREFIX}-TXP-{t:02d}",
                "source": "purchase_order",
                "loads": [{"name": f"{NAME_PREFIX}-L-P{t:02d}-1", "own_sale_order": False}],
            }
        )
    return {
        "marker": SEED_MARKER,
        "partners": [f"{NAME_PREFIX} Buyer", f"{NAME_PREFIX} Supplier", f"{NAME_PREFIX} Carrier"],
        "transactions": transactions,
        "lane_loads": [f"{NAME_PREFIX}-L-LANE-{n:04d}" for n in range(1, lane_loads + 1)],
        "accepted_documents": [f"{NAME_PREFIX}-DOC-A-{n:02d}" for n in range(1, accepted_documents + 1)],
        "pending_documents": [f"{NAME_PREFIX}-DOC-P-{n:02d}" for n in range(1, pending_documents + 1)],
    }


def expected_summary(plan):
    """Counts the seeded database must show for this plan."""
    tx_loads = [load for tx in plan["transactions"] for load in tx["loads"]]
    return {
        "transactions": len(plan["transactions"]),
        "multi_load_transactions": sum(1 for tx in plan["transactions"] if len(tx["loads"]) > 1),
        "loads": len(tx_loads) + len(plan["lane_loads"]),
        "null_company_loads": sum(1 for load in tx_loads if not load["own_sale_order"]),
        "legacy_parent_links": len(plan["transactions"]),
        "dispatched_unacknowledged": len(plan["lane_loads"]),
        "accepted_documents": len(plan["accepted_documents"]),
        "documents": len(plan["accepted_documents"]) + len(plan["pending_documents"]),
    }


def synthetic_bytes(name):
    """Deterministic synthetic attachment content (not a real document)."""
    return f"{NAME_PREFIX} synthetic evidence for {name}\n".encode()


def synthetic_checksum(name):
    """Odoo's ir.attachment checksum (sha1 of the raw bytes) for synthetic_bytes(name)."""
    return hashlib.sha1(synthetic_bytes(name)).hexdigest()  # noqa: S324 - Odoo's own attachment checksum


# ---------------------------------------------------------------------------
# Odoo shell part. Runs only where the shell provides ``env``.
# ---------------------------------------------------------------------------
def _partner(env, name, **vals):
    return env["res.partner"].create({"name": name, "is_company": True, **vals})


def seed(env, plan):
    guard_database(env.cr.dbname)
    params = env["ir.config_parameter"].sudo()  # sudo: seed marker is a system parameter on a test clone
    if params.get_param(SEED_MARKER):
        raise SystemExit(f"export_upgrade_seed: {env.cr.dbname} is already seeded ({SEED_MARKER})")
    company = env.company
    admin = env.ref("base.user_admin")
    now = env.cr.now()
    buyer = _partner(env, plan["partners"][0], customer_rank=1)
    supplier = _partner(env, plan["partners"][1], supplier_rank=1)
    _partner(env, plan["partners"][2], supplier_rank=1)
    SaleOrder, PurchaseOrder = env["sale.order"], env["purchase.order"]
    Transaction, Load = env["plasticos.transaction"], env["plasticos.load"]

    env.cr.execute(SQL_ADD_LEGACY_PARENT_COLUMN)
    tx_records, tx_loads = [], []
    for tx in plan["transactions"]:
        vals = {"name": tx["name"], "buyer_id": buyer.id, "supplier_id": supplier.id}
        so = SaleOrder
        if tx["source"] == "sale_order":
            so = SaleOrder.create({"partner_id": buyer.id, "company_id": company.id})
            vals["sale_order_id"] = so.id
        record = Transaction.create(vals)
        if tx["source"] == "purchase_order":
            po = PurchaseOrder.create({"partner_id": supplier.id, "company_id": company.id})
            record.write({"purchase_order_ids": [(4, po.id)]})
        loads = Load
        for spec in tx["loads"]:
            load_vals = {"name": spec["name"]}
            if spec["own_sale_order"]:
                load_vals["sale_order_id"] = so.id
            loads |= Load.create(load_vals)
        env.cr.execute(SQL_LEGACY_PARENT_LINK, (record.id, loads.ids))
        # The legacy column keeps the value it had: the first load of the parent.
        env.cr.execute(SQL_SET_LEGACY_PARENT, (loads[:1].id, record.id))
        tx_records.append(record)
        tx_loads.append(loads)

    # The parent links above were written with SQL; reread them through the ORM.
    env.invalidate_all()

    lane_so = SaleOrder.create({"partner_id": buyer.id, "company_id": company.id})
    lane = Load.create([{"name": name, "sale_order_id": lane_so.id} for name in plan["lane_loads"]])
    env.cr.execute(SQL_LEGACY_DISPATCHED, (now - timedelta(days=1), lane.ids))

    tag = env["plasticos.document.tag"].search([], order="id asc", limit=1)
    if not tag:
        raise SystemExit("export_upgrade_seed: no plasticos.document.tag to attach legacy documents to")
    subjects = [load for loads in tx_loads for load in loads]
    Document, Attachment = env["plasticos.document"], env["ir.attachment"]
    for index, name in enumerate(plan["accepted_documents"] + plan["pending_documents"]):
        load = subjects[index % len(subjects)]
        attachment = Attachment.create(
            {
                "name": f"{name}.txt",
                "datas": base64.b64encode(synthetic_bytes(name)),
                "res_model": "plasticos.load",
                "res_id": load.id,
                "mimetype": "text/plain",
            }
        )
        document = Document.create(
            {
                "name": name,
                "res_model": "plasticos.load",
                "res_id": load.id,
                "attachment_id": attachment.id,
                "tag_id": tag.id,
            }
        )
        if name in plan["accepted_documents"]:
            parent = load.transaction_id
            env.cr.execute(
                SQL_LEGACY_ACCEPTED_DOCUMENT,
                (
                    admin.id,
                    now - timedelta(days=2),
                    attachment.checksum,
                    company.id,
                    admin.id,
                    now - timedelta(days=2),
                    attachment.checksum,
                    attachment.id,
                    load.id,
                    parent.id or None,
                    document.id,
                ),
            )
    params.set_param(SEED_MARKER, json.dumps({"plan": expected_summary(plan)}, sort_keys=True))
    env.invalidate_all()
    return observed_summary(env)


def observed_summary(env):
    """What the database holds now, read back with SQL (the same counts as expected_summary)."""
    cr = env.cr
    pattern = f"{NAME_PREFIX}-%"
    queries = {
        "transactions": ("SELECT count(*) FROM plasticos_transaction WHERE name LIKE %s", (pattern,)),
        "multi_load_transactions": (
            "SELECT count(*) FROM (SELECT t.id FROM plasticos_transaction t JOIN plasticos_load l"
            " ON l.transaction_id = t.id WHERE t.name LIKE %s GROUP BY t.id HAVING count(*) > 1) s",
            (pattern,),
        ),
        "loads": ("SELECT count(*) FROM plasticos_load WHERE name LIKE %s", (pattern,)),
        "null_company_loads": (
            "SELECT count(*) FROM plasticos_load WHERE name LIKE %s AND company_id IS NULL",
            (pattern,),
        ),
        "legacy_parent_links": (
            "SELECT count(*) FROM plasticos_transaction t JOIN plasticos_load l"
            " ON l.id = t.load_id AND l.transaction_id = t.id WHERE t.name LIKE %s",
            (pattern,),
        ),
        "dispatched_unacknowledged": (
            "SELECT count(*) FROM plasticos_load WHERE name LIKE %s AND state = 'dispatched'"
            " AND dispatch_sent IS NOT NULL AND dispatch_acknowledged IS NULL",
            (pattern,),
        ),
        "accepted_documents": (
            "SELECT count(*) FROM plasticos_document WHERE name LIKE %s AND association_state = 'accepted'"
            " AND verified AND associated_by IS NOT NULL AND associated_at IS NOT NULL"
            " AND source_revision = evidence_digest",
            (pattern,),
        ),
        "documents": ("SELECT count(*) FROM plasticos_document WHERE name LIKE %s", (pattern,)),
    }
    result = {}
    for key, (sql, args) in queries.items():
        cr.execute(sql, args)
        result[key] = cr.fetchone()[0]
    return result


def main(env):
    plan = build_plan()
    observed = seed(env, plan)
    expected = expected_summary(plan)
    print("S6_SEED_EXPECTED " + json.dumps(expected, sort_keys=True))
    print("S6_SEED_OBSERVED " + json.dumps(observed, sort_keys=True))
    if observed != expected:
        env.cr.rollback()
        raise SystemExit("export_upgrade_seed: observed counts differ from the plan; rolled back")
    env.cr.commit()
    print(f"S6_SEED_COMMITTED {env.cr.dbname}")


if "env" in globals() and __name__ != "export_upgrade_seed":
    main(globals()["env"])
