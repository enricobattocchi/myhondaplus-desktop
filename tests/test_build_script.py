"""Tests for the shared PyInstaller build script."""

import os
from pathlib import Path

import pytest

from scripts.build_pyinstaller import build_pyinstaller_command
from scripts.smoke_test_bundle import bundle_contains_resources, smoke_run_executable


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


def test_bundle_contains_required_resources(tmp_path):
    (tmp_path / "foo" / "myhondaplus_desktop" / "icons").mkdir(parents=True)
    (tmp_path / "bar" / "myhondaplus_desktop" / "translations").mkdir(parents=True)

    assert bundle_contains_resources(tmp_path) is True


def test_bundle_detects_missing_resources(tmp_path):
    (tmp_path / "myhondaplus_desktop" / "icons").mkdir(parents=True)

    assert bundle_contains_resources(tmp_path) is False


def test_smoke_run_executable_accepts_running_process(monkeypatch):
    events = []

    class FakeProcess:
        def poll(self):
            return None

        def communicate(self, timeout):
            raise AssertionError("communicate should not be called")

        def terminate(self):
            events.append("terminate")

        def wait(self, timeout):
            events.append(("wait", timeout))

    monkeypatch.setattr("scripts.smoke_test_bundle.subprocess.Popen", lambda *args, **kwargs: FakeProcess())
    monkeypatch.setattr("scripts.smoke_test_bundle.time.sleep", lambda _: None)

    smoke_run_executable(Path("/tmp/fake-app"))

    assert events == ["terminate", ("wait", 5)]


def test_smoke_run_executable_rejects_early_failure(monkeypatch):
    class FakeProcess:
        def poll(self):
            return 1

        def communicate(self, timeout):
            assert timeout == 1
            return ("boot log", "missing library")

        def terminate(self):
            raise AssertionError("terminate should not be called")

        def wait(self, timeout):
            raise AssertionError("wait should not be called")

    monkeypatch.setattr("scripts.smoke_test_bundle.subprocess.Popen", lambda *args, **kwargs: FakeProcess())
    monkeypatch.setattr("scripts.smoke_test_bundle.time.sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="exited early with code 1") as exc_info:
        smoke_run_executable(Path("/tmp/fake-app"))

    assert "stdout:\nboot log" in str(exc_info.value)
    assert "stderr:\nmissing library" in str(exc_info.value)
