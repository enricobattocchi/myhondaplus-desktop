"""Tests for worker threads."""

import json
from unittest.mock import MagicMock

import pytest
from pymyhondaplus import HondaAPIError, HondaAuthError

from myhondaplus_desktop import workers
from myhondaplus_desktop.workers import (
    CommandWorker,
    ScheduleLoadWorker,
    TripsWorker,
    UpdateCheckWorker,
    VehiclesWorker,
)


@pytest.fixture()
def mock_api():
    api = MagicMock()
    api.tokens.vehicles = [
        {"vin": "VIN123", "fuel_type": "BEV", "role": "primary"},
    ]
    return api


def _run_worker(worker):
    """Run the worker synchronously and capture signals."""
    results = {"finished": None, "error": None, "auth_error": False, "update": None}
    if hasattr(worker, "finished"):
        worker.finished.connect(lambda v: results.update(finished=v))
    if hasattr(worker, "error"):
        worker.error.connect(lambda v: results.update(error=v))
    if hasattr(worker, "auth_error"):
        worker.auth_error.connect(lambda: results.update(auth_error=True))
    if hasattr(worker, "update_available"):
        worker.update_available.connect(lambda version, url: results.update(update=(version, url)))
    worker.run()
    return results


def test_trips_api_error_secondary_driver(mock_api):
    mock_api.tokens.vehicles = [
        {"vin": "VIN123", "fuel_type": "BEV", "role": "secondary"},
    ]
    mock_api.get_all_trips.side_effect = HondaAPIError(403, "Forbidden")

    worker = TripsWorker(mock_api, "VIN123")
    results = _run_worker(worker)

    assert results["finished"] is None
    assert results["error"] is not None
    # Should mention non-primary role (translation key or resolved text)
    assert "not_available" in results["error"] or "secondary" in results["error"]


def test_trips_api_error_primary_driver(mock_api):
    mock_api.get_all_trips.side_effect = HondaAPIError(500, "Server error")

    worker = TripsWorker(mock_api, "VIN123")
    results = _run_worker(worker)

    assert results["finished"] is None
    assert results["error"] is not None
    # Should get the generic failure message, not the role-specific one
    assert "not_available" not in results["error"] and "secondary" not in results["error"]


def test_command_worker_success(mock_api):
    result = MagicMock(success=True, timed_out=False, reason="", status="done")
    mock_api.wait_for_command.return_value = result

    worker = CommandWorker(mock_api, "Lock", lambda: "cmd-123")
    results = _run_worker(worker)

    assert results["finished"] == "Lock"
    assert results["error"] is None
    mock_api.wait_for_command.assert_called_once_with("cmd-123")


def test_command_worker_timeout(mock_api):
    result = MagicMock(success=False, timed_out=True, reason="", status="timeout")
    mock_api.wait_for_command.return_value = result

    worker = CommandWorker(mock_api, "Lock", lambda: "cmd-123")
    results = _run_worker(worker)

    assert results["finished"] is None
    assert results["error"] is not None
    assert "timed out" in results["error"].lower()


def test_command_worker_auth_error(mock_api):
    worker = CommandWorker(
        mock_api,
        "Lock",
        lambda: (_ for _ in ()).throw(HondaAuthError(401, "expired")),
    )
    results = _run_worker(worker)

    assert results["auth_error"] is True
    assert results["finished"] is None
    assert results["error"] is None


def test_update_check_worker_emits_when_newer_release_available(monkeypatch):
    payload = {"tag_name": "v2.2.0", "html_url": "https://example.com/release"}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _Response())

    worker = UpdateCheckWorker("2.1.1")
    results = _run_worker(worker)

    assert results["update"] == ("2.2.0", "https://example.com/release")


def test_update_check_worker_ignores_older_or_equal_release(monkeypatch):
    payload = {"tag_name": "v2.1.1", "html_url": "https://example.com/release"}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _Response())

    worker = UpdateCheckWorker("2.1.1")
    results = _run_worker(worker)

    assert results["update"] is None


def test_schedule_load_worker_returns_parsed_schedule_data(monkeypatch, mock_api):
    monkeypatch.setattr(workers, "parse_ev_status", lambda dashboard: {
        "climate_temp": "hotter",
        "climate_duration": 20,
        "climate_defrost": False,
    })
    monkeypatch.setattr(workers, "parse_climate_schedule", lambda dashboard: [{"enabled": True}])
    monkeypatch.setattr(workers, "parse_charge_schedule", lambda dashboard: [{"location": "home"}])
    mock_api.get_dashboard.return_value = {"raw": True}

    worker = ScheduleLoadWorker(mock_api, "VIN123")
    results = _run_worker(worker)

    assert results["error"] is None
    assert results["finished"] == {
        "climate_schedule": [{"enabled": True}],
        "charge_schedule": [{"location": "home"}],
        "climate_temp": "hotter",
        "climate_duration": 20,
        "climate_defrost": False,
    }


def test_vehicles_worker_persists_loaded_vehicles(mock_api):
    vehicles = [{"vin": "VIN123", "name": "Honda e"}]
    mock_api.get_vehicles.return_value = vehicles

    worker = VehiclesWorker(mock_api)
    results = _run_worker(worker)

    assert results["error"] is None
    assert results["finished"] == vehicles
    assert mock_api.tokens.vehicles == vehicles
    mock_api._save_tokens.assert_called_once_with()
