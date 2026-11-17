"""Odoo-shell driver for ``make import-erp``.

Executed inside ``odoo shell`` against the target database (Makefile pipes this
file into the shell). Configuration arrives via environment variables so the
single file serves both the docker and the no-Docker harness paths:

* ``ERP_DRY`` — ``1`` for a resolve-and-map preview (nothing persisted)
* ``ERP_LIMIT`` — newest N worksheets, or ``25%`` for the newest quarter (diagnostics / test databases)
* ``ERP_PAYLOAD_ROOT`` — non-default payload directory (statement or grid form)
* ``ERP_SQL_SERVER`` / ``ERP_SQL_DATABASE`` (+ ``ERP_SQL_USER`` /
  ``ERP_SQL_PASSWORD`` / ``ERP_SQL_PORT`` / ``ERP_SQL_DRIVER``) — read the
  requested partner and/or transaction-reconstruction tables directly from
  the restored ERP database through ``PROJECTION_SCRIPTS`` (ADR-021). Takes
  precedence over ``ERP_PAYLOAD_ROOT``.
* ``ERP_REPORT_PATH`` — write the machine-readable summary JSON here
* ``ERP_TARGET_DB`` — the disposable database this run may write; the
  database check refuses any other database and any production database
* ``ERP_PARTNERS_ONLY`` — ``1`` imports only CounterParty, Address, Contact,
  ContactRoleAssignment, and SalesReps (Concern 1). The six deal tables are
  not opened. Without this flag, a full run writes sale orders, purchase
  orders, and invoices from the direct SQL source.
* ``ERP_LAYER`` — ``counterparties``, ``addresses``, ``contacts``, ``roles``,
  or ``salesreps``. Only that table is read, and only after the previous
  layer's validator passes.
* ``ERP_REQUIRE_EMPTY`` — ``0`` allows a database that already has business
  partners. Any other value (including unset) refuses a full import or the
  ``counterparties`` layer when any ``res.partner`` row is not the company, a
  login user, or a localization-owned (``l10n_*``) reference partner.
* ``ERP_PRODUCTION_PERMIT`` — path of an operator-written one-use permit
  (``erp/production_permit.py``). Production (``ODOO_STAGE=production`` or a
  production-named database) is refused without one. A permit admits one
  applied run of its phase: ``erp_partners`` (``ERP_PARTNERS_ONLY=1`` on an
  empty target) or ``erp_commercial`` (full run, ``ERP_REQUIRE_EMPTY=0``,
  after a committed ``erp_partners`` phase on the same source). Both need the
  direct SQL source and refuse ``ERP_LIMIT``, ``ERP_PAYLOAD_ROOT`` and
  ``ERP_LAYER``. It is consumed before the first write.
* ``ERP_PROBE`` — ``erp_partners`` or ``erp_commercial``: print the target
  identity and the source fingerprint a permit for that phase must bind, then
  roll back. Writes nothing.

Order of operations for an applied run: database check → (layer mode) the
previous layer's check → import each stage → that stage's validator → commit.
A validator that fails raises before the commit, the transaction is rolled
back, and nothing of the run is persisted. A full dry run still checks that
sale, purchase, and account are installed. It does not apply the write-target
database check. Partner-only and single-layer dry runs do not persist. Exit
code is otherwise nonzero when a validator fails, when a mandatory run-level
check (the payables identity reconciliation) fails in any mode, or when the
summary reports ``failed``, so the Makefile target fails closed
(``erp.summary.run_exit_status``). Exit 0 is script completion, not data
acceptance: every applied run prints ``DATA VERDICT`` (``erp.summary.data_verdict``).
A dry run always ends with a rollback.
"""

import json
import os
import sys
from pathlib import Path

from odoo.addons.plasticos_partner_import.erp import reader
from odoo.addons.plasticos_partner_import.erp import summary as import_summary
from odoo.addons.plasticos_partner_import.erp.limits import parse_limit
from odoo.addons.plasticos_partner_import.scripts.run_erp_import import run
from odoo.addons.plasticos_partner_import.scripts.validate_partner_layer import (
    DATABASE_CHECK,
    LAYER_BEFORE,
    LayerRejected,
    check_full_run_extension,
    validate,
)


