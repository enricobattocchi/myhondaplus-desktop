"""Configuration and settings persistence."""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from pymyhondaplus.api import DEFAULT_TOKEN_FILE
from pymyhondaplus.auth import DEFAULT_DEVICE_KEY_FILE

SETTINGS_DIR = Path.home() / ".config" / "myhondaplus-desktop"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"


@dataclass
class Settings:
    vin: str = ""
    language: str = ""  # empty = auto-detect from system locale

    def save(self):
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls) -> "Settings":
        if not SETTINGS_FILE.exists():
            return cls()
        try:
            data = json.loads(SETTINGS_FILE.read_text())
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except (json.JSONDecodeError, TypeError):
            return cls()
