#!/usr/bin/env bash
# =============================================================================
# Semgrep Full Audit Script — Comprehensive Code Analysis
# =============================================================================
# Runs semgrep with multiple rule sets against the entire codebase and
# produces structured JSON and human-readable reports.
#
# Usage:
#   ./scripts/run_semgrep_audit.sh [--output-dir DIR]
#
# Output:
#   - reports/semgrep/semgrep_full_audit.json    (raw JSON)
#   - reports/semgrep/semgrep_debt_table.txt    (human-readable table)
#   - reports/semgrep/semgrep_summary.md        (markdown summary)
#
# Prerequisites:
#   pip install semgrep
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${REPO_ROOT}/reports/semgrep"
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}=== Semgrep Full Audit ===${NC}"
echo "Output directory: $OUTPUT_DIR"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check semgrep is installed
if ! command -v semgrep &> /dev/null; then
    echo -e "${RED}Error: semgrep is not installed${NC}"
    echo "Install with: pip install semgrep"
    exit 1
fi

echo -e "${BLUE}Step 1: Running semgrep with all rule sets...${NC}"
echo ""

# Build the semgrep command with multiple configs
SEMGREP_CONFIGS=(
    "--config" "${REPO_ROOT}/.semgrep/"
    "--config" "p/python"
    "--config" "p/django"
    "--config" "p/secrets"
    "--config" "p/security-audit"
    "--config" "p/owasp-top-ten"
)

# Target directories (plasticos modules + ci scripts)
TARGETS=(
    "plasticos_base"
    "plasticos_intake"
    "plasticos_automation"
    "plasticos_inference_engine"
    "plasticos_buyer_match_engine"
    "plasticos_logistics"
    "plasticos_offer"
    "plasticos_transaction"
    "plasticos_matching"
    "plasticos_enrichment"
    "plasticos_security_base"
    "ci"
    "scripts"
)

# Filter to existing directories
EXISTING_TARGETS=()
for target in "${TARGETS[@]}"; do
    if [[ -d "${REPO_ROOT}/${target}" ]]; then
        EXISTING_TARGETS+=("${target}")
    fi
done

echo "Scanning directories:"
for target in "${EXISTING_TARGETS[@]}"; do
    echo "  - $target"
done
echo ""

# Run semgrep
cd "$REPO_ROOT"

echo -e "${YELLOW}Running semgrep (this may take a few minutes)...${NC}"
semgrep scan \
    "${SEMGREP_CONFIGS[@]}" \
    --json \
    --output "${OUTPUT_DIR}/semgrep_full_audit_${TIMESTAMP}.json" \
    --timeout 300 \
    --max-target-bytes 5000000 \
    "${EXISTING_TARGETS[@]}" 2>&1 | tee "${OUTPUT_DIR}/semgrep_log_${TIMESTAMP}.txt" || true

# Check if output was created
if [[ ! -f "${OUTPUT_DIR}/semgrep_full_audit_${TIMESTAMP}.json" ]]; then
    echo -e "${RED}Error: Semgrep did not produce output${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Semgrep scan complete${NC}"
echo ""

# Create symlink to latest
ln -sf "semgrep_full_audit_${TIMESTAMP}.json" "${OUTPUT_DIR}/semgrep_full_audit.json"

echo -e "${BLUE}Step 2: Generating human-readable table...${NC}"

# Generate table from JSON
python3 << 'PYTHON_SCRIPT'
import json
import sys
from pathlib import Path
from collections import defaultdict

output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/semgrep")
json_file = output_dir / "semgrep_full_audit.json"

if not json_file.exists():
    print("No JSON file found")
    sys.exit(1)

with open(json_file) as f:
    data = json.load(f)

results = data.get("results", [])
errors = data.get("errors", [])

# Group by severity
by_severity = defaultdict(list)
for r in results:
    severity = r.get("extra", {}).get("severity", "INFO")
    by_severity[severity].append(r)

