"""Publication refuses before any remote mutation unless Staging and live L4 agree.

Git push, gh, make, and the L4 interpreter are stubs. Nothing here contacts GitHub.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = "scripts/make_push_pipeline.sh"
PUSH = "scripts/git_push_with_pr.sh"
PRE_COMMIT_ARGS = "ARGS=(hook-impl --config=.pre-commit-config.yaml --hook-type=pre-push)"
REPO = "cryptoxdog/IB-Odoo_19"
PRODUCTION_SCRIPTS = ("make_push_pipeline.sh", "git_open_pr.sh", "apply_pr_kernel_metadata.sh")

# A REST-only `gh`, shaped like a cloud session: `gh auth status`, `gh pr ...`,
# `gh label ...` and `gh api graphql` are refused (HTTP 403). `gh api` answers
# only the REST routes the ceremony uses, with GitHub's method, field and
# response shapes; anything else is a 404 or 422, never a silent success.
FAKE_GH = r"""
import json
import os
import subprocess
import sys
from urllib.parse import parse_qsl

REPO = "cryptoxdog/IB-Odoo_19"
OWNER = REPO.split("/")[0]
args = sys.argv[1:]


def log(line):
    with open(os.environ["FAKE_GH_LOG"], "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


if not args or args[0] != "api" or args[1:2] == ["graphql"]:
    log("gh FORBIDDEN " + " ".join(args))
    fail("gh: GitHub GraphQL is not available from Claude Code sessions (HTTP 403)")

method, endpoint, jq, fields = None, None, None, {}
rest = iter(args[1:])
for arg in rest:
    if arg in ("--method", "-X"):
        method = next(rest)
    elif arg in ("-f", "--raw-field"):
        key, _, value = next(rest).partition("=")
        if key.endswith("[]"):
            fields.setdefault(key[:-2], []).append(value)
        else:
            fields[key] = value
    elif arg in ("--jq", "-q"):
        jq = next(rest)
    elif arg.startswith("-") or endpoint is not None:
        fail(f"fake gh: unsupported argument {arg}")
    else:
        endpoint = arg
if endpoint is None:
    fail("fake gh: no endpoint")
# gh semantics: GET by default, POST once a field is added, unless --method.
method = method or ("POST" if fields else "GET")
path, _, query = endpoint.partition("?")
params = dict(parse_qsl(query))
if method == "GET":
    params.update(fields)
    fields = {}
log(f"gh {method} {path}")
with open(os.environ["FAKE_GH_CALLS"], "a", encoding="utf-8") as handle:
    record = {
        "method": method,
        "path": path,
        "params": params,
        "fields": fields,
        "gh_repo": os.environ.get("GH_REPO"),
        "gh_host": os.environ.get("GH_HOST"),
    }
    handle.write(json.dumps(record) + "\n")

with open(os.environ["FAKE_GH_STATE"], encoding="utf-8") as handle:
    state = json.load(handle)


def save():
    with open(os.environ["FAKE_GH_STATE"], "w", encoding="utf-8") as handle:
        json.dump(state, handle)


def denied(knob):
    if os.environ.get(knob, "0") != "0":
        fail(f"HTTP 403: {knob}")


def emit(payload):
    if jq is None:
        print(json.dumps(payload))
    elif jq == ".[].name":
        for item in payload:
            print(item["name"])
    elif jq == '.body // ""':
        print(payload.get("body") or "")
    else:
        fail(f"fake gh: unsupported --jq {jq}")
    sys.exit(0)


def find(number):
    for pr in state["pulls"]:
        if str(pr["number"]) == number:
            return pr
    fail("HTTP 404: Not Found")


if path == "user" and method == "GET":
    denied("GH_USER_RC")
    emit({"login": OWNER})
if not path.startswith(f"repos/{REPO}/"):
    fail("HTTP 404: Not Found")
parts = path[len(f"repos/{REPO}/") :].split("/")

if parts == ["pulls"] and method == "GET":
    denied("GH_LIST_RC")
    if os.environ.get("GH_LIST_MALFORMED") == "1":
        print("<html>upstream proxy error</html>")
        sys.exit(0)
    if sorted(params) != ["base", "head", "state"]:
        fail("fake gh: the PR lookup must filter by state, base and head")
    emit(
        [
            pr
            for pr in state["pulls"]
            if pr["state"] == params["state"]
            and pr["base"]["ref"] == params["base"]
            and pr["head"]["label"] == params["head"]
        ]
    )
if parts == ["pulls"] and method == "POST":
    denied("GH_CREATE_RC")
    if sorted(fields) != ["base", "body", "head", "title"]:
        fail("HTTP 422: Validation Failed")
    label = f"{OWNER}:{fields['head']}"
    for pr in state["pulls"]:
        if pr["state"] == "open" and pr["head"]["label"] == label and pr["base"]["ref"] == fields["base"]:
            fail("HTTP 422: A pull request already exists")
    sha = state.get("branches", {}).get(fields["head"])
    if not sha:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    number = state.get("next_number", 300)
    state["next_number"] = number + 1
    pr = {
        "number": number,
        "html_url": f"https://github.com/{REPO}/pull/{number}",
        "state": "open",
        "title": fields["title"],
        "body": fields["body"],
        "base": {"ref": fields["base"], "repo": {"full_name": REPO}},
        "head": {"ref": fields["head"], "sha": sha, "label": label, "repo": {"full_name": REPO}},
        "labels": [],
    }
    state["pulls"].append(pr)
    save()
    emit(pr)
if len(parts) == 2 and parts[0] == "pulls" and method in ("GET", "PATCH"):
    pr = find(parts[1])
    if method == "PATCH":
        if sorted(fields) != ["body"]:
            fail("HTTP 422: Validation Failed")
        pr["body"] = fields["body"]
        save()
    emit(pr)
if len(parts) == 3 and parts[0] == "issues" and parts[2] == "comments" and method == "POST":
    denied("GH_COMMENT_RC")
    find(parts[1])
    if sorted(fields) != ["body"]:
        fail("HTTP 422: Validation Failed")
    state.setdefault("comments", []).append({"issue": int(parts[1]), "body": fields["body"]})
    save()
    emit({"id": len(state["comments"])})
if parts == ["labels"] and method == "GET":
    denied("GH_LABEL_RC")
    emit([{"name": name} for name in state.get("labels", [])])
if len(parts) == 3 and parts[0] == "issues" and parts[2] == "labels" and method == "POST":
    denied("GH_LABEL_RC")
    pr = find(parts[1])
    if not isinstance(fields.get("labels"), list):
        fail("HTTP 422: Validation Failed")
    pr["labels"].extend(fields["labels"])
    save()
    emit([{"name": name} for name in pr["labels"]])
fail(f"HTTP 404: no route for {method} {path}")
"""


def _real(name: str) -> str:
    found = shutil.which(name)
    assert found, name
    return found


REAL_GIT = _real("git")
REAL_PYTHON = _real("python3")


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _plant_l4_provider(tmp_path: Path) -> None:
    """Fixture governance tree. CI runners have no ~/.cursor-governance."""
    gov = tmp_path / "gov-home" / ".cursor-governance"
    scripts = gov / "ops" / "scripts"
    autonomy = gov / "ops" / "autonomy"
    scripts.mkdir(parents=True)
    autonomy.mkdir(parents=True)
    (autonomy / "l4_local.py").write_text("# fixture provider\n", encoding="utf-8")
    gov_root = str(gov.resolve())
    _write(
        scripts / "resolve_governance_paths.sh",
        f'#!/bin/bash\nresolve_governance_paths() {{\n  GOV_ROOT="{gov_root}"\n  return 0\n}}\n',
    )


def _pre_push_hook(seq: Path, *, args_line: str = PRE_COMMIT_ARGS) -> str:
    """A hook shaped like `pre-commit install --hook-type pre-push` output that logs each run."""
    return (
        "#!/usr/bin/env bash\n"
        "# File generated by pre-commit: https://pre-commit.com\n"
        "# start templated\n"
        f"{args_line}\n"
        "# end templated\n"
        f'echo "pre-push $1" >> "{seq}"\n'
        'exit "${PRE_PUSH_RC:-0}"\n'
    )


def _init_repo(tmp_path: Path, branch: str = "fix/example") -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True)
    _plant_l4_provider(tmp_path)
    seq = tmp_path / "seq.log"
    subprocess.run([REAL_GIT, "init", "-b", branch], cwd=repo, check=True, capture_output=True)
    scripts = repo / "scripts"
    scripts.mkdir()
    for name in (*PRODUCTION_SCRIPTS, "git_push_with_pr.sh", "build_pr_body.py", "pr_labels_from_commit.py"):
        shutil.copy(ROOT / "scripts" / name, scripts / name)
    _write(
        scripts / "install_smoke.sh",
        f"""#!/bin/bash
echo "smoke $*" >> "{seq}"
exit "${{INSTALL_SMOKE_RC:-0}}"
""",
    )
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    (repo / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".cache/\n", encoding="utf-8")
    subprocess.run(
        [REAL_GIT, "add", "scripts", "README.md", ".pre-commit-config.yaml", ".gitignore"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [REAL_GIT, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [REAL_GIT, "remote", "add", "origin", "https://github.com/cryptoxdog/IB-Odoo_19.git"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    _write(repo / ".git" / "hooks" / "pre-push", _pre_push_hook(seq))
    # REAL_REMOTE: route origin to a local bare repo so a real `git push` runs
    # the real pre-push hook. The script still sees the GitHub origin URL.
    _write(
        bindir / "git",
        f"""#!/bin/bash
github="https://github.com/cryptoxdog/IB-Odoo_19.git"
if [[ "$1" == "push" ]]; then
  echo "push" >> "{seq}"
  if [[ -n "${{REAL_REMOTE:-}}" ]]; then
    exec "{REAL_GIT}" -c "url.$REAL_REMOTE.pushInsteadOf=$github" "$@"
  fi
  exit 0
fi
if [[ "$1" == "fetch" ]]; then
  echo "fetch" >> "{seq}"
  if [[ -n "${{REAL_REMOTE:-}}" ]]; then
    exec "{REAL_GIT}" -c "url.$REAL_REMOTE.insteadOf=$github" "$@"
  fi
  exit 0
fi
if [[ "$1" == "ls-remote" ]]; then
  echo "ls-remote" >> "{seq}"
  if [[ -n "${{REAL_REMOTE:-}}" ]]; then
    exec "{REAL_GIT}" -c "url.$REAL_REMOTE.insteadOf=$github" "$@"
  fi
  if [[ -n "${{REMOTE_SHA:-}}" ]]; then
    printf '%s\\n' "$REMOTE_SHA"
  else
    "{REAL_GIT}" rev-parse HEAD
  fi
  exit 0
fi
exec "{REAL_GIT}" "$@"
""",
    )
    _write(
        bindir / "python3",
        f"""#!/bin/bash
joined="$*"
if [[ "$joined" == *l4_local.py* ]]; then
  echo "l4 $joined" >> "{seq}"
  count="$(grep -c '^l4 ' "{seq}" || true)"
  if [[ -n "${{L4_FAIL_CALL:-}}" && "$count" == "$L4_FAIL_CALL" ]]; then
    echo '{{"allowed": false, "reason": "stale"}}'
    exit 2
  fi
  if [[ "${{L4_RC:-0}}" != "0" ]]; then
    echo '{{"allowed": false, "reason": "denied"}}'
    exit "$L4_RC"
  fi
  echo '{{"allowed": true, "reason": "test-receipt"}}'
  exit 0
fi
exec "{REAL_PYTHON}" "$@"
""",
    )
    _write(
        bindir / "make",
        f"""#!/bin/bash
echo "make PR_CHECK_FORCE_SMOKE=${{PR_CHECK_FORCE_SMOKE-}}" >> "{seq}"
if [[ "${{MAKE_DIRTY:-0}}" == "1" ]]; then
  echo dirty >> "$PWD/dirty.txt"
fi
exit 0
""",
    )
    _write(
        bindir / "gitleaks",
        f"""#!/bin/bash
echo "gitleaks $*" >> "{seq}"
exit "${{GITLEAKS_RC:-0}}"
""",
    )
    (tmp_path / "fake_gh.py").write_text(FAKE_GH, encoding="utf-8")
    _write(bindir / "gh", f'#!/bin/bash\nexec "{REAL_PYTHON}" "{tmp_path / "fake_gh.py"}" "$@"\n')
    _set_gh_state(tmp_path, pulls=[], labels=[], branches={})
    return repo, seq


def _gh_state(tmp_path: Path) -> dict:
    path = tmp_path / "gh-state.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _set_gh_state(tmp_path: Path, **updates: object) -> None:
    state = _gh_state(tmp_path)
    state.update(updates)
    (tmp_path / "gh-state.json").write_text(json.dumps(state), encoding="utf-8")


def _gh_calls(tmp_path: Path) -> list[dict]:
    path = tmp_path / "gh-calls.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _rest_pr(
    number: int, branch: str, sha: str, *, body: str = "", head_repo: str = REPO, base_repo: str = REPO
) -> dict:
    """A pull request in the shape `GET repos/{owner}/{repo}/pulls` returns."""
    return {
        "number": number,
        "html_url": f"https://github.com/{REPO}/pull/{number}",
        "state": "open",
        "body": body,
        "base": {"ref": "Staging", "repo": {"full_name": base_repo}},
        "head": {
            "ref": branch,
            "sha": sha,
            "label": f"{head_repo.split('/')[0]}:{branch}",
            "repo": {"full_name": head_repo},
        },
        "labels": [],
    }


def _seed_open_pr(tmp_path: Path, repo: Path, branch: str = "fix/example", **kwargs: str) -> None:
    sha = subprocess.check_output([REAL_GIT, "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    _set_gh_state(tmp_path, pulls=[_rest_pr(222, branch, sha, **kwargs)])


def _commit(repo: Path, subject: str) -> None:
    (repo / "change.txt").write_text(f"{subject}\n", encoding="utf-8")
    subprocess.run([REAL_GIT, "add", "change.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        [REAL_GIT, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", subject],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _behind_staging(repo: Path) -> None:
    """origin/Staging at the fixture's first commit, so HEAD is ahead and a new PR is created."""
    subprocess.run([REAL_GIT, "update-ref", "refs/remotes/origin/Staging", "HEAD"], cwd=repo, check=True)


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith(("COV_CORE_", "COVERAGE_"))}
    env.pop("L9_L4_LOCAL_AUTONOMY", None)
    env.pop("L9_LOCAL_PUSH_AUTHORIZED", None)
    env.pop("SKIP", None)
    env.pop("GH_REPO", None)
    env.pop("GH_HOST", None)
    env["FAKE_GH_STATE"] = str(tmp_path / "gh-state.json")
    env["FAKE_GH_LOG"] = str(tmp_path / "seq.log")
    env["FAKE_GH_CALLS"] = str(tmp_path / "gh-calls.jsonl")
    env["PATH"] = f"{tmp_path / 'bin'}{os.pathsep}/bin{os.pathsep}/usr/bin"
    if "HOME" not in extra:
        env["HOME"] = str(tmp_path / "gov-home")
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env.pop("INSTALL_SMOKE_GATE", None)
    env.update(extra)
    return env


