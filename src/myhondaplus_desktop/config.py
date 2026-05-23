"""Configuration and settings persistence."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import platformdirs

APP_NAME = "myhondaplus-desktop"


def settings_dir() -> Path:
    return Path(platformdirs.user_config_path(APP_NAME, appauthor=False))


def settings_file() -> Path:
    return settings_dir() / "settings.json"


def storage_dir() -> Path:
    return Path(platformdirs.user_data_path(APP_NAME, appauthor=False))


def token_file() -> Path:
    return storage_dir() / "honda_tokens.json"


def device_key_file() -> Path:
    return storage_dir() / "honda_device_key.pem"


def image_cache_dir() -> Path:
    return storage_dir() / "image_cache"


# Background polling: allowed intervals.
# These are the values the Settings UI exposes; out-of-range values loaded
# from a hand-edited settings.json (or from a future version with different
# defaults) get clamped back to the safe default to avoid hammering the
# Honda backend.
ALLOWED_CACHED_INTERVALS = (5, 10, 15, 30, 60)
DEFAULT_CACHED_INTERVAL = 10
ALLOWED_CAR_REFRESH_HOURS = (6, 12, 24)
DEFAULT_CAR_REFRESH_HOURS = 12


@dataclass
class Settings:
    vin: str = ""
    language: str = ""  # empty = auto-detect from system locale
    theme: str = "system"  # one of "system", "light", "dark"
    # System tray
    tray_enabled: bool = True
    close_to_tray: bool = False
    start_minimized: bool = False
    # Background polling (only runs while the window is hidden / minimized)
    background_poll_enabled: bool = False
    background_poll_cached_interval_min: int = DEFAULT_CACHED_INTERVAL
    background_car_refresh_enabled: bool = False
    background_car_refresh_hours: int = DEFAULT_CAR_REFRESH_HOURS
    # Desktop notifications, evaluated on every dashboard-loaded snapshot.
    # The library normalises Honda's chargeStatus to {charging, stopped,
    # unknown}: there is no separate "complete" value, so we cannot tell
    # apart "finished at 100%", "reached the configured charge limit", and
    # "interrupted mid-session" — they all surface as `stopped`.
    notify_charge_started: bool = False
    notify_charge_stopped: bool = True
    notify_climate_started: bool = False
    notify_climate_stopped: bool = False
    notify_door_unlocked: bool = False
    notify_battery_low_pct: int = 0  # 0 disables; valid range 1..100
    notify_warning_lit: bool = False

    def save(self):
        path = settings_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> "Settings":
        path = settings_file()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            loaded = cls(**{k: v for k, v in data.items()
                            if k in cls.__dataclass_fields__})
        except (json.JSONDecodeError, TypeError):
            return cls()
        # Clamp polling intervals to allowed values. We never want a
        # corrupted or hand-edited file to push polling below 5 minutes.
        if loaded.background_poll_cached_interval_min not in ALLOWED_CACHED_INTERVALS:
            loaded.background_poll_cached_interval_min = DEFAULT_CACHED_INTERVAL
        if loaded.background_car_refresh_hours not in ALLOWED_CAR_REFRESH_HOURS:
            loaded.background_car_refresh_hours = DEFAULT_CAR_REFRESH_HOURS
        # Clamp the battery-low threshold: 0 means disabled, otherwise 1..100.
        # `bool` is a subclass of `int`; reject it explicitly so a hand-edited
        # `true` doesn't quietly enable a 1% threshold.
        if (not isinstance(loaded.notify_battery_low_pct, int)
                or isinstance(loaded.notify_battery_low_pct, bool)):
            loaded.notify_battery_low_pct = 0
        elif loaded.notify_battery_low_pct < 0:
            loaded.notify_battery_low_pct = 0
        elif loaded.notify_battery_low_pct > 100:
            loaded.notify_battery_low_pct = 100
        return loaded
