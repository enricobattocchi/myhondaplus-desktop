"""Tests for the shared PyInstaller build script."""

import os

from scripts.build_pyinstaller import build_pyinstaller_command


def test_build_command_includes_shared_assets_and_imports():
    command = build_pyinstaller_command("My Honda+ for desktop", icon="app-icon.icns")

    assert command[:4] == ["pyinstaller", "--name", "My Honda+ for desktop", "--windowed"]
    assert "--icon" in command
    assert "app-icon.icns" in command
    assert "src/myhondaplus_desktop/__main__.py" in command
    assert "myhondaplus_desktop.session" in command
    assert "myhondaplus_desktop.widgets.schedules" in command

    separator = ";" if os.name == "nt" else ":"
    assert f"src/myhondaplus_desktop/icons{separator}myhondaplus_desktop/icons" in command
    assert (
        f"src/myhondaplus_desktop/translations{separator}myhondaplus_desktop/translations"
        in command
    )


def test_build_command_adds_onefile_only_when_requested():
    normal = build_pyinstaller_command("App")
    onefile = build_pyinstaller_command("App", onefile=True)

    assert "--onefile" not in normal
    assert "--onefile" in onefile
