"""Validate that a release tag matches the application version."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def read_package_version() -> str:
    init_py = Path("src/myhondaplus_desktop/__init__.py")
    module = ast.parse(init_py.read_text(encoding="utf-8"), filename=str(init_py))
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__version__":
                    value = node.value
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        return value.value
    raise RuntimeError(f"Could not read __version__ from {init_py}")


__version__ = read_package_version()


def release_tag_matches_version(release_tag: str) -> bool:
    expected_tags = {__version__, f"v{__version__}"}
    return release_tag in expected_tags


def main() -> int:
    release_tag = sys.argv[1] if len(sys.argv) > 1 else ""
    expected_tags = {__version__, f"v{__version__}"}

    print(f"Application version: {__version__}")

    if not release_tag:
        print("No release tag provided; skipping tag validation.")
        return 0

    print(f"Release tag: {release_tag}")
    if not release_tag_matches_version(release_tag):
        print(
            "Release tag does not match application version. "
            f"Expected one of: {', '.join(sorted(expected_tags))}",
            file=sys.stderr,
        )
        return 1

    print("Release tag matches application version.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
