"""Validate that a release tag matches the application version."""

from __future__ import annotations

import sys

from myhondaplus_desktop import __version__


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
