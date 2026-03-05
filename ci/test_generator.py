#!/usr/bin/env python3
"""
Auto-generate test skeletons for untested models
"""

import ast
from pathlib import Path


class TestGenerator:
    def __init__(self, model_file):
        self.model_file = Path(model_file)
        with open(model_file) as f:
            self.tree = ast.parse(f.read())

    def generate_test_file(self):
        """Generate comprehensive test file"""
        model_name = self._extract_model_name()
        methods = self._extract_public_methods()
        fields = self._extract_fields()

        test_content = f'''# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError

@tagged('post_install', '-at_install')
class Test{self._to_camel_case(model_name)}(TransactionCase):
    """Test suite for {model_name}"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TODO: Setup test data

    def _create_{model_name.split('.')[-1]}(self, **kwargs):
        """Helper to create {model_name} with defaults"""
        vals = {{
            # TODO: Add required fields
        }}
        vals.update(kwargs)
        return self.env['{model_name}'].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_{model_name.split('.')[-1]}()

        self.assertTrue(record.exists())
        # TODO: Add specific assertions

'''

        # Generate test for each action method
        for method in methods:
            if method.startswith("action_"):
                test_content += f'''
    def test_{method}_executes_successfully(self):
        """Test {method} executes without error"""
        record = self._create_{model_name.split('.')[-1]}()

        result = record.{method}()

        # TODO: Add assertions about expected outcome
        self.assertTrue(True, "Replace with real assertion")

'''

        # Generate constraint tests
        for field in fields:
            if field.get("required"):
                test_content += f'''
    def test_constraint_{field['name']}_required(self):
        """Test {field['name']} is required"""
        with self.assertRaises(ValidationError):
            self.env['{model_name}'].create({{
                # TODO: Add other required fields except {field['name']}
            }})

'''

        return test_content

    def _extract_model_name(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_name":
                        return ast.literal_eval(node.value)
        return "unknown.model"

    def _extract_public_methods(self):
        methods = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                if not node.name.startswith("_"):
                    methods.append(node.name)
        return methods

    def _extract_fields(self):
        fields = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if isinstance(node.value, ast.Call):
                            if hasattr(node.value.func, "attr"):
                                field_type = node.value.func.attr
                                if field_type in ["Char", "Integer", "Many2one", "Selection"]:
                                    # Check if required
                                    required = any(
                                        kw.arg == "required" and kw.value.value
                                        for kw in node.value.keywords
                                        if hasattr(kw.value, "value")
                                    )
                                    fields.append({"name": target.id, "type": field_type, "required": required})
        return fields

    def _to_camel_case(self, snake_str):
        return "".join(word.title() for word in snake_str.replace(".", "_").split("_"))


# Usage
for model_file in Path(".").rglob("models/*.py"):
    if "test_" not in str(model_file):
        generator = TestGenerator(model_file)
        test_content = generator.generate_test_file()

        # Write to test file
        test_file = model_file.parent.parent / "tests" / f"test_{model_file.stem}.py"
        test_file.parent.mkdir(exist_ok=True)

        if not test_file.exists():
            with open(test_file, "w") as f:
                f.write(test_content)
            print(f"✅ Generated {test_file}")
        else:
            print(f"⏭️  Skipped {test_file} (already exists)")
