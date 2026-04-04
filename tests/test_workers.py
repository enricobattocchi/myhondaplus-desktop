"""Tests for worker threads."""

from unittest.mock import MagicMock, patch

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
    assert "not_available" in results["error"]


def test_trips_api_error_primary_driver(mock_api):
    mock_api.get_all_trips.side_effect = HondaAPIError(500, "Server error")

    worker = TripsWorker(mock_api, "VIN123")
    results = _run_worker(worker)

    assert results["finished"] is None
    assert results["error"] is not None
    assert "secondary" not in results["error"]
