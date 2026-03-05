#!/usr/bin/env python3
"""
Database Schema Consistency Audit
Validates Python models against actual PostgreSQL schema.
"""

import psycopg2


class SchemaAudit:
    def __init__(self, db_config):
        self.conn = psycopg2.connect(**db_config)
        self.cursor = self.conn.cursor()

    def get_database_tables(self):
        """List all tables in PostgreSQL"""
        self.cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
        """)
        return {row[0] for row in self.cursor.fetchall()}

    def get_database_columns(self, table):
        """Get columns for a specific table"""
        self.cursor.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
        """,
            (table,),
        )
        return {row[0]: {"type": row[1], "nullable": row[2] == "YES"} for row in self.cursor.fetchall()}

    def get_missing_indexes(self):
        """Find foreign keys without indexes"""
        self.cursor.execute("""
            SELECT
                t.relname AS table_name,
                a.attname AS column_name
            FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
            JOIN pg_class t ON t.oid = c.conrelid
            WHERE c.contype = 'f'  -- Foreign key
            AND NOT EXISTS (
                SELECT 1 FROM pg_index i
                WHERE i.indrelid = c.conrelid
                AND a.attnum = ANY(i.indkey)
            )
        """)
        return [(row[0], row[1]) for row in self.cursor.fetchall()]

    def check_orphaned_fields(self):
        """Find ir.model.fields entries with no corresponding column"""
        self.cursor.execute("""
            SELECT
                f.name AS field_name,
                m.model AS model_name,
                f.ttype AS field_type
            FROM ir_model_fields f
            JOIN ir_model m ON f.model_id = m.id
            WHERE f.state = 'manual'
            AND f.store = true
            AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns c
                WHERE c.table_name = REPLACE(m.model, '.', '_')
                AND c.column_name = f.name
            )
        """)

        errors = []
        for field_name, model_name, _field_type in self.cursor.fetchall():
            errors.append(
                {
                    "type": "ORPHANED_FIELD",
                    "severity": "MODERATE",
                    "model": model_name,
                    "field": field_name,
                    "message": f"Field '{field_name}' in ir.model.fields but no DB column",
                    "fix": "Delete from ir.model.fields or recreate column",
                }
            )
        return errors

    def check_type_mismatches(self, model_fields):
        """Compare Python field types to PostgreSQL column types"""
        errors = []

        ODOO_TO_PG_TYPE = {
            "Char": "character varying",
            "Text": "text",
            "Html": "text",
            "Integer": "integer",
            "Float": "numeric",
            "Boolean": "boolean",
            "Date": "date",
            "Datetime": "timestamp without time zone",
            "Many2one": "integer",
        }

        db_tables = self.get_database_tables()

        for model_name, fields in model_fields.items():
            table_name = model_name.replace(".", "_")

            if table_name not in db_tables:
                errors.append(
                    {
                        "type": "MISSING_TABLE",
                        "severity": "CRITICAL",
                        "model": model_name,
                        "table": table_name,
                        "message": f"Model '{model_name}' has no database table '{table_name}'",
                    }
                )
                continue

            db_columns = self.get_database_columns(table_name)

            for field_name, field_meta in fields.items():
                if field_meta.get("compute") and not field_meta.get("store"):
                    continue  # Skip non-stored computed fields

                if field_name not in db_columns:
                    errors.append(
                        {
                            "type": "MISSING_COLUMN",
                            "severity": "HIGH",
                            "model": model_name,
                            "field": field_name,
                            "message": f"Field '{field_name}' defined but no column in DB",
                        }
                    )
                    continue

                expected_type = ODOO_TO_PG_TYPE.get(field_meta["type"])
                actual_type = db_columns[field_name]["type"]

                if expected_type and expected_type != actual_type:
                    errors.append(
                        {
                            "type": "TYPE_MISMATCH",
                            "severity": "MODERATE",
                            "model": model_name,
                            "field": field_name,
                            "expected": expected_type,
                            "actual": actual_type,
                            "message": f"Type mismatch: Python={field_meta['type']}, PG={actual_type}",
                        }
                    )

        return errors


# Usage:
# auditor = SchemaAudit({"dbname": "mydb", "user": "odoo", "password": "..."})
# errors = auditor.check_orphaned_fields()
