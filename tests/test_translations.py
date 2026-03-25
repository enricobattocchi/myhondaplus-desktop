"""Tests to verify translation file consistency."""

import json
from importlib.resources import files


def _load_translation(lang: str) -> dict:
    path = files("myhondaplus_desktop") / "translations" / f"{lang}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_italian_has_all_english_keys():
    """Every key in en.json should exist in it.json."""
    en = _load_translation("en")
    it = _load_translation("it")
    missing = [k for k in en if k not in it]
    assert not missing, f"Italian missing keys: {missing}"


def test_english_has_all_italian_keys():
    """No extra keys in it.json that don't exist in en.json."""
    en = _load_translation("en")
    it = _load_translation("it")
    extra = [k for k in it if k not in en]
    assert not extra, f"Italian has extra keys: {extra}"


def test_placeholders_match():
    """Placeholders in translations should match the English ones."""
    import re
    en = _load_translation("en")
    it = _load_translation("it")
    placeholder_re = re.compile(r"\{(\w+)\}")

    for key in en:
        if key not in it:
            continue
        en_placeholders = set(placeholder_re.findall(en[key]))
        it_placeholders = set(placeholder_re.findall(it[key]))
        assert en_placeholders == it_placeholders, (
            f"Key '{key}': EN has {en_placeholders}, IT has {it_placeholders}")


def test_no_empty_values():
    """No translation value should be empty."""
    for lang in ["en", "it"]:
        data = _load_translation(lang)
        empty = [k for k, v in data.items() if not v.strip()]
        assert not empty, f"{lang}.json has empty values: {empty}"
