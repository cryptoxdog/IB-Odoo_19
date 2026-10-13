# D-06 algorithm harness on a Community model. It reproduces the loop of
# plasticos_documents_native.batch_sync_unlinked line for line, with
# res.partner standing in for documents.document (marker: ref = 'ncd-unlinked')
# and res.partner.category standing in for the legacy row. It proves the
# pagination, failure-isolation and counting algorithm on real Odoo +
# PostgreSQL; it is NOT a proof of the Enterprise module itself.
env = globals()["env"]  # injected by `odoo shell`; this file runs only there
results = []


def check(name, ok, detail=""):
    results.append(("PASS" if ok else "FAIL", name, detail))


Partner = env["res.partner"]
Category = env["res.partner.category"]
N = 450
docs = Partner.create([{"name": f"ncd doc {i}", "ref": "ncd-unlinked"} for i in range(N)])
ids = docs.ids
fail_ids = set(ids[49::50])  # raise AFTER creating the legacy row
empty_ids = set(ids[69::70]) - fail_ids  # return an empty result (no tag)
processed = []
logged_failures = []


def sync(doc, failing):
    processed.append(doc.id)
    if doc.id in empty_ids:
        return Category
    legacy = Category.create({"name": f"ncd legacy {doc.id}"})
    if doc.id in failing:
        # A SQL error, so the transaction would be aborted without a savepoint.
        env.cr.execute("SELECT 1/0")
    doc.write({"ref": f"ncd-linked-{legacy.id}"})
    return legacy


def batch_sync(failing):
    domain = [("ref", "=", "ncd-unlinked")]
    last_id = 0
    seen = 0
    synced = 0
    pages = 0
    while True:
        batch = Partner.search([*domain, ("id", ">", last_id)], order="id ASC", limit=200)
        if not batch:
            break
        pages += 1
        last_id = batch[-1].id
        seen += len(batch)
        for doc in batch:
            try:
                with env.cr.savepoint():
                    legacy = sync(doc, failing)
            except Exception:
                logged_failures.append(doc.id)  # the module logs here
                continue
            if legacy:
                synced += 1
    return seen, synced, pages


seen, synced, pages = batch_sync(fail_ids)
linked = Partner.search_count([("id", "in", ids), ("ref", "=like", "ncd-linked-%")])
orphans = Category.search_count([("name", "=like", "ncd legacy %")]) - linked
expected_linked = N - len(fail_ids) - len(empty_ids)
check(
    "every eligible record considered once (>200, 3 pages)",
    sorted(processed) == ids and pages == 3,
    f"seen={seen} processed={len(processed)} pages={pages}",
)
check("no record skipped at a page boundary", seen == N and len(set(processed)) == N)
check(
    "count equals real links (empty results not counted)",
    synced == linked == expected_linked,
    f"synced={synced} linked={linked} expected={expected_linked} empty={len(empty_ids)}",
)
check(
    "a SQL failure does not stop later documents",
    linked == expected_linked and max(processed) == ids[-1],
    f"failures={len(fail_ids)}",
)
check("a failed document leaves no orphan legacy row", orphans == 0, f"orphans={orphans}")
remaining = Partner.search([("id", "in", ids), ("ref", "=", "ncd-unlinked")])
check(
    "failed and empty documents remain eligible",
    set(remaining.ids) == fail_ids | empty_ids,
    f"remaining={len(remaining)}",
)

processed.clear()
empty_ids.clear()
seen2, synced2, pages2 = batch_sync(set())
linked2 = Partner.search_count([("id", "in", ids), ("ref", "=like", "ncd-linked-%")])
legacy_rows = Category.search_count([("name", "=like", "ncd legacy %")])
check(
    "retry run picks up only the remaining records",
    sorted(processed) == sorted(remaining.ids),
    f"seen={seen2} synced={synced2}",
)
check(
    "retry links all; no duplicate legacy rows",
    linked2 == N and legacy_rows == N,
    f"linked={linked2} legacy_rows={legacy_rows}",
)
seen3, synced3, pages3 = batch_sync(set())
check("a third run terminates with nothing to do", (seen3, synced3, pages3) == (0, 0, 0))

env.cr.rollback()
for status, name, detail in results:
    print(f"D06 {status} | {name} | {detail}")
print("D06 SUMMARY", sum(r[0] == "PASS" for r in results), "/", len(results))
