# Running the C1–C6 launch gates without Docker

The gates in `LAUNCH_GATES.md` need a real Odoo registry and a real PostgreSQL
server: separate sessions, real `cr.commit()`/`rollback()`, real row locks, and
session advisory-lock lifetime. `TransactionCase` cannot provide any of that —
`cr.commit()` is neutered and `registry.cursor()` returns the test cursor.

Docker is the usual way to get that. It is not the only way, and a container
with no Docker daemon can still run every gate.

## What is actually required

| Need | Supplied by |
|---|---|
| PostgreSQL 16 server | `initdb` + `pg_ctl` from `postgresql-16` — no daemon, no container |
| Odoo 19 | source tarball from `nightly.odoo.com` (Odoo's official distribution) |
| Python 3.12 | matches Odoo 19 and this repo's target |
| Second DB session | plain `psycopg2.connect(...)` — the assertion must not read from the transaction under test |

`github.com/odoo/odoo` may be blocked by an egress policy; `nightly.odoo.com`
serves the same source and is the supported channel.

## Setup

```bash
# 1. PostgreSQL 16 cluster (initdb refuses to run as root)
mkdir -p /var/lib/postgresql/c1c6 && chown -R postgres:postgres /var/lib/postgresql/c1c6
su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /var/lib/postgresql/c1c6 -A trust -U odoo"
su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/postgresql/c1c6 \
  -o '-p 5433 -k /tmp' -l /var/lib/postgresql/c1c6/pg.log start"
pg_isready -h /tmp -p 5433

# 2. Odoo 19 source
mkdir -p /opt/odoo-src && cd /opt/odoo-src
curl -sS -O https://nightly.odoo.com/19.0/nightly/src/odoo_19.0.latest.tar.gz
tar xzf odoo_19.0.latest.tar.gz

# 3. Runtime. psycopg2 and python-ldap need C headers that may be absent:
#    psycopg2-binary is a drop-in, and python-ldap is only used by auth_ldap.
python3.12 -m venv /opt/odoo-venv
/opt/odoo-venv/bin/pip install -U pip wheel setuptools
grep -vE '^(psycopg2|python-ldap)' odoo-19.0*/requirements.txt > /tmp/req.txt
/opt/odoo-venv/bin/pip install -r /tmp/req.txt psycopg2-binary
/opt/odoo-venv/bin/pip install --no-deps -e odoo-19.0*/

# 4. Database + modules
createdb -h /tmp -p 5433 -U odoo c1c6_test
ADDONS=/opt/odoo-src/odoo-19.0*/odoo/addons
/opt/odoo-venv/bin/odoo -d c1c6_test --db_host=/tmp --db_port=5433 --db_user=odoo \
  --addons-path="$ADDONS,$PWD" -i plasticos_crm_sync --stop-after-init --log-level=warn
```

`plasticos_gate` and `plasticos_enrichment` additionally require the private
`constellation_node_sdk`; install it before running the enrichment-side gates.
`plasticos_crm_sync` needs no SDK, and it is where C1, C2, C4 and C5 live.

## Writing a gate

Two rules decide whether a gate proves anything.

1. **Assert from a session Odoo does not own.** A plain `psycopg2.connect(...)`
   with `autocommit=True`. Reading through the Odoo env under test can return
   uncommitted values from its own transaction and prove nothing.
2. **Initialize the addons path before importing addon modules**, or
   `odoo.addons.plasticos_*` is not importable:

```python
import odoo, odoo.modules.module
from odoo.tools import config
config["db_host"] = "/tmp"; config["db_port"] = 5433; config["db_user"] = "odoo"
config["addons_path"] = f"{ADDONS},{REPO}"
odoo.modules.module.initialize_sys_path()          # required before the next import
from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator
```

Drive a gate with `odoo.modules.registry.Registry(DB).cursor()` and inject a
scripted adapter via `orchestrator._build_adapter = lambda c: StubAdapter()`.

## REPEATABLE READ — the reason these gates exist

Odoo runs cursors at **REPEATABLE READ**, not READ COMMITTED. A transaction's
snapshot is fixed by its first statement, so **a row committed by another
cursor after that point is invisible for the rest of the transaction** —
`.exists()` returns False and a write to it becomes an `UPDATE ... WHERE id=N`
matching zero rows, with no error.

`run_connection` hits this directly: the advisory-lock `SELECT` opens the
transaction, then the sync-run row is created and committed on a second cursor.
Everything the first transaction writes to that row is silently discarded;
transactions after the first page commit take a fresh snapshot and work
normally. That asymmetry is why a fully successful run looked correct while a
failed one reported `contacts_upserted=0`.

The fix is to end the ambient transaction right after creating the durable row.
`pg_try_advisory_lock` is session-scoped, so the lock survives that commit — the
same property C5 asserts for the page commits.

No unit test can see this. Under `TransactionCase` there is one cursor and one
snapshot, and mocked cursors model whatever the author believed. It is only
visible against a real server, which is the whole argument for C1–C6.
