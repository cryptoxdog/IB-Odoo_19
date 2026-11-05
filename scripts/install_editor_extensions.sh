#!/usr/bin/env bash
# Install the editor extensions recommended in .vscode/extensions.json.
#
# Single source of truth: .vscode/extensions.json (git-tracked, carries over on
# every clone). This script just automates the "click Install" step so a fresh
# clone on a new machine doesn't need manual UI interaction per extension.
#
# Usage: bash scripts/install_editor_extensions.sh
# (wired as: make install-extensions)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTENSIONS_JSON="$REPO_ROOT/.vscode/extensions.json"

if [ ! -f "$EXTENSIONS_JSON" ]; then
  echo "No $EXTENSIONS_JSON found — nothing to install." >&2
  exit 1
fi

# Prefer the Cursor CLI; fall back to VS Code's `code` if Cursor isn't on PATH.
BIN=""
if command -v cursor >/dev/null 2>&1; then
  BIN="cursor"
elif command -v code >/dev/null 2>&1; then
  BIN="code"
else
  echo "Neither 'cursor' nor 'code' CLI found on PATH." >&2
  echo "In Cursor: Cmd+Shift+P -> 'Shell Command: Install cursor command in PATH', then re-run." >&2
  exit 1
fi

# Extract the recommendations array without requiring jq (not guaranteed on a
# fresh machine before `make venv`); python3 ships with the OS on every
# supported platform here. Use a portable read loop — macOS ships bash 3.2,
# which has no `mapfile` builtin (bash 4+ only).
EXTENSIONS=()
while IFS= read -r ext; do
  EXTENSIONS+=("$ext")
done < <(python3 -c '
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
for ext in data.get("recommendations", []):
    print(ext)
' "$EXTENSIONS_JSON")

if [ "${#EXTENSIONS[@]}" -eq 0 ]; then
  echo "No recommendations listed in $EXTENSIONS_JSON." >&2
  exit 0
fi

echo "→ Installing ${#EXTENSIONS[@]} recommended extension(s) via '$BIN'..."
FAILED=()
for ext in "${EXTENSIONS[@]}"; do
  echo "  - $ext"
  if ! "$BIN" --install-extension "$ext" --force >/tmp/install_ext_"$ext".log 2>&1; then
    FAILED+=("$ext")
  fi
done

echo ""
if [ "${#FAILED[@]}" -eq 0 ]; then
  echo "✅ All recommended extensions installed."
else
  echo "⚠️  ${#FAILED[@]} extension(s) could not be installed (not on this editor's registry, e.g. Open VSX):"
  for ext in "${FAILED[@]}"; do
    echo "  - $ext (see /tmp/install_ext_${ext}.log)"
  done
  echo "These may need a manual .vsix install from the VS Code Marketplace."
fi
