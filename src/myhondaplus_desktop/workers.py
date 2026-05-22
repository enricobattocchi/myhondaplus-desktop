"""Background workers for API calls (run off the GUI thread).

All workers expose a ``result_ready`` signal (rather than overriding the
inherited ``finished`` signal). Owners listen to ``QThread.finished`` to
know when ``run()`` has actually returned, which is the only safe moment
to drop the last Python reference: dropping it while the thread is still
running triggers ``QThread::~QThread()`` -> ``qFatal`` -> ``abort()``.
Use :func:`retire_worker` when reassigning a field that holds a worker
that may still be in flight.
"""

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
from pymyhondaplus.api import CarLocation, compute_trip_stats
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


_USER_SIGNAL_NAMES = (
    "result_ready", "error", "progress", "auth_error",
    "device_registration_needed", "update_available",
)


def retire_worker(worker, retired_list):
    """Park a still-running QThread until ``run()`` returns.

    Reassigning the field that holds a running worker drops the only
    Python reference and triggers ``QThread::~QThread()``-while-running
    ``qFatal`` -> ``abort``. This holds a strong reference in the
    caller-owned ``retired_list`` until ``QThread.finished`` fires.

    Also disconnects the worker's user-facing signals so stale results
    don't update the UI after the caller has moved on.
    """
    if worker is None or not worker.isRunning():
        return
    for name in _USER_SIGNAL_NAMES:
        sig = getattr(worker, name, None)
        if sig is None:
            continue
        try:
            sig.disconnect()
        except TypeError:
            pass
    retired_list.append(worker)
    worker.finished.connect(
        lambda: retired_list.remove(worker)
        if worker in retired_list else None)


class ApiWorker(QThread):
    """Base worker that runs a callable in a thread."""
    result_ready = pyqtSignal(object)
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
            self.result_ready.emit(result)
        except Exception as e:
            logger.exception("Worker error")
            self.error.emit(_friendly_error(e))


class LoginWorker(QThread):
    """Handles the login flow (initiate + complete)."""
    result_ready = pyqtSignal(object)
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
            self.result_ready.emit(tokens)
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
            self.result_ready.emit(tokens)
        except Exception as e:
            self.error.emit(_friendly_error(e))


class DeviceRegistrationWorker(QThread):
    """Handles the device registration step."""
    result_ready = pyqtSignal()
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
            self.result_ready.emit()
        except Exception as e:
            self.error.emit(_friendly_error(e))


class VerifyAndLoginWorker(QThread):
    """Verifies magic link then completes login."""
    result_ready = pyqtSignal(object)
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
            self.result_ready.emit(tokens)
        except Exception as e:
            self.error.emit(_friendly_error(e))


class DashboardWorker(QThread):
    """Fetches dashboard data."""
    result_ready = pyqtSignal(object)
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
                command_id = self.api.refresh_dashboard(self.vin)
                result = self.api.wait_for_command(command_id, timeout=90)
                dashboard = self.api.get_dashboard_cached(self.vin)
                status = parse_ev_status(dashboard)
                self.result_ready.emit((status, not result.success))
            else:
                self.progress.emit(t("workers.loading_status"))
                dashboard = self.api.get_dashboard(self.vin)
                status = parse_ev_status(dashboard)
                self.result_ready.emit((status, False))
        except HondaAuthError:
            self.auth_error.emit()
        except Exception as e:
            logger.exception("Dashboard error")
            self.error.emit(_friendly_error(e))


class CommandWorker(QThread):
    """Executes a remote command and waits for completion."""
    result_ready = pyqtSignal(str)
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
                self.result_ready.emit(self.label)
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


class LocateWorker(QThread):
    """Locates the car via Honda's car-location endpoint.

    Honda's ``/tsp/car-location`` returns the GPS fix in the command-status
    response (in ``output.Content`` as a JSON-encoded payload), not by
    updating the dashboard cache. This worker calls the command, parses the
    result via ``CarLocation.from_command_result``, and emits the typed
    location for the UI to display directly.
    """
    result_ready = pyqtSignal(object)  # CarLocation or None on parse failure
    error = pyqtSignal(str)
    auth_error = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, api: HondaAPI, vin: str, label: str):
        super().__init__()
        self.api = api
        self.vin = vin
        self.label = label

    def run(self):
        try:
            self.progress.emit(t("workers.sending", label=self.label))
            command_id = self.api.refresh_location(self.vin)
            if not command_id:
                self.error.emit(t("workers.no_command_id", label=self.label))
                return
            result = self.api.wait_for_command(command_id, timeout=90)
            if not result.success:
                if result.timed_out:
                    self.error.emit(t("workers.timed_out", label=self.label))
                else:
                    self.error.emit(
                        f"{self.label}: {result.reason or result.status}")
                return
            self.result_ready.emit(CarLocation.from_command_result(result))
        except HondaAuthError:
            self.auth_error.emit()
        except Exception as e:
            logger.exception("Locate error")
            self.error.emit(f"{self.label}: {_friendly_error(e)}")


class TripsWorker(QThread):
    """Fetches trip history and statistics."""
    result_ready = pyqtSignal(object)
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
            self.result_ready.emit({"trips": trips, "stats": stats})
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
    result_ready = pyqtSignal(object)
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
            self.result_ready.emit({
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
    result_ready = pyqtSignal(str)
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
                self.result_ready.emit(self.label)
                return

            result = self.api.wait_for_command(command_id, timeout=90)
            if result.success:
                self.result_ready.emit(self.label)
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


class ImageWorker(QThread):
    """Downloads and caches a vehicle image."""
    result_ready = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url: str, cache_dir):
        super().__init__()
        self._url = url
        self._cache_dir = cache_dir

    def run(self):
        import hashlib
        import urllib.request
        from pathlib import Path

        try:
            cache_dir = Path(self._cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Determine extension from URL
            url_path = self._url.rsplit("?", 1)[0]
            if "." in url_path.rsplit("/", 1)[-1]:
                ext = "." + url_path.rsplit(".", 1)[-1].lower()
                if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                    ext = ".img"
            else:
                ext = ".img"

            key = hashlib.sha256(self._url.encode()).hexdigest()[:16]
            cached = cache_dir / f"{key}{ext}"

            if cached.exists():
                self.result_ready.emit(str(cached))
                return

            req = urllib.request.Request(self._url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            cached.write_bytes(data)
            self.result_ready.emit(str(cached))
        except Exception as e:
            logger.debug("Image download failed: %s", e)
            self.error.emit(str(e))


class VehiclesWorker(QThread):
    """Fetches vehicle list (VIN, name, plate)."""
    result_ready = pyqtSignal(object)
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
            self.result_ready.emit(vehicles)
        except Exception as e:
            logger.exception("Vehicles error")
            self.error.emit(_friendly_error(e))