def _setting(name: str) -> str:
    return os.environ.get(f"ERP_{name}") or ""


def _flag(name: str) -> bool:
    return _setting(name).strip().lower() in {"1", "true", "yes", "y"}


def _odoo_env():
    """The Odoo environment injected by ``odoo shell`` stdin execution."""
    env = globals().get("env")
    if env is None:
        raise SystemExit("no Odoo environment (run inside `odoo shell`)")
    return env


def _require_empty_partner_set(env) -> None:
    """Refuse the import when the database already has business partners.

    A pristine initialized Odoo database may contain the company partner,
    login-user partners, and localization-owned res.partner reference records.
    Those are infrastructure/reference data, not imported business partners.
    Any other pre-existing partner blocks a first historical import.
    """
    if _setting("REQUIRE_EMPTY").strip().lower() in {"0", "false", "no", "n"}:
        return
    # Direct SQL justification: a whole-table census before a bulk load; the ORM would browse every partner.
    env.cr.execute(
        """
        SELECT count(*)
          FROM res_partner AS partner
         WHERE partner.id NOT IN (
                SELECT partner_id
                  FROM res_users
                 WHERE partner_id IS NOT NULL

                UNION

                SELECT partner_id
                  FROM res_company
                 WHERE partner_id IS NOT NULL
               )
           AND NOT EXISTS (
                SELECT 1
                  FROM ir_model_data AS data
                 WHERE data.model = 'res.partner'
                   AND data.res_id = partner.id
                   AND LEFT(data.module, 5) = 'l10n_'
               )
        """
    )
    extra = int(env.cr.fetchone()[0])
    # Direct SQL justification: same bulk census, total rows including archived partners.
    env.cr.execute("SELECT count(*) FROM res_partner")
    total = int(env.cr.fetchone()[0])
    print(f"res.partner before import: {total} (pre-existing business partners: {extra})")
    if extra:
        raise SystemExit("refusing import: database already contains business partner rows")


def _database_name(env) -> str:
    # Direct SQL justification: the connected database's own name is the identity being verified.
    env.cr.execute("SELECT current_database()")
    return str(env.cr.fetchone()[0] or "")


def _audit(event: str, **fields) -> dict:
    """One redacted machine-readable audit line. Carries identities and digests, never credentials or rows."""
    record = {"event": f"erp_production.{event}", **fields}
    print("ERP_PRODUCTION_AUDIT " + json.dumps(record, sort_keys=True, default=str))
    return record


