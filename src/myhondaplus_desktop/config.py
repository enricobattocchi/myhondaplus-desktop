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


@dataclass
class Settings:
    vin: str = ""
    language: str = ""  # empty = auto-detect from system locale

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
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except (json.JSONDecodeError, TypeError):
            return cls()
