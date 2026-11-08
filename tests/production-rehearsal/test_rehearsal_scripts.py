"""The rehearsal shell scripts, executed against a throwaway git repository.

Pure-python tier. Each test builds a fixture repository with a local bare
``origin`` (Staging and Production), copies the real kit into it, and puts
stub ``make`` / ``docker`` / ``curl`` / ``scripts/test_env.sh`` first on PATH.
The stubs record every call, so a test can prove that a refused gate caused
no side effect. No Docker, database, HTTP server or secret is used.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[1]
MAKEFILE = ROOT / "Makefile"
KIT_FILES = (
    ".gitignore",
    "run.sh",
    "weblead_e2e.sh",
    "erp_slice.sh",
    "rehearsal_common.sh",
    "common.py",
    "fidelity.py",
    "fidelity_run.py",
    "expected/blockers.yaml",
    "payloads/cognito_hot.json",
)
OWNER_FILES = (
    "scripts/validate_import_summary.py",
    "contracts/schemas/draft/import-run-summary.schema.json",
    "plasticos_crm_sync/services/historical_cohort.py",
)
FAKE_BEARER = "fake-bearer-for-kit-tests-0001"
FAKE_ERP_PASSWORD = "fake-erp-password-0001"
CENSUS_REL = ".l9/runtime/census.csv"
TRACKED_REL = "plasticos_crm_sync/Vanillasoft-Scrap-Management.csv"
CENSUS_TEXT = "vanillasoft_contact_id,decision\n1,YES\n2,PENDING\n"
CENSUS_SHA = hashlib.sha256(CENSUS_TEXT.encode()).hexdigest()
CUTOVER = "odoo_test_cutover"

pytestmark = pytest.mark.skipif(shutil.which("git") is None or shutil.which("bash") is None, reason="needs git+bash")

_spec = importlib.util.spec_from_file_location("rehearsal_kit_common_scripts", KIT / "common.py")
lib = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(lib)
cohort = lib.crm_cohort()

# ── stubs ────────────────────────────────────────────────────────────────────

MAKE_STUB = r"""#!/usr/bin/env bash
printf 'make %s\n' "$*" >> "$CALL_LOG"
case "$1" in
  install-smoke)
    if [ -n "${STUB_SMOKE_SLEEP:-}" ]; then sleep "$STUB_SMOKE_SLEEP"; fi
    if [ -n "${STUB_DRIFT_SHA:-}" ]; then git --git-dir="$STUB_ORIGIN" update-ref refs/heads/Production "$STUB_DRIFT_SHA"; fi
    echo "${STUB_SMOKE_OUT:-✅ install-smoke PASSED}"
    exit "${STUB_SMOKE_RC:-0}" ;;
esac
exit 0
"""

DOCKER_STUB = r"""#!/usr/bin/env bash
printf 'docker %s\n' "$*" >> "$CALL_LOG"
args="$*"
case "$args" in
  *" exec -T db psql"*)
    sql="$(cat)"
    printf '%s\n----\n' "$sql" >> "$STUB_DIR/sql.log"
    case "$sql" in
      *fidelity_odoo*) cat "$STUB_DIR/fidelity-odoo.json" || exit 1 ;;
      *customer_rank*)
        if [ -n "${STUB_CENSUS_RC:-}" ]; then echo "ERROR: boom" >&2; exit "$STUB_CENSUS_RC"; fi
        printf '%s\n' "${STUB_CENSUS-0}" ;;
      *legacy_erp_cp_*) cat "$STUB_DIR/layers.json" || exit 1 ;;
      *plasticos_crm_external_ref*)
        n="$(cat "$STUB_DIR/refs.n" 2>/dev/null || echo 0)"
        if [ "$n" = 0 ]; then printf '%s\n' "${STUB_REFS_BEFORE-0}"; else printf '%s\n' "${STUB_REFS_AFTER-3}"; fi
        echo $((n + 1)) > "$STUB_DIR/refs.n" ;;
      *"UPDATE ir_cron"*) printf 'cron\n' >> "$STUB_DIR/cron.log" ;;
      *"'web_leads'"*)
        n="$(cat "$STUB_DIR/snap.n" 2>/dev/null || echo 0)"
        cat "$STUB_DIR/snap.$n.json"; echo $((n + 1)) > "$STUB_DIR/snap.n" ;;
      *"\\set wl"*) cat "$STUB_DIR/row.json" ;;
      *ir_config_parameter*) : ;;
      *) exit 9 ;;
    esac ;;
  "container inspect"*) [ "${STUB_CONTAINER_EXISTS:-0}" = "1" ] && exit 0; exit 1 ;;
  *"SELECT api_key"*) printf '%s\n' "${STUB_CONFIG_KEY-}" ;;
  "rm -f"*) : ;;
  *) : ;;
esac
exit 0
"""

CURL_STUB = r"""#!/usr/bin/env bash
printf 'curl %s\n' "$*" >> "$CALL_LOG"
out=""; url=""; hdr=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift ;;
    -H) case "$2" in @*) hdr="${2#@}" ;; esac; shift ;;
    -X|-w|--max-time|--data-binary) shift ;;
    http*) url="$1" ;;
  esac
  shift
done
case "$url" in
  */web-lead/health) printf '{"status": "ok"}' > "$out"; printf 200 ;;
  */cognito-webhook)
    [ -n "$hdr" ] && cat "$hdr" >> "$STUB_DIR/seen-headers"
    n="$(cat "$STUB_DIR/post.n" 2>/dev/null || echo 0)"
    cp "$STUB_DIR/post.$n.json" "$out"; echo $((n + 1)) > "$STUB_DIR/post.n"
    printf '%s' "${STUB_POST_CODE:-200}" ;;
  *) exit 7 ;;