def _write_json(path: str, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _sidecar(report_path: str, suffix: str) -> str:
    root, _ext = os.path.splitext(report_path)
    return f"{root}-{suffix}.json"


class _ProductionGate:
    """One verified permit, bound to the observed target, consumed once before the first write."""

    def __init__(self, env, permit_module, permit, observed):
        self.env = env
        self.permits = permit_module
        self.permit = permit
        self.observed = observed
        self.fingerprint: dict | None = None
        self.events: list[dict] = []

    @property
    def phase(self) -> str:
        return self.permit.phase

    @classmethod
    def open(cls, env, path: str, *, dry_run: bool, layer, database):
        from odoo.addons.plasticos_partner_import.erp import production_permit as permits  # noqa: PLC0415

        observed = _observe(env, permits)
        try:
            permit = permits.load_permit(path)
        except permits.PermitRefused as refused:
            _audit("refused", reasons=list(refused.reasons), observed=observed.as_dict())
            raise
        reasons: list[str] = []
        if dry_run:
            reasons.append("a permit admits an applied run; unset ERP_DRY")
        if layer:
            reasons.append("a permitted run imports every partner layer; unset ERP_LAYER")
        if _setting("LIMIT").strip():
            reasons.append("ERP_LIMIT is a diagnostic cap and is refused on a permitted run")
        if _setting("PAYLOAD_ROOT").strip():
            reasons.append("a permitted run reads the direct SQL source; unset ERP_PAYLOAD_ROOT")
        if database is None:
            reasons.append("a permitted run needs the direct SQL source (ERP_SQL_SERVER / ERP_SQL_DATABASE)")
        require_empty_off = _setting("REQUIRE_EMPTY").strip().lower() in {"0", "false", "no", "n"}
        partners_only = _flag("PARTNERS_ONLY")
        if permit.phase == permits.PHASE_PARTNERS:
            if not partners_only:
                reasons.append("an erp_partners permit needs ERP_PARTNERS_ONLY=1")
            if require_empty_off:
                reasons.append("an erp_partners permit cannot disable the empty-target guard (ERP_REQUIRE_EMPTY=0)")
        else:
            if partners_only:
                reasons.append("an erp_commercial permit runs the full import; unset ERP_PARTNERS_ONLY")
            if not require_empty_off:
                reasons.append("an erp_commercial permit resumes on imported partners; set ERP_REQUIRE_EMPTY=0")
            if not _param(env, permits.PHASE1_WITNESS_PARAM):
                reasons.append("no committed erp_partners phase on this database")
        if _param(env, permits.consumed_key(permit.permit_id)) is not None:
            reasons.append(f"permit {permit.permit_id} was already consumed")
        try:
            permits.verify_permit(permit, observed, phase=permit.phase)
        except permits.PermitRefused as refused:
            reasons.extend(refused.reasons)
        if reasons:
            _audit("refused", reasons=reasons, permit=permit.bindings(), observed=observed.as_dict())
            raise permits.PermitRefused(reasons)
        gate = cls(env, permits, permit, observed)
        gate.events.append(_audit("admitted", permit=permit.bindings(), observed=observed.as_dict()))
        from odoo.addons.plasticos_partner_import.scripts.validate_partner_layer import (
            admit_production,  # noqa: PLC0415
        )

        admit_production(observed.database_name)
        return gate

    def bind(self, payload) -> None:
        """``on_payload``: bind the rows actually loaded, then consume the permit and commit before any write."""
        permits = self.permits
        fingerprint = permits.source_fingerprint(payload.tables, permits.phase_tables(self.phase))
        reasons: list[str] = []
        if fingerprint["sha256"] != self.permit.source_fingerprint:
            reasons.append("loaded ERP source does not match the permit source_fingerprint")
        if not reasons and self.phase == permits.PHASE_COMMERCIAL:
            try:
                permits.check_phase1_witness(
                    _param(self.env, permits.PHASE1_WITNESS_PARAM), self.permit, self.observed, fingerprint
                )
            except permits.PermitRefused as refused:
                reasons.extend(refused.reasons)
        if reasons:
            self.events.append(_audit("refused", reasons=reasons, source_fingerprint=fingerprint["sha256"]))
            raise permits.PermitRefused(reasons)
        consumed = json.dumps(
            {
                "permit": self.permit.bindings(),
                "observed": self.observed.as_dict(),
                "source_fingerprint": fingerprint["sha256"],
                "consumed_at": _utc_now(),
            },
            sort_keys=True,
        )
        # One-use consumption is a single atomic insert on the unique key, so two concurrent runs cannot
        # both consume one permit; the ORM set_param reads then writes.
        # Direct SQL justification: atomic INSERT ... ON CONFLICT DO NOTHING RETURNING on ir_config_parameter.key.
        self.env.cr.execute(
            """
            INSERT INTO ir_config_parameter (key, value, create_uid, write_uid, create_date, write_date)
            VALUES (%s, %s, %s, %s, now() AT TIME ZONE 'UTC', now() AT TIME ZONE 'UTC')
            ON CONFLICT (key) DO NOTHING
            RETURNING id
            """,
            (permits.consumed_key(self.permit.permit_id), consumed, self.env.uid, self.env.uid),
        )
        if self.env.cr.fetchone() is None:
            self.env.cr.rollback()
            self.events.append(_audit("refused", reasons=[f"permit {self.permit.permit_id} was already consumed"]))
            raise permits.PermitRefused([f"permit {self.permit.permit_id} was already consumed"])
        self.env.cr.commit()
        self.fingerprint = fingerprint
        self.events.append(
            _audit(
                "consumed", permit_id=self.permit.permit_id, phase=self.phase, source_fingerprint=fingerprint["sha256"]
            )
        )

    def finish(self, verdict: dict) -> dict:
        """Write the phase witness in the same transaction as the phase's last data, then commit."""
        permits = self.permits
        witness = permits.witness_record(self.permit, self.observed, self.fingerprint, verdict)
        param = permits.PHASE1_WITNESS_PARAM if self.phase == permits.PHASE_PARTNERS else permits.PHASE2_WITNESS_PARAM
        self.env["ir.config_parameter"].set_param(param, json.dumps(witness, sort_keys=True))
        self.env.cr.commit()
        self.events.append(_audit("committed", phase=self.phase, witness=witness))
        return witness

    def receipt(self, verdict: dict | None) -> dict:
        return {
            "permit_bindings": self.permit.bindings(),
            "observed_target": self.observed.as_dict(),
            "source_fingerprint": self.fingerprint,
            "data_verdict": verdict,
            "audit_events": self.events,
        }


def _utc_now() -> str:
    from datetime import UTC, datetime  # noqa: PLC0415

    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _param(env, key: str) -> str | None:
    # Direct SQL justification: read the committed row, bypassing the ir.config_parameter ormcache.
    env.cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (key,))
    row = env.cr.fetchone()
    return row[0] if row else None


