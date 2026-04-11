"""Tests for worker threads."""

import json
from unittest.mock import MagicMock

import pytest
from pymyhondaplus import HondaAPIError, HondaAuthError

from myhondaplus_desktop import workers
from myhondaplus_desktop.workers import (
    CommandWorker,
    DashboardWorker,
    DeviceRegistrationWorker,
    LoginWorker,
    ScheduleLoadWorker,
    ScheduleSaveWorker,
    TripsWorker,
    UpdateCheckWorker,
    VehiclesWorker,
    VerifyAndLoginWorker,
    _friendly_error,
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
        worker.finished.connect(lambda *args: results.update(finished=args[0] if args else True))
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
    mock_api.wait_for_command.assert_called_once_with("cmd-123", timeout=90)


def test_command_worker_timeout(mock_api):
    result = MagicMock(success=False, timed_out=True, reason="", status="timeout")
    mock_api.wait_for_command.return_value = result

    worker = CommandWorker(mock_api, "Lock", lambda: "cmd-123")
    results = _run_worker(worker)

    assert results["finished"] is None
    assert results["error"] is not None
    assert "timed" in results["error"].lower()


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


def test_update_check_worker_logs_debug_on_failure(monkeypatch, caplog):
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(
        RuntimeError("network down")
    ))

    worker = UpdateCheckWorker("2.1.1")
    with caplog.at_level("DEBUG"):
        results = _run_worker(worker)

    assert results["update"] is None
    assert "Update check failed" in caplog.text


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


class DummyStorage:
    def __init__(self):
        self.clear_calls = 0

    def clear(self):
        self.clear_calls += 1


class FakeAuth:
    parse_key = ("magic", "email")

    def __init__(self, device_key=None):
        self.device_key = device_key
        self.initiate_result = {
            "transactionId": "tx-123",
            "signatureChallenge": "sig-456",
        }
        self.complete_result = {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
        }
        self.initiate_error = None
        self.reset_error = None
        self.verify_error = None
        self.calls = []

    def initiate_login(self, email, password, locale="it"):
        self.calls.append(("initiate_login", email, password, locale))
        if self.initiate_error:
            raise self.initiate_error
        return self.initiate_result

    def complete_login(self, email, password, transaction_id, signature_challenge, locale="it"):
        self.calls.append(
            ("complete_login", email, password, transaction_id, signature_challenge, locale)
        )
        return self.complete_result

    def reset_device_authenticator(self, email, password):
        self.calls.append(("reset_device_authenticator", email, password))
        if self.reset_error:
            raise self.reset_error

    def verify_magic_link(self, key, link_type):
        self.calls.append(("verify_magic_link", key, link_type))
        if self.verify_error:
            raise self.verify_error

    @staticmethod
    def parse_verify_link_key(link: str):
        return FakeAuth.parse_key


def test_login_worker_success(monkeypatch):
    auth = FakeAuth()
    monkeypatch.setattr(workers, "_build_auth", lambda storage: auth)

    worker = LoginWorker("user@example.com", "secret", storage=DummyStorage())
    results = _run_worker(worker)

    assert results["error"] is None
    assert results["finished"] == auth.complete_result
    assert auth.calls[:2] == [
        ("initiate_login", "user@example.com", "secret", "it"),
        ("complete_login", "user@example.com", "secret", "tx-123", "sig-456", "it"),
    ]


def test_login_worker_requests_device_registration(monkeypatch):
    auth = FakeAuth()
    auth.initiate_error = HondaAuthError(401, "device-authenticator-not-registered")
    monkeypatch.setattr(workers, "_build_auth", lambda storage: auth)

    worker = LoginWorker("user@example.com", "secret", storage=DummyStorage())
    state = {"needed": False}
    worker.device_registration_needed.connect(lambda: state.update(needed=True))
    results = _run_worker(worker)

    assert state["needed"] is True
    assert results["finished"] is None
    assert results["error"] is None


def test_device_registration_worker_ignores_blocked_error():
    auth = FakeAuth()
    auth.reset_error = HondaAuthError(429, "currently blocked")

    worker = DeviceRegistrationWorker(auth, "user@example.com", "secret")
    results = _run_worker(worker)

    assert results["error"] is None
    assert results["finished"] is True


