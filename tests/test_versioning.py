"""Tests for package version configuration."""

import tomllib
from pathlib import Path

from myhondaplus_desktop import __version__
from scripts.check_release_version import release_tag_matches_version


def test_pyproject_uses_dynamic_version_from_package():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["dynamic"] == ["version"]
    assert "version" not in pyproject["project"]
    assert pyproject["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "myhondaplus_desktop.__version__"
    }


def test_release_tag_validation_accepts_supported_tag_formats():
    assert release_tag_matches_version(__version__)
    assert release_tag_matches_version(f"v{__version__}")


def test_release_tag_validation_rejects_mismatched_tags():
    assert not release_tag_matches_version("0.1.0")
    assert not release_tag_matches_version("v0.1.0")
