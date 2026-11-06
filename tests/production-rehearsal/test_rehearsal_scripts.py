"""The rehearsal shell scripts, executed against a throwaway git repository.

Pure-python tier. Each test builds a fixture repository with a local bare
``origin`` (Staging and Production), copies the real kit into it, and puts
stub ``make`` / ``docker`` / ``curl`` / ``scripts/test_env.sh`` first on PATH.
The stubs record every call, so a test can prove that a refused gate caused
no side effect. No Docker, database, HTTP server or secret is used.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[1]
KIT_FILES = (
    "run.sh",
    "weblead_e2e.sh",
    "erp_slice.sh",
    "rehearsal_common.sh",
    "rehearsal_lib.py",
    "expected/blockers.yaml",
    "payloads/cognito_hot.json",
)
OWNER_FILES = (
    "scripts/validate_import_summary.py",
    "contracts/schemas/draft/import-run-summary.schema.json",
    "plasticos_crm_sync/services/import_summary.py",
)
FAKE_BEARER = "fake-bearer-for-kit-tests-0001"
FAKE_ERP_PASSWORD = "fake-erp-password-0001"

pytestmark = pytest.mark.skipif(shutil.which("git") is None or shutil.which("bash") is None, reason="needs git+bash")

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
      *customer_rank*)
        if [ -n "${STUB_CENSUS_RC:-}" ]; then echo "ERROR: boom" >&2; exit "$STUB_CENSUS_RC"; fi
        printf '%s\n' "${STUB_CENSUS-0}" ;;
      *legacy_erp_cp_*) cat "$STUB_DIR/layers.json" || exit 1 ;;
      *plasticos_crm_external_ref*) printf '%s\n' "${STUB_CONTACTS-2}" ;;
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

TEST_ENV_STUB = r"""#!/usr/bin/env bash
printf 'test_env %s\n' "$*" >> "$CALL_LOG"
sub="$1"
case "$sub" in
  clone) exit "${STUB_TE_CLONE_RC:-0}" ;;
  upgrade) exit "${STUB_TE_UPGRADE_RC:-0}" ;;
  assert-clone) exit "${STUB_TE_ASSERT_RC:-0}" ;;
  run)
    for arg in "$@"; do
      case "$arg" in
        REPORT_PATH=*|VANILLASOFT_REPORT_PATH=*)
          path="${arg#*=}"; host="${STUB_REPO}${path#/mnt/extra-addons}"
          base="$(basename "$host" .json)"
          if [ -f "$STUB_DIR/$base.json" ]; then cp "$STUB_DIR/$base.json" "$host"; fi
          if [ -f "$STUB_DIR/$base-census.json" ]; then cp "$STUB_DIR/$base-census.json" "$(dirname "$host")/$base-census.json"; fi ;;
      esac
    done
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
  python3 "$(dirname "$0")/rehearsal_lib.py" gate-write "$dir" "$gate" "$state" "stub-$state"
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


@pytest.fixture
def fx(tmp_path):
    return Fixture(tmp_path, stub_helpers=True)


def _side_effect_calls(fx: Fixture) -> list[str]:
    return [line for line in fx.calls_text().splitlines() if line.split(" ", 1)[0] in ("make", "docker", "test_env")]


# ── RK-01: revision identity refuses before any side effect ─────────────────


def test_clean_exact_staging_all_gates_pass(fx):
    fx.with_capability_bind()
    fx.stub_json("06-crm-result.json", _summary("vanillasoft"))
    result = fx.run("run.sh")
    assert result.returncode == 0, result.stdout + result.stderr
    assert fx.verdict()["verdict"] == "ready"
    assert all(g["state"] == "PASS" for g in fx.gates().values())
    assert fx.verdict()["staging_sha"] == fx.staging_sha
    assert "fake-vanillasoft-key-0001" not in fx.calls_text()
    text = (fx.latest() / "verdict.txt").read_text()
    assert "verdict=ready" in text


@pytest.mark.parametrize("case", ["feature-branch", "ahead", "dirty-untracked", "dirty-tracked", "fetch-fails"])
def test_gate1_refusal_has_no_side_effects(fx, case):
    if case == "feature-branch":
        _git(fx.repo, "checkout", "-q", "-b", "feat/x", env=fx.env)
        reason = "not-on-staging"
    elif case == "ahead":
        (fx.repo / "feature.txt").write_text("local\n", encoding="utf-8")
        _git(fx.repo, "commit", "-qam", "ahead", env=fx.env)
        reason = "head-not-origin-staging"
    elif case == "dirty-untracked":
        (fx.repo / "plasticos_new_addon.py").write_text("x = 1\n", encoding="utf-8")
        reason = "worktree-dirty"
    elif case == "dirty-tracked":
        (fx.repo / "feature.txt").write_text("edited\n", encoding="utf-8")
        reason = "worktree-dirty"
    else:
        _git(fx.repo, "remote", "set-url", "origin", str(fx.tmp / "missing.git"), env=fx.env)
        reason = "remote-fetch-failed"
    result = fx.run("run.sh")
    assert result.returncode != 0
    gates = fx.gates()
    assert (gates[1]["state"], gates[1]["reason"]) == ("FAIL", reason)
    assert all(gates[g]["state"] == "SKIPPED" for g in range(2, 8))
    assert fx.verdict()["verdict"] == "failed"
    assert _side_effect_calls(fx) == []


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
    assert (gates[2]["state"], gates[2]["reason"]) == ("FAIL", "merge-conflict")
    assert all(gates[g]["state"] == "SKIPPED" for g in range(3, 8))
    assert _side_effect_calls(fx) == []
    assert "exit_code=1" in (fx.latest() / "02-merge-tree.txt").read_text()