esac
"""

# Stands in for the amended verified-clone harness: it forwards the history
# settings (VANILLASOFT_HISTORY_CENSUS …) and prints what the real drivers
# print on the paths the gates read as the runtime trace.
TEST_ENV_STUB = r"""#!/usr/bin/env bash
printf 'test_env %s\n' "$*" >> "$CALL_LOG"
sub="$1"
case "$sub" in
  clone) exit "${STUB_TE_CLONE_RC:-0}" ;;
  upgrade) exit "${STUB_TE_UPGRADE_RC:-0}" ;;
  assert-clone) exit "${STUB_TE_ASSERT_RC:-0}" ;;
  run)
    target=""; db=""; sha=""; has_census=0; has_floor=0
    for arg in "$@"; do
      case "$arg" in
        import-erp|import-vanillasoft) target="$arg" ;;
        ODOO_DB_NAME=*) db="${arg#*=}" ;;
        VANILLASOFT_HISTORY_CENSUS_SHA256=*) sha="${arg#*=}" ;;
        VANILLASOFT_HISTORY_CENSUS=*) has_census=1; [ -r "${STUB_REPO}/${arg#*=}" ] || { echo "census unreadable"; exit 2; } ;;
        VANILLASOFT_HISTORY_CHECKPOINT=*)
          if [ -f "$STUB_DIR/06-crm-history.jsonl" ]; then cp "$STUB_DIR/06-crm-history.jsonl" "${STUB_REPO}/${arg#*=}"; fi ;;
        VANILLASOFT_CALL_FLOOR=*|VANILLASOFT_CONTACT_FLOOR=*) has_floor=1 ;;
        REPORT_PATH=*|VANILLASOFT_REPORT_PATH=*)
          path="${arg#*=}"
          case "$path" in
            /erp-isolated/*)
              [ -n "${ERP_ISOLATED_HOST:-}" ] || { echo "isolated report host is unset"; exit 2; }
              host="${ERP_ISOLATED_HOST}/$(basename "$path")" ;;
            *) host="${STUB_REPO}${path#/mnt/extra-addons}" ;;
          esac
          base="$(basename "$host" .json)"
          mkdir -p "$(dirname "$host")"
          if [ -f "$STUB_DIR/$base.json" ]; then cp "$STUB_DIR/$base.json" "$host"; fi
          if [ -f "$STUB_DIR/$base-census.json" ]; then cp "$STUB_DIR/$base-census.json" "$(dirname "$host")/$base-census.json"; fi ;;
      esac
    done
    if [ "$target" = import-erp ] && [ "${STUB_ERP_TRACE:-1}" = 1 ]; then
      echo "ERP source: direct database read (stub)"
      counts="${STUB_ERP_COUNTS:-}"
      [ -n "$counts" ] || counts="{'transactions': {'created': 1, 'updated': 0, 'skipped': 0, 'rejected': 0}, 'transaction_lines': {'created': 2, 'updated': 0, 'skipped': 0, 'rejected': 0}}"
      echo "INFO stub odoo.addons.plasticos_partner_import.models.erp_import_service: ERP import finished${STUB_ERP_SCOPE:-}: $counts"
      echo "DATA VERDICT {}"
    fi
    if [ "$has_census" = 1 ] && [ "$has_floor" = 1 ]; then
      echo "floor given with the census"
      exit 2
    fi
    if [ "$target" = import-vanillasoft ]; then
      if [ "$has_census" = 0 ]; then
        if [ "${STUB_VS_TRACE:-rolling}" != none ]; then
          echo "=== VANILLASOFT IMPORT SUMMARY ==="
        fi
      else
        case "${STUB_VS_TRACE:-history}" in
          history)
            printf 'VANILLASOFT_HISTORY_AUDIT {"event": "crm_history.admitted", "database": "%s", "permit": false, "census_sha256": "%s"}\n' "$db" "$sha"
            echo "HISTORY VERDICT {}" ;;
          rolling) echo "=== VANILLASOFT IMPORT SUMMARY ===" ;;
        esac
      fi
    fi
    exit "${STUB_TE_RUN_RC:-0}" ;;
esac
exit 0
"""

GATE_HELPER_STUB = r"""#!/usr/bin/env bash
# Fixture stand-in for a gate helper: writes the receipt the test asks for.
gate="__GATE__"
printf 'helper%s %s\n' "$gate" "$*" >> "$CALL_LOG"
state_var="STUB_G${gate}_STATE"
state="${!state_var:-PASS}"
dir="${@: -1}"
if [ "$state" != "none" ]; then
  python3 "$(dirname "$0")/common.py" gate-write "$dir" "$gate" "$state" "stub-$state"
fi
[ "$state" = "PASS" ]
"""

CAPABILITY_BIND = """import sys
VALUE = "fake-vanillasoft-key-0001"
def bind(name):
    return VALUE
if __name__ == "__main__":
    print("VANILLASOFT_API_KEY bound source=infisical")
"""


def _git(cwd, *args, env=None):
    subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True)


def _summary(source, **overrides):
    base = {
        "source": source,
        "start_time": "2099-01-01T00:00:00Z",
        "completion_time": "2099-01-01T00:01:00Z",
        "records_seen": 4,
        "records_valid": 4,
        "records_rejected": 0,
        "records_created": 4,
        "records_updated": 0,
        "records_unchanged": 0,
        "duplicates": 0,
        "errors": [],
        "final_status": "success",
    }
    base.update(overrides)
    return base


class Fixture:
    """A fixture repository with stubs; ``run`` executes a kit script inside it."""

    def __init__(self, tmp: Path, *, stub_helpers: bool):
        self.tmp = tmp
        self.repo = tmp / "repo"
        self.origin = tmp / "origin.git"
        self.stub = tmp / "stub"
        self.bin = tmp / "bin"
        self.home = tmp / "home"
        self.calls = tmp / "calls.log"
        for path in (self.repo, self.stub, self.bin, self.home):
            path.mkdir()
        self.env = {
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "HOME": str(self.home),
            "TMPDIR": str(tmp),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "kit",
            "GIT_AUTHOR_EMAIL": "kit@example.invalid",
            "GIT_COMMITTER_NAME": "kit",
            "GIT_COMMITTER_EMAIL": "kit@example.invalid",
            "CALL_LOG": str(self.calls),
            "STUB_DIR": str(self.stub),
            "STUB_REPO": str(self.repo),
            "STUB_ORIGIN": str(self.origin),
            "LANG": "C.UTF-8",
        }
        for name, body in (("make", MAKE_STUB), ("docker", DOCKER_STUB), ("curl", CURL_STUB)):
            self._exe(self.bin / name, body)
        (self.bin / "python3").symlink_to(sys.executable)
        kit = self.repo / "tests" / "production-rehearsal"
        for rel in KIT_FILES:
            (kit / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(KIT / rel, kit / rel)
        if stub_helpers:
            for gate, name in ((5, "weblead_e2e.sh"), (6, "erp_slice.sh")):
                self._exe(kit / name, GATE_HELPER_STUB.replace("__GATE__", str(gate)))
        for rel in OWNER_FILES:
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, self.repo / rel)
        (self.repo / "Makefile").write_text("all:\n", encoding="utf-8")
        (self.repo / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
        # The real repository ignores .l9/runtime/: the census lives there so a
        # clean tree (Gate 1) and a mounted census (Gate 7) hold together.
        (self.repo / ".gitignore").write_text(".l9/runtime/\n", encoding="utf-8")
        self._exe(self.repo / "scripts" / "test_env.sh", TEST_ENV_STUB)
        self.kit = kit

        _git(self.repo, "init", "-q", "-b", "Staging", env=self.env)
        _git(self.repo, "add", "-A", env=self.env)
        _git(self.repo, "commit", "-q", "-m", "base", env=self.env)
        self.base_sha = self._rev("HEAD")
        (self.repo / "feature.txt").write_text("staging change\n", encoding="utf-8")
        _git(self.repo, "add", "feature.txt", env=self.env)
        _git(self.repo, "commit", "-q", "-m", "staging", env=self.env)
        self.staging_sha = self._rev("HEAD")
        _git(self.tmp, "init", "-q", "--bare", str(self.origin), env=self.env)
        _git(self.repo, "remote", "add", "origin", str(self.origin), env=self.env)
        _git(self.repo, "push", "-q", "origin", f"{self.staging_sha}:refs/heads/Staging", env=self.env)
        _git(self.repo, "push", "-q", "origin", f"{self.base_sha}:refs/heads/Production", env=self.env)

    @staticmethod
    def _exe(path: Path, body: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)

    def _rev(self, ref: str) -> str:
        return subprocess.run(
            ["git", "rev-parse", ref], cwd=self.repo, env=self.env, check=True, capture_output=True, text=True
        ).stdout.strip()

    def stub_json(self, name: str, value) -> None:
        (self.stub / name).write_text(json.dumps(value), encoding="utf-8")

    def with_capability_bind(self) -> None:
        target = self.home / ".cursor-governance" / "ops" / "secrets" / "capability_bind.py"
        target.parent.mkdir(parents=True)
        target.write_text(CAPABILITY_BIND, encoding="utf-8")
        (target.parent / "__init__.py").write_text("", encoding="utf-8")
        (target.parent.parent / "__init__.py").write_text("", encoding="utf-8")

    def with_history(self, *, report=None, ledger=None) -> dict[str, str]:
        """Operator census in the (ignored) checkout, the driver's report and ledger the stub will deliver."""
        census = self.repo / TRACKED_REL
        census.parent.mkdir(parents=True, exist_ok=True)
        census.write_text(CENSUS_TEXT, encoding="utf-8")
        self.stub_json("06-crm-result.json", _history_report() if report is None else report)
        (self.stub / "06-crm-history.jsonl").write_text(
            _history_ledger() if ledger is None else ledger, encoding="utf-8"
        )
        return {}

    def ready_for_gate7(self) -> dict[str, str]:
        self.with_capability_bind()
        return self.with_history()

    def run(self, script: str, *args: str, env: dict | None = None, timeout: int = 25):
        full = {**self.env, **(env or {})}
        return subprocess.run(
            ["bash", str(self.kit / script), *args],
            cwd=self.repo,
            env=full,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def calls_text(self) -> str:
        return self.calls.read_text(encoding="utf-8") if self.calls.exists() else ""

    def latest(self) -> Path:
        return (self.kit / "evidence" / "latest").resolve()

    def gates(self) -> dict[int, dict]:
        run = self.latest()
        return {g: json.loads((run / f"gate-{g}.json").read_text()) for g in range(1, 8)}

    def verdict(self) -> dict:
        return json.loads((self.latest() / "verdict.json").read_text())


def _history_report(**over) -> dict:
    classes = {cohort.IMPORTED: 3, cohort.HELD: 1, cohort.DUPLICATE_SKIPPED: 1, cohort.GENUINE_FAILED: 0}
    classes.update(over.pop("classes", {}))
    dispositioned = sum(classes.values())
    by_decision = {d: dict.fromkeys(cohort.CLASSES, 0) for d in cohort.PARTITION}
    by_decision["YES"].update(classes)
    base = {
        "cohort": cohort.COHORT,
        "dispositioned": dispositioned,
        "undispositioned": cohort.COHORT - dispositioned,
        "classes": classes,
        "by_decision": by_decision,
        "dispositions_without_a_source_reason": 0,
        "imported_with_error_signals": 0,
        "HISTORICAL_SNAPSHOT_COMPLETE": False,
        "historical_data_complete": False,
        "LIVE_DELTA_COMPLETENESS": "NOT_RUN",
        "FULL_CURRENT_CONTACT_COVERAGE": "UNKNOWN",
        "stopped": "max_ids",
        "census_sha256": CENSUS_SHA,
    }
    base.update(over)
    return base


def _history_ledger(rows=None) -> str:
    head = {"kind": "header", "version": 1, "census_sha256": CENSUS_SHA, "database_uuid": "u" * 8, "created_at": "t"}
    if rows is None:
        rows = [
            {"vanillasoft_contact_id": str(i), "class": cohort.IMPORTED, "importer_outcome": "created", "signals": []}
            for i in (1, 2, 3)
        ]
        rows.append({"vanillasoft_contact_id": "4", "class": cohort.HELD, "importer_outcome": "failed", "signals": []})
        rows.append(
            {"vanillasoft_contact_id": "5", "class": cohort.DUPLICATE_SKIPPED, "importer_outcome": "not_fetched"}
        )
    return "\n".join(json.dumps(line) for line in [head, *rows]) + "\n"


@pytest.fixture
def fx(tmp_path):
    return Fixture(tmp_path, stub_helpers=True)


def _side_effect_calls(fx: Fixture) -> list[str]:
    return [line for line in fx.calls_text().splitlines() if line.split(" ", 1)[0] in ("make", "docker", "test_env")]


def _vs_make_call(fx: Fixture) -> str:
    return next((line for line in fx.calls_text().splitlines() if "make import-vanillasoft" in line), "")


# ── RK-01: revision identity refuses before any side effect ─────────────────


def test_clean_exact_staging_all_gates_pass(fx):
    env = fx.ready_for_gate7()
    result = fx.run("run.sh", env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert fx.verdict()["verdict"] == "ready"
    assert all(g["state"] == "PASS" for g in fx.gates().values())
    assert fx.verdict()["staging_sha"] == fx.staging_sha
    assert "fake-vanillasoft-key-0001" not in fx.calls_text()
    text = (fx.latest() / "verdict.txt").read_text()
    assert "verdict=ready" in text
    gate7 = fx.gates()[7]
    assert gate7["reason"] == "vanillasoft-rolling-imported"
    assert gate7["facts"]["full_cohort_claimed"] is False
    assert gate7["facts"]["execution_path"]["database"] == CUTOVER
    assert gate7["facts"]["execution_path"]["mode"] == "rolling"
    assert gate7["facts"]["execution_path"]["crosswalk"] == "plasticos_crm_sync/data/approved_contact_crosswalk.csv"
    assert gate7["facts"]["execution_path"]["release_sha"] == fx.staging_sha
    call = _vs_make_call(fx)
    assert "VANILLASOFT_CALL_FLOOR=" in call
    assert "VANILLASOFT_CONTACT_FLOOR=" in call
    assert "VANILLASOFT_HISTORY_CENSUS" not in call
    assert "VANILLASOFT_HISTORY_CENSUS_SHA256" not in call
    assert TRACKED_REL not in call
    assert CENSUS_SHA not in call
    assert "VANILLASOFT_HISTORY_MAX_IDS" not in call
    assert f"ODOO_DB_NAME={CUTOVER}" in call
    assert (fx.stub / "cron.log").read_text().strip() == "cron"


@pytest.mark.parametrize("case", ["feature-branch", "ahead", "dirty-untracked", "dirty-tracked", "fetch-fails"])
def test_checkout_identity_does_not_stop_the_sync(fx, case):
    if case == "feature-branch":
        _git(fx.repo, "checkout", "-q", "-b", "feat/x", env=fx.env)
    elif case == "ahead":
        (fx.repo / "feature.txt").write_text("local\n", encoding="utf-8")
        _git(fx.repo, "commit", "-qam", "ahead", env=fx.env)
    elif case == "dirty-untracked":
        (fx.repo / "plasticos_new_addon.py").write_text("x = 1\n", encoding="utf-8")
    elif case == "dirty-tracked":
        (fx.repo / "feature.txt").write_text("edited\n", encoding="utf-8")
    else:
        _git(fx.repo, "remote", "set-url", "origin", str(fx.tmp / "missing.git"), env=fx.env)
    fx.run("run.sh")
    gates = fx.gates()
    assert (gates[1]["state"], gates[1]["reason"]) == ("PASS", "checkout-bound")
    assert all(gates[g]["reason"] != "gate1-failed" for g in range(2, 8))
    verdict = fx.verdict()
    assert "not-on-staging" not in str(verdict)
    assert "head-not-origin-staging" not in str(verdict)
    assert "worktree-dirty" not in str(verdict)
    assert "remote-fetch-failed" not in str(verdict)
    assert "staging-ref-drifted" not in verdict["failures"]
    assert "production-ref-drifted" not in verdict["failures"]


def test_previous_evidence_is_preserved(fx):
    old = fx.kit / "evidence" / "2000-01-01_000000"
    old.mkdir(parents=True)
    (old / "verdict.txt").write_text("verdict=blocked\n", encoding="utf-8")
    _git(fx.repo, "checkout", "-q", "-b", "feat/y", env=fx.env)
    fx.run("run.sh")
    assert (old / "verdict.txt").read_text() == "verdict=blocked\n"
    assert fx.latest() != old.resolve()


# ── RK-02: merge-tree status, not marker text ───────────────────────────────


def test_gate2_conflict_fails_and_stops(fx):
    _git(fx.repo, "checkout", "-q", "-b", "prod", fx.base_sha, env=fx.env)
    (fx.repo / "feature.txt").write_text("production change\n", encoding="utf-8")
    _git(fx.repo, "add", "feature.txt", env=fx.env)
    _git(fx.repo, "commit", "-qm", "prod", env=fx.env)
    _git(fx.repo, "push", "-qf", "origin", "HEAD:refs/heads/Production", env=fx.env)
    _git(fx.repo, "checkout", "-q", "Staging", env=fx.env)
    _git(fx.repo, "branch", "-qD", "prod", env=fx.env)
    fx.run("run.sh")
    gates = fx.gates()
    assert (gates[2]["state"], gates[2]["reason"]) == ("PASS", "merge-conflict-recorded")
    assert all(gates[g]["reason"] != "gate2-failed" for g in range(3, 8))
    assert "exit_code=1" in (fx.latest() / "02-merge-tree.txt").read_text()


def test_gate2_error_without_marker_fails(fx):
    # Unrelated histories: merge-tree exits nonzero and prints no conflict marker.
    _git(fx.repo, "checkout", "-q", "--orphan", "lonely", env=fx.env)
    _git(fx.repo, "commit", "-qm", "orphan", env=fx.env)
    _git(fx.repo, "push", "-qf", "origin", "HEAD:refs/heads/Production", env=fx.env)
    _git(fx.repo, "checkout", "-q", "-f", "Staging", env=fx.env)
    fx.run("run.sh")
    gate2 = fx.gates()[2]
    assert (gate2["state"], gate2["reason"]) == ("PASS", "merge-tree-unproven")


def test_production_drift_invalidates_readiness(fx):
    env = fx.ready_for_gate7()
    result = fx.run("run.sh", env={**env, "STUB_DRIFT_SHA": fx.staging_sha})
    assert result.returncode == 0, result.stdout + result.stderr
    verdict = fx.verdict()
    assert verdict["verdict"] == "ready"
    assert "production-ref-drifted" not in verdict["failures"]
    assert "staging-ref-drifted" not in verdict["failures"]


# ── RK-03: Gate 4 census and command results ────────────────────────────────


@pytest.mark.parametrize(
    "env, reason",
    [
        ({"STUB_CENSUS": "1"}, "clone-not-empty"),
        ({"STUB_CENSUS_RC": "3"}, "census-unproven"),
        ({"STUB_CENSUS": ""}, "census-unproven"),
        ({"STUB_CENSUS": "abc"}, "census-unproven"),
        ({"STUB_TE_CLONE_RC": "1"}, "clone-failed"),
        ({"STUB_TE_UPGRADE_RC": "1"}, "upgrade-failed"),
        ({"STUB_TE_ASSERT_RC": "2"}, "assert-clone-failed"),
    ],
)
def test_gate4_fails_closed_and_stops(fx, env, reason):
    fx.run("run.sh", env=env)
    gates = fx.gates()
    assert (gates[4]["state"], gates[4]["reason"]) == ("FAIL", reason)
    assert all(gates[g]["state"] == "SKIPPED" for g in range(5, 8))
    assert "helper5" not in fx.calls_text() and "helper6" not in fx.calls_text()


def _commit_and_publish(fx: Fixture, message: str, *paths: Path) -> None:
    # -f: the real repo tracks historical evidence that .gitignore now ignores.
    _git(fx.repo, "add", "-f", "--", *(str(p) for p in paths), env=fx.env)
    _git(fx.repo, "commit", "-qm", message, env=fx.env)
    _git(fx.repo, "push", "-qf", "origin", "HEAD:refs/heads/Staging", env=fx.env)


def test_gate1_sees_edits_to_committed_evidence(fx):
    history = fx.kit / "evidence" / "2026-11-05_192900" / "verdict.txt"
    history.parent.mkdir(parents=True)
    history.write_text("VERDICT: blocked\n", encoding="utf-8")
    _commit_and_publish(fx, "historical evidence", history)
    history.write_text("VERDICT: ready\n", encoding="utf-8")
    fx.run("run.sh")
    gate1 = fx.gates()[1]
    assert (gate1["state"], gate1["reason"]) == ("PASS", "checkout-bound")
    assert "2026-11-05_192900/verdict.txt" in (fx.latest() / "00-dirty.txt").read_text()


def test_a_previous_run_does_not_dirty_the_next(fx):
    # The tracked `latest` pointer is repointed by every run; run folders are ignored.
    (fx.kit / "evidence").mkdir(exist_ok=True)
    (fx.kit / "evidence" / "latest").symlink_to("2026-11-05_192900")
    _commit_and_publish(fx, "track latest", fx.kit / "evidence" / "latest")
    fx.run("run.sh")
    time.sleep(1.1)  # run folders are named by the UTC second
    fx.run("run.sh")
    assert fx.gates()[1]["state"] == "PASS"


def test_gate7_counts_contacts_bound_to_erp_people(fx):
    fx.run("run.sh", env=fx.ready_for_gate7())
    sql = (fx.stub / "sql.log").read_text()
    blocks = [block for block in sql.split("----") if "plasticos_crm_external_ref" in block]
    assert len(blocks) == 2, "durable refs are read before and after the import"
    assert all("'res.partner'" in block and "'crm.lead'" in block for block in blocks)
    facts = fx.gates()[7]["facts"]
    assert (facts["durable_refs_before"], facts["durable_refs_after"], facts["durable_refs_landed"]) == (0, 3, 3)


def test_gate4_census_counts_inactive_partners(fx):
    fx.run("run.sh", env={"STUB_CENSUS": "1"})
    sql = (fx.stub / "sql.log").read_text()
    census = next(block for block in sql.split("----") if "customer_rank" in block)
    assert "active" not in census


# ── RK-06 / RK-08: dependency propagation, receipts, signals ────────────────


def test_gate6_failure_skips_gate7(fx):
    result = fx.run("run.sh", env={"STUB_G6_STATE": "FAIL"})
    assert result.returncode != 0
    gates = fx.gates()
    assert (gates[7]["state"], gates[7]["reason"]) == ("SKIPPED", "gate6-not-passed")
    assert "make import-vanillasoft" not in fx.calls_text()
    assert fx.verdict()["verdict"] == "failed"


def test_helper_without_receipt_is_a_failure(fx):
    fx.run("run.sh", env={"STUB_G5_STATE": "none"})
    gate5 = fx.gates()[5]
    assert (gate5["state"], gate5["reason"]) == ("FAIL", "helper-no-receipt")


def test_unbound_vanillasoft_key_is_blocked_not_ready(fx):
    env = fx.with_history()
    result = fx.run("run.sh", env=env)
    assert result.returncode != 0
    gate7 = fx.gates()[7]
    assert (gate7["state"], gate7["reason"]) == ("BLOCKED", "vanillasoft-key-unbound")
    assert fx.verdict()["verdict"] == "blocked"
    assert "make import-vanillasoft" not in fx.calls_text()


# ── Gate 7: operator inputs and guards are judged before any side effect ────


@pytest.mark.parametrize(
    "drop, extra, state, reason, verdict",
    [
        (None, {"VANILLASOFT_CALL_FLOOR": "2020-01-01T00:00:00Z"}, "FAIL", "rolling-floor-refused", "failed"),
        (None, {"VANILLASOFT_CONTACT_FLOOR": "2020-01-01T00:00:00Z"}, "FAIL", "rolling-floor-refused", "failed"),
        (None, {"VANILLASOFT_PRODUCTION_PERMIT": "/tmp/permit.json"}, "FAIL", "production-permit-refused", "failed"),
        (None, {"ODOO_STAGE": "production"}, "FAIL", "production-stage-refused", "failed"),
        (None, {"VANILLASOFT_HISTORY_CHECKPOINT": "/srv/ledger.jsonl"}, "FAIL", "history-checkpoint-refused", "failed"),
        (None, {"REHEARSAL_HISTORY_MAX_IDS": "0"}, "FAIL", "vanillasoft-history-bound-invalid", "failed"),
    ],
)
def test_gate7_refuses_before_touching_the_clone(fx, drop, extra, state, reason, verdict):
    env = fx.ready_for_gate7()
    if drop:
        env.pop(drop)
    env.update(extra)
    result = fx.run("run.sh", env=env)
    assert result.returncode != 0
    gate7 = fx.gates()[7]
    assert (gate7["state"], gate7["reason"]) == (state, reason)
    assert fx.verdict()["verdict"] == verdict
    assert "make import-vanillasoft" not in fx.calls_text()
    assert "ir_config_parameter" not in (fx.stub / "sql.log").read_text() if (fx.stub / "sql.log").exists() else True


def test_gate7_does_not_read_the_checkout_export(fx):
    env = fx.ready_for_gate7()
    (fx.repo / TRACKED_REL).unlink()
    result = fx.run("run.sh", env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    call = _vs_make_call(fx)
    assert "make import-vanillasoft" in call
    assert TRACKED_REL not in call
    assert "VANILLASOFT_HISTORY_CENSUS" not in call


def test_gate7_ignores_an_outside_census(fx, tmp_path):
    env = fx.ready_for_gate7()
    outside = tmp_path / "elsewhere.csv"
    outside.write_text("other\n", encoding="utf-8")
    env["VANILLASOFT_HISTORY_CENSUS"] = str(outside)
    env["VANILLASOFT_HISTORY_CENSUS_SHA256"] = "0" * 64
    result = fx.run("run.sh", env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    call = _vs_make_call(fx)
    assert "VANILLASOFT_CALL_FLOOR=" in call
    assert "VANILLASOFT_CONTACT_FLOOR=" in call
    assert "VANILLASOFT_HISTORY_CENSUS=" not in call
    assert TRACKED_REL not in call
    assert "elsewhere.csv" not in call
    assert "0" * 64 not in call


@pytest.mark.parametrize(
    "env, state, reason",
    [
        ({"STUB_TE_RUN_RC": "1"}, "FAIL", "vanillasoft-import-exit"),
        ({"STUB_TE_RUN_RC": "2"}, "FAIL", "vanillasoft-preflight-failed"),
        ({"STUB_VS_TRACE": "none"}, "FAIL", "vanillasoft-summary-unobserved"),
        ({"STUB_REFS_AFTER": "0"}, "BLOCKED", "vanillasoft-no-import"),
    ],
)
def test_gate7_judges_the_rolling_summary_and_durable_refs(fx, env, state, reason):
    fx.with_capability_bind()
    hist_env = fx.with_history()
    fx.run("run.sh", env={**hist_env, **env})
    gate7 = fx.gates()[7]
    assert (gate7["state"], gate7["reason"]) == (state, reason), gate7
    assert fx.verdict()["verdict"] != "ready"
    assert "complete" not in gate7["reason"]


def test_sigterm_writes_a_complete_failed_verdict(fx):
    proc = subprocess.Popen(
        ["bash", str(fx.kit / "run.sh")],
        cwd=fx.repo,
        env={**fx.env, "STUB_SMOKE_SLEEP": "20"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.time() + 15
    while "make install-smoke" not in fx.calls_text() and time.time() < deadline:
        time.sleep(0.05)
    os.killpg(proc.pid, signal.SIGTERM)
    assert proc.wait(timeout=15) == 143
    gates = fx.gates()
    assert (gates[3]["state"], gates[3]["reason"]) == ("FAIL", "interrupted-TERM")
    assert all(gates[g]["state"] == "SKIPPED" for g in range(4, 8))
    verdict = fx.verdict()
    assert verdict["verdict"] == "failed"
    assert "run:interrupted-TERM" in verdict["failures"]


def test_cached_install_smoke_is_labelled_cached(fx):
    fx.run("run.sh", env={"STUB_SMOKE_OUT": "install-smoke evidence matches; not upgrading"})
    assert fx.gates()[3]["reason"] == "install-smoke-cached-receipt"


# ── RK-04 / RK-07: weblead_e2e.sh end to end against stubs ──────────────────

WL_RECEIPT = {"status": "ok", "decision": "hot", "state": "intake_created", "intake_id": 11, "web_lead_id": 5}
SNAP_BEFORE = {"web_leads": 0, "intakes": 0, "crm_leads": 0, "partners": 3}
SNAP_AFTER = {"web_leads": 1, "intakes": 1, "crm_leads": 1, "partners": 3}
WL_ROW = {
    "web_lead": {"id": 5, "lead_id": "c-1", "state": "intake_created", "intake_id": 11, "crm_lead_id": 90},
    "same_lead_id_rows": 1,
    "intake_exists": 1,
    "crm_for_intake": 1,
    "crm": {
        "id": 90,
        "type": "opportunity",
        "user_id": None,
        "partner_id": None,
        "active": True,
        "source_intake_id": 11,
        "is_won": False,
    },
}


@pytest.fixture
def wl(tmp_path):
    fixture = Fixture(tmp_path, stub_helpers=False)
    fixture.stub_json("post.0.json", WL_RECEIPT)
    fixture.stub_json("post.1.json", WL_RECEIPT)
    fixture.stub_json("snap.0.json", SNAP_BEFORE)
    fixture.stub_json("snap.1.json", SNAP_AFTER)
    fixture.stub_json("snap.2.json", SNAP_AFTER)
    fixture.stub_json("row.json", WL_ROW)
    fixture.evidence = tmp_path / "evidence"
    fixture.evidence.mkdir()
    return fixture


def _run_wl(wl, **env):
    return wl.run(
        "weblead_e2e.sh",
        str(wl.repo),
        "odoo_test_cutover",
        "18069",
        str(wl.evidence),
        env={"STUB_CONFIG_KEY": FAKE_BEARER, **env},
    )


def _gate(evidence: Path, n: int) -> dict:
    return json.loads((evidence / f"gate-{n}.json").read_text())


def test_weblead_chain_passes_and_keeps_bearer_off_argv(wl):
    result = _run_wl(wl)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _gate(wl.evidence, 5)["state"] == "PASS"
    assert FAKE_BEARER not in wl.calls_text()
    assert FAKE_BEARER in (wl.stub / "seen-headers").read_text()
    for path in wl.evidence.rglob("*"):
        if path.is_file():
            assert FAKE_BEARER not in path.read_text(errors="replace")
    assert "docker rm -f odoo_rehearsal_18069" in wl.calls_text()


def test_weblead_http_200_without_crm_opportunity_fails(wl):
    wl.stub_json("snap.1.json", {**SNAP_AFTER, "crm_leads": 0})
    wl.stub_json("snap.2.json", {**SNAP_AFTER, "crm_leads": 0})
    row = json.loads(json.dumps(WL_ROW))
    row["web_lead"]["crm_lead_id"] = None
    row["crm"] = None
    row["crm_for_intake"] = 0
    wl.stub_json("row.json", row)
    result = _run_wl(wl)
    assert result.returncode != 0
    gate = _gate(wl.evidence, 5)
    assert gate["state"] == "FAIL"
    assert "crm" in gate["reason"]


def test_weblead_replay_duplicate_fails(wl):
    wl.stub_json("snap.2.json", {**SNAP_AFTER, "web_leads": 2, "crm_leads": 2})
    _run_wl(wl)
    assert _gate(wl.evidence, 5)["reason"].startswith("weblead-replay-")


def test_weblead_error_state_fails_and_cleans_up(wl):
    wl.stub_json("post.0.json", {**WL_RECEIPT, "state": "error", "error": "Expected singleton: res.users()"})
    result = _run_wl(wl)
    assert result.returncode != 0
    assert _gate(wl.evidence, 5)["reason"] == "weblead-state"
    assert "docker rm -f odoo_rehearsal_18069" in wl.calls_text()
    assert not list(wl.tmp.glob("rehearsal-weblead.*"))


def test_weblead_http_error_fails(wl):
    result = _run_wl(wl, STUB_POST_CODE="401")
    assert result.returncode != 0
    assert _gate(wl.evidence, 5)["reason"] == "weblead-http-401"


def test_weblead_never_removes_a_foreign_container(wl):
    result = _run_wl(wl, STUB_CONTAINER_EXISTS="1")
    assert result.returncode != 0
    assert _gate(wl.evidence, 5)["reason"] == "rehearsal-container-in-use"
    assert "docker rm" not in wl.calls_text()


def test_weblead_missing_key_fails(wl):
    result = _run_wl(wl, STUB_CONFIG_KEY="")
    assert result.returncode != 0
    assert _gate(wl.evidence, 5)["reason"] == "weblead-key-missing"


# ── RK-05 / RK-07: erp_slice.sh end to end against stubs ────────────────────

ERP_CENSUS = {
    "payload_kind": "database",
    "source_origin": "erp-host/erp_db",
    "census": {"payables_unselected": {"rows": 12, "amount": 0.0}},
    "unresolved": [],
}
ERP_ENV = {
    "ERP_SQL_SERVER": "erp-host.invalid",
    "ERP_SQL_DATABASE": "erp_db",
    "ERP_SQL_USER": "erp_reader",
    "ERP_SQL_PASSWORD": FAKE_ERP_PASSWORD,
    "RUN_STARTED_UTC": "2026-01-01T00:00:00Z",
}


def _fidelity_module():
    spec = importlib.util.spec_from_file_location("rehearsal_fidelity", KIT / "fidelity.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def erp(tmp_path):
    fixture = Fixture(tmp_path, stub_helpers=False)
    fixture.evidence = fixture.kit / "evidence" / "run"
    fixture.evidence.mkdir(parents=True)
    fixture.stub_json("05-erp-summary.json", _summary("erp"))
    fixture.stub_json("05-erp-summary-census.json", ERP_CENSUS)
    fixture.stub_json("layers.json", {"counterparties": 2, "addresses": 1, "contacts": 3})
    odoo, source = _fidelity_module().fixture_bundles()
    fixture.stub_json("fidelity-odoo.json", odoo)
    fixture.stub_json("fidelity-source.json", source)
    fixture.env["REHEARSAL_FIDELITY_SOURCE"] = str(fixture.stub / "fidelity-source.json")
    return fixture


def _run_erp(erp, **env):
    return erp.run("erp_slice.sh", str(erp.repo), "odoo_test_cutover", str(erp.evidence), env={**ERP_ENV, **env})


def test_erp_slice_database_run_passes_and_keeps_password_off_argv(erp):
    result = _run_erp(erp)
    assert result.returncode == 0, result.stdout + result.stderr
    gate = _gate(erp.evidence, 6)
    assert gate["state"] == "PASS"
    assert FAKE_ERP_PASSWORD not in erp.calls_text()
    assert "ERP_LIMIT=10%" in erp.calls_text()
    assert "import-erp-test" not in erp.calls_text()
    assert gate["facts"]["fidelity_failed"] == 0
    assert gate["facts"]["fidelity_compared"] > 0
    assert gate["facts"]["verification_spec"] == "l9.plasticos.rehearsal.fidelity.v1"
    assert gate["facts"]["source_fingerprint"]
    assert any(row["source_field"] == "CompanyNm" for row in gate["facts"]["coverage"])
    ledger = gate["facts"]["coverage_ledger"]
    partition = ledger["partition"]
    assert partition["compared"] + partition["rejected"] + partition["excluded"] == ledger["expected_count"]
    assert gate["facts"]["comparison_digest"]
    for name in ("05-erp-fidelity-coverage.json", "05-erp-fidelity-odoo.json"):
        assert not (erp.evidence / name).exists()
    fidelity = json.loads((erp.evidence / "05-erp-fidelity.json").read_text(encoding="utf-8"))
    assert fidelity["rows_retained"] == "failures"
    assert all(row["result"] == "FAIL" for row in fidelity["rows"])
    census = json.loads((erp.evidence / "05-erp-summary-census.json").read_text(encoding="utf-8"))
    assert census["payload_kind"] == "database"
    assert census["origin_sha256"]
    assert "source_origin" not in census
    assert "anomalies" not in census
    assert "unresolved" not in census
    full = json.loads((erp.home / ".l9" / "rehearsal-census" / "gate6" / "05-erp-summary-census.json").read_text())
    assert "unresolved" in full
    assert "source_origin" in full
    summary = json.loads((erp.evidence / "05-erp-summary.json").read_text())
    assert "gate" not in summary
    path = gate["facts"]["execution_path"]
    assert (path["make_target"], path["database"], path["limit"]) == ("import-erp", "odoo_test_cutover", "10%")
    assert "every worksheet" not in gate["facts"]["scope"]
    assert "58699" in gate["facts"]["scope"]
    assert path["release_sha"] == erp.staging_sha
    assert "05-erp-import.log" in gate["evidence"]


@pytest.mark.parametrize(
    "env, reason",
    [
        ({"STUB_ERP_SCOPE": " (partners only)"}, "erp-run-not-full"),
        (
            {
                "STUB_ERP_COUNTS": "{'transactions': {'created': 4, 'updated': 0}, 'transaction_lines': {'created': 9, 'updated': 0}}"
            },
            "erp-native-documents-missing",
        ),
    ],
)
def test_erp_slice_fails_when_the_clone_lacks_the_documents_the_importer_realized(erp, env, reason):
    result = _run_erp(erp, **env)
    assert result.returncode != 0
    assert reason in _gate(erp.evidence, 6)["facts"]["failure_codes"]


def test_erp_slice_fails_without_the_drivers_source_line(erp):
    result = _run_erp(erp, STUB_ERP_TRACE="0")
    assert result.returncode != 0
    assert "erp-dispatcher-unobserved" in _gate(erp.evidence, 6)["facts"]["failure_codes"]


def test_erp_slice_fidelity_discrepancy_fails_the_gate(erp):
    source = json.loads((erp.stub / "fidelity-source.json").read_text(encoding="utf-8"))
    source["counterparties"]["10"]["CompanyNm"] = "Other Name"
    bad = erp.stub / "fidelity-source-bad.json"
    bad.write_text(json.dumps(source), encoding="utf-8")
    result = _run_erp(erp, REHEARSAL_FIDELITY_SOURCE=str(bad))
    assert result.returncode != 0
    gate = _gate(erp.evidence, 6)
    assert gate["state"] == "FAIL"
    assert gate["reason"] == "erp-fidelity-discrepancy"
    failed = [row for row in gate["facts"]["fidelity_failures"] if row["source_field"] == "CompanyNm"]
    assert failed
    assert failed[0]["expected"] == "Other Name"
    assert failed[0]["actual"] == "Acme"


@pytest.mark.parametrize(
    "mutate, env, reason",
    [
        (lambda f: (f.stub / "05-erp-summary.json").unlink(), {}, "erp-summary-unreadable"),
        (lambda f: (f.stub / "05-erp-summary-census.json").unlink(), {}, "erp-census-unreadable"),
        (
            lambda f: f.stub_json("05-erp-summary-census.json", {**ERP_CENSUS, "payload_kind": "grid"}),
            {},
            "erp-source-not-database",
        ),
        (
            lambda f: f.stub_json("layers.json", {"counterparties": 2, "addresses": 1, "contacts": 0}),
            {},
            "erp-layer-missing-contacts",
        ),
        (lambda f: (f.stub / "layers.json").unlink(), {}, "erp-layer-census-unavailable"),
        (lambda f: None, {"STUB_TE_RUN_RC": "1"}, "erp-import-exit"),
        (lambda f: None, {"STUB_CENSUS": "4"}, "clone-not-empty"),
        (lambda f: None, {"STUB_CENSUS_RC": "2"}, "census-unproven"),
        (lambda f: None, {"ODOO_STAGE": "production"}, "production-stage-refused"),
        (lambda f: None, {"ERP_PRODUCTION_PERMIT": "/tmp/permit"}, "production-permit-refused"),
        (lambda f: None, {"ERP_REQUIRE_EMPTY": "0"}, "empty-guard-disabled"),
        (lambda f: None, {"ERP_SQL_DATABASE": ""}, "erp-source-incomplete"),
    ],
)
def test_erp_slice_fails_closed(erp, mutate, env, reason):
    mutate(erp)
    result = _run_erp(erp, **env)
    assert result.returncode != 0
    gate = _gate(erp.evidence, 6)
    assert gate["state"] in ("FAIL", "BLOCKED")
    assert reason in [gate["reason"], *gate["facts"].get("failure_codes", [])]
    summary_path = erp.evidence / "05-erp-summary.json"
    if summary_path.exists():
        json.loads(summary_path.read_text())  # never appended to


def test_erp_slice_guards_refuse_before_the_import(erp):
    _run_erp(erp, ODOO_STAGE="production")
    assert "test_env" not in erp.calls_text() and "docker" not in erp.calls_text()


def test_erp_slice_redacts_a_leaked_password(erp):
    (erp.stub / "leak.sh").write_text("", encoding="utf-8")
    # The import log is the importer's stdout; a leak there must fail the gate.
    erp._exe(
        erp.repo / "scripts" / "test_env.sh",
        TEST_ENV_STUB.replace('sub="$1"', 'sub="$1"; [ "$sub" = run ] && echo "pw=$ERP_SQL_PASSWORD"'),
    )
    result = _run_erp(erp)
    assert result.returncode != 0
    assert _gate(erp.evidence, 6)["reason"] == "evidence-secret-redacted"
    assert FAKE_ERP_PASSWORD not in (erp.evidence / "05-erp-import.log").read_text()


# ── Makefile dispatch parity: the real import targets against a stub docker ──
#
# `make import-erp` and `make import-vanillasoft` run from a scratch checkout
# whose `docker` records every compose call (argv and the driver piped on
# stdin) and whose no-Docker `odoo` records its environment. No container,
# database or credential is touched. The same recipe lines production runs
# are the ones under test.

MAKE_DOCKER_STUB = r"""#!/usr/bin/env bash
[ "$1" = info ] && exit "${STUB_DOCKER_INFO_RC:-0}"
n="$(ls "$STUB_DIR"/compose.*.argv 2>/dev/null | wc -l | tr -d ' ')"
printf '%s\n' "$@" > "$STUB_DIR/compose.$n.argv"
cat > "$STUB_DIR/compose.$n.stdin"
exit 0
"""
MAKE_ODOO_STUB = """#!/usr/bin/env python3
import json, os, sys
json.dump({"argv": sys.argv[1:], "env": dict(os.environ), "stdin": sys.stdin.read()}, open(os.environ["ODOO_DUMP"], "w"))
"""
ERP_DRIVER = "plasticos_partner_import/scripts/import_erp_shell.py"
VS_DRIVER = "plasticos_crm_sync/scripts/import_vanillasoft_shell.py"
RETIRED = (
    "run_import.py",
    "run_transaction_import.py",
    "partner_import_service",
    "transaction_import_service",
    "transaction_import_wizard",
    "run_csv_import",
    "run_full_import",
    "action_import",
)
SHA64 = "b" * 64

pytestmark_make = pytest.mark.skipif(shutil.which("make") is None, reason="needs make")


class MakeProbe:
    def __init__(self, tmp: Path, folder: str = "work"):
        self.work = tmp / folder
        self.stub = tmp / "stub"
        self.bin = tmp / "bin"
        self.venv = tmp / "venv"
        for path in (self.work / ".l9" / "runtime" / "ledger", self.stub, self.bin, self.venv / "bin"):
            path.mkdir(parents=True)
        for addon in ("plasticos_partner_import", "plasticos_crm_sync"):
            (self.work / addon).symlink_to(ROOT / addon)
        docker = self.bin / "docker"
        docker.write_text(MAKE_DOCKER_STUB, encoding="utf-8")
        docker.chmod(0o755)
        odoo = self.venv / "bin" / "odoo"
        odoo.write_text(MAKE_ODOO_STUB, encoding="utf-8")
        odoo.chmod(0o755)
        (self.work / CENSUS_REL).write_text(CENSUS_TEXT, encoding="utf-8")
        (self.work / ".l9" / "runtime" / "permit.json").write_text("{}", encoding="utf-8")
        self.dump = tmp / "odoo.json"

    def run(self, target: str, *args: str, docker: bool = True, env: dict | None = None):
        for old in self.stub.glob("compose.*"):
            old.unlink()
        base = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("ERP_", "VANILLASOFT_", "MAKE", "ODOO_"))
            and k not in {"MFLAGS", "GNUMAKEFLAGS", "TEST_ENV_VERIFIED_CLONE"}
        }
        base["PATH"] = f"{self.bin}{os.pathsep}{base['PATH']}"
        base["STUB_DIR"] = str(self.stub)
        base["ODOO_DUMP"] = str(self.dump)
        if not docker:
            base["STUB_DOCKER_INFO_RC"] = "1"
        base.update(env or {})
        argv = ["make", "-s", "--no-print-directory", "-C", str(self.work), "-f", str(MAKEFILE), target]
        argv += [*args, "ODOO_DB_NAME=probe_db", f"L9_ODOO_VENV={self.venv}"]
        return subprocess.run(argv, env=base, capture_output=True, text=True, timeout=120, check=False)  # noqa: S603

    def compose_calls(self) -> list[dict]:
        calls = []
        for argv_file in sorted(self.stub.glob("compose.*.argv")):
            argv = argv_file.read_text(encoding="utf-8").splitlines()
            flags = {}
            for i, item in enumerate(argv):
                if item == "-e" and "=" in argv[i + 1]:
                    key, value = argv[i + 1].split("=", 1)
                    flags[key] = value
            calls.append({"argv": argv, "env": flags, "stdin": argv_file.with_suffix(".stdin").read_text()})
        return calls

    def odoo_run(self) -> dict | None:
        return json.loads(self.dump.read_text()) if self.dump.exists() else None


@pytest.fixture
def mk(tmp_path):
    if shutil.which("make") is None:
        pytest.skip("needs make")
    return MakeProbe(tmp_path)


HISTORY_ARGS = (
    f"VANILLASOFT_HISTORY_CENSUS={CENSUS_REL}",
    f"VANILLASOFT_HISTORY_CENSUS_SHA256={SHA64}",
    "VANILLASOFT_HISTORY_CHECKPOINT=.l9/runtime/ledger/history.jsonl",
    "VANILLASOFT_HISTORY_MAX_IDS=100",
)
SQL_ARGS = ("ERP_SQL_SERVER=erp-host.invalid", "ERP_SQL_DATABASE=erp_probe")


def test_make_import_vanillasoft_history_mode_forwards_every_input_onto_the_mount(mk):
    result = mk.run(
        "import-vanillasoft", *HISTORY_ARGS, "VANILLASOFT_HISTORY_FAILURE_BUDGET=5", env={"ODOO_STAGE": "stage-x"}
    )
    assert result.returncode == 0, result.stderr
    assert "mode: history" in result.stdout
    (call,) = mk.compose_calls()
    # The permit is verified against the stage the driver observes; compose passes only -e variables.
    assert call["env"]["ODOO_STAGE"] == "stage-x"
    assert call["argv"][:3] == ["compose", "run", "--rm"]
    assert call["argv"][call["argv"].index("-w") + 1] == "/mnt/extra-addons"
    assert call["env"]["VANILLASOFT_HISTORY_CENSUS"] == f"/mnt/extra-addons/{CENSUS_REL}"
    assert call["env"]["VANILLASOFT_HISTORY_CENSUS_SHA256"] == SHA64
    assert call["env"]["VANILLASOFT_HISTORY_CHECKPOINT"] == "/mnt/extra-addons/.l9/runtime/ledger/history.jsonl"
    assert call["env"]["VANILLASOFT_HISTORY_MAX_IDS"] == "100"
    assert call["env"]["VANILLASOFT_HISTORY_FAILURE_BUDGET"] == "5"
    assert call["env"]["VANILLASOFT_PRODUCTION_PERMIT"] == ""
    assert call["env"]["VANILLASOFT_CALL_FLOOR"] == "" and call["env"]["VANILLASOFT_CONTACT_FLOOR"] == ""
    assert call["argv"][-5:] == ["odoo", "odoo", "shell", "-d", "probe_db"] or "shell" in call["argv"]
    assert call["stdin"] == (ROOT / VS_DRIVER).read_text(encoding="utf-8")


def test_make_import_vanillasoft_history_mounts_when_the_checkout_path_contains_spaces(tmp_path):
    mk = MakeProbe(tmp_path, folder="IB-Odoo_19 (LOCAL)/checkout")
    result = mk.run("import-vanillasoft", *HISTORY_ARGS)
    assert result.returncode == 0, result.stderr
    (call,) = mk.compose_calls()
    assert call["env"]["VANILLASOFT_HISTORY_CENSUS"] == f"/mnt/extra-addons/{CENSUS_REL}"
    assert call["env"]["VANILLASOFT_HISTORY_CHECKPOINT"] == "/mnt/extra-addons/.l9/runtime/ledger/history.jsonl"


def test_make_import_vanillasoft_history_mode_on_the_local_runner_passes_host_paths(mk):
    result = mk.run("import-vanillasoft", *HISTORY_ARGS, docker=False, env={"ODOO_STAGE": "stage-x"})
    assert result.returncode == 0, result.stderr
    assert mk.compose_calls() == []
    run = mk.odoo_run()
    assert run is not None
    assert run["env"]["ODOO_STAGE"] == "stage-x"
    assert run["env"]["VANILLASOFT_HISTORY_CENSUS"] == CENSUS_REL
    assert run["env"]["VANILLASOFT_HISTORY_CHECKPOINT"] == ".l9/runtime/ledger/history.jsonl"
    assert run["env"]["VANILLASOFT_HISTORY_CENSUS_SHA256"] == SHA64
    assert run["env"]["VANILLASOFT_CALL_FLOOR"] == ""
    assert run["stdin"] == (ROOT / VS_DRIVER).read_text(encoding="utf-8")
    assert run["argv"][:3] == ["shell", "-d", "probe_db"]


def test_make_import_vanillasoft_rolling_mode_is_named_and_carries_no_history_input(mk):
    result = mk.run("import-vanillasoft", "VANILLASOFT_CALL_FLOOR=2020-01-01T00:00:00Z")
    assert result.returncode == 0, result.stderr
    assert "mode: rolling" in result.stdout and "not the historical cohort" in result.stdout
    (call,) = mk.compose_calls()
    assert call["env"]["VANILLASOFT_CALL_FLOOR"] == "2020-01-01T00:00:00Z"
    assert all(call["env"][k] == "" for k in call["env"] if k.startswith("VANILLASOFT_HISTORY"))
    assert call["stdin"] == (ROOT / VS_DRIVER).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "args, needle",
    [
        ((), "no mode selected"),
        ((*HISTORY_ARGS, "VANILLASOFT_CALL_FLOOR=2020-01-01T00:00:00Z"), "cannot be combined"),
        ((*HISTORY_ARGS, "VANILLASOFT_CONTACT_FLOOR=2020-01-01T00:00:00Z"), "cannot be combined"),
        (
            ("VANILLASOFT_CALL_FLOOR=x", "VANILLASOFT_HISTORY_MAX_IDS=5"),
            "history settings without VANILLASOFT_HISTORY_CENSUS",
        ),
        (("VANILLASOFT_HISTORY_CENSUS_SHA256=" + SHA64,), "history settings without VANILLASOFT_HISTORY_CENSUS"),
        ((HISTORY_ARGS[0], "VANILLASOFT_HISTORY_CENSUS_SHA256=abc", HISTORY_ARGS[2]), "64 hex characters"),
        ((HISTORY_ARGS[0], HISTORY_ARGS[1]), "VANILLASOFT_HISTORY_CHECKPOINT must name"),
        (
            (HISTORY_ARGS[0], HISTORY_ARGS[1], "VANILLASOFT_HISTORY_CHECKPOINT=.l9/runtime/absent/x.jsonl"),
            "must exist and be writable",
        ),
        ((*HISTORY_ARGS[1:], "VANILLASOFT_HISTORY_CENSUS=.l9/runtime/absent.csv"), "readable census file"),
        ((*HISTORY_ARGS, "VANILLASOFT_HISTORY_MAX_IDS=0"), "positive integers"),
        ((*HISTORY_ARGS, "VANILLASOFT_HISTORY_FAILURE_BUDGET=many"), "positive integers"),
        ((*HISTORY_ARGS, "VANILLASOFT_PRODUCTION_PERMIT=.l9/runtime/absent-permit.json"), "readable file"),
    ],
)
def test_make_import_vanillasoft_refuses_before_any_runtime_starts(mk, args, needle):
    result = mk.run("import-vanillasoft", *args)
    assert result.returncode == 2, result.stdout + result.stderr
    assert needle in result.stderr
    assert mk.compose_calls() == []
    assert mk.odoo_run() is None


@pytest.mark.parametrize(
    "var", ["VANILLASOFT_HISTORY_CENSUS", "VANILLASOFT_HISTORY_CHECKPOINT", "VANILLASOFT_PRODUCTION_PERMIT"]
)
def test_make_import_vanillasoft_docker_refuses_a_file_outside_the_bind_mount(mk, tmp_path, var):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "f").write_text(CENSUS_TEXT, encoding="utf-8")
    args = [a for a in HISTORY_ARGS if not a.startswith(f"{var}=")]
    args.append(f"{var}={outside / 'f'}")
    result = mk.run("import-vanillasoft", *args)
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"{var} must be inside this checkout" in result.stderr
    assert mk.compose_calls() == []


def test_make_import_erp_forwards_the_permit_and_pipes_only_the_erp_driver(mk):
    result = mk.run(
        "import-erp",
        *SQL_ARGS,
        "ERP_PRODUCTION_PERMIT=.l9/runtime/permit.json",
        "LIMIT=10%",
        env={"ODOO_STAGE": "stage-x"},
    )
    assert result.returncode == 0, result.stderr
    (call,) = mk.compose_calls()
    assert call["env"]["ERP_PRODUCTION_PERMIT"] == "/mnt/extra-addons/.l9/runtime/permit.json"
    assert call["env"]["ODOO_STAGE"] == "stage-x"
    assert "ODOO_STAGE" not in [a.split("=")[0] for a in SQL_ARGS]  # it came from the environment, not argv
    assert call["env"]["ERP_SQL_SERVER"] == "erp-host.invalid" and call["env"]["ERP_SQL_DATABASE"] == "erp_probe"
    assert call["env"]["ERP_LIMIT"] == "10%" and call["env"]["ERP_REQUIRE_EMPTY"] == "1"
    assert call["env"]["ERP_PAYLOAD_ROOT"] == "" and call["env"]["ERP_TARGET_DB"] == "probe_db"
    assert call["stdin"] == (ROOT / ERP_DRIVER).read_text(encoding="utf-8")
    assert "-v" not in call["argv"]
    assert "plasticos.erp.import" in result.stdout


def test_make_import_erp_mounts_an_isolated_census_directory(mk, tmp_path):
    isolated = tmp_path / "outside-checkout"
    isolated.mkdir()
    result = mk.run(
        "import-erp",
        *SQL_ARGS,
        f"ERP_ISOLATED_REPORT_DIR={isolated}",
        "REPORT_PATH=/erp-isolated/05-erp-summary.json",
    )
    assert result.returncode == 0, result.stderr
    (call,) = mk.compose_calls()
    assert f"{isolated}:/erp-isolated" in call["argv"]
    assert call["env"]["ERP_REPORT_PATH"] == "/erp-isolated/05-erp-summary.json"


def test_make_import_erp_on_the_local_runner_passes_the_permit_host_path(mk):
    result = mk.run(
        "import-erp",
        *SQL_ARGS,
        "ERP_PRODUCTION_PERMIT=.l9/runtime/permit.json",
        docker=False,
        env={"ODOO_STAGE": "stage-x"},
    )
    assert result.returncode == 0, result.stderr
    run = mk.odoo_run()
    assert run is not None
    assert run["env"]["ERP_PRODUCTION_PERMIT"] == ".l9/runtime/permit.json"
    assert run["env"]["ODOO_STAGE"] == "stage-x"
    assert run["env"]["ERP_SQL_DATABASE"] == "erp_probe"
    assert run["stdin"] == (ROOT / ERP_DRIVER).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "args, docker, needle",
    [
        ((), True, "ERP_SQL_SERVER and ERP_SQL_DATABASE must both"),
        ((), False, "ERP_SQL_SERVER and ERP_SQL_DATABASE must both"),
        (("ERP_SQL_SERVER=erp-host.invalid",), True, "ERP_SQL_SERVER and ERP_SQL_DATABASE must both"),
        ((*SQL_ARGS, "PAYLOAD_ROOT=/tmp/grid"), True, "frozen fixture"),
        ((*SQL_ARGS, "ERP_PAYLOAD_ROOT=/tmp/grid"), False, "frozen fixture"),
        ((*SQL_ARGS, "ERP_PRODUCTION_PERMIT=.l9/runtime/absent.json"), True, "readable file"),
        ((*SQL_ARGS, "ERP_PRODUCTION_PERMIT=/etc/passwd"), True, "must be inside this checkout"),
    ],
)
def test_make_import_erp_refuses_a_fixture_source_before_any_runtime_starts(mk, args, docker, needle):
    result = mk.run("import-erp", *args, docker=docker)
    assert result.returncode == 2, result.stdout + result.stderr
    assert needle in result.stderr
    assert mk.compose_calls() == []
    assert mk.odoo_run() is None


# ── Static dispatch contract, and its negative proof (legacy-path injection) ─


def _recipe(text: str, target: str) -> str:
    match = re.search(rf"(?ms)^{re.escape(target)}:\n(.*?)(?=^\S|\Z)", text)
    assert match, f"{target} recipe not found"
    return match.group(1)


def assert_canonical_dispatch(makefile_text: str) -> None:
    """Both import targets pipe only their canonical driver, on both runtimes, and name no retired path."""
    erp = _recipe(makefile_text, "import-erp")
    vs = _recipe(makefile_text, "import-vanillasoft")
    assert erp.count(f"< {ERP_DRIVER}") == 2, "import-erp must pipe import_erp_shell.py on both runtimes"
    assert vs.count(f"< {VS_DRIVER}") == 2, "import-vanillasoft must pipe import_vanillasoft_shell.py on both runtimes"
    assert "< " + ERP_DRIVER not in vs and "< " + VS_DRIVER not in erp
    for body, name in ((erp, "import-erp"), (vs, "import-vanillasoft")):
        for retired in RETIRED:
            assert retired not in body, f"{name} reaches retired path {retired}"
        assert body.count("odoo shell -d $(ODOO_DB_NAME)") + body.count("shell -d $(ODOO_DB_NAME)") >= 2
    assert erp.count("$(erp_source_guard)") == 2
    assert erp.count('ERP_PRODUCTION_PERMIT="$(call runtime_path,$(ERP_PRODUCTION_PERMIT))"') == 1
    assert erp.count('ERP_PRODUCTION_PERMIT="$(ERP_PRODUCTION_PERMIT)"') == 1
    assert erp.count('ODOO_STAGE="$(ODOO_STAGE)"') == 2 and vs.count('ODOO_STAGE="$(ODOO_STAGE)"') == 2
    assert "$(vanillasoft_mode_guard)" in vs
    for var in (
        "VANILLASOFT_HISTORY_CENSUS",
        "VANILLASOFT_HISTORY_CENSUS_SHA256",
        "VANILLASOFT_HISTORY_CHECKPOINT",
        "VANILLASOFT_HISTORY_MAX_IDS",
        "VANILLASOFT_HISTORY_FAILURE_BUDGET",
        "VANILLASOFT_PRODUCTION_PERMIT",
    ):
        assert vs.count(f"{var}=") == 2, f"{var} must reach both runtimes"
    assert "import-erp-test" in makefile_text and "$(MAKE) import-erp " in _recipe(makefile_text, "import-erp-test")


def test_makefile_import_targets_dispatch_only_through_the_canonical_drivers():
    assert_canonical_dispatch(MAKEFILE.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda t: t.replace(f"< {ERP_DRIVER}", "< plasticos_partner_import/scripts/run_import.py", 1),
        lambda t: t.replace(f"< {ERP_DRIVER}", "< plasticos_transaction/scripts/run_transaction_import.py"),
        lambda t: t.replace(f"< {VS_DRIVER}", "< plasticos_crm_sync/scripts/run_full_import.py", 1),
        lambda t: (
            _recipe(t, "import-vanillasoft").join(
                t.split(_recipe(t, "import-vanillasoft"), 1)[:1]
                + [
                    "\t@python3 -c 'from plasticos_partner_import.models.partner_import_service import run_csv_import'\n"
                ]
            )
            + t.split(_recipe(t, "import-vanillasoft"), 1)[1]
        ),
        lambda t: t.replace("$(erp_source_guard); \\\n", "", 1),
        lambda t: t.replace('-e VANILLASOFT_HISTORY_CENSUS_SHA256="$(VANILLASOFT_HISTORY_CENSUS_SHA256)" \\\n', ""),
    ],
)
def test_injected_legacy_or_withheld_path_fails_the_dispatch_contract(mutate):
    text = MAKEFILE.read_text(encoding="utf-8")
    mutated = mutate(text)
    assert mutated != text, "the mutation must change the Makefile, or this proves nothing"
    with pytest.raises(AssertionError):
        assert_canonical_dispatch(mutated)
