#!/bin/bash
# Odoo 19 Pattern Checker
# Catches Odoo-specific bugs that ruff/mypy cannot detect
# Only scans files tracked by git (respects .gitignore)
# Run: ./scripts/check_odoo_patterns.sh
#
# Bug patterns checked (see reports/BUG_FIXES_SUMMARY.md):
# 1. _sql_constraints (deprecated in Odoo 17+, use models.Constraint)
# 2. @api.depends("id") (disallowed)
# 3. @api.one/@api.multi (removed)
# 4. category_id on res.groups (removed)
# 5. numbercall on ir.cron (deprecated)
# 6. Unescaped & in XML
# 7. Empty __init__.py in modules
# 8. Namespace drift (PlastoS vs PlasticoS)
# 9. Empty inherit files (dead code)
# 10. XML cron model_id missing module prefix
# 11. XML eval() with nested double quotes
# 12. <tree> instead of <list> (Odoo 19)
# 13. string attribute on <search> (invalid RNG)
# 14. string on <group name="group_by"> (invalid RNG)
# 15. decoration-secondary (invalid decoration)
# 16. t-esc deprecated (use t-out in Odoo 17+)
# 17. Module dependency wiring
# 18. Related fields with old intake paths (polymer→polymer_id)
# 19. Deprecated attrs= attribute (Odoo 17+)
# 20. Deprecated states= attribute (Odoo 17+)
# 21. Font Awesome icons without title (Odoo 19 accessibility)
# 22. String writes to Many2one fields (BUG-073 pattern)

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