def _run(repo: Path, tmp_path: Path, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", PIPELINE, "", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=_env(tmp_path, **extra),
        timeout=30,
    )


def _seq(seq: Path) -> str:
    return seq.read_text(encoding="utf-8") if seq.exists() else ""


def _assert_no_push(seq: Path) -> None:
    assert "\npush\n" not in f"\n{_seq(seq)}\n"


def test_feature_to_staging_publishes_after_gates_without_forced_smoke(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    _seed_open_pr(tmp_path, repo)
    proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0", INSTALL_SMOKE_GATE="1")
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output
    text = _seq(seq)
    assert "make PR_CHECK_FORCE_SMOKE=1" not in text
    assert "make PR_CHECK_FORCE_SMOKE=\n" in text or "make PR_CHECK_FORCE_SMOKE=\r\n" in text
    worktree = os.path.realpath(repo)
    governance = os.path.realpath(os.path.expanduser("~/.cursor-governance"))
    workspaces = [line.split("--workspace", 1)[1].strip() for line in text.splitlines() if line.startswith("l4 ")]
    assert workspaces == [worktree, worktree]
    assert governance not in workspaces
    assert text.index("l4 ") < text.rindex("l4 ") < text.index("gitleaks ")
    assert text.index("gitleaks ") < text.index("smoke --resolve") < text.index("make ")
    assert text.index("make ") < text.index("smoke --recheck") < text.index("\npush\n")
    assert "Open PR #222" in output


def test_production_base_refuses_before_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    proc = _run(repo, tmp_path, "fix/example", "Production", "1", "0")
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "destination must be Staging" in output
    _assert_no_push(seq)


def test_staging_to_production_refuses_before_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path, branch="Staging")
    proc = _run(repo, tmp_path, "Staging", "Production", "1", "0")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "destination must be Staging" in (proc.stdout + proc.stderr)
    _assert_no_push(seq)


