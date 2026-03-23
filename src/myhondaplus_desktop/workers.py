"""Background workers for API calls (run off the GUI thread)."""

import time
import logging

from PyQt6.QtCore import QThread, pyqtSignal

from pymyhondaplus import HondaAPI, HondaAuth, DeviceKey, HondaAPIError, parse_ev_status, SecretStorage
from pymyhondaplus.api import compute_trip_stats

logger = logging.getLogger(__name__)


class ApiWorker(QThread):
    """Base worker that runs a callable in a thread."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            logger.exception("Worker error")
            self.error.emit(str(e))


class LoginWorker(QThread):
    """Handles the login flow (initiate + complete)."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    device_registration_needed = pyqtSignal()

    def __init__(self, email: str, password: str, storage: SecretStorage,
                 locale: str = "it"):
        super().__init__()
        self.email = email
        self.password = password
        self.locale = locale
        try:
            self.device_key = DeviceKey(storage=storage)
        except (ValueError, Exception):
            # Corrupted key — clear and generate fresh
            storage.clear()
            self.device_key = DeviceKey(storage=storage)
        self.auth = HondaAuth(device_key=self.device_key)

    def run(self):
        try:
            self.progress.emit("Logging in...")
            result = self.auth.initiate_login(
                self.email, self.password, locale=self.locale)
            self.progress.emit("Completing login...")
            tokens = self.auth.complete_login(
                self.email, self.password,
                result["transactionId"], result["signatureChallenge"],
                locale=self.locale,
            )
            self.finished.emit(tokens)
        except RuntimeError as e:
            if "device-authenticator-not-registered" in str(e):
                self.device_registration_needed.emit()
            else:
                self.error.emit(str(e))
        except Exception as e:
            logger.exception("Login error")
            self.error.emit(str(e))

    def do_device_registration(self):
        """Called after user provides verification link (runs in thread)."""
        try:
            self.progress.emit("Requesting device verification...")
            try:
                self.auth.reset_device_authenticator(self.email, self.password)
            except RuntimeError as e:
                if "currently blocked" not in str(e):
                    raise
            self.progress.emit("Waiting for email verification...")
            self.device_registration_needed.emit()
        except Exception as e:
            self.error.emit(str(e))

    def verify_and_login(self, link: str):
        """Called with the verification link. Runs in a new thread."""
        try:
            key, link_type = HondaAuth.parse_verify_link_key(link)
            if not key:
                self.error.emit(f"Could not extract key from link: {link}")
                return
            self.progress.emit("Verifying link...")
            self.auth.verify_magic_link(key, link_type)
            self.progress.emit("Logging in...")
            result = self.auth.initiate_login(
                self.email, self.password, locale=self.locale)
            tokens = self.auth.complete_login(
                self.email, self.password,
                result["transactionId"], result["signatureChallenge"],
                locale=self.locale,
            )
            self.finished.emit(tokens)
        except Exception as e:
            self.error.emit(str(e))


class DeviceRegistrationWorker(QThread):
    """Handles the device registration step."""
    finished = pyqtSignal()
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, auth: HondaAuth, email: str, password: str):
        super().__init__()
        self.auth = auth
        self.email = email
        self.password = password

    def run(self):
        try:
            self.progress.emit("Requesting device verification email...")
            try:
                self.auth.reset_device_authenticator(self.email, self.password)
            except RuntimeError as e:
                if "currently blocked" not in str(e):
                    raise
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class VerifyAndLoginWorker(QThread):
    """Verifies magic link then completes login."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, auth: HondaAuth, email: str, password: str,
                 link: str, locale: str = "it"):
        super().__init__()
        self.auth = auth
        self.email = email
        self.password = password
        self.link = link
        self.locale = locale

    def run(self):
        try:
            key, link_type = HondaAuth.parse_verify_link_key(self.link)
            if not key:
                self.error.emit(f"Could not extract key from link: {self.link}")
                return
            self.progress.emit("Verifying link...")
            self.auth.verify_magic_link(key, link_type)
            self.progress.emit("Logging in...")
            result = self.auth.initiate_login(
                self.email, self.password, locale=self.locale)
            tokens = self.auth.complete_login(
                self.email, self.password,
                result["transactionId"], result["signatureChallenge"],
                locale=self.locale,
            )
            self.finished.emit(tokens)
        except Exception as e:
            self.error.emit(str(e))


class DashboardWorker(QThread):
    """Fetches dashboard data."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, api: HondaAPI, vin: str, fresh: bool = False):
        super().__init__()
        self.api = api
        self.vin = vin
        self.fresh = fresh

    def run(self):
        try:
            if self.fresh:
                self.progress.emit("Waking up car...")
            else:
                self.progress.emit("Loading status...")
            dashboard = self.api.get_dashboard(self.vin, fresh=self.fresh)
            status = parse_ev_status(dashboard)
            self.finished.emit(status)
        except Exception as e:
            logger.exception("Dashboard error")
            self.error.emit(str(e))


