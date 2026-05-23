"""Background polling: cached dashboard + optional refresh-from-car ticks.

The poller fires two independent timers, each emitting a signal the host
(``MainWindow``) wires to a refresh action. The host is responsible for
ignoring ticks while the window is visible (the user is presumably
already there and can refresh by hand), so this module stays focused on
*when* to refresh, not *whether*.

Numeric values: minutes for the cached-dashboard interval, hours for the
refresh-from-car interval. Both are validated upstream in
``Settings.load`` and clamped to known-safe ranges, so the poller can
trust whatever it reads from the Settings object.
"""

import logging

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .config import Settings

logger = logging.getLogger(__name__)


class BackgroundPoller(QObject):
    """Owns the two background-polling timers (cached dashboard, car refresh).

    Construct it once, call ``start()`` after login, ``stop()`` on logout.
    The two timers run independently; each toggle in Settings controls
    whether its timer is started by ``start()``.

    The host should connect:
    - ``cached_refresh_requested`` to a non-fresh dashboard refresh
    - ``car_refresh_requested`` to a fresh refresh (wakes the TCU)
    """

    cached_refresh_requested = pyqtSignal()
    car_refresh_requested = pyqtSignal()

    def __init__(self, settings: Settings, parent: QObject | None = None):
        super().__init__(parent)
        self._settings = settings
        self._cached_timer = QTimer(self)
        self._cached_timer.timeout.connect(self.cached_refresh_requested.emit)
        self._car_timer = QTimer(self)
        self._car_timer.timeout.connect(self.car_refresh_requested.emit)
        self._configure_intervals()

    def _configure_intervals(self) -> None:
        cached_ms = self._settings.background_poll_cached_interval_min * 60 * 1000
        self._cached_timer.setInterval(cached_ms)
        car_ms = self._settings.background_car_refresh_hours * 60 * 60 * 1000
        self._car_timer.setInterval(car_ms)

    def start(self) -> None:
        """Start the timers that are enabled in Settings."""
        self._configure_intervals()
        if self._settings.background_poll_enabled:
            self._cached_timer.start()
            logger.info(
                "Background polling started (cached every %d min)",
                self._settings.background_poll_cached_interval_min)
        if self._settings.background_car_refresh_enabled:
            self._car_timer.start()
            logger.info(
                "Background car refresh started (every %d h)",
                self._settings.background_car_refresh_hours)

    def stop(self) -> None:
        """Stop both timers regardless of their current state."""
        was_active = self._cached_timer.isActive() or self._car_timer.isActive()
        self._cached_timer.stop()
        self._car_timer.stop()
        if was_active:
            logger.info("Background polling stopped")

    @property
    def is_running(self) -> bool:
        return self._cached_timer.isActive() or self._car_timer.isActive()
