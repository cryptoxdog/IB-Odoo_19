#!/bin/bash
# Odoo 19 Pattern Checker
# Catches Odoo-specific bugs that ruff/mypy cannot detect
# Only scans files tracked by git (respects .gitignore)
# Run: ./scripts/check_odoo_patterns.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

echo "🔍 Checking Odoo 19 patterns (git-tracked files only)..."
echo ""

# Get git-tracked Python files
PY_FILES=$(git ls-files '*.py' 2>/dev/null || find . -name "*.py" -type f)
XML_FILES=$(git ls-files '*.xml' 2>/dev/null || find . -name "*.xml" -type f)

# 1. _sql_constraints (deprecated in Odoo 17+)
echo -n "Checking _sql_constraints... "
MATCHES=$(echo "$PY_FILES" | xargs grep -l "_sql_constraints" 2>/dev/null | xargs grep "_sql_constraints" 2>/dev/null | grep -v "models.Constraint" | grep -v "export_odoo_index" || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES"
    echo -e "${YELLOW}Fix: Convert to models.Constraint${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 2. @api.depends("id") (disallowed in Odoo 19)
echo -n "Checking @api.depends('id')... "
MATCHES=$(echo "$PY_FILES" | xargs grep -E '@api\.depends\([^)]*["\x27]id["\x27]' 2>/dev/null || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES"
    echo -e "${YELLOW}Fix: Remove 'id' from @api.depends${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 3. @api.one / @api.multi (removed in Odoo 13+)
echo -n "Checking @api.one/@api.multi... "
MATCHES=$(echo "$PY_FILES" | xargs grep -E '@api\.(one|multi)' 2>/dev/null || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES"
    echo -e "${YELLOW}Fix: Remove decorator, update method${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 4. category_id on res.groups in XML (removed in Odoo 19)
echo -n "Checking category_id on res.groups... "
MATCHES=$(echo "$XML_FILES" | xargs grep -l 'model="res.groups"' 2>/dev/null | xargs grep -A5 'model="res.groups"' 2>/dev/null | grep -E 'category_id.*ref=' || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES"
    echo -e "${YELLOW}Fix: Remove category_id from res.groups records${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 5. numbercall on ir.cron (deprecated)
echo -n "Checking numbercall field... "
MATCHES=$(echo "$XML_FILES" | xargs grep "numbercall" 2>/dev/null || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES"
    echo -e "${YELLOW}Fix: Remove numbercall field from cron records${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 6. Unescaped & in XML (causes parse errors)
echo -n "Checking unescaped & in XML... "
MATCHES=$(echo "$XML_FILES" | xargs grep -E ' & [^a]' 2>/dev/null | grep -v '&amp;' | grep -v '&lt;' | grep -v '&gt;' | grep -v '&quot;' || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES"
    echo -e "${YELLOW}Fix: Replace & with \&amp;${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 7. Empty __init__.py in Odoo modules (models won't load)
echo -n "Checking empty __init__.py in modules... "
EMPTY_INITS=""
for init_file in $(git ls-files '*/__init__.py' 2>/dev/null); do
    # Check if it's in a plasticos_* module directory
    if [[ "$init_file" == plasticos_*/__init__.py ]] || [[ "$init_file" == plasticos_*/models/__init__.py ]]; then
        if [ ! -s "$init_file" ]; then
            EMPTY_INITS="$EMPTY_INITS $init_file"
        fi
    fi
done
if [ -n "$EMPTY_INITS" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$EMPTY_INITS"
    echo -e "${YELLOW}Fix: Add 'from . import models' or model imports${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

echo ""
if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}❌ Found $ERRORS Odoo pattern issue(s)${NC}"
    exit 1
else
    echo -e "${GREEN}✅ All Odoo pattern checks passed${NC}"
    exit 0
fi
