#!/bin/bash
# Odoo Module Dependency Wiring Checker (wrapper)
# Ensures all modules are properly wired to their dependencies
#
# Run: ./scripts/check_module_wiring.sh [module_name]
#      ./scripts/check_module_wiring.sh  # checks all modules
#      ./scripts/check_module_wiring.sh plasticos_facility_profile  # single module
#
# Checks performed:
# 1. DEPENDENCY WIRING: Model references match declared dependencies
# 2. IMPORT WIRING: All .py files in models/ are imported in __init__.py
# 3. MODULE INIT WIRING: models package is imported in module __init__.py
# 4. FILE EXISTENCE: All imported modules actually exist

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run the Python checker
python3 "$SCRIPT_DIR/check_module_wiring.py" "$@"
