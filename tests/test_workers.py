"""Tests for worker threads."""

from unittest.mock import MagicMock

import pytest
from pymyhondaplus import HondaAPIError

from myhondaplus_desktop.workers import TripsWorker


@pytest.fixture()
def mock_api():
    api = MagicMock()
    api.tokens.vehicles = [
        {"vin": "VIN123", "fuel_type": "BEV", "role": "primary"},
    ]
    return api


def _run_worker(worker):
    """Run the worker synchronously and capture signals."""
    results = {"finished": None, "error": None}
    worker.finished.connect(lambda v: results.update(finished=v))
    worker.error.connect(lambda v: results.update(error=v))
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
