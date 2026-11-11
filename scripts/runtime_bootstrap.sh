#!/usr/bin/env bash
# Prepare this machine for the Odoo Enterprise runtime gate.
#
# A cloud agent session has Docker but no Odoo Enterprise source, so the
# install-smoke and runtime tests in the make pr-check smoke stage could not run
# there. This script binds an Enterprise checkout and admits the pinned fixture
# named in config/test_env_fixture.conf. It runs no Odoo tests. The runtime-test
# owners are unchanged: the make pr-check smoke stage and l9-pr-integration-testing.
#
# Enterprise checkout, first match wins:
#   1. ODOO_ENTERPRISE_PATH, when set (the same variable scripts/test_env.sh reads)
#   2. ./odoo-enterprise (a directory or symlink; git-ignored)
#   3. ../odoo-enterprise, a sibling checkout. A cloud session clones each attached
#      repository next to this one; it is linked as ./odoo-enterprise.
#   4. a shallow clone of ODOO_ENTERPRISE_REPO (owner/name or a git URL) into
#      ./odoo-enterprise, at ODOO_ENTERPRISE_REF when set, else its default branch
# There is no default repository: the Enterprise source is licensed and private.
#
# Fixture: scripts/test_env.sh status decides. A ready template is reused. An
# absent template is admitted through scripts/test_env.sh rebuild, the same path
# as make test-env-rebuild. A template that exists but is not admitted for the
# current inputs is left alone; recovering it is an operator decision.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "❌ runtime-bootstrap: run inside the IB-Odoo_19 checkout" >&2
  exit 2
}
cd "$ROOT"

LINK="./odoo-enterprise"
SIBLING="../odoo-enterprise"
# The Odoo series this repository runs. It is a repository fact, not a branch name:
# the private Enterprise copy may live on main.
SERIES="19.0"
REF="${ODOO_ENTERPRISE_REF:-}"

refuse() {
  echo "❌ runtime-bootstrap: $*" >&2
  exit 2
}
note() { echo "→ $*"; }

is_enterprise() { [ -f "$1/web_enterprise/__manifest__.py" ]; }

# Odoo manifests carry either a series-qualified version (19.0.1.0) or a
# series-relative one (1.0). A qualified version must name the expected series.
# A relative one cannot prove the series, so the checked-out git branch is
# compared when it names a series (N.0); a branch such as main proves nothing
# and is accepted. Otherwise Odoo itself refuses incompatible modules
# when the fixture is installed.
check_series() {
  local dir="$1" version branch
  version="$(python3 - "$dir/web_enterprise/__manifest__.py" <<'PY'
import ast
import sys

try:
    data = ast.literal_eval(open(sys.argv[1], encoding="utf-8").read())
except (OSError, SyntaxError, ValueError) as exc:
    raise SystemExit(f"unreadable web_enterprise manifest: {exc}")
print(str(data.get("version", "")) if isinstance(data, dict) else "")
PY
)" || refuse "cannot read $dir/web_enterprise/__manifest__.py"
  if [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9] ]]; then
    case "$version" in
      "$SERIES".*) return 0 ;;
      *) refuse "$dir is Odoo Enterprise $version; this repository needs series $SERIES" ;;
    esac
  fi
  branch="$(git -C "$dir" symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
  if [[ "$branch" =~ ^[0-9]+\.[0-9]+$ ]] && [ "$branch" != "$SERIES" ]; then
    refuse "$dir has branch $branch checked out; this repository needs Enterprise $SERIES"
  fi
  if ! [[ "$branch" =~ ^[0-9]+\.[0-9]+$ ]]; then
    note "Enterprise series is not provable from $dir; the fixture install refuses incompatible modules"
  fi
}

