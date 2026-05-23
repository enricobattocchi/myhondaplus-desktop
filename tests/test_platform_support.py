"""Tests for the platform / desktop-environment detection helpers."""

import sys

from myhondaplus_desktop import platform_support


def test_is_macos_reflects_sys_platform(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert platform_support.is_macos() is True
    monkeypatch.setattr(sys, "platform", "linux")
    assert platform_support.is_macos() is False


def test_is_windows_reflects_sys_platform(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert platform_support.is_windows() is True
    monkeypatch.setattr(sys, "platform", "linux")
    assert platform_support.is_windows() is False


def test_is_linux_reflects_sys_platform(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert platform_support.is_linux() is True
    monkeypatch.setattr(sys, "platform", "linux2")
    assert platform_support.is_linux() is True
    monkeypatch.setattr(sys, "platform", "darwin")
    assert platform_support.is_linux() is False


def test_desktop_env_returns_xdg_value_lowercased(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    assert platform_support.desktop_env() == "gnome"
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    assert platform_support.desktop_env() == "kde"


def test_desktop_env_empty_off_linux(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    assert platform_support.desktop_env() == ""


def test_desktop_env_empty_when_unset(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    assert platform_support.desktop_env() == ""


def test_session_type_returns_xdg_session_type(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    assert platform_support.session_type() == "wayland"
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    assert platform_support.session_type() == "x11"


def test_is_gnome_matches_gnome_variants(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    assert platform_support.is_gnome() is True
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "ubuntu:GNOME")
    assert platform_support.is_gnome() is True
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    assert platform_support.is_gnome() is False
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "MATE")
    assert platform_support.is_gnome() is False


def test_click_opens_menu_only_on_macos(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert platform_support.click_opens_menu() is True
    monkeypatch.setattr(sys, "platform", "linux")
    assert platform_support.click_opens_menu() is False
    monkeypatch.setattr(sys, "platform", "win32")
    assert platform_support.click_opens_menu() is False
