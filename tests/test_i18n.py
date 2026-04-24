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


def test_active_capability_labels_translated_english():
    load_language("en")
    caps = VehicleCapabilities(raw={
        "telematicsRemoteLockUnlock": {"featureStatus": "active"},
        "telematicsRemoteCharge": {"featureStatus": "active"},
        "telematicsRemoteHorn": {"featureStatus": "notSupported"},
    })
    labels = active_capability_labels(caps)
    assert "Lock/Unlock" in labels
    assert "Charging" in labels
    assert "Horn" not in labels
    assert len(labels) == 2


def test_active_capability_labels_translated_italian():
    load_language("it")
    caps = VehicleCapabilities(raw={
        "telematicsRemoteLockUnlock": {"featureStatus": "active"},
    })
    labels = active_capability_labels(caps)
    assert labels == ["Blocca/Sblocca"]


def test_active_capability_labels_unknown_key_renders_raw():
    load_language("en")
    caps = VehicleCapabilities(raw={
        "useSpecificTemperatureControl": {"featureStatus": "active"},
        "telematicsFuturePhonyFeature": {"featureStatus": "active"},
    })
    labels = active_capability_labels(caps)
    assert "useSpecificTemperatureControl" in labels
    assert "telematicsFuturePhonyFeature" in labels


def test_active_capability_labels_no_actives():
    load_language("en")
    caps = VehicleCapabilities(raw={
        "telematicsRemoteLockUnlock": {"featureStatus": "notSupported"},
    })
    assert active_capability_labels(caps) == []


def test_active_capability_labels_no_raw():
    load_language("en")
    caps = VehicleCapabilities(raw={})
    assert active_capability_labels(caps) == []
