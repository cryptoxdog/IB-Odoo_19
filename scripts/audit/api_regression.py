#!/usr/bin/env python3
"""
API Contract Regression Detector
Compares current branch against main to find breaking changes.
"""

import ast
import subprocess
from pathlib import Path


class APIRegressionAudit:
    def __init__(self, repo_path=".", base_branch="main"):
        self.repo_path = Path(repo_path)
        self.base_branch = base_branch

    def get_git_diff_files(self):
        """Get list of changed Python files"""
        result = subprocess.run(
            ["git", "diff", "--name-only", self.base_branch, "HEAD"], capture_output=True, text=True, cwd=self.repo_path
        )
        return [f for f in result.stdout.split("\n") if f.endswith(".py")]

    def parse_python_file(self, file_path):
        """Extract public API from Python file"""
        try:
            with open(self.repo_path / file_path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except Exception:
            return {}

        api = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                api[class_name] = {"methods": {}, "fields": {}}

                for item in node.body:
                    # Public methods (not starting with _)
                    if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                        api[class_name]["methods"][item.name] = {
                            "args": [arg.arg for arg in item.args.args],
                            "decorators": [d.id if isinstance(d, ast.Name) else str(d) for d in item.decorator_list],
                            "returns": ast.unparse(item.returns) if item.returns else None,
                        }

        return api

    def get_file_at_commit(self, file_path, commit):
        """Get file content at specific commit"""
        result = subprocess.run(
            ["git", "show", f"{commit}:{file_path}"], capture_output=True, text=True, cwd=self.repo_path
        )
        return result.stdout if result.returncode == 0 else None

    def check_api_changes(self):
        """Detect breaking API changes"""
        errors = []
        changed_files = self.get_git_diff_files()

        for file_path in changed_files:
            if "/tests/" in file_path or "/__pycache__/" in file_path:
                continue

            # Parse current version
            current_api = self.parse_python_file(file_path)

            # Get and parse base branch version
            base_content = self.get_file_at_commit(file_path, self.base_branch)
            if not base_content:
                continue

            try:
                base_tree = ast.parse(base_content)
                base_api = {}
                for node in ast.walk(base_tree):
                    if isinstance(node, ast.ClassDef):
                        class_name = node.name
                        base_api[class_name] = {"methods": {}}
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                                base_api[class_name]["methods"][item.name] = {
                                    "args": [arg.arg for arg in item.args.args]
                                }
            except Exception:
                continue

            # Compare APIs
            for class_name, base_class in base_api.items():
                if class_name not in current_api:
                    errors.append(
                        {
                            "type": "CLASS_REMOVED",
                            "severity": "CRITICAL",
                            "class": class_name,
                            "file": file_path,
                            "message": f"Public class '{class_name}' was removed",
                        }
                    )
                    continue

                for method_name, base_method in base_class["methods"].items():
                    if method_name not in current_api[class_name]["methods"]:
                        errors.append(
                            {
                                "type": "METHOD_REMOVED",
                                "severity": "CRITICAL",
                                "class": class_name,
                                "method": method_name,
                                "file": file_path,
                                "message": f"Public method '{method_name}' was removed",
                            }
                        )
                        continue

                    current_method = current_api[class_name]["methods"][method_name]

                    # Check signature changes
                    if base_method["args"] != current_method["args"]:
                        errors.append(
                            {
                                "type": "SIGNATURE_CHANGED",
                                "severity": "HIGH",
                                "class": class_name,
                                "method": method_name,
                                "file": file_path,
                                "old_args": base_method["args"],
                                "new_args": current_method["args"],
                                "message": f"Method signature changed: {method_name}",
                            }
                        )

        return errors