def test_protected_sources_refuse_before_push(tmp_path: Path) -> None:
    for branch in ("Staging", "Production"):
        repo, seq = _init_repo(tmp_path / branch, branch=branch)
        proc = _run(repo, tmp_path / branch, branch, "Staging", "1", "0")
        output = proc.stdout + proc.stderr
        assert proc.returncode == 1, output
        assert "protected source" in output or "self-PR" in output
        _assert_no_push(seq)


def test_self_pr_and_detached_head_refuse_before_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path / "self", branch="Staging")
    proc = _run(repo, tmp_path / "self", "Staging", "Staging", "1", "0")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    _assert_no_push(seq)

    detached, detached_seq = _init_repo(tmp_path / "detached")
    subprocess.run([REAL_GIT, "checkout", "--detach"], cwd=detached, check=True, capture_output=True)
    proc = _run(detached, tmp_path / "detached", "fix/example", "Staging", "1", "0")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "detached HEAD" in (proc.stdout + proc.stderr)
    _assert_no_push(detached_seq)


def test_dirty_tree_refuses_before_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    (repo / "dirty.txt").write_text("x\n", encoding="utf-8")
    proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "not clean" in (proc.stdout + proc.stderr)
    _assert_no_push(seq)


def test_l4_denial_and_second_check_failure_do_not_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path / "deny")
    denied = _run(repo, tmp_path / "deny", "fix/example", "Staging", "1", "0", L4_RC="2")
    assert denied.returncode == 1, denied.stdout + denied.stderr
    assert "denied release" in (denied.stdout + denied.stderr)
    _assert_no_push(seq)

    repo2, seq2 = _init_repo(tmp_path / "second")
    second = _run(repo2, tmp_path / "second", "fix/example", "Staging", "1", "0", L4_FAIL_CALL="2")
    output = second.stdout + second.stderr
    assert second.returncode == 1, output
    assert "make " not in _seq(seq2)
    _assert_no_push(seq2)


