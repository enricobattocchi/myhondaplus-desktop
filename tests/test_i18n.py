"""Tests for the i18n module."""

from myhondaplus_desktop.i18n import load_language, t, available_languages, active_language


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
