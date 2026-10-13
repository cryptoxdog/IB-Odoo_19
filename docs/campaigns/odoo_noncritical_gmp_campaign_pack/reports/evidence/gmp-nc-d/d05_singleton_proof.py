# D-05 runtime proof. Runs inside `odoo shell` on a disposable clone and never commits.
import psycopg2

from odoo.exceptions import ValidationError

env = globals()["env"]  # injected by `odoo shell`; this file runs only there

Config = env["plasticos.automation.config"].with_context(active_test=False)
results = []


def check(name, ok, detail=""):
    results.append(("PASS" if ok else "FAIL", name, detail))


def rows():
    env.cr.execute("SELECT id, active FROM plasticos_automation_config ORDER BY id")
    return env.cr.fetchall()


before = rows()
active = Config.search([("active", "=", True)])
check("seed holds exactly one active configuration", len(active) == 1, f"rows={before}")
existing = active[:1]

try:
    existing._check_singleton()
    check("the current record is excluded from its own check", True)
except ValidationError as exc:
    check("the current record is excluded from its own check", False, str(exc))

sp = env.cr.savepoint()
inactive = Config.create({"name": "d05 inactive", "active": False})
try:
    inactive._check_singleton()
    existing._check_singleton()
    check("an inactive record raises no false conflict", True, f"inactive_id={inactive.id}")
except ValidationError as exc:
    check("an inactive record raises no false conflict", False, str(exc))
sp.close(rollback=True)

env.cr.execute(
    "SELECT conname FROM pg_constraint WHERE conrelid = 'plasticos_automation_config'::regclass AND contype = 'x'"
)
exclude = [r[0] for r in env.cr.fetchall()]
check("database EXCLUDE constraint is present", len(exclude) == 1, f"constraints={exclude}")

sp = env.cr.savepoint()
try:
    Config.create({"name": "d05 second active", "active": True})
    check("database constraint rejects a second active record", False, "create succeeded")
except (psycopg2.Error, ValidationError) as exc:
    check("database constraint rejects a second active record", True, type(exc).__name__)
sp.close(rollback=True)

# Isolate the Python constraint (the changed search_count path): drop the
# EXCLUDE constraint inside a savepoint, then roll the DDL back.
sp = env.cr.savepoint()
env.cr.execute(f'ALTER TABLE plasticos_automation_config DROP CONSTRAINT "{exclude[0]}"')
try:
    Config.create({"name": "d05 python-only second active", "active": True})
    check("search_count constraint rejects a second active record", False, "create succeeded")
except ValidationError as exc:
    check("search_count constraint rejects a second active record", True, str(exc)[:80])
sp.close(rollback=True)

sp = env.cr.savepoint()
env.cr.execute(f'ALTER TABLE plasticos_automation_config DROP CONSTRAINT "{exclude[0]}"')
second = Config.create({"name": "d05 reactivation", "active": False})
try:
    second.write({"active": True})
    check("search_count constraint rejects reactivating a second record", False, "write succeeded")
except ValidationError as exc:
    check("search_count constraint rejects reactivating a second record", True, str(exc)[:80])
sp.close(rollback=True)

env.cr.execute(
    "SELECT count(*) FROM pg_constraint WHERE conrelid = 'plasticos_automation_config'::regclass AND contype = 'x'"
)
check("EXCLUDE constraint restored after rollback", env.cr.fetchone()[0] == 1)
check("no configuration record created or removed", rows() == before, f"after={rows()}")

env.cr.rollback()
for status, name, detail in results:
    print(f"D05 {status} | {name} | {detail}")
print("D05 SUMMARY", sum(r[0] == "PASS" for r in results), "/", len(results))