class CommandWorker(QThread):
    """Executes a remote command and polls for completion."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    POLL_INTERVAL = 2
    TIMEOUT = 60

    def __init__(self, api: HondaAPI, label: str, func, *args, **kwargs):
        super().__init__()
        self.api = api
        self.label = label
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            self.progress.emit(f"Sending {self.label}...")
            command_id = self._func(*self._args, **self._kwargs)
            if not command_id:
                self.error.emit(f"{self.label}: no command ID returned")
                return

            start = time.time()
            while time.time() - start < self.TIMEOUT:
                self.progress.emit(
                    f"{self.label}: polling... ({int(time.time() - start)}s)")
                result = self.api.poll_command(command_id)
                if result["status_code"] == 200:
                    self.finished.emit(self.label)
                    return
                time.sleep(self.POLL_INTERVAL)

            self.error.emit(f"{self.label}: timed out")
        except Exception as e:
            logger.exception("Command error")
            self.error.emit(f"{self.label}: {e}")


class TripsWorker(QThread):
    """Fetches trip history and statistics."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, api: HondaAPI, vin: str, month_start: str = "",
                 include_locations: bool = False):
        super().__init__()
        self.api = api
        self.vin = vin
        self.month_start = month_start
        self.include_locations = include_locations

    def run(self):
        import requests
        try:
            self.progress.emit("Loading trips...")
            trips = self.api.get_all_trips(self.vin, month_start=self.month_start)
            if self.include_locations and trips:
                for i, trip in enumerate(trips):
                    start = trip.get("StartTime", "")
                    end = trip.get("EndTime", "")
                    if start and end:
                        self.progress.emit(
                            f"Loading locations ({i + 1}/{len(trips)})...")
                        try:
                            locs = self.api.get_trip_locations(
                                self.vin, start, end)
                            trip.update(locs)
                        except Exception:
                            pass
            # Get fuel type for consumption unit
            vehicle = next(
                (v for v in self.api.tokens.vehicles if v["vin"] == self.vin),
                None)
            fuel_type = (vehicle or {}).get("fuel_type", "")
            stats = compute_trip_stats(trips, fuel_type=fuel_type) if trips else None
            self.finished.emit({"trips": trips, "stats": stats})
        except requests.HTTPError:
            # Check if user role is non-primary (e.g. secondary driver)
            vehicle = next(
                (v for v in self.api.tokens.vehicles if v["vin"] == self.vin),
                None)
            role = (vehicle or {}).get("role", "")
            if role and role != "primary":
                self.error.emit(
                    f"Trip history is not available for {role} users")
            else:
                self.error.emit("Failed to load trip history")
        except Exception as e:
            logger.exception("Trips error")
            self.error.emit(str(e))


class VehiclesWorker(QThread):
    """Fetches vehicle list (VIN, name, plate)."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, api: HondaAPI):
        super().__init__()
        self.api = api

    def run(self):
        try:
            vehicles = self.api.get_vehicles()
            # Store in tokens for persistence
            self.api.tokens.vehicles = vehicles
            self.api._save_tokens()
            self.finished.emit(vehicles)
        except Exception as e:
            logger.exception("Vehicles error")
            self.error.emit(str(e))
