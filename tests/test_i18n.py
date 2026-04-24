"""Tests for the i18n module."""

from pymyhondaplus.api import VehicleCapabilities

from myhondaplus_desktop import i18n
from myhondaplus_desktop.i18n import (
    _detect_language,
    active_capability_labels,
    active_language,
    available_languages,
    load_language,
    t,
)


def test_available_languages():
    langs = available_languages()
    assert "en" in langs
    assert "it" in langs


def test_load_english():
    load_language("en")
    assert active_language() == "en"
    assert t("app.name") == "My Honda+ for desktop"


def test_load_italian():
    load_language("it")
    assert active_language() == "it"
    assert t("app.name") == "My Honda+ per desktop"


def test_fallback_to_english():
    load_language("xx")  # nonexistent language
    assert active_language() == "xx"
    # Should fall back to English
    assert t("app.name") == "My Honda+ for desktop"


def test_placeholder_substitution():
    load_language("en")
    assert t("app.version", version="1.2.3") == "Version 1.2.3"


def test_placeholder_substitution_italian():
    load_language("it")
    assert t("app.version", version="1.2.3") == "Versione 1.2.3"


def test_missing_key_returns_key():
    load_language("en")
    assert t("nonexistent.key") == "nonexistent.key"


def test_bad_placeholder_no_crash():
    load_language("en")
    # Missing placeholder should not crash
    result = t("app.version")  # expects {version} but none given
    assert "version" in result.lower()


def test_detect_language_from_locale(monkeypatch):
    monkeypatch.setattr(i18n.locale, "getlocale", lambda: ("it_IT", "UTF-8"))
    assert _detect_language() == "it"


def test_detect_language_falls_back_to_english(monkeypatch):
    monkeypatch.setattr(i18n.locale, "getlocale", lambda: (None, None))
    assert _detect_language() == "en"


def test_active_capability_labels_returns_raw_api_keys():
    caps = VehicleCapabilities(raw={
        "telematicsRemoteLockUnlock": {"featureStatus": "active"},
        "telematicsRemoteCharge": {"featureStatus": "active"},
        "telematicsRemoteHorn": {"featureStatus": "notSupported"},
    })
    labels = active_capability_labels(caps)
    assert labels == ["telematicsRemoteCharge", "telematicsRemoteLockUnlock"]


def test_active_capability_labels_same_regardless_of_locale():
    caps = VehicleCapabilities(raw={
        "telematicsRemoteLockUnlock": {"featureStatus": "active"},
    })
    load_language("en")
    en_labels = active_capability_labels(caps)
    load_language("it")
    it_labels = active_capability_labels(caps)
    load_language("en")  # Restore default so test ordering is stable.
    assert en_labels == it_labels == ["telematicsRemoteLockUnlock"]


def test_active_capability_labels_future_flags_render_raw():
    caps = VehicleCapabilities(raw={
        "useSpecificTemperatureControl": {"featureStatus": "active"},
        "telematicsFuturePhonyFeature": {"featureStatus": "active"},
    })
    labels = active_capability_labels(caps)
    assert labels == ["telematicsFuturePhonyFeature", "useSpecificTemperatureControl"]


def test_active_capability_labels_no_actives():
    caps = VehicleCapabilities(raw={
        "telematicsRemoteLockUnlock": {"featureStatus": "notSupported"},
    })
    assert active_capability_labels(caps) == []


def test_active_capability_labels_no_raw():
    caps = VehicleCapabilities(raw={})
    assert active_capability_labels(caps) == []


def test_active_capability_labels_non_dict_entries_ignored():
    caps = VehicleCapabilities(raw={
        "telematicsRemoteLockUnlock": {"featureStatus": "active"},
        "bogusStringEntry": "not a dict",
        "anotherWeirdOne": None,
    })
    labels = active_capability_labels(caps)
    assert labels == ["telematicsRemoteLockUnlock"]
