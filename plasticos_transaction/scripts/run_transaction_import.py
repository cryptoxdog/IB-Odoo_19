#!/usr/bin/env python3
"""
Run transaction import from cieTrade.WksDetail.csv.

Usage (Odoo shell):
    from plasticos_transaction.scripts.run_transaction_import import run
    run(env)

    # Or with custom path:
    run(env, csv_path="/custom/path/to/file.csv")

    # Dry run (validate only):
    run(env, dry_run=True)
"""
import os


def run(env, csv_path: str = None, dry_run: bool = False):
    """
    Execute transaction import.

    Args:
        env: Odoo environment
        csv_path: Path to CSV file (defaults to module's cieTrade.WksDetail.csv)
        dry_run: If True, validate without committing
    """
    if csv_path is None:
        # Default to the CSV in the module directory
        module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csv_path = os.path.join(module_path, "cieTrade.WksDetail.csv")

    print(f"Importing transactions from: {csv_path}")
    print(f"Dry run: {dry_run}")

    service = env["plasticos.transaction.import.service"]
    result = service.run_csv_import(csv_path, dry_run=dry_run)

    print("\n=== IMPORT RESULTS ===")
    print(f"Transactions created: {result['transactions_created']}")
    print(f"Lines created: {result['lines_created']}")
    print(f"Errors: {len(result['errors'])}")

    if result["errors"]:
        print("\nFirst 10 errors:")
        for err in result["errors"][:10]:
            print(f"  - {err}")

    return result
