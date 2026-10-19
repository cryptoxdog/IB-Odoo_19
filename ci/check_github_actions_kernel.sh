#!/usr/bin/env bash
# GitHub Actions Kernel gate (github_actions_kernel.v1)
# DORA R5 | developer_support
# Checks: triggers, permissions, secrets_handling, job_dependencies (YAML parse),
#         third-party action SHA pins, hard_bans (no secrets, no wildcard permissions)
#
# Usage:
#   ci/check_github_actions_kernel.sh              # all workflow files
#   ci/check_github_actions_kernel.sh --staged     # git-index paths only (make commit)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAGED_ONLY=0
if [[ "${1:-}" == "--staged" ]]; then
    STAGED_ONLY=1
fi

collect_files() {
    if [[ "$STAGED_ONLY" -eq 1 ]]; then
        git diff --cached --name-only --diff-filter=ACMR -- '.github/workflows/*.yml' '.github/workflows/*.yaml' 2>/dev/null || true
    else
        find .github/workflows -maxdepth 1 \( -name '*.yml' -o -name '*.yaml' \) 2>/dev/null | sort || true
    fi
}

FILES=()
while IFS= read -r line; do
    [[ -n "$line" ]] && FILES+=("$line")
done < <(collect_files)

if [[ ${#FILES[@]} -eq 0 ]]; then
    exit 0
fi

echo "→ GitHub Actions kernel check (github_actions_kernel.v1)..."
FAIL=0
RESULTS=()

fail() {
    RESULTS+=("❌ $1")
    FAIL=1
}

pass() {
    RESULTS+=("✅ $1")
}

for f in "${FILES[@]}"; do
    [[ -f "$f" ]] || continue
    base="$(basename "$f")"

    # Event keys are checked structurally below, not as source-text substrings.

    # hard_ban — wildcard permissions
    if grep -qE 'write-all|read-all|permissions:[[:space:]]*\*' "$f"; then
        fail "$base: wildcard permissions forbidden (write-all/read-all/*)"
    else
        pass "$base: permissions (no wildcards)"
    fi

    # secrets_handling — hardcoded secret patterns
    if grep -qE 'ghp_[A-Za-z0-9]+|gho_[A-Za-z0-9]+|github_pat_[A-Za-z0-9]+|sk-[A-Za-z0-9]{20,}' "$f"; then
        fail "$base: possible hardcoded secret/token in workflow"
    else
        pass "$base: secrets_handling (no inline tokens)"
    fi

    # caching / job graph / merge gates — YAML must parse (structural sanity)
    if python3 -c "
import sys, yaml
from pathlib import Path
p = Path('$f')
try:
    data = yaml.safe_load(p.read_text())
except Exception as e:
    print(f'YAML parse error: {e}', file=sys.stderr)
    sys.exit(1)
if not isinstance(data, dict):
    print('Workflow root must be a mapping', file=sys.stderr)
    sys.exit(1)
if 'on' not in data and True not in data:
    print('Workflow must declare events', file=sys.stderr)
    sys.exit(1)
jobs = data.get('jobs') or {}
if jobs and not isinstance(jobs, dict):
    print('jobs: must be a mapping', file=sys.stderr)
    sys.exit(1)
for job_id, job in (jobs or {}).items():
    needs = job.get('needs')
    if needs is None:
        continue
    need_list = [needs] if isinstance(needs, str) else list(needs)
    for dep in need_list:
        if dep not in jobs:
            print(f'job {job_id} needs unknown job {dep}', file=sys.stderr)
            sys.exit(1)
sys.exit(0)
"; then
        pass "$base: job_dependencies + YAML valid"
    else
        fail "$base: YAML/job_dependencies invalid"
    fi

    # Third-party actions — mutable tags forbidden (actions/* exempt per 86-ci-github-actions)
    if grep -E '^[[:space:]]*- uses:' "$f" | grep -vE 'uses:[[:space:]]+actions/' | grep -qE '@(v[0-9]+[^[:space:]]*|main|master|latest)[[:space:]]*(#|$)'; then
        fail "$base: third-party action uses mutable tag (@vN/@main) — pin SHA"
    else
        pass "$base: third-party actions SHA-pinned or actions/* only"
    fi

    # merge_gate_logic — every mandatory ci.yml Phase 1 job must exist and run in
    # parallel (no needs:, so one push surfaces every failing check at once); an
    # aggregator job must gate on ALL of them with if: always() as the single
    # fail-closed verdict. Keep `required` equal to ci.yml's Phase 1 inventory.
    # A structurally present aggregator is not enough: it must also be
    # fail-closed — no continue-on-error (job or step), and its run script must
    # compare needs.<job>.result != success for every required job and exit
    # non-zero. ci.yml must also run this kernel in static-checks, so the
    # invariant is enforced by CI, not only by local `make commit`.
    if [[ "$base" == "ci.yml" ]]; then
        if python3 - "$f" <<'PY'
import re, shlex, sys, yaml
from pathlib import Path
data = yaml.safe_load(Path(sys.argv[1]).read_text())
jobs = data.get('jobs') or {}
required = {'lint', 'static-checks', 'pure-python-tests', 'gate-sdk-tests', 'secret-scan', 'audit-baseline'}
missing = required - jobs.keys()
if missing:
    print(f'missing required jobs: {missing}', file=sys.stderr)
    sys.exit(1)
for j in required:
    if jobs[j].get('needs'):
        print(f'{j} must not have needs: (Phase 1 must stay parallel)', file=sys.stderr)
        sys.exit(1)

def fail_open(v):
    # continue-on-error: anything but absent/false (incl. expressions) can mask failure
    return v is not None and v is not False and str(v).strip().lower() != 'false'

def fail_closed_problems(job):
    problems = []
    if fail_open(job.get('continue-on-error')):
        problems.append('job has continue-on-error')
    steps = job.get('steps') or []
    if any(fail_open(s.get('continue-on-error')) for s in steps):
        problems.append('a step has continue-on-error')
    scripts = [str(s.get('run') or '') for s in steps if s.get('run')]
    if len(scripts) != 1:
        problems.append('aggregator must have exactly one executable run step')
        return problems
    # Gate-result shell is deliberately a tiny language: echo diagnostics,
    # one OR of all six actual status checks, unconditional exit 1, then echo.
    # Grepping substrings is unsafe: comments and dead code can fake compliance.
    lines = [line.strip() for line in scripts[0].replace('\\\n', ' ').splitlines()
             if line.strip() and not line.lstrip().startswith('#')]
    starts = [i for i, line in enumerate(lines) if line.startswith('if ')]
    if len(starts) != 1:
        problems.append('aggregator requires one executable fail-closed if')
        return problems
    pos = starts[0]
    atom = r'\[\s*"\$\{\{\s*needs\.([a-z0-9-]+)\.result\s*\}\}"\s*!=\s*"success"\s*\]'
    names = re.findall(atom, lines[pos])
    shape = re.sub(atom, '@', lines[pos])
    if len(names) != len(required) or set(names) != required or not re.fullmatch(
        r'if\s+@(?:\s*\|\|\s*@){5}\s*;\s*then', shape
    ):
        problems.append('aggregator must OR every actual needs result against success')
    if lines[pos + 1:pos + 4] != [
        'echo "::error::One or more CI Gate jobs failed — see the job that reported ❌ above."',
        'exit 1',
        'fi',
    ]:
        problems.append('aggregator failure branch must unconditionally exit 1')
    def safe_echo(line):
        if not line.startswith('echo "') or not line.endswith('"'):
            return False
        content = line[6:-1]
        content = re.sub(r'\$\{\{\s*needs\.[a-z0-9-]+\.result\s*\}\}', '', content)
        return not any(char in content for char in ('$', '`', '\\', '"'))
    for line in lines[:pos] + lines[pos + 4:]:
        if not safe_echo(line):
            problems.append('aggregator contains executable code outside the verified gate')
            break
    return problems

candidates = []
for job_id, job in jobs.items():
    needs = job.get('needs')
    if not needs:
        continue
    need_set = set([needs] if isinstance(needs, str) else needs)
    if required.issubset(need_set) and job.get('if') == 'always()':
        candidates.append(job_id)
if not candidates:
    print(f'no aggregator job found (needs: must cover ALL of {sorted(required)} + if: always())', file=sys.stderr)
    sys.exit(1)
reports = {c: fail_closed_problems(jobs[c]) for c in candidates}
if not any(not p for p in reports.values()):
    for c, p in reports.items():
        print(f'aggregator {c} is fail-open: {p}', file=sys.stderr)
    sys.exit(1)
static_run = '\n'.join(str(s.get('run') or '') for s in (jobs['static-checks'].get('steps') or []))
if not re.search(r'run_check\b[^\n]*check_github_actions_kernel\.sh', static_run):
    print('static-checks must run ci/check_github_actions_kernel.sh via run_check (blocking)', file=sys.stderr)
    sys.exit(1)

# Read YAML structure rather than looking for strings that could be comments.
events = data.get('on', data.get(True))
if not isinstance(events, dict) or set(events) != {'push', 'pull_request', 'workflow_dispatch'}:
    raise SystemExit('CI events: expected push, pull_request and workflow_dispatch only')
push = events.get('push')
if not isinstance(push, dict) or push != {'branches': ['Staging', 'Production']}:
    raise SystemExit('CI events: feature pushes must not duplicate pull-request CI')
if events.get('pull_request') not in (None, {}):
    raise SystemExit('CI events: pull_request must retain opened/synchronize/reopened without filters')

job = jobs['pure-python-tests']
if 'if' in job or fail_open(job.get('continue-on-error')):
    raise SystemExit('pure-python-tests must run unconditionally and fail closed')
if str((job.get('env') or {}).get('PLASTICOS_CONTRACT_CI')) != '1':
    raise SystemExit('pure-python-tests must enforce mandatory contract execution')
steps = job.get('steps') or []
selected = [step for step in steps if step.get('id') == 'pure-tests']
if len(selected) != 1:
    raise SystemExit('exactly one pure-tests step must own the complete pytest invocation')
step = selected[0]
if 'if' in step or fail_open(step.get('continue-on-error')) or step.get('working-directory'):
    raise SystemExit('pure-tests must not be conditional, masked, or moved out of the repository root')
for env in (data.get('env') or {}, job.get('env') or {}, step.get('env') or {}):
    if any(key in env for key in ('PYTEST_ADDOPTS', 'PYTEST_PLUGINS', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD',
                                 'PLASTICOS_SMOKE_SOURCE')):
        raise SystemExit('pytest runtime selection/plugin overrides require explicit review')
if (step.get('env') or {}).get('PLASTICOS_CONTRACT_CI', '1') != '1':
    raise SystemExit('pure-tests cannot disable mandatory contracts')
# This owner intentionally admits one simple invocation, not arbitrary shell control flow.
script = str(step.get('run') or '').replace('\\\n', ' ')
tokens = shlex.split(script, comments=True)
expected = ['python3', '-m', 'pytest', 'tests/', '-v', '--cov=.',
            '--cov-report=term-missing:skip-covered', '--junitxml=artifacts/pytest/pure-python.xml']
if tokens != expected:
    raise SystemExit('pure-tests must execute the full tests/ tier once; filtering or failure masking is forbidden')
if sum(len(re.findall(r'(?m)^\s*python3\s+-m\s+pytest\b', str(s.get('run') or ''))) for s in steps) != 1:
    raise SystemExit('the pure-Python job must not duplicate pytest execution')
reports = [step for step in steps if str(step.get('uses') or '').startswith('actions/upload-artifact@')]
if not any(step.get('if') == 'always()' and (step.get('with') or {}).get('path') == 'artifacts/pytest/'
           and (step.get('with') or {}).get('if-no-files-found') == 'error' for step in reports):
    raise SystemExit('pure-python-tests must retain JUnit evidence even when tests fail')
sys.exit(0)
PY
        then
            pass "$base: merge_gate_logic (fail-slow parallel Phase 1 + fail-closed aggregator + kernel enforced in CI)"
        else
            fail "$base: ci.yml must run every Phase 1 job (lint/static-checks/pure-python-tests/gate-sdk-tests/secret-scan/audit-baseline) in parallel (no needs:) with a fail-closed aggregator (needs: all of them + if: always(), no continue-on-error, compares each needs.<job>.result != success and exits non-zero) and must run this kernel in static-checks"
        fi
    fi
done

echo ""
for r in "${RESULTS[@]}"; do
    echo "  $r"
done
echo ""

if [[ $FAIL -ne 0 ]]; then
    echo "❌ GitHub Actions kernel check FAILED"
    echo "   Kernel: github_actions_kernel.v1 | hard_bans: no secrets, no wildcard permissions"
    exit 1
fi

echo "✅ GitHub Actions kernel check passed (${#FILES[@]} workflow file(s))"
exit 0