def _addon_repository() -> Path:
    import odoo.addons.plasticos_partner_import as addon  # noqa: PLC0415

    return Path(addon.__file__).resolve().parent.parent


def _observe(env, permits):
    release_sha, clean = permits.release_identity(_addon_repository())
    return permits.Observed(
        database_name=_database_name(env),
        database_uuid=(_param(env, "database.uuid") or "").strip().lower(),
        odoo_stage=(os.environ.get("ODOO_STAGE") or "").strip().lower(),
        release_sha=release_sha,
        release_clean=clean,
    )


def _probe(env, phase: str) -> int:
    """Print the identity and fingerprint a permit for ``phase`` must bind. Reads only; always rolls back."""
    from odoo.addons.plasticos_partner_import.erp import production_permit as permits  # noqa: PLC0415

    if phase not in permits.PHASES:
        raise SystemExit(f"ERP_PROBE must be one of {', '.join(permits.PHASES)}")
    try:
        observed = _observe(env, permits)
        database = reader.database_source_from_env(os.environ)
        payload = reader.load_payload(
            _setting("PAYLOAD_ROOT") or None, only=permits.phase_tables(phase), database=database
        )
        fingerprint = permits.source_fingerprint(payload.tables, permits.phase_tables(phase))
        probe = {
            "phase": phase,
            "observed": observed.as_dict(),
            "source": {
                "source_kind": payload.kind.value,
                "source_origin": payload.origin,
                "source_fingerprint": fingerprint,
            },
            "phase1_witness": json.loads(_param(env, permits.PHASE1_WITNESS_PARAM) or "null"),
            "phase2_witness": json.loads(_param(env, permits.PHASE2_WITNESS_PARAM) or "null"),
            "permit_template": {
                "permit_id": "<operator-chosen, 8-80 chars>",
                "phase": phase,
                "database_name": observed.database_name,
                "database_uuid": observed.database_uuid,
                "odoo_stage": "production",
                "release_sha": observed.release_sha,
                "source_fingerprint": fingerprint["sha256"],
                "expires_at": "<UTC, at most 24h ahead>",
                "approved_by": "<operator>",
            },
        }
    finally:
        env.cr.rollback()
    print("ERP_PRODUCTION_PROBE " + json.dumps(probe, sort_keys=True))
    if _setting("REPORT_PATH"):
        _write_json(_setting("REPORT_PATH"), probe)
    return 0