# Write table
table_file = output_dir / "semgrep_debt_table.txt"
with open(table_file, "w") as f:
    f.write("=" * 120 + "\n")
    f.write("SEMGREP FULL AUDIT RESULTS\n")
    f.write("=" * 120 + "\n\n")

    f.write(f"Total findings: {len(results)}\n")
    f.write(f"  ERROR:   {len(by_severity.get('ERROR', []))}\n")
    f.write(f"  WARNING: {len(by_severity.get('WARNING', []))}\n")
    f.write(f"  INFO:    {len(by_severity.get('INFO', []))}\n")
    f.write(f"\nErrors during scan: {len(errors)}\n")
    f.write("\n" + "-" * 120 + "\n\n")

    # Table header
    f.write(f"{'File':<50} {'Line':<6} {'Severity':<10} {'Rule':<40} {'Message':<50}\n")
    f.write("-" * 156 + "\n")

    # Sort by severity (ERROR first, then WARNING, then INFO)
    severity_order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    sorted_results = sorted(results, key=lambda x: (
        severity_order.get(x.get("extra", {}).get("severity", "INFO"), 3),
        x.get("path", ""),
        x.get("start", {}).get("line", 0)
    ))

    for r in sorted_results:
        path = r.get("path", "")[:49]
        line = str(r.get("start", {}).get("line", ""))[:5]
        severity = r.get("extra", {}).get("severity", "INFO")[:9]
        rule = r.get("check_id", "")[:39]
        message = r.get("extra", {}).get("message", "")[:49]

        f.write(f"{path:<50} {line:<6} {severity:<10} {rule:<40} {message:<50}\n")

print(f"Table written to: {table_file}")

# Write markdown summary
summary_file = output_dir / "semgrep_summary.md"
with open(summary_file, "w") as f:
    f.write("# Semgrep Audit Summary\n\n")
    f.write(f"**Date:** {Path(json_file).stem.split('_')[-1] if '_' in json_file.stem else 'latest'}\n\n")

    f.write("## Overview\n\n")
    f.write(f"| Metric | Count |\n")
    f.write(f"|--------|-------|\n")
    f.write(f"| Total Findings | {len(results)} |\n")
    f.write(f"| ERROR | {len(by_severity.get('ERROR', []))} |\n")
    f.write(f"| WARNING | {len(by_severity.get('WARNING', []))} |\n")
    f.write(f"| INFO | {len(by_severity.get('INFO', []))} |\n")
    f.write(f"| Scan Errors | {len(errors)} |\n\n")

    # Group by file
    by_file = defaultdict(list)
    for r in results:
        by_file[r.get("path", "unknown")].append(r)

    f.write("## Findings by File\n\n")
    for filepath in sorted(by_file.keys()):
        findings = by_file[filepath]
        error_count = sum(1 for r in findings if r.get("extra", {}).get("severity") == "ERROR")
        warn_count = sum(1 for r in findings if r.get("extra", {}).get("severity") == "WARNING")

        severity_badge = ""
        if error_count > 0:
            severity_badge = f" 🔴 {error_count} ERROR"
        if warn_count > 0:
            severity_badge += f" 🟡 {warn_count} WARNING"

        f.write(f"### `{filepath}`{severity_badge}\n\n")
        f.write("| Line | Severity | Rule | Message |\n")
        f.write("|------|----------|------|--------|\n")

        for r in sorted(findings, key=lambda x: x.get("start", {}).get("line", 0)):
            line = r.get("start", {}).get("line", "?")
            severity = r.get("extra", {}).get("severity", "INFO")
            rule = r.get("check_id", "").split(".")[-1][:30]
            message = r.get("extra", {}).get("message", "")[:60].replace("|", "\\|")
            f.write(f"| {line} | {severity} | {rule} | {message} |\n")

        f.write("\n")

    # Top rules
    by_rule = defaultdict(int)
    for r in results:
        by_rule[r.get("check_id", "unknown")] += 1

    f.write("## Top 10 Rules Triggered\n\n")
    f.write("| Rule | Count |\n")
    f.write("|------|-------|\n")
    for rule, count in sorted(by_rule.items(), key=lambda x: -x[1])[:10]:
        f.write(f"| {rule} | {count} |\n")
    f.write("\n")

print(f"Summary written to: {summary_file}")
PYTHON_SCRIPT

echo -e "${GREEN}✓ Reports generated${NC}"
echo ""

# Summary
echo -e "${GREEN}=== Audit Complete ===${NC}"
echo ""
echo "Output files:"
echo "  - ${OUTPUT_DIR}/semgrep_full_audit.json"
echo "  - ${OUTPUT_DIR}/semgrep_debt_table.txt"
echo "  - ${OUTPUT_DIR}/semgrep_summary.md"
echo ""
echo "View summary:"
echo "  cat ${OUTPUT_DIR}/semgrep_summary.md"
echo ""
echo "View detailed table:"
echo "  cat ${OUTPUT_DIR}/semgrep_debt_table.txt"
