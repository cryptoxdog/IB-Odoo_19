#!/usr/bin/env python3
"""
Critical Manifest Checker
=========================
Validates that essential files, classes, and methods defined in
ci/critical_manifest.json exist in the codebase.

This serves as a "Do Not Delete" lock for critical architecture.
"""

import ast
import json
import sys
from pathlib import Path


class CriticalManifestChecker:
    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir)
        self.manifest_path = self.root_dir / "ci" / "critical_manifest.json"
        self.errors = []

    def load_manifest(self):
        if not self.manifest_path.exists():
            print(f"⚠️  Manifest not found at {self.manifest_path}")
            return None
        with open(self.manifest_path) as f:
            return json.load(f)

    def check_file_existence(self, file_path):
        full_path = self.root_dir / file_path
        if not full_path.exists():
            self.errors.append(f"❌ MISSING FILE: {file_path}")
            return False
        return True

    def check_symbols(self, file_path, class_name, required_methods=None):
        full_path = self.root_dir / file_path
        try:
            with open(full_path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except Exception as e:
            self.errors.append(f"❌ PARSE ERROR: {file_path}: {e}")
            return

        found_class = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                found_class = node
                break

        if not found_class:
            self.errors.append(f"❌ MISSING CLASS: '{class_name}' in {file_path}")
            return

        if required_methods:
            existing_methods = {n.name for n in found_class.body if isinstance(n, ast.FunctionDef)}
            for method in required_methods:
                if method not in existing_methods:
                    self.errors.append(f"❌ MISSING METHOD: '{class_name}.{method}' in {file_path}")

    def run(self):
        print(f"🔒 Checking Critical Manifest: {self.manifest_path}")
        manifest = self.load_manifest()
        if not manifest:
            return 1

        # 1. Check Files
        for file_path in manifest.get("files", []):
            self.check_file_existence(file_path)

        # 2. Check Symbols
        for symbol in manifest.get("symbols", []):
            file_path = symbol["file"]
            if self.check_file_existence(file_path):
                self.check_symbols(file_path, symbol["class"], symbol.get("methods", []))

        print("-" * 60)
        if self.errors:
            print(f"FAILED: Found {len(self.errors)} critical missing components:")
            for err in self.errors:
                print(err)
            return 1
        else:
            print("✅ All critical components verified.")
            return 0


if __name__ == "__main__":
    checker = CriticalManifestChecker()
    sys.exit(checker.run())
