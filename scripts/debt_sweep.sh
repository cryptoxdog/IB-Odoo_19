#!/usr/bin/env bash
# =============================================================================
# Debt Sweep Script — Force Full-Repo Review via CodeRabbit
# =============================================================================
# This script creates a "debt sweep" branch that touches every Python and XML
# file with a no-op change, forcing all review agents to process the entire
# codebase at once.
#
# Usage:
#   ./scripts/debt_sweep.sh [--dry-run] [--branch-name NAME]
#
# Options:
#   --dry-run       Show what would be done without making changes
#   --branch-name   Custom branch name (default: chore/debt-sweep-YYYY-MM)
#
# After running:
#   1. Open a DRAFT PR against staging
#   2. Post the debt audit prompt from scripts/coderabbit_debt_audit_prompt.md
#   3. Wait for CodeRabbit to complete full walkthrough
#   4. Collect findings and create remediation GMPs
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DRY_RUN=false
BRANCH_NAME="chore/debt-sweep-$(date +%Y-%m)"
COMMIT_MSG="chore: debt sweep trigger — no logic changes, forces full CI+review scan"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --branch-name)
            BRANCH_NAME="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}=== Code Debt Sweep Script ===${NC}"
echo ""

# Check we're in a git repo
if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    echo -e "${RED}Error: Not in a git repository${NC}"
    exit 1
fi

# Check for uncommitted changes
if [[ -n $(git status --porcelain) ]]; then
    echo -e "${YELLOW}Warning: You have uncommitted changes${NC}"
    git status --short
    echo ""
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Aborted${NC}"
        exit 1
    fi
fi

# Count files to touch
PY_COUNT=$(git ls-files '*.py' | wc -l | tr -d ' ')
XML_COUNT=$(git ls-files '*.xml' | wc -l | tr -d ' ')
TOTAL_COUNT=$((PY_COUNT + XML_COUNT))

echo -e "${GREEN}Files to touch:${NC}"
echo "  Python files: $PY_COUNT"
echo "  XML files:    $XML_COUNT"
echo "  Total:        $TOTAL_COUNT"
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}DRY RUN MODE — No changes will be made${NC}"
    echo ""
    echo "Would execute:"
    echo "  1. git checkout -b $BRANCH_NAME"
    echo "  2. touch all $TOTAL_COUNT tracked .py and .xml files"
    echo "  3. git add -A"
    echo "  4. git commit -m \"$COMMIT_MSG\""
    echo ""
    echo "Sample files that would be touched:"
    git ls-files '*.py' '*.xml' | head -10
    echo "  ..."
    exit 0
fi

# Create sweep branch
echo -e "${BLUE}Step 1: Creating sweep branch...${NC}"
git checkout -b "$BRANCH_NAME"
echo -e "${GREEN}✓ Created branch: $BRANCH_NAME${NC}"
echo ""

# Touch all Python and XML files
echo -e "${BLUE}Step 2: Touching all tracked .py and .xml files...${NC}"
git ls-files '*.py' '*.xml' | xargs -I{} touch {}
echo -e "${GREEN}✓ Touched $TOTAL_COUNT files${NC}"
echo ""

# Stage changes
echo -e "${BLUE}Step 3: Staging changes...${NC}"
git add -A
echo -e "${GREEN}✓ Changes staged${NC}"
echo ""

# Commit
echo -e "${BLUE}Step 4: Committing...${NC}"
git commit -m "$COMMIT_MSG"
echo -e "${GREEN}✓ Committed${NC}"
echo ""

# Summary
echo -e "${GREEN}=== Debt Sweep Branch Ready ===${NC}"
echo ""
echo "Next steps:"
echo "  1. Push the branch:"
echo "     git push origin $BRANCH_NAME"
echo ""
echo "  2. Open a DRAFT PR against staging"
echo ""
echo "  3. Post the debt audit prompt in the PR:"
echo "     cat scripts/coderabbit_debt_audit_prompt.md"
echo ""
echo "  4. Wait for CodeRabbit to complete full walkthrough"
echo ""
echo "  5. Run semgrep audit:"
echo "     ./scripts/run_semgrep_audit.sh"
echo ""
echo "  6. Collect all findings and create remediation GMPs"
echo ""
echo -e "${YELLOW}Remember: After the sweep is complete, revert .coderabbit.yaml to 'chill' profile${NC}"