def test_verify_and_login_worker_success(monkeypatch):
    auth = FakeAuth()
    monkeypatch.setattr(workers.HondaAuth, "parse_verify_link_key", lambda link: ("magic", "email"))
    worker = VerifyAndLoginWorker(auth, "user@example.com", "secret", "magic-link")
    results = _run_worker(worker)

    assert results["error"] is None
    assert results["finished"] == auth.complete_result
    assert ("verify_magic_link", "magic", "email") in auth.calls


def test_verify_and_login_worker_reports_bad_link(monkeypatch):
    auth = FakeAuth()
    monkeypatch.setattr(workers.HondaAuth, "parse_verify_link_key", lambda link: ("", ""))
    worker = VerifyAndLoginWorker(auth, "user@example.com", "secret", "bad-link")
    results = _run_worker(worker)

    assert results["finished"] is None
    assert "Could not extract key from link" in results["error"]


def test_dashboard_worker_fresh_success(monkeypatch, mock_api):
    mock_api.refresh_dashboard.return_value = MagicMock(success=True)
    mock_api.get_dashboard_cached.return_value = {"raw": True}
    monkeypatch.setattr(workers, "parse_ev_status", lambda d: {"battery": 80})

    worker = DashboardWorker(mock_api, "VIN123", fresh=True)
    results = _run_worker(worker)

    assert results["error"] is None
    assert results["finished"]["battery"] == 80
    assert results["finished"]["_refresh_stale"] is False
    mock_api.refresh_dashboard.assert_called_once_with("VIN123")
    mock_api.get_dashboard_cached.assert_called_once_with("VIN123")


def test_dashboard_worker_fresh_car_not_responding(monkeypatch, mock_api):
    mock_api.refresh_dashboard.return_value = MagicMock(success=False)
    mock_api.get_dashboard_cached.return_value = {"raw": True}
    monkeypatch.setattr(workers, "parse_ev_status", lambda d: {"battery": 70})

    worker = DashboardWorker(mock_api, "VIN123", fresh=True)
    results = _run_worker(worker)

    assert results["error"] is None
    assert results["finished"]["battery"] == 70
    assert results["finished"]["_refresh_stale"] is True


def test_dashboard_worker_cached_has_no_stale_flag(monkeypatch, mock_api):
    mock_api.get_dashboard.return_value = {"raw": True}
    monkeypatch.setattr(workers, "parse_ev_status", lambda d: {"battery": 90})

    worker = DashboardWorker(mock_api, "VIN123", fresh=False)
    results = _run_worker(worker)

    assert results["error"] is None
    assert "_refresh_stale" not in results["finished"]
    mock_api.refresh_dashboard.assert_not_called()


def test_schedule_save_worker_uses_90s_timeout(mock_api):
    result = MagicMock(success=True)
    mock_api.wait_for_command.return_value = result

    worker = ScheduleSaveWorker(mock_api, "Climate", lambda vin, rules: "cmd-456", "VIN123", [])
    results = _run_worker(worker)

    assert results["finished"] == "Climate"
    mock_api.wait_for_command.assert_called_once_with("cmd-456", timeout=90)


# --- _friendly_error tests ---


def test_friendly_error_network():
    assert _friendly_error(ConnectionError("refused")) == "Could not connect to Honda servers. Please check your internet connection."


def test_friendly_error_timeout():
    assert _friendly_error(TimeoutError()) == "Could not connect to Honda servers. Please check your internet connection."


def test_friendly_error_invalid_credentials():
    e = HondaAuthError(401, "invalid_credentials")
    assert _friendly_error(e) == "Invalid email or password. Please try again."


def test_friendly_error_account_locked():
    e = HondaAuthError(429, "currently blocked")
    assert _friendly_error(e) == "Account temporarily locked. Please try again later."


def test_friendly_error_api_error():
    e = HondaAPIError(500, "Internal Server Error")
    result = _friendly_error(e)
    assert "500" in result


def test_friendly_error_generic():
    e = RuntimeError("something weird")
    result = _friendly_error(e)
    assert "something weird" in result
