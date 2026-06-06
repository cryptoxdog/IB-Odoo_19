#!/usr/bin/env bash
# Validate L9 skills + repo wiring (PlasticOS). Requires governance symlinks.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GC="$HOME/Dropbox/cursor governance/GlobalCommands"
[ -d "$GC" ] || GC="$HOME/Dropbox/Cursor Governance/GlobalCommands"
SKILLS="$GC/skills"
GOV_VALIDATE="$GC/ops/scripts/validate_governance_symlinks.sh"

FAIL=0
L9_SKILLS=(l9-structured-reasoning l9-skill-compiler l9-wire-skill-into-repo l9-create-skill l9-update-agent-docs l9-gmp-protocol)

pass() { echo "  OK: $1"; }
fail() { echo "  FAIL: $1"; FAIL=1; }

echo "=== Governance symlinks (canonical) ==="
if [ -x "$GOV_VALIDATE" ]; then
  bash "$GOV_VALIDATE" "$REPO_ROOT" || FAIL=1
else
  fail "missing $GOV_VALIDATE"
fi

echo ""
echo "=== L9 packs (GlobalCommands/skills) ==="
for skill in "${L9_SKILLS[@]}"; do
  skill_md="$SKILLS/$skill/SKILL.md"
  if [ ! -f "$skill_md" ]; then fail "missing $skill_md"; continue; fi
  name=$(grep -E '^name:' "$skill_md" | head -1 | sed 's/^name:[[:space:]]*//')
  if [ "$name" = "$skill" ]; then pass "$skill name matches"; else fail "$skill name=$name"; fi
done

echo ""
echo "=== No stale repo copies ==="
for old in structured-reasoning skill-compiler gmp-protocol update-agent-docs; do
  [ -d "$REPO_ROOT/.claude/skills/$old" ] && fail "stale .claude/skills/$old/" || pass "no .claude/skills/$old/"
done

echo ""
echo "=== Repo registries ==="
for skill in "${L9_SKILLS[@]}"; do
  grep -q "$skill" "$REPO_ROOT/.claude/README.md" && pass "$skill in README" || fail "$skill missing from README"
  grep -q "\`$skill\`" "$REPO_ROOT/AGENTS.md" && pass "$skill in AGENTS.md" || fail "$skill missing from AGENTS.md"
done

echo ""
echo "=== PlasticOS project skills (plasticos-* prefix) ==="
PROJECT_SKILLS=(plasticos-new-odoo-module plasticos-new-model-field plasticos-odoo-sh-deploy plasticos-xml-view)
for skill in "${PROJECT_SKILLS[@]}"; do
  skill_md="$REPO_ROOT/.claude/skills/$skill/SKILL.md"
  if [ ! -f "$skill_md" ]; then fail "missing $skill_md"; continue; fi
  name=$(grep -E '^name:' "$skill_md" | head -1 | sed 's/^name:[[:space:]]*//')
  if [ "$name" = "$skill" ]; then pass "$skill name matches directory"; else fail "$skill name=$name"; fi
done
for stale in new-odoo-module new-model-field odoo-sh-deploy; do
  [ -d "$REPO_ROOT/.claude/skills/$stale" ] && fail "stale unprefixed .claude/skills/$stale/" || pass "no .claude/skills/$stale/"
done

echo ""
if [ $FAIL -eq 0 ]; then
  echo "RESULT: PASS"
  exit 0
else
  echo "RESULT: FAIL"
  exit 1
fi