def test_disable_and_breakglass_switches_do_not_invoke_l4_or_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path / "off")
    off = _run(repo, tmp_path / "off", "fix/example", "Staging", "1", "0", L9_L4_LOCAL_AUTONOMY="0")
    assert off.returncode == 1, off.stdout + off.stderr
    assert "not release authorization" in (off.stdout + off.stderr)
    assert not _seq(seq).startswith("l4 ")
    assert "l4 " not in _seq(seq)
    _assert_no_push(seq)

    repo2, seq2 = _init_repo(tmp_path / "glass")
    glass = _run(repo2, tmp_path / "glass", "fix/example", "Staging", "1", "0", L9_LOCAL_PUSH_AUTHORIZED="yes")
    assert glass.returncode == 1, glass.stdout + glass.stderr
    assert "L9_LOCAL_PUSH_AUTHORIZED" in (glass.stdout + glass.stderr)
    assert "l4 " not in _seq(seq2)
    _assert_no_push(seq2)


def test_missing_provider_blocks_without_a_dropbox_fallback(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0", HOME=str(home))
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "L4 provider is not available" in output
    _assert_no_push(seq)
    script = (ROOT / "scripts" / "git_push_with_pr.sh").read_text(encoding="utf-8")
    assert "Dropbox" not in script
    assert "check-remote" in script
    assert "--workspace" in script


def test_missing_gh_auth_and_pr_lookup_refuse_before_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path / "nogh")
    bindir = tmp_path / "nogh" / "bin"
    bindir.joinpath("gh").unlink()
    # Ubuntu merges /bin and /usr/bin, so a PATH that contains /bin still finds gh.
    bindir.joinpath("bash").symlink_to(_real("bash"))
    bindir.joinpath("tr").symlink_to(_real("tr"))
    missing = _run(
        repo,
        tmp_path / "nogh",
        "fix/example",
        "Staging",
        "1",
        "0",
        PATH=str(bindir),
    )
    assert missing.returncode == 1, missing.stdout + missing.stderr
    assert "gh CLI is not available" in (missing.stdout + missing.stderr)
    _assert_no_push(seq)

    repo2, seq2 = _init_repo(tmp_path / "auth")
    unauth = _run(repo2, tmp_path / "auth", "fix/example", "Staging", "1", "0", GH_USER_RC="1")
    assert unauth.returncode == 1
    assert "not authenticated (gh api user failed)" in (unauth.stdout + unauth.stderr)
    _assert_no_push(seq2)
    assert "l4 " not in _seq(seq2)

    repo3, seq3 = _init_repo(tmp_path / "list")
    lookup = _run(repo3, tmp_path / "list", "fix/example", "Staging", "1", "0", GH_LIST_RC="1")
    assert lookup.returncode == 1
    assert "cannot look up pull requests" in (lookup.stdout + lookup.stderr)
    _assert_no_push(seq3)


@pytest.mark.parametrize("fault", ["malformed", "foreign_base_repo"])
def test_malformed_or_foreign_lookup_refuses_before_push(tmp_path: Path, fault: str) -> None:
    repo, seq = _init_repo(tmp_path)
    extra: dict[str, str] = {}
    if fault == "malformed":
        extra["GH_LIST_MALFORMED"] = "1"
    else:
        _seed_open_pr(tmp_path, repo, base_repo="other/repo")
    proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0", **extra)
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "cannot look up pull requests" in output
    assert "l4 " not in _seq(seq)
    _assert_no_push(seq)
    assert [call["method"] for call in _gh_calls(tmp_path)] == ["GET", "GET"]


