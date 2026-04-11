"""Background workers for API calls (run off the GUI thread)."""

import logging

from pymyhondaplus import (
    DeviceKey,
    HondaAPI,
    HondaAPIError,
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


def _friendly_error(e: Exception) -> str:
    """Map exceptions to user-facing translated messages."""
    if isinstance(e, HondaAuthError):
        msg = str(e).lower()
        if "invalid_credentials" in msg or "invalid_grant" in msg:
            return t("error.invalid_credentials")
        if "account_locked" in msg or "currently blocked" in msg:
            return t("error.account_locked")
        return t("error.auth_failed", detail=str(e))
    if isinstance(e, HondaAPIError):
        status = getattr(e, "status_code", None) or ""
        return t("error.api_error", status=status)
    if isinstance(e, (ConnectionError, TimeoutError, OSError)):
        return t("error.network")
    return t("error.unexpected", detail=str(e))


def _build_auth(storage: SecretStorage) -> HondaAuth:
    """Create a HondaAuth instance, recovering from corrupted device keys."""
    try:
        device_key = DeviceKey(storage=storage)
    except (ValueError, Exception):
        storage.clear()
        device_key = DeviceKey(storage=storage)
    return HondaAuth(device_key=device_key)


def _complete_login(auth: HondaAuth, email: str, password: str, locale: str, progress) -> dict:
    """Run the standard initiate/complete login sequence."""
    progress(t("workers.logging_in"))
    result = auth.initiate_login(email, password, locale=locale)
    progress(t("workers.completing_login"))
    return auth.complete_login(
        email,
        password,
        result["transactionId"],
        result["signatureChallenge"],
        locale=locale,
    )


def _reset_device_authenticator(auth: HondaAuth, email: str, password: str, progress):
    """Trigger Honda's device registration flow, ignoring temporary blocks."""
    progress(t("workers.device_verification"))
    try:
        auth.reset_device_authenticator(email, password)
    except HondaAuthError as e:
        if "currently blocked" not in str(e):
            raise


def _verify_magic_link(auth: HondaAuth, link: str):
    """Verify a Honda magic link and return the parsed key info."""
    key, link_type = HondaAuth.parse_verify_link_key(link)
    if not key:
        raise ValueError(f"Could not extract key from link: {link}")
    auth.verify_magic_link(key, link_type)


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
            self.error.emit(_friendly_error(e))


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
        self.auth = _build_auth(storage)

    def run(self):
        try:
            tokens = _complete_login(
                self.auth, self.email, self.password, self.locale, self.progress.emit
            )
            self.finished.emit(tokens)
        except HondaAuthError as e:
            if "device-authenticator-not-registered" in str(e):
                self.device_registration_needed.emit()
            else:
                self.error.emit(_friendly_error(e))
        except Exception as e:
            logger.exception("Login error")
            self.error.emit(_friendly_error(e))

    def do_device_registration(self):
        """Called after user provides verification link (runs in thread)."""
        try:
            _reset_device_authenticator(
                self.auth, self.email, self.password, self.progress.emit
            )
            self.progress.emit(t("workers.device_verification"))
            self.device_registration_needed.emit()
        except Exception as e:
            self.error.emit(_friendly_error(e))

    def verify_and_login(self, link: str):
        """Called with the verification link. Runs in a new thread."""
        try:
            self.progress.emit(t("workers.verifying_link"))
            _verify_magic_link(self.auth, link)
            tokens = _complete_login(
                self.auth, self.email, self.password, self.locale, self.progress.emit
            )
            self.finished.emit(tokens)
        except Exception as e:
            self.error.emit(_friendly_error(e))


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
            _reset_device_authenticator(
                self.auth, self.email, self.password, self.progress.emit
            )
            self.finished.emit()
        except Exception as e:
            self.error.emit(_friendly_error(e))


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
            self.progress.emit(t("workers.verifying_link"))
            _verify_magic_link(self.auth, self.link)
            tokens = _complete_login(
                self.auth, self.email, self.password, self.locale, self.progress.emit
            )
            self.finished.emit(tokens)
        except Exception as e:
            self.error.emit(_friendly_error(e))


class DashboardWorker(QThread):
    """Fetches dashboard data."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    auth_error = pyqtSignal()
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
                result = self.api.refresh_dashboard(self.vin)
                dashboard = self.api.get_dashboard_cached(self.vin)
                status = parse_ev_status(dashboard)
                status["_refresh_stale"] = not result.success
            else:
                self.progress.emit(t("workers.loading_status"))
                dashboard = self.api.get_dashboard(self.vin)
                status = parse_ev_status(dashboard)
            self.finished.emit(status)
        except HondaAuthError:
            self.auth_error.emit()
        except Exception as e:
            logger.exception("Dashboard error")
            self.error.emit(_friendly_error(e))


class CommandWorker(QThread):
    """Executes a remote command and waits for completion."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    auth_error = pyqtSignal()
    progress = pyqtSignal(str)

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

            result = self.api.wait_for_command(command_id, timeout=90)
            if result.success:
                self.finished.emit(self.label)
            elif result.timed_out:
                self.error.emit(t("workers.timed_out", label=self.label))
            else:
                self.error.emit(
                    f"{self.label}: {result.reason or result.status}")
        except HondaAuthError:
            self.auth_error.emit()
        except Exception as e:
            logger.exception("Command error")
            self.error.emit(f"{self.label}: {_friendly_error(e)}")


class TripsWorker(QThread):
    """Fetches trip history and statistics."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    auth_error = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, api: HondaAPI, vin: str, month_start: str = "",
                 include_locations: bool = False):
        super().__init__()
        self.api = api
        self.vin = vin
        self.month_start = month_start
        self.include_locations = include_locations

    def run(self):
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
        except HondaAuthError:
            self.auth_error.emit()
        except HondaAPIError:
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
            self.error.emit(_friendly_error(e))


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
            logger.debug("Update check failed", exc_info=True)


class ScheduleLoadWorker(QThread):
    """Fetches schedules and climate settings from dashboard."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    auth_error = pyqtSignal()
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
        except HondaAuthError:
            self.auth_error.emit()
        except Exception as e:
            logger.exception("Schedule load error")
            self.error.emit(_friendly_error(e))


class ScheduleSaveWorker(QThread):
    """Saves a schedule and waits for completion."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    auth_error = pyqtSignal()
    progress = pyqtSignal(str)

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

            result = self.api.wait_for_command(command_id, timeout=90)
            if result.success:
                self.finished.emit(self.label)
            elif result.timed_out:
                self.error.emit(t("workers.timed_out", label=self.label))
            else:
                self.error.emit(
                    f"{self.label}: {result.reason or result.status}")
        except HondaAuthError:
            self.auth_error.emit()
        except Exception as e:
            logger.exception("Schedule save error")
            self.error.emit(f"{self.label}: {_friendly_error(e)}")


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
            self.error.emit(_friendly_error(e))
