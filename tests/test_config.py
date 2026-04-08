"""Tests for config and local storage paths."""

from myhondaplus_desktop import config
from myhondaplus_desktop.config import Settings


def test_settings_uses_platform_config_dir(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    monkeypatch.setattr(config.platformdirs, "user_data_path", lambda *args, **kwargs: data_dir)

    assert config.settings_dir() == config_dir
    assert config.settings_file() == config_dir / "settings.json"
    assert config.storage_dir() == data_dir
    assert config.token_file() == data_dir / "honda_tokens.json"
    assert config.device_key_file() == data_dir / "honda_device_key.pem"


def test_settings_save_and_load_roundtrip(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    monkeypatch.setattr(config.platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)

    settings = Settings(vin="VIN123", language="it")
    settings.save()

    saved = config.settings_file()
    assert saved == config_dir / "settings.json"
    assert saved.exists()
    assert Settings.load() == settings


def test_settings_load_ignores_invalid_json(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    monkeypatch.setattr(config.platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    path = config.settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")

    assert Settings.load() == Settings()


def test_settings_load_ignores_unknown_fields(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    monkeypatch.setattr(config.platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    path = config.settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"vin": "VIN123", "language": "en", "unexpected": "value"}',
        encoding="utf-8",
    )

    assert Settings.load() == Settings(vin="VIN123", language="en")
