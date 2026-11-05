#!/usr/bin/env python3
import getpass
import sys

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("Error: 'psycopg2' module not found.")
    print("Please install it using: pip install psycopg2-binary")
    sys.exit(1)


def fix_permissions():
    print("=== Odoo Database Permission Fixer ===")
    print("This script connects as a Superuser (postgres) to grant permissions to the Odoo user.")

    # 1. Gather Connection Details
    db_host = input("Database Host [192.168.1.1]: ").strip() or "192.168.1.1"
    db_port = input("Database Port [5432]: ").strip() or "5432"
    admin_user = input("Admin/Superuser Username [postgres]: ").strip() or "postgres"
    admin_pass = getpass.getpass(f"Password for {admin_user}: ")

    target_odoo_user = input("Target Odoo User (from odoo.conf): ").strip()
    if not target_odoo_user:
        print("Error: Target Odoo User is required.")
        return

    target_db_name = input("Target Database Name (to create/check): ").strip()
    if not target_db_name:
        print("Error: Target Database Name is required.")
        return

    try:
        # 2. Connect to 'postgres' database to perform administrative tasks
        print(f"\nConnecting to {db_host}:{db_port} as {admin_user}...")
        conn = psycopg2.connect(dbname="postgres", user=admin_user, password=admin_pass, host=db_host, port=db_port)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        print("Connected successfully.")

        # 3. Grant Permissions
        print(f"Granting SELECT on pg_database to {target_odoo_user}...")
        try:
            # psycopg2.sql.Identifier safely quotes the role name (SonarCloud S8702)
            cur.execute(sql.SQL("GRANT SELECT ON pg_database TO {}").format(sql.Identifier(target_odoo_user)))
            print("✅ Permission GRANTED.")
        except Exception as e:
            print(f"⚠️  Could not grant permission: {e}")
            print("Continuing...")

        # 4. Check/Create Database
        print(f"Checking if database '{target_db_name}' exists...")
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db_name,))
        exists = cur.fetchone()

        if not exists:
            print(f"Database '{target_db_name}' does not exist. Creating it...")
            try:
                cur.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(target_db_name), sql.Identifier(target_odoo_user)
                    )
                )
                print(f"✅ Database '{target_db_name}' CREATED successfully.")
            except Exception as e:
                print(f"❌ Failed to create database: {e}")
        else:
            print(f"✅ Database '{target_db_name}' already exists.")

        cur.close()
        conn.close()
        print("\n=== Done. Please restart your Odoo service. ===")

    except psycopg2.OperationalError as e:
        print(f"\n❌ Connection failed: {e}")
        print("Please check your host, port, and credentials.")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")


if __name__ == "__main__":
    fix_permissions()