def _record_outcome(env, result: dict, gate, *, dry_run: bool, partners_only: bool, report_path: str | None) -> None:
    """Roll a dry run back; for an applied run print the data verdict and commit a permitted phase's witness."""
    if dry_run:
        env.cr.rollback()
        return
    verdict = import_summary.data_verdict(result, partners_only=partners_only)
    print("DATA VERDICT " + json.dumps(verdict, sort_keys=True))
    if gate is not None:
        gate.finish(verdict)
    if report_path:
        _write_json(_sidecar(report_path, "verdict"), verdict)
        if gate is not None:
            _write_json(_sidecar(report_path, "permit"), gate.receipt(verdict))


def main() -> int:
    try:
        limit = parse_limit(_setting("LIMIT"))
    except ValueError as invalid:
        raise SystemExit(f"refusing import: {invalid}") from None
    env = _odoo_env()
    probe = _setting("PROBE").strip().lower()
    if probe:
        return _probe(env, probe)
    dry_run = _flag("DRY")
    layer = _setting("LAYER").strip().lower() or None
    if layer and layer not in LAYER_BEFORE:
        raise SystemExit(f"ERP_LAYER must be one of {', '.join(LAYER_BEFORE)}")
    permit_path = _setting("PRODUCTION_PERMIT").strip()
    if dry_run and not _flag("PARTNERS_ONLY") and not layer:
        failures: list[str] = []
        check_full_run_extension(env, failures)
        if failures:
            for message in failures:
                print(message)
            return 1
    database = reader.database_source_from_env(os.environ)
    if database is not None:
        print(f"ERP source: direct database read ({database.label})")

    gate = None
    if permit_path:
        try:
            gate = _ProductionGate.open(env, permit_path, dry_run=dry_run, layer=layer, database=database)
        except RuntimeError as refused:
            env.cr.rollback()
            print(f"refusing production import: {refused}")
            return 1

    if not dry_run:
        if validate(env, DATABASE_CHECK):
            print("refusing import: the database check did not pass")
            return 1
        if layer and LAYER_BEFORE[layer] != DATABASE_CHECK and validate(env, LAYER_BEFORE[layer]):
            print(f"refusing layer {layer}: the {LAYER_BEFORE[layer]} validator did not pass")
            return 1
        if layer in (None, "counterparties"):
            _require_empty_partner_set(env)

    def after_stage(name: str, payload) -> None:
        """Validate the stage just written against the rows it read. Raise before any commit."""
        if validate(env, name, payload=payload):
            raise LayerRejected(name)

    partners_only = _flag("PARTNERS_ONLY") or bool(layer)
    report_path = _setting("REPORT_PATH") or None
    try:
        result = run(
            env,
            payload_root=_setting("PAYLOAD_ROOT") or None,
            limit=limit,
            # A permitted partner phase commits its rows together with its witness, below.
            commit=gate is None or not partners_only,
            dry_run=dry_run,
            report_path=report_path,
            partners_only=partners_only,
            layer=layer,
            database=database,
            after_stage=None if dry_run else after_stage,
            on_payload=gate.bind if gate is not None else None,
        )
    except LayerRejected as rejected:
        env.cr.rollback()
        print(f"refusing to commit: the {rejected} validator did not pass; the stage was rolled back")
        return 1
    except RuntimeError as refused:
        if gate is None or not isinstance(refused, gate.permits.PermitRefused):
            raise
        env.cr.rollback()
        print(f"refusing production import: {refused}")
        if report_path:
            _write_json(_sidecar(report_path, "permit"), gate.receipt(None))
        return 1
    _record_outcome(env, result, gate, dry_run=dry_run, partners_only=partners_only, report_path=report_path)

    for failure in result.get("failures") or []:
        print(f"IMPORT FAILED: {failure.get('check')}: {failure.get('detail')}")
    status = import_summary.run_exit_status(result, dry_run=dry_run, layer=layer)
    if status:
        if not result.get("failures"):
            print("IMPORT FAILED: material errors — see summary errors list")
    elif layer:
        print(f"layer {layer} validated and committed")
    # Always printed, always last: its final line is the review count.
    for line in import_summary.review_lines(result):
        print(line)
    return status


if __name__ == "__main__":
    sys.exit(main())
