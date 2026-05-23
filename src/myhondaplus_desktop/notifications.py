"""Edge-detection rules for desktop notifications.

The dispatcher takes two consecutive ``EVStatus``-like snapshots (any
object with ``.get(key, default)``) and the current Settings, and
returns a list of ``(title, body)`` tuples ready to show. The transport
(``QSystemTrayIcon.showMessage`` or anything else) is the caller's
responsibility.

The first snapshot after startup intentionally never fires anything:
without a "before" state we'd flood the user with "X happened" for
events that actually happened before the app was running.
"""

import logging

from .config import Settings
from .i18n import t

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Decide which notifications to fire given two consecutive snapshots."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def evaluate(self, previous, current,
                 vehicle_name: str = "") -> list[tuple[str, str]]:
        """Return the (title, body) pairs to fire for this transition.

        ``previous`` may be ``None`` (first snapshot of the session); in
        that case nothing fires. ``vehicle_name`` is interpolated into
        body strings (falls back to a localized "Your car" placeholder).
        """
        if previous is None or current is None:
            return []

        name = vehicle_name or t("notifications.fallback_vehicle_name")
        notifications: list[tuple[str, str]] = []
        s = self._settings

        if s.notify_charge_started:
            n = self._charge_started(previous, current, name)
            if n is not None:
                notifications.append(n)

        if s.notify_charge_stopped:
            n = self._charge_stopped(previous, current, name)
            if n is not None:
                notifications.append(n)

        if s.notify_climate_started:
            n = self._climate_started(previous, current, name)
            if n is not None:
                notifications.append(n)

        if s.notify_climate_stopped:
            n = self._climate_stopped(previous, current, name)
            if n is not None:
                notifications.append(n)

        if s.notify_door_unlocked:
            n = self._door_unlocked(previous, current, name)
            if n is not None:
                notifications.append(n)

        if s.notify_battery_low_pct > 0:
            n = self._battery_low(previous, current, s.notify_battery_low_pct, name)
            if n is not None:
                notifications.append(n)

        if s.notify_warning_lit:
            n = self._warning_lit(previous, current, name)
            if n is not None:
                notifications.append(n)

        return notifications

    @staticmethod
    def _charge_started(previous, current, name) -> tuple[str, str] | None:
        prev_status = previous.get("charge_status")
        curr_status = current.get("charge_status")
        if prev_status != "charging" and curr_status == "charging":
            return (
                t("notifications.charge_started.title"),
                t("notifications.charge_started.body", vehicle_name=name),
            )
        return None

    @staticmethod
    def _charge_stopped(previous, current, name) -> tuple[str, str] | None:
        """Charging stopped (for any reason: 100%, charge limit, interruption).

        Honda's normalised `charge_status` only has `charging` / `stopped`
        / `unknown`, so we cannot tell the three cases apart on the wire.
        The body reports the level the battery was at when charging
        stopped, which the user can use to infer the cause themselves.
        """
        prev_status = previous.get("charge_status")
        curr_status = current.get("charge_status")
        if prev_status == "charging" and curr_status != "charging":
            battery = current.get("battery_level", 0)
            return (
                t("notifications.charge_stopped.title"),
                t("notifications.charge_stopped.body",
                  vehicle_name=name, battery=battery),
            )
        return None

    @staticmethod
    def _climate_started(previous, current, name) -> tuple[str, str] | None:
        prev_active = bool(previous.get("climate_active"))
        curr_active = bool(current.get("climate_active"))
        if not prev_active and curr_active:
            return (
                t("notifications.climate_started.title"),
                t("notifications.climate_started.body", vehicle_name=name),
            )
        return None

    @staticmethod
    def _climate_stopped(previous, current, name) -> tuple[str, str] | None:
        prev_active = bool(previous.get("climate_active"))
        curr_active = bool(current.get("climate_active"))
        if prev_active and not curr_active:
            return (
                t("notifications.climate_stopped.title"),
                t("notifications.climate_stopped.body", vehicle_name=name),
            )
        return None

    @staticmethod
    def _door_unlocked(previous, current, name) -> tuple[str, str] | None:
        prev_locked = previous.get("doors_locked")
        curr_locked = current.get("doors_locked")
        if prev_locked is True and curr_locked is False:
            return (
                t("notifications.door_unlocked.title"),
                t("notifications.door_unlocked.body", vehicle_name=name),
            )
        return None

    @staticmethod
    def _battery_low(previous, current, threshold: int, name) -> tuple[str, str] | None:
        prev_bat = previous.get("battery_level")
        curr_bat = current.get("battery_level")
        if prev_bat is None or curr_bat is None:
            return None
        try:
            prev_bat = int(prev_bat)
            curr_bat = int(curr_bat)
        except (TypeError, ValueError):
            return None
        if prev_bat >= threshold and curr_bat < threshold:
            return (
                t("notifications.battery_low.title"),
                t("notifications.battery_low.body",
                  vehicle_name=name, battery=curr_bat, threshold=threshold),
            )
        return None

    @classmethod
    def _warning_lit(cls, previous, current, name) -> tuple[str, str] | None:
        if cls._is_warning_clear(previous.get("warning_lamps")) and \
                not cls._is_warning_clear(current.get("warning_lamps")):
            return (
                t("notifications.warning_lit.title"),
                t("notifications.warning_lit.body", vehicle_name=name),
            )
        return None

    @staticmethod
    def _is_warning_clear(value) -> bool:
        """True if ``warning_lamps`` represents an absence of active warnings.

        Tolerant of the field's shape: int counter, list of lamps,
        comma-separated string, or None.
        """
        if value is None:
            return True
        if isinstance(value, bool):
            return not value
        if isinstance(value, int):
            return value == 0
        if isinstance(value, str):
            stripped = value.strip()
            return stripped in ("", "0", "none", "None")
        if isinstance(value, (list, tuple, set)):
            return len(value) == 0
        return False