def test_gate2_error_without_marker_fails(fx):
    # Unrelated histories: merge-tree exits nonzero and prints no conflict marker.
    _git(fx.repo, "checkout", "-q", "--orphan", "lonely", env=fx.env)
    _git(fx.repo, "commit", "-qm", "orphan", env=fx.env)
    _git(fx.repo, "push", "-qf", "origin", "HEAD:refs/heads/Production", env=fx.env)
    _git(fx.repo, "checkout", "-q", "-f", "Staging", env=fx.env)
    fx.run("run.sh")
    gate2 = fx.gates()[2]
    assert (gate2["state"], gate2["reason"]) == ("FAIL", "merge-tree-error")
    assert fx.verdict()["verdict"] == "failed"


def test_production_drift_invalidates_readiness(fx):
    fx.with_capability_bind()
    fx.stub_json("06-crm-result.json", _summary("vanillasoft"))
    result = fx.run("run.sh", env={"STUB_DRIFT_SHA": fx.staging_sha})
    assert result.returncode != 0
    verdict = fx.verdict()
    assert verdict["verdict"] == "failed"
    assert "run:production-ref-drifted" in verdict["failures"]


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
    result = fx.run("run.sh")
    assert result.returncode != 0
    gate7 = fx.gates()[7]
    assert (gate7["state"], gate7["reason"]) == ("BLOCKED", "vanillasoft-key-unbound")
    assert fx.verdict()["verdict"] == "blocked"


@pytest.mark.parametrize(
    "summary, env, state, reason",
    [
        (None, {}, "FAIL", "vanillasoft-summary-unreadable"),
        (_summary("vanillasoft", final_status="failed"), {}, "FAIL", "vanillasoft-business-acceptance"),
        (_summary("vanillasoft"), {"STUB_TE_RUN_RC": "1"}, "FAIL", "vanillasoft-import-exit"),
        (_summary("vanillasoft"), {"STUB_CONTACTS": "0"}, "BLOCKED", "vanillasoft-empty-window"),
    ],
)
def test_gate7_reads_the_summary_not_the_exit_code(fx, summary, env, state, reason):
    fx.with_capability_bind()
    if summary is not None:
        fx.stub_json("06-crm-result.json", summary)
    fx.run("run.sh", env=env)
    gate7 = fx.gates()[7]
    assert (gate7["state"], gate7["reason"]) == (state, reason)
    assert fx.verdict()["verdict"] != "ready"


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

ERP_CENSUS = {"payload_kind": "database", "source_origin": "erp-host/erp_db", "census": {}, "unresolved": []}
ERP_ENV = {
    "ERP_SQL_SERVER": "erp-host.invalid",
    "ERP_SQL_DATABASE": "erp_db",
    "ERP_SQL_USER": "erp_reader",
    "ERP_SQL_PASSWORD": FAKE_ERP_PASSWORD,
    "RUN_STARTED_UTC": "2026-01-01T00:00:00Z",
}


@pytest.fixture
def erp(tmp_path):
    fixture = Fixture(tmp_path, stub_helpers=False)
    fixture.evidence = fixture.kit / "evidence" / "run"
    fixture.evidence.mkdir(parents=True)
    fixture.stub_json("05-erp-summary.json", _summary("erp"))
    fixture.stub_json("05-erp-summary-census.json", ERP_CENSUS)
    fixture.stub_json("layers.json", {"counterparties": 2, "addresses": 1, "contacts": 3})
    return fixture


def _run_erp(erp, **env):
    return erp.run("erp_slice.sh", str(erp.repo), "odoo_test_cutover", str(erp.evidence), env={**ERP_ENV, **env})


def test_erp_slice_database_run_passes_and_keeps_password_off_argv(erp):
    result = _run_erp(erp)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _gate(erp.evidence, 6)["state"] == "PASS"
    assert FAKE_ERP_PASSWORD not in erp.calls_text()
    assert "LIMIT=10%" in erp.calls_text()
    summary = json.loads((erp.evidence / "05-erp-summary.json").read_text())
    assert "gate" not in summary


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
