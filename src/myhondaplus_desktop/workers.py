"""Background workers for API calls (run off the GUI thread)."""

import logging
import time

from pymyhondaplus import (
    DeviceKey,
    HondaAPI,
    HondaAuth,
    HondaAuthError,
    SecretStorage,
    parse_charge_schedule,
    parse_climate_schedule,
    parse_ev_status,
)
from pymyhondaplus.api import compute_trip_stats
from PyQt6.QtCore import QThread, pyqtSignal

from .i18n import t

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
            self.progress.emit(t("workers.logging_in"))
            result = self.auth.initiate_login(
                self.email, self.password, locale=self.locale)
            self.progress.emit(t("workers.completing_login"))
            tokens = self.auth.complete_login(
                self.email, self.password,
                result["transactionId"], result["signatureChallenge"],
                locale=self.locale,
            )
            self.finished.emit(tokens)
        except HondaAuthError as e:
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
            self.progress.emit(t("workers.device_verification"))
            try:
                self.auth.reset_device_authenticator(self.email, self.password)
            except HondaAuthError as e:
                if "currently blocked" not in str(e):
                    raise
            self.progress.emit(t("workers.device_verification"))
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
            self.progress.emit(t("workers.verifying_link"))
            self.auth.verify_magic_link(key, link_type)
            self.progress.emit(t("workers.logging_in"))
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
            self.progress.emit(t("workers.device_verification"))
            try:
                self.auth.reset_device_authenticator(self.email, self.password)
            except HondaAuthError as e:
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
            self.progress.emit(t("workers.verifying_link"))
            self.auth.verify_magic_link(key, link_type)
            self.progress.emit(t("workers.logging_in"))
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
                self.progress.emit(t("workers.waking_car"))
            else:
                self.progress.emit(t("workers.loading_status"))
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
            self.progress.emit(t("workers.sending", label=self.label))
            command_id = self._func(*self._args, **self._kwargs)
            if not command_id:
                self.error.emit(t("workers.no_command_id", label=self.label))
                return

            start = time.time()
            while time.time() - start < self.TIMEOUT:
                self.progress.emit(
                    t("workers.polling", label=self.label,
                      seconds=int(time.time() - start)))
                result = self.api.poll_command(command_id)
                if result["status_code"] == 200:
                    self.finished.emit(self.label)
                    return
                time.sleep(self.POLL_INTERVAL)

            self.error.emit(t("workers.timed_out", label=self.label))
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
            self.progress.emit(t("trips.loading"))
            trips = self.api.get_all_trips(self.vin, month_start=self.month_start)
            if self.include_locations and trips:
                for i, trip in enumerate(trips):
                    start = trip.get("StartTime", "")
                    end = trip.get("EndTime", "")
                    if start and end:
                        self.progress.emit(
                            t("trips.loading_locations",
                              current=i + 1, total=len(trips)))
                        try:
                            locs = self.api.get_trip_locations(
                                self.vin, start, end)
                            trip.update(locs)
                        except Exception:
                            pass
            # Get fuel type and distance unit
            vehicle = next(
                (v for v in self.api.tokens.vehicles if v["vin"] == self.vin),
                None)
            fuel_type = (vehicle or {}).get("fuel_type", "")
            # Fetch dashboard for unit info
            dashboard = self.api.get_dashboard(self.vin)
            ev_status = parse_ev_status(dashboard)
            distance_unit = ev_status.get("distance_unit", "km")
            stats = compute_trip_stats(
                trips, fuel_type=fuel_type,
                distance_unit=distance_unit) if trips else None
            self.finished.emit({"trips": trips, "stats": stats})
        except requests.HTTPError:
            # Check if user role is non-primary (e.g. secondary driver)
            vehicle = next(
                (v for v in self.api.tokens.vehicles if v["vin"] == self.vin),
                None)
            role = (vehicle or {}).get("role", "")
            if role and role != "primary":
                self.error.emit(t("trips.not_available", role=role))
            else:
                self.error.emit(t("trips.failed"))
        except Exception as e:
            logger.exception("Trips error")
            self.error.emit(str(e))


class UpdateCheckWorker(QThread):
    """Checks GitHub for a newer release."""
    update_available = pyqtSignal(str, str)  # (new_version, release_url)

    RELEASES_URL = "https://api.github.com/repos/enricobattocchi/myhondaplus-desktop/releases/latest"

    def __init__(self, current_version: str):
        super().__init__()
        self._current = current_version

    @staticmethod
    def _parse_version(v: str) -> tuple:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))

    def run(self):
        try:
            import json
            import urllib.request
            req = urllib.request.Request(
                self.RELEASES_URL,
                headers={"Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            tag = data.get("tag_name", "")
            url = data.get("html_url", "")
            if tag and self._parse_version(tag) > self._parse_version(self._current):
                self.update_available.emit(tag.lstrip("v"), url)
        except Exception:
            pass  # Fail silently


class ScheduleLoadWorker(QThread):
    """Fetches schedules and climate settings from dashboard."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, api: HondaAPI, vin: str):
        super().__init__()
        self.api = api
        self.vin = vin

    def run(self):
        try:
            self.progress.emit(t("schedules.loading"))
            dashboard = self.api.get_dashboard(self.vin)
            ev = parse_ev_status(dashboard)
            climate_schedule = parse_climate_schedule(dashboard)
            charge_schedule = parse_charge_schedule(dashboard)
            self.finished.emit({
                "climate_schedule": climate_schedule,
                "charge_schedule": charge_schedule,
                "climate_temp": ev.get("climate_temp", "normal"),
                "climate_duration": ev.get("climate_duration", 30),
                "climate_defrost": ev.get("climate_defrost", True),
            })
        except Exception as e:
            logger.exception("Schedule load error")
            self.error.emit(str(e))


class ScheduleSaveWorker(QThread):
    """Saves a schedule and polls for completion."""
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
            self.progress.emit(t("workers.sending", label=self.label))
            command_id = self._func(*self._args, **self._kwargs)
            if not command_id:
                self.finished.emit(self.label)
                return

            start = time.time()
            while time.time() - start < self.TIMEOUT:
                self.progress.emit(
                    t("workers.polling", label=self.label,
                      seconds=int(time.time() - start)))
                result = self.api.poll_command(command_id)
                if result["status_code"] == 200:
                    self.finished.emit(self.label)
                    return
                time.sleep(self.POLL_INTERVAL)

            self.error.emit(t("workers.timed_out", label=self.label))
        except Exception as e:
            logger.exception("Schedule save error")
            self.error.emit(f"{self.label}: {e}")


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