# 1. _sql_constraints (deprecated in Odoo 17+, use models.Constraint)
# Exclude: reports/, AI Agent Files/ (docs/specs only)
echo -n "Checking deprecated _sql_constraints... "
MATCHES=$(echo "$PY_FILES" | xargs grep -l '_sql_constraints\s*=' 2>/dev/null | grep -v 'reports/' | grep -v 'AI Agent Files/' || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES" | sed 's/^/  /'
    echo -e "${YELLOW}Fix: Convert to models.Constraint(\"SQL\", \"message\") per Odoo 17+${NC}"
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

# 8. Namespace drift (PlastoS vs PlasticoS) - Bug #12
echo -n "Checking namespace drift (PlastoS vs PlasticoS)... "
MATCHES=$(echo "$PY_FILES" | xargs grep -E 'class Plastos[A-Z]' 2>/dev/null | grep -v 'Plasticos' || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES"
    echo -e "${YELLOW}Fix: Rename class from Plastos* to Plasticos*${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 9. Empty inherit files (dead code) - Bug #14
echo -n "Checking empty inherit files... "
EMPTY_INHERITS=""
for py_file in $(echo "$PY_FILES" | grep '_inherit\.py$'); do
    # Check if file only has class stub with _inherit and no fields/methods
    CONTENT=$(cat "$py_file" 2>/dev/null | grep -v '^#' | grep -v '^$' | grep -v 'from\|import' || true)
    LINE_COUNT=$(echo "$CONTENT" | wc -l | tr -d ' ')
    # If file has < 5 non-empty, non-import lines, it's likely empty
    if [ "$LINE_COUNT" -lt 5 ]; then
        # Check if it only has _inherit and nothing else meaningful
        HAS_FIELDS=$(echo "$CONTENT" | grep -E '^\s+\w+\s*=\s*fields\.' || true)
        HAS_METHODS=$(echo "$CONTENT" | grep -E '^\s+def\s+' || true)
        if [ -z "$HAS_FIELDS" ] && [ -z "$HAS_METHODS" ]; then
            EMPTY_INHERITS="$EMPTY_INHERITS $py_file"
        fi
    fi
done
if [ -n "$EMPTY_INHERITS" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$EMPTY_INHERITS"
    echo -e "${YELLOW}Fix: Delete empty inherit files and remove from __init__.py${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 10. XML cron model_id missing module prefix - Bug #13
echo -n "Checking cron model_id refs without module prefix... "
MATCHES=""
for xml_file in $(echo "$XML_FILES" | grep 'cron\.xml$'); do
    # Look for model_id refs that don't have a module prefix (no dot before model_)
    FOUND=$(grep -E 'ref="model_plasticos' "$xml_file" 2>/dev/null | grep -v '\.' || true)
    if [ -n "$FOUND" ]; then
        MATCHES="$MATCHES\n$xml_file:\n$FOUND"
    fi
done
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo -e "$MATCHES"
    echo -e "${YELLOW}Fix: Add module prefix to model_id refs (e.g., ref=\"plasticos_logistics.model_plasticos_load\")${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 11. XML eval() with nested double quotes - Bug #15
echo -n "Checking XML eval with nested double quotes... "
MATCHES=$(echo "$XML_FILES" | xargs grep -E 'eval="[^"]*ref\("[^"]*"\)[^"]*"' 2>/dev/null || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES"
    echo -e "${YELLOW}Fix: Use single quotes inside eval: ref('external_id') instead of ref(\"external_id\")${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 12. <tree> instead of <list> in view definitions (Odoo 19)
echo -n "Checking <tree> instead of <list> in views... "
MATCHES=$(echo "$XML_FILES" | xargs grep -E '<tree[^>]*>' 2>/dev/null | grep -v 'tree.txt' || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES"
    echo -e "${YELLOW}Fix: Replace <tree> with <list> (Odoo 19 requires <list>)${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 13. string attribute on <search> element (invalid in Odoo 19 RNG)
echo -n "Checking string attribute on <search>... "
MATCHES=$(echo "$XML_FILES" | xargs grep -E '<search[^>]+string=' 2>/dev/null || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES"
    echo -e "${YELLOW}Fix: Remove string attribute from <search> element${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 14. string attribute on <group name="group_by"> in search views (invalid in Odoo 19 RNG)
echo -n "Checking string on group_by in search views... "
MATCHES=$(echo "$XML_FILES" | xargs grep -E '<group[^>]+name="group_by"[^>]+string=' 2>/dev/null || true)
MATCHES2=$(echo "$XML_FILES" | xargs grep -E '<group[^>]+string=[^>]+name="group_by"' 2>/dev/null || true)
COMBINED="$MATCHES$MATCHES2"
if [ -n "$COMBINED" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$COMBINED"
    echo -e "${YELLOW}Fix: Remove string attribute from <group name=\"group_by\"> in search views${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 15. decoration-secondary (invalid Odoo decoration)
echo -n "Checking invalid decoration-secondary... "
MATCHES=$(echo "$XML_FILES" | xargs grep -E 'decoration-secondary=' 2>/dev/null || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES"
    echo -e "${YELLOW}Fix: Use valid decorations: decoration-info, decoration-success, decoration-warning, decoration-danger, decoration-muted${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 16. t-esc deprecated in QWeb (Odoo 17+, use t-out)
echo -n "Checking deprecated t-esc in QWeb... "
MATCHES=$(echo "$XML_FILES" | xargs grep -E 't-esc=' 2>/dev/null || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES" | head -10
    COUNT=$(echo "$MATCHES" | wc -l | tr -d ' ')
    echo "... ($COUNT occurrences total)"
    echo -e "${YELLOW}Fix: Replace t-esc with t-out (Odoo 17+ deprecation)${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 17. Module dependency wiring check
echo -n "Checking module dependency wiring... "
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! python3 "$SCRIPT_DIR/check_module_wiring.py" > /dev/null 2>&1; then
    echo -e "${RED}FOUND${NC}"
    # Run again to show output
    python3 "$SCRIPT_DIR/check_module_wiring.py" 2>&1 | sed 's/\x1b\[[0-9;]*m//g' | grep -E "^✗|references model|Add to" | head -15
    echo -e "${YELLOW}Fix: Add missing dependencies to __manifest__.py${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 18. Related fields pointing to old intake field names (refactored to Many2one)
# intake.polymer → intake.polymer_id, intake.form → intake.form_id, etc.
echo -n "Checking related fields with old intake paths... "
MATCHES=$(echo "$PY_FILES" | xargs grep -E 'related=["'"'"'][^"'"'"']*intake[^"'"'"']*\.(polymer|form|color|source_type)["'"'"']' 2>/dev/null | grep -v '_id' || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES"
    echo -e "${YELLOW}Fix: Update related path to use Many2one (e.g., intake_id.polymer_id.name instead of intake_id.polymer)${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 19. Deprecated attrs= attribute in views (Odoo 17+ uses invisible/readonly/required directly)
echo -n "Checking deprecated attrs= in views... "
MATCHES=$(echo "$XML_FILES" | xargs grep -E '\sattrs=' 2>/dev/null || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES" | head -5
    COUNT=$(echo "$MATCHES" | wc -l | tr -d ' ')
    echo "... ($COUNT occurrences total)"
    echo -e "${YELLOW}Fix: Replace attrs={'invisible': ...} with invisible=\"...\" (Odoo 17+)${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 20. Deprecated states= attribute on fields (Odoo 17+ uses invisible/readonly)
echo -n "Checking deprecated states= on fields... "
MATCHES=$(echo "$XML_FILES" | xargs grep -E '\sstates=' 2>/dev/null || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES" | head -5
    COUNT=$(echo "$MATCHES" | wc -l | tr -d ' ')
    echo "... ($COUNT occurrences total)"
    echo -e "${YELLOW}Fix: Replace states= with invisible=\"state == 'x'\" (Odoo 17+)${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 21. Font Awesome icons without title (Odoo 19 accessibility)
echo -n "Checking Font Awesome icons without title... "
MATCHES=$(echo "$XML_FILES" | xargs grep -E '<i[^>]*class="[^"]*fa[^"]*"' 2>/dev/null | grep -v 'title=' || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES"
    echo -e "${YELLOW}Fix: Add title=\"...\" to <i class=\"fa ...\"> for accessibility (Odoo 19)${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 22. Writing string values to Many2one fields (BUG-073 pattern)
# Catches: "polymer": value, "form": value, "source_type": value when target model has _id fields
# Excludes: graph_service (builds query params), matcher.py (builds result dicts),
#           enrichment_service (builds API payloads), material_profile.py (builds export packets),
#           transaction_import (legacy CSV import uses Char fields for historical data)
echo -n "Checking string writes to Many2one fields... "
MATCHES=$(echo "$PY_FILES" | xargs grep -E '"(polymer|form|source_type)":\s*\w+' 2>/dev/null | grep -v '_id' | grep -v 'graph_service' | grep -v 'matcher.py' | grep -v 'enrichment_service' | grep -v 'material_profile.py' | grep -v 'transaction_import' || true)
if [ -n "$MATCHES" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "$MATCHES"
    echo -e "${YELLOW}Fix: Use Many2one field names (polymer_id, form_id, source_type_id) with record IDs, not string codes${NC}"
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
