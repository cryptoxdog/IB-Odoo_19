#!/usr/bin/env python3
"""Keep a module README's ``module_version`` front matter equal to its manifest.

pre-commit passes the staged top-level ``plasticos_*/__manifest__.py`` files.
For each one, the module's ``README.md`` front matter line ``module_version:`` is
rewritten to the manifest ``version`` when they differ. Quoting is preserved and
nothing else in the README changes. A README without front matter, or whose
front matter has no ``module_version`` key, is left alone.

Exit status: 0 when every README already matched, 1 when a README was rewritten
(re-stage it and commit again) or a manifest version could not be read.

``tests/test_module_readme_batch_pipeline.py`` and
``tests/test_module_readme_index.py`` hold the README to the committed manifest
in CI; this hook makes the same fix at commit time instead of after a red run.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

# The same front-matter shape tests/test_module_readme_index.py reads.
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
VERSION_LINE = re.compile(r"^(module_version:[ \t]*)([\"']?)([^\"'\n]*?)\2[ \t]*$", re.MULTILINE)
MANIFEST_PATH = re.compile(r"^plasticos_[^/]+/__manifest__\.py$")


class ManifestError(ValueError):
    """The manifest has no readable string ``version``."""


def manifest_version(manifest: Path) -> str:
    try:
        data = ast.literal_eval(manifest.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError) as exc:
        raise ManifestError(f"{manifest}: cannot read the manifest ({exc})") from exc
    version = data.get("version") if isinstance(data, dict) else None
    if not isinstance(version, str) or not version.strip():
        raise ManifestError(f"{manifest}: no string 'version' key")
    return version.strip()


def sync(manifest: Path) -> Path | None:
    """Rewrite the README's module_version when it differs. Return the README when changed."""
    readme = manifest.parent / "README.md"
    if not readme.is_file():
        return None
    text = readme.read_text(encoding="utf-8")
    front = FRONT_MATTER.match(text)
    if front is None:
        return None
    block = front.group(1)
    line = VERSION_LINE.search(block)
    if line is None:
        return None
    version = manifest_version(manifest)
    if line.group(3) == version:
        return None
    quote = line.group(2)
    new_block = f"{block[: line.start()]}{line.group(1)}{quote}{version}{quote}{block[line.end() :]}"
    readme.write_text(f"{text[: front.start(1)]}{new_block}{text[front.end(1) :]}", encoding="utf-8")
    return readme


def main(argv: list[str]) -> int:
    status = 0
    for raw in argv:
        rel = Path(raw).as_posix()
        if not MANIFEST_PATH.match(rel):
            continue
        try:
            changed = sync(Path(raw))
        except ManifestError as exc:
            print(f"README module_version: {exc}", file=sys.stderr)
            status = 1
            continue
        if changed is not None:
            print(
                f"README module_version: updated {changed.as_posix()} to the manifest version; stage it and commit again"
            )
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