def test_remote_sha_mismatch_fails_the_push_proof(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    _seed_open_pr(tmp_path, repo)
    proc = _run(
        repo,
        tmp_path,
        "fix/example",
        "Staging",
        "1",
        "0",
        REMOTE_SHA="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef" in output
    assert all(call["method"] == "GET" for call in _gh_calls(tmp_path)), "no PR mutation after a failed push proof"


def test_direct_push_to_a_protected_branch_refuses(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    proc = subprocess.run(
        ["bash", PUSH, "Production"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=_env(tmp_path),
        timeout=30,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "protected branch" in (proc.stdout + proc.stderr)
    _assert_no_push(seq)


def test_open_pr_refuses_a_non_staging_base(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    proc = subprocess.run(
        ["bash", "scripts/git_open_pr.sh", "fix/example", "Production"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=_env(tmp_path),
        timeout=30,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "destination must be Staging" in (proc.stdout + proc.stderr)
    assert _seq(seq) == ""


def test_pr_check_reuses_live_evidence_not_a_source_hash() -> None:
    text = (ROOT / "scripts" / "pr_check_run.sh").read_text(encoding="utf-8")
    assert "smoke_fingerprint" not in text
    assert "--recheck" in text
    assert "install-smoke.sha" not in text


def test_api_push_and_autopilot_do_not_publish() -> None:
    proc = subprocess.run(
        [REAL_PYTHON, str(ROOT / "scripts" / "api_push.py")], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 1
    assert "only publication ceremony is make pr" in proc.stdout
    sys.path.insert(0, str(ROOT / "scripts"))
    from pr_autopilot import atomic_push

    assert atomic_push("fix/example", "fix: local only") is False


def test_remote_feedback_trusts_ssl_cert_file_over_certifi(tmp_path: Path) -> None:
    """pr-remote-feedback must honour SSL_CERT_FILE, or a TLS-intercepting egress proxy blocks make pr."""
    bundle = tmp_path / "proxy-ca.pem"
    bundle.write_text("", encoding="utf-8")
    probe = "import sys; sys.path.insert(0, 'scripts'); import pr_autopilot; print(pr_autopilot._SSL_CAFILE)"
    env = {key: value for key, value in os.environ.items() if key != "SSL_CERT_FILE"}
    pinned = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        env={**env, "SSL_CERT_FILE": str(bundle)},
        capture_output=True,
        text=True,
    )
    assert pinned.returncode == 0, pinned.stderr
    assert pinned.stdout.strip() == str(bundle)
    default = subprocess.run([sys.executable, "-c", probe], cwd=ROOT, env=env, capture_output=True, text=True)
    assert default.returncode == 0, default.stderr
    assert default.stdout.strip() != str(bundle)


def _push(repo: Path, tmp_path: Path, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", PUSH, *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=_env(tmp_path, **extra),
        timeout=30,
    )


def test_full_install_is_optional_and_resolve_still_runs(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    proc = _push(repo, tmp_path, "fix/example")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    text = _seq(seq)
    assert text.index("smoke --resolve") < text.index("make ") < text.index("\npush\n")
    assert "smoke --recheck" not in text


def test_direct_push_runs_the_gates_before_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    proc = _push(repo, tmp_path, "fix/example", INSTALL_SMOKE_GATE="1")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    text = _seq(seq)
    assert text.index("gitleaks ") < text.index("smoke --resolve") < text.index("make ")
    assert text.index("make ") < text.index("smoke --recheck") < text.index("\npush\n")


def test_failed_or_missing_gitleaks_does_not_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path / "fail")
    failed = _push(repo, tmp_path / "fail", "fix/example", GITLEAKS_RC="2")
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert "gitleaks detect failed" in (failed.stdout + failed.stderr)
    _assert_no_push(seq)

    repo2, seq2 = _init_repo(tmp_path / "missing")
    (tmp_path / "missing" / "bin" / "gitleaks").unlink()
    missing = _push(repo2, tmp_path / "missing", "fix/example")
    assert missing.returncode == 1, missing.stdout + missing.stderr
    assert "gitleaks is not on PATH" in (missing.stdout + missing.stderr)
    _assert_no_push(seq2)


def _bare_remote(tmp_path: Path, repo: Path, branch: str = "fix/example") -> tuple[Path, str]:
    """A real local remote already holding the current commit; the repo then moves one commit ahead."""
    bare = tmp_path / "remote.git"
    subprocess.run([REAL_GIT, "init", "--bare", str(bare)], check=True, capture_output=True)
    subprocess.run(
        [REAL_GIT, "-C", str(bare), "fetch", str(repo), f"{branch}:refs/heads/{branch}"],
        check=True,
        capture_output=True,
    )
    seeded = _remote_sha(bare, branch)
    (repo / "change.txt").write_text("next\n", encoding="utf-8")
    subprocess.run([REAL_GIT, "add", "change.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        [REAL_GIT, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "next"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return bare, seeded


def _remote_sha(bare: Path, branch: str = "fix/example") -> str:
    return subprocess.check_output(
        [REAL_GIT, "--git-dir", str(bare), "rev-parse", f"refs/heads/{branch}"], text=True
    ).strip()


def _head(repo: Path) -> str:
    return subprocess.check_output([REAL_GIT, "rev-parse", "HEAD"], cwd=repo, text=True).strip()


def _hook_runs(seq: Path) -> int:
    return sum(1 for line in _seq(seq).splitlines() if line.startswith("pre-push "))


@pytest.mark.parametrize("entry", ["make_pr", "direct"])
def test_rejecting_pre_push_hook_stops_publication(tmp_path: Path, entry: str) -> None:
    repo, seq = _init_repo(tmp_path)
    bare, seeded = _bare_remote(tmp_path, repo)
    _seed_open_pr(tmp_path, repo)
    env = {"REAL_REMOTE": str(bare), "PRE_PUSH_RC": "1"}
    if entry == "make_pr":
        proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0", **env)
    else:
        proc = _push(repo, tmp_path, "fix/example", **env)
    output = proc.stdout + proc.stderr
    assert proc.returncode != 0, output
    assert _hook_runs(seq) == 1, "the real pre-push hook must run on the push"
    assert _remote_sha(bare) == seeded, "a rejecting pre-push hook let the remote ref advance"
    assert "Open PR" not in output
    assert "gh " not in _seq(seq).split("pre-push ", 1)[1], "no GitHub API call after a rejected push"
    assert all(call["method"] == "GET" for call in _gh_calls(tmp_path))


@pytest.mark.parametrize("entry", ["make_pr", "direct"])
def test_accepting_pre_push_hook_runs_once_and_publishes_validated_head(tmp_path: Path, entry: str) -> None:
    repo, seq = _init_repo(tmp_path)
    bare, seeded = _bare_remote(tmp_path, repo)
    _seed_open_pr(tmp_path, repo)
    env = {"REAL_REMOTE": str(bare), "INSTALL_SMOKE_GATE": "1"}
    if entry == "make_pr":
        proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0", **env)
    else:
        proc = _push(repo, tmp_path, "fix/example", **env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _hook_runs(seq) == 1
    assert _remote_sha(bare) == _head(repo) != seeded
    text = _seq(seq)
    assert text.index("make ") < text.index("smoke --recheck") < text.index("pre-push ")


@pytest.mark.parametrize(
    "disable",
    ["missing", "not_executable", "hooks_path_dev_null", "foreign_hook", "skip_on_missing_config", "skip_env"],
)
def test_missing_or_disabled_pre_push_enforcement_refuses_before_validation(tmp_path: Path, disable: str) -> None:
    repo, seq = _init_repo(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-push"
    extra: dict[str, str] = {}
    if disable == "missing":
        hook.unlink()
    elif disable == "not_executable":
        hook.chmod(0o644)
    elif disable == "hooks_path_dev_null":
        subprocess.run([REAL_GIT, "config", "core.hooksPath", "/dev/null"], cwd=repo, check=True)
    elif disable == "foreign_hook":
        _write(hook, "#!/bin/bash\nexit 0\n")
    elif disable == "skip_on_missing_config":
        _write(hook, _pre_push_hook(seq, args_line=PRE_COMMIT_ARGS[:-1] + " --skip-on-missing-config)"))
    else:
        extra["SKIP"] = "gitleaks-push"
    proc = _push(repo, tmp_path, "fix/example", **extra)
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "refusing to publish" in output
    _assert_no_push(seq)
    text = _seq(seq)
    assert "make " not in text and "gitleaks " not in text, "refuse before validation, not after"


def test_bad_origin_and_skip_switches_refuse(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path / "url")
    subprocess.run(
        [REAL_GIT, "remote", "set-url", "--push", "origin", "https://github.com/cryptoxdog/IB-Odoo_19.git"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        [REAL_GIT, "remote", "set-url", "--add", "--push", "origin", "https://github.com/other/repo.git"],
        cwd=repo,
        check=True,
    )
    multi = _push(repo, tmp_path / "url", "fix/example")
    assert multi.returncode == 1, multi.stdout + multi.stderr
    assert "exactly one push URL" in (multi.stdout + multi.stderr)
    _assert_no_push(seq)

    repo2, seq2 = _init_repo(tmp_path / "foreign")
    subprocess.run(
        [REAL_GIT, "remote", "set-url", "origin", "https://github.com/other/repo.git"],
        cwd=repo2,
        check=True,
    )
    foreign = _push(repo2, tmp_path / "foreign", "fix/example")
    assert foreign.returncode == 1
    assert "not cryptoxdog/IB-Odoo_19" in (foreign.stdout + foreign.stderr)
    _assert_no_push(seq2)

    repo3, seq3 = _init_repo(tmp_path / "skip")
    skipped = _push(repo3, tmp_path / "skip", "fix/example", PR_CHECK_SKIP_SMOKE="1")
    assert skipped.returncode == 1
    assert "PR_CHECK_SKIP_SMOKE" in (skipped.stdout + skipped.stderr)
    _assert_no_push(seq3)


def test_operator_smoke_bypass_skips_only_the_smoke_recheck(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    proc = _push(repo, tmp_path, "fix/example", PR_SMOKE_BYPASS="docs-only change")
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output
    assert "install-smoke BYPASSED by operator: docs-only change" in output
    text = _seq(seq)
    assert text.index("gitleaks ") < text.index("make ") < text.index("\npush\n")
    assert "smoke --recheck" not in text

    repo2, seq2 = _init_repo(tmp_path / "blank")
    blank = _push(repo2, tmp_path / "blank", "fix/example", PR_SMOKE_BYPASS="  ", PR_CHECK_SKIP_SMOKE="1")
    assert blank.returncode == 1
    assert "PR_CHECK_SKIP_SMOKE" in (blank.stdout + blank.stderr)
    _assert_no_push(seq2)


def test_scope_receipt_without_smoke_inputs_skips_only_the_recheck(tmp_path: Path) -> None:
    # make pr-check (faked here) leaves .cache/pr-check/scope.json; a change that
    # reached no addon or installer input publishes without the Docker recheck.
    repo, seq = _init_repo(tmp_path)
    (repo / ".cache" / "pr-check").mkdir(parents=True)
    _write(repo / ".cache" / "pr-check" / "scope.json", json.dumps({"schema": "l9.pr-check-scope.v1", "smoke": 0}))
    proc = _push(repo, tmp_path, "fix/example")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    text = _seq(seq)
    assert text.index("smoke --resolve") < text.index("make ") < text.index("\npush\n")
    assert "smoke --recheck" not in text
    for name, receipt in (("needed", '{"smoke": 1}'), ("broken", "not json")):
        repo2, seq2 = _init_repo(tmp_path / name)
        (repo2 / ".cache" / "pr-check").mkdir(parents=True)
        _write(repo2 / ".cache" / "pr-check" / "scope.json", receipt)
        assert _push(repo2, tmp_path / name, "fix/example", INSTALL_SMOKE_GATE="1").returncode == 0
        assert "smoke --recheck" in _seq(seq2), "RECHECK: with the gate on, only an explicit smoke=0 receipt skips it"


def test_worktree_change_after_validation_does_not_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    proc = _push(repo, tmp_path, "fix/example", MAKE_DIRTY="1")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "changed during validation" in (proc.stdout + proc.stderr)
    _assert_no_push(seq)


def _open_pr(repo: Path, tmp_path: Path, *extra_args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/git_open_pr.sh", "fix/example", "Staging", *extra_args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=_env(tmp_path, **extra),
        timeout=30,
    )


def test_reused_pr_keeps_its_body_and_gains_the_stamp(tmp_path: Path) -> None:
    repo, _seq_path = _init_repo(tmp_path)
    _seed_open_pr(tmp_path, repo, body="Human notes stay.\n")
    proc = _open_pr(repo, tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    saved = _gh_state(tmp_path)["pulls"][0]["body"]
    assert saved.startswith("Human notes stay.")
    assert saved.count("<!-- L9_PROTECTED_ROOT_PR -->") == 1
    patches = [call for call in _gh_calls(tmp_path) if call["method"] == "PATCH"]
    assert [call["path"] for call in patches] == [f"repos/{REPO}/pulls/222"]
    assert set(patches[0]["fields"]) == {"body"}
    again = _open_pr(repo, tmp_path)
    assert again.returncode == 0, again.stdout + again.stderr
    assert _gh_state(tmp_path)["pulls"][0]["body"].count("<!-- L9_PROTECTED_ROOT_PR -->") == 1
    assert len([call for call in _gh_calls(tmp_path) if call["method"] == "PATCH"]) == 1, "no second stamp write"


def test_cloud_surface_publishes_over_rest_when_gh_auth_status_fails(tmp_path: Path) -> None:
    """`gh auth status` and every GraphQL-backed form fail; `gh api user` works. make pr still publishes."""
    repo, seq = _init_repo(tmp_path)
    _behind_staging(repo)
    _commit(repo, "fix: cloud publication")
    _set_gh_state(tmp_path, labels=["bug"])
    status = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, env=_env(tmp_path), check=False)
    assert status.returncode == 1, "the fixture must model the cloud surface"
    proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0")
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output
    text = _seq(seq)
    assert "gh FORBIDDEN" not in text.replace("gh FORBIDDEN auth status\n", "", 1)
    assert "PR created → Staging: https://github.com/cryptoxdog/IB-Odoo_19/pull/300" in output
    calls = _gh_calls(tmp_path)
    assert [(call["method"], call["path"]) for call in calls] == [
        ("GET", "user"),
        ("GET", f"repos/{REPO}/pulls"),
        ("GET", "user"),
        ("GET", f"repos/{REPO}/pulls"),
        ("POST", f"repos/{REPO}/pulls"),
        ("GET", f"repos/{REPO}/labels"),
        ("POST", f"repos/{REPO}/issues/300/labels"),
    ]
    assert calls[1]["params"] == {"state": "open", "base": "Staging", "head": "cryptoxdog:fix/example"}
    create = calls[4]
    assert create["fields"]["base"] == "Staging"
    assert create["fields"]["head"] == "fix/example"
    assert create["fields"]["title"] == "fix: cloud publication"
    assert create["fields"]["body"].count("<!-- L9_PROTECTED_ROOT_PR -->") == 1
    assert calls[6]["fields"] == {"labels": ["bug"]}
    assert text.index("\npush\n") < text.index(f"gh POST repos/{REPO}/pulls")
    assert _gh_state(tmp_path)["pulls"][0]["head"]["sha"] == _head(repo)


def test_unset_gh_repo_binds_origin_and_reaches_every_child(tmp_path: Path) -> None:
    repo, _seq_path = _init_repo(tmp_path)
    _behind_staging(repo)
    _commit(repo, "fix: propagate repository")
    _set_gh_state(tmp_path, labels=["bug"])
    proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    calls = _gh_calls(tmp_path)
    assert calls[-1]["path"] == f"repos/{REPO}/issues/300/labels", "apply_pr_kernel_metadata.sh must run"
    assert {call["gh_repo"] for call in calls} == {REPO}
    assert {call["gh_host"] for call in calls} == {"github.com"}


def test_matching_gh_repo_publishes(tmp_path: Path) -> None:
    repo, _seq_path = _init_repo(tmp_path)
    _seed_open_pr(tmp_path, repo)
    proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0", GH_REPO=REPO)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Open PR #222" in proc.stdout


@pytest.mark.parametrize("entry", ["make_pr", "open_pr"])
def test_foreign_gh_repo_refuses_before_any_api_call(tmp_path: Path, entry: str) -> None:
    repo, seq = _init_repo(tmp_path)
    _seed_open_pr(tmp_path, repo)
    if entry == "make_pr":
        proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0", GH_REPO="other/repo")
    else:
        proc = _open_pr(repo, tmp_path, GH_REPO="other/repo")
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "GH_REPO=other/repo is not the origin repository cryptoxdog/IB-Odoo_19" in output
    assert _gh_calls(tmp_path) == []
    assert "l4 " not in _seq(seq)
    _assert_no_push(seq)


@pytest.mark.parametrize("entry", ["make_pr", "open_pr"])
def test_foreign_gh_host_refuses_before_any_api_call(tmp_path: Path, entry: str) -> None:
    """`gh api repos/...` follows GH_HOST, not origin; an Enterprise host must not receive these calls."""
    repo, seq = _init_repo(tmp_path)
    _seed_open_pr(tmp_path, repo)
    host = "github.example.com"
    if entry == "make_pr":
        proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0", GH_HOST=host)
    else:
        proc = _open_pr(repo, tmp_path, GH_HOST=host)
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert f"GH_HOST={host} is not the origin host github.com" in output
    assert _gh_calls(tmp_path) == []
    assert "l4 " not in _seq(seq)
    _assert_no_push(seq)


def test_github_com_gh_host_publishes(tmp_path: Path) -> None:
    repo, _seq_path = _init_repo(tmp_path)
    _seed_open_pr(tmp_path, repo)
    proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0", GH_HOST="github.com")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert {call["gh_host"] for call in _gh_calls(tmp_path)} == {"github.com"}


@pytest.mark.parametrize("entry", ["make_pr", "open_pr"])
@pytest.mark.parametrize("origin", ["foreign", "two_push_urls"])
def test_unauthorized_origin_refuses_before_any_api_call(tmp_path: Path, entry: str, origin: str) -> None:
    repo, seq = _init_repo(tmp_path)
    if origin == "foreign":
        subprocess.run([REAL_GIT, "remote", "set-url", "origin", "git@github.com:other/repo.git"], cwd=repo, check=True)
    else:
        for url in ("https://github.com/cryptoxdog/IB-Odoo_19.git", "https://github.com/other/repo.git"):
            subprocess.run([REAL_GIT, "remote", "set-url", "--add", "--push", "origin", url], cwd=repo, check=True)
    proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0") if entry == "make_pr" else _open_pr(repo, tmp_path)
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "not cryptoxdog/IB-Odoo_19" in output or "exactly one push URL" in output
    assert _gh_calls(tmp_path) == []
    _assert_no_push(seq)


@pytest.mark.parametrize(
    "authorized",
    [
        "https://github.com/cryptoxdog/IB-Odoo_19",
        "git@github.com:cryptoxdog/IB-Odoo_19.git",
        "ssh://git@github.com/cryptoxdog/IB-Odoo_19.git",
    ],
)
def test_authorized_origin_forms_bind_the_repository(tmp_path: Path, authorized: str) -> None:
    repo, _seq_path = _init_repo(tmp_path)
    subprocess.run([REAL_GIT, "remote", "set-url", "origin", authorized], cwd=repo, check=True)
    _seed_open_pr(tmp_path, repo)
    proc = _open_pr(repo, tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert {call["gh_repo"] for call in _gh_calls(tmp_path)} == {REPO}


@pytest.mark.parametrize("fault", ["fork_head", "wrong_branch"])
def test_reused_pr_proof_refuses_the_wrong_head(tmp_path: Path, fault: str) -> None:
    repo, _seq_path = _init_repo(tmp_path)
    # The lookup filter matches; the payload itself names the wrong head.
    pr = _rest_pr(222, "fix/example", _head(repo))
    if fault == "fork_head":
        pr["head"]["repo"]["full_name"] = "someone/IB-Odoo_19"
    else:
        pr["head"]["ref"] = "fix/other"
    _set_gh_state(tmp_path, pulls=[pr])
    proc = _open_pr(repo, tmp_path)
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "PR publication proof failed" in output
    assert ("head repository is someone/IB-Odoo_19" if fault == "fork_head" else "head branch is fix/other") in output
    assert not [call for call in _gh_calls(tmp_path) if call["method"] != "GET"]


def test_created_pr_with_a_different_head_sha_reports_partial_publication(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    _behind_staging(repo)
    _commit(repo, "fix: proof")
    _set_gh_state(tmp_path, branches={"fix/example": "0" * 40})
    proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0")
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert f"head SHA is {'0' * 40}, expected {_head(repo)}" in output
    assert f"partial publication: origin/fix/example was pushed at {_head(repo)}" in output
    assert "\npush\n" in f"\n{_seq(seq)}\n"


def test_create_denied_after_push_reports_partial_publication(tmp_path: Path) -> None:
    repo, _seq_path = _init_repo(tmp_path)
    _behind_staging(repo)
    _commit(repo, "fix: denied")
    proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0", GH_CREATE_RC="1")
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "pull request creation failed" in output
    assert "partial publication" in output
    assert _gh_state(tmp_path)["pulls"] == []


def test_labels_use_rest_skip_unknown_and_never_fail_publication(tmp_path: Path) -> None:
    repo, _seq_path = _init_repo(tmp_path / "unknown")
    _commit(repo, "fix: no such label")
    _seed_open_pr(tmp_path / "unknown", repo)
    skipped = _open_pr(repo, tmp_path / "unknown")
    assert skipped.returncode == 0, skipped.stdout + skipped.stderr
    assert not [
        call
        for call in _gh_calls(tmp_path / "unknown")
        if call["path"].endswith("/labels") and call["method"] == "POST"
    ]

    repo2, _seq2 = _init_repo(tmp_path / "denied")
    _commit(repo2, "fix: labels denied")
    _seed_open_pr(tmp_path / "denied", repo2)
    _set_gh_state(tmp_path / "denied", labels=["bug"])
    denied = _open_pr(repo2, tmp_path / "denied", GH_LABEL_RC="1")
    assert denied.returncode == 0, denied.stdout + denied.stderr
    assert _gh_state(tmp_path / "denied")["pulls"][0]["labels"] == []


def test_operator_smoke_bypass_note_is_a_rest_comment(tmp_path: Path) -> None:
    repo, _seq_path = _init_repo(tmp_path / "ok")
    _seed_open_pr(tmp_path / "ok", repo)
    proc = _run(repo, tmp_path / "ok", "fix/example", "Staging", "1", "0", PR_SMOKE_BYPASS="docs-only change")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    comments = _gh_state(tmp_path / "ok")["comments"]
    assert comments == [
        {
            "issue": 222,
            "body": f"Local Odoo install-smoke was bypassed for {_head(repo)} by the operator: docs-only change",
        }
    ]

    repo2, _seq2 = _init_repo(tmp_path / "denied")
    _seed_open_pr(tmp_path / "denied", repo2)
    denied = _run(
        repo2, tmp_path / "denied", "fix/example", "Staging", "1", "0", PR_SMOKE_BYPASS="docs-only", GH_COMMENT_RC="1"
    )
    assert denied.returncode == 0, denied.stdout + denied.stderr
    assert "warning: could not post the install-smoke bypass note on the PR" in denied.stderr


def test_production_scripts_never_call_graphql_backed_gh() -> None:
    import re

    # `gh` in command position (line start, after ! ; & | ( $( or a shell keyword), not inside an echo'd hint.
    pattern = re.compile(
        r"(^|[!;&|(]|\$\(|\b(?:if|then|else|do|while|until)\s)\s*gh\s+(auth|pr|label|repo|issue|api\s+graphql)\b"
    )
    for name in PRODUCTION_SCRIPTS:
        for number, line in enumerate((ROOT / "scripts" / name).read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            assert not pattern.search(line.strip()), f"{name}:{number}: {line.strip()}"


def test_real_gitleaks_rejects_a_seeded_secret(tmp_path: Path) -> None:
    if shutil.which("gitleaks") is None:
        pytest.skip("gitleaks is not installed in this job; the push script refuses a missing binary")
    repo = tmp_path / "scan"
    repo.mkdir()
    shutil.copy(ROOT / ".gitleaks.toml", repo / ".gitleaks.toml")
    token = "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"
    (repo / "secret.txt").write_text(f"token={token}\n", encoding="utf-8")
    proc = subprocess.run(
        ["gitleaks", "detect", "--config", ".gitleaks.toml", "--redact", "--exit-code", "2", "--no-git"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