resolve_enterprise() {
  if [ -n "${ODOO_ENTERPRISE_PATH:-}" ] && [ "$ODOO_ENTERPRISE_PATH" != "$LINK" ]; then
    is_enterprise "$ODOO_ENTERPRISE_PATH" ||
      refuse "ODOO_ENTERPRISE_PATH=$ODOO_ENTERPRISE_PATH has no web_enterprise/__manifest__.py"
    note "Enterprise checkout: $ODOO_ENTERPRISE_PATH (ODOO_ENTERPRISE_PATH)"
    check_series "$ODOO_ENTERPRISE_PATH"
    return 0
  fi
  if [ -e "$LINK" ] || [ -L "$LINK" ]; then
    is_enterprise "$LINK" ||
      refuse "$LINK exists but is not an Odoo Enterprise checkout (no web_enterprise/__manifest__.py); fix or remove it yourself"
    note "Enterprise checkout: $LINK"
    check_series "$LINK"
    return 0
  fi
  if is_enterprise "$SIBLING"; then
    check_series "$SIBLING"
    ln -s "$SIBLING" "$LINK"
    note "Enterprise checkout: $SIBLING, linked as $LINK"
    return 0
  fi
  if [ -n "${ODOO_ENTERPRISE_REPO:-}" ]; then
    local url="$ODOO_ENTERPRISE_REPO"
    case "$url" in
      *://* | *@*:*) ;;
      */*) url="https://github.com/${url%.git}.git" ;;
      *) refuse "ODOO_ENTERPRISE_REPO must be owner/name or a git URL (got '$ODOO_ENTERPRISE_REPO')" ;;
    esac
    local where="${REF:-its default branch}"
    note "cloning Enterprise from $url ($where) into $LINK"
    git clone --quiet --depth 1 ${REF:+--branch "$REF"} "$url" "$LINK" ||
      refuse "could not clone $url ($where). A cloud session reaches a private repository only when it is attached to the session"
    is_enterprise "$LINK" || refuse "$url ($where) has no web_enterprise/__manifest__.py"
    check_series "$LINK"
    return 0
  fi
  refuse "no Odoo Enterprise checkout. Use one of:
   - attach your private Enterprise repository to this session as a sibling named odoo-enterprise
   - set ODOO_ENTERPRISE_REPO=<owner>/<private-repo> (Enterprise $SERIES; ODOO_ENTERPRISE_REF picks a branch)
   - set ODOO_ENTERPRISE_PATH=<directory>
   One-time setup: docs/LOCAL_DEV_SETUP.md, section 'Cloud agent sessions'."
}

require_docker() {
  command -v docker >/dev/null 2>&1 || refuse "docker is not installed on this machine"
  docker info >/dev/null 2>&1 || refuse "the Docker daemon is not reachable (docker info failed)"
}

# A cloud agent session reaches the network through an HTTPS proxy that
# re-signs traffic with its own CA. Build containers do not trust that CA, so the
# Dockerfile's pip step fails to clone its git-pinned dependencies ("server
# certificate verification failed"). When the session CA file exists, the
# Dockerfile's base image is rebuilt locally from the registry image with that CA
# trusted, under the same tag; a build without --pull resolves FROM from the
# local image first, so the unchanged Dockerfile builds on top of it. The local
# tag carries the CA digest as a label and a matching label is reused, so a rerun
# leaves the image, and the fixture fingerprint, unchanged. Without the CA file
# (a workstation) this step does nothing.
PROXY_CA="${RUNTIME_BOOTSTRAP_PROXY_CA:-/root/.ccr/ca-bundle.crt}"
CA_LABEL="org.plasticos.session-proxy-ca"
trust_proxy_ca() {
  [ -f "$PROXY_CA" ] || return 0
  local base digest current user ctx
  base="$(sed -n 's/^FROM[[:space:]]\{1,\}\([^[:space:]]\{1,\}\).*/\1/p' Dockerfile 2>/dev/null | head -1)"
  [ -n "$base" ] || refuse "cannot read the base image from the FROM line of Dockerfile"
  digest="$(sha256sum "$PROXY_CA" | cut -c1-64)"
  current="$(docker image inspect --format "{{ index .Config.Labels \"$CA_LABEL\" }}" "$base" 2>/dev/null || true)"
  if [ "$current" = "$digest" ]; then
    note "base image $base already trusts the session proxy CA"
    return 0
  fi
  note "session proxy CA found; rebuilding base image $base locally with it trusted"
  docker pull --quiet "$base" >/dev/null || refuse "could not pull base image $base"
  user="$(docker image inspect --format '{{.Config.User}}' "$base" 2>/dev/null || true)"
  ctx="$(mktemp -d)"
  cp "$PROXY_CA" "$ctx/session-proxy-ca.crt"
  cat >"$ctx/Dockerfile" <<EOF
FROM $base
USER root
COPY session-proxy-ca.crt /usr/local/share/ca-certificates/session-proxy-ca.crt
RUN update-ca-certificates >/dev/null
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt GIT_SSL_CAINFO=/etc/ssl/certs/ca-certificates.crt REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
LABEL $CA_LABEL=$digest
USER ${user:-root}
EOF
  if ! docker build --quiet -t "$base" "$ctx" >/dev/null; then
    rm -rf "$ctx"
    refuse "could not rebuild base image $base with the session proxy CA"
  fi
  rm -rf "$ctx"
}

admit_fixture() {
  local status state
  status="$(bash scripts/test_env.sh status)" || refuse "scripts/test_env.sh status failed"
  state="$(printf '%s\n' "$status" | sed -n 's/^template:[[:space:]]*[^ ]* (\(.*\))$/\1/p' | head -1)"
  case "$state" in
    ready)
      note "pinned Enterprise fixture is admitted for the current inputs; reusing it"
      ;;
    absent)
      note "pinned Enterprise fixture is absent; admitting it (scripts/test_env.sh rebuild)"
      bash scripts/test_env.sh rebuild
      ;;
    "")
      refuse "could not read the template state from scripts/test_env.sh status"
      ;;
    *)
      refuse "pinned Enterprise fixture: $state. Recovering it is an operator decision: make test-env-rebuild"
      ;;
  esac
}

require_docker
resolve_enterprise
trust_proxy_ca
admit_fixture
echo "✅ Odoo Enterprise runtime is ready on this machine."
echo "   Publish with PR_SMOKE=1 make pr to run the install-smoke and the Odoo runtime tests here;"
echo "   a cloud session skips them by default."
