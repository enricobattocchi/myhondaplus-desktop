# My Honda+ for desktop (unofficial)

[![Release](https://img.shields.io/github/v/release/enricobattocchi/myhondaplus-desktop)](https://github.com/enricobattocchi/myhondaplus-desktop/releases)
[![Downloads](https://img.shields.io/github/downloads/enricobattocchi/myhondaplus-desktop/total.svg)](https://github.com/enricobattocchi/myhondaplus-desktop/releases)
[![Latest downloads](https://img.shields.io/github/downloads/enricobattocchi/myhondaplus-desktop/latest/total.svg)](https://github.com/enricobattocchi/myhondaplus-desktop/releases/latest)

Unofficial desktop GUI for Honda Connect Europe (My Honda+). Control and monitor your Honda vehicle from your computer.

Built with PyQt6 and [pymyhondaplus](https://github.com/enricobattocchi/pymyhondaplus).

> **Europe only** — this app uses the Honda Connect Europe API (My Honda+ app). It does **not** work with HondaLink (North America), Honda Connect (Japan/Asia), or any non-European Honda connected service.

## Disclaimer

This project is **unofficial** and **not affiliated with, endorsed by, or connected to Honda Motor Co., Ltd.** in any way.

- Use at your own risk. The authors accept no responsibility for any damage to your vehicle, account, or warranty.
- Honda may change their API at any time, which could break this application without notice.
- Sending remote commands (lock, unlock, climate, charging) to your vehicle is your responsibility.
- This project does not store or transmit your credentials to any third party. Authentication is performed directly with Honda's servers. Tokens are encrypted at rest.

## Features

- **Vehicle dashboard** — battery level, range, charge status, plug status, charge limits, odometer
- **Location** — GPS coordinates with clickable OpenStreetMap link
- **Security** — door lock status, windows, hood, trunk, lights
- **Climate** — active/off status, cabin and interior temperature
- **Warnings** — active warning lamps
- **Remote commands** — lock/unlock, climate on/off/settings, charge on/off/limit, horn + lights, locate
- **Charge & climate schedules** — view, create, and clear charge prohibition and climate schedules
- **Vehicle info** — VIN, model, grade, year, fuel type, weight, odometer, production date, registration date, country
- **Subscription details** — package, status, price, payment period, renewal, services list
- **Vehicle capabilities** — list of supported features for your vehicle
- **Geofence** — set, view, and clear a geofence centered on your vehicle
- **Trip history** — monthly trip list with statistics, optional GPS locations, CSV export
- **Multi-vehicle support** — dropdown with vehicle name and plate number, auto-populated from your account
- **Secure storage** — tokens and device keys encrypted at rest via OS keyring or machine-derived key
- **Persistent login** — auto-refresh on expiry, no need to re-enter credentials
- **Lucide SVG icons** — crisp, theme-aware icons throughout the UI
- **Light/dark theme** — auto-detects the system color scheme, or pick explicitly from Settings (System / Light / Dark). `--light` / `--dark` CLI flags still override.
- **System tray** — battery bar on the tray icon (coloured on Linux/Windows: green ≥ 50%, yellow 20-49%, red below; monochrome template on macOS with a "!" glyph below the user's low-battery threshold); tooltip with name and lock status; optional "close to tray" and "start minimized".
- **Background polling** — optional periodic dashboard refresh while the window is hidden (off by default; defaults match the HA integration when enabled).
- **Desktop notifications** — alerts for charging started / stopped, climate started / stopped, car unlocked, battery below a configurable threshold, warning light on.
- **Multi-language** — 13 languages included, [easy to add more](TRANSLATING.md)

## Supported vehicles

Tested on Honda e. Should work with other Honda Connect Europe vehicles (e:Ny1, ZR-V, CR-V, Civic, HR-V, Jazz 2020+) — contributions welcome!

## Download

Pre-built binaries are available from the [latest release](https://github.com/enricobattocchi/myhondaplus-desktop/releases/latest):

| Platform | File |
|----------|------|
| macOS | `My-Honda-Plus-for-desktop-<version>-macOS.dmg` |
| Windows | `My-Honda-Plus-for-desktop-<version>-Windows.exe` |
| Linux | `My-Honda-Plus-for-desktop-<version>-x86_64.AppImage` |

### Install via pip

```bash
pip install myhondaplus-desktop
```

### From source

```bash
git clone https://github.com/enricobattocchi/myhondaplus-desktop.git
cd myhondaplus-desktop
python -m venv .venv
.venv/bin/pip install -e .
```

## Usage

```bash
myhondaplus-desktop
# or
python -m myhondaplus_desktop

# Force light or dark theme (overrides the Settings choice for this run)
myhondaplus-desktop --light
myhondaplus-desktop --dark

# Start with the window hidden in the tray (useful for autostart entries)
myhondaplus-desktop --minimized
```

### First login

1. Enter your Honda Connect Europe (My Honda+) email and password
2. If this is a new device, the app will request a verification email from Honda
3. **Do not click** the link in the email — copy the URL and paste it in the dialog
4. You're in! Tokens are encrypted and saved locally for future sessions

### Dashboard

Once logged in, the app shows your vehicle status with auto-refresh. Use the buttons at the bottom to send commands to your car.

Commands that could be disruptive (unlock, horn + lights) require confirmation before sending.

### Trips

Switch to the Trips tab to see trip history for the current month. Use the arrows to navigate between months. Enable "Include locations" for start/end GPS coordinates (double-click to open in OpenStreetMap). Export to CSV with the Export button.

### Vehicle

The Vehicle tab shows your car's specifications, subscription services, and capabilities as reported by Honda Connect.

### Geofence

The Geofence tab shows a map with a circular geofence centered on your vehicle's location. Pick the radius from the dropdown (in km or miles, following your account's distance unit), then use Save to store it on Honda's servers or Clear to remove it. This mirrors the official app; for an arbitrary radius or a custom center, use the pymyhondaplus CLI.

### Settings

All preferences live in the **Impostazioni** tab (last tab on the right), grouped in four panels:

- **General** — language, theme.
- **Tray** — show the icon, "close to tray" (hide instead of quit when pressing the window's X), "start minimized" (window hidden at launch, app reachable from the tray).
- **Background polling** — refresh the cached dashboard at a configurable interval (5 / 10 / 15 / 30 / 60 minutes; default 10), and optionally wake the TCU on a slower one (6 / 12 / 24 hours). Polling only runs while the window is hidden — open window means the user is there and can refresh by hand.
- **Notifications** — desktop alerts for the events listed above, each independently toggleable. Notifications use the OS notification daemon (libnotify on Linux, balloon on Windows, NSUserNotification on macOS).

Most setting changes take effect on restart; the label below the panels makes that visible.

### System tray

When the OS exposes a tray (most Linux DEs, Windows, macOS menu bar) the app shows an icon with a battery bar drawn along the bottom. Linux and Windows render the bar in traffic-light colours; macOS uses a monochrome template (so the menu bar can tint it for light and dark themes) and overlays a "!" glyph when the battery falls below the user's low-battery threshold. The tooltip shows the vehicle name, battery percentage, and lock state and refreshes after every dashboard load.

The tray menu has **Show window**, **Settings** (jumps to the Settings tab), **Exit**, and a **Veicolo** submenu when the account has more than one vehicle.

Notes per platform:

- **GNOME** removed the native tray in 3.26 — install the **AppIndicator and KStatusNotifierItem Support** extension to make the icon visible. The app shows a hint in Settings if it detects GNOME without the extension.
- **macOS** keeps the icon as a monochrome template image so the menu bar can tint it properly; click opens the menu (single-click toggle is a Linux/Windows convention).
- **Wayland**: KDE works out of the box; GNOME-Wayland needs the same AppIndicator extension as X11; other compositors depend on the user's status bar configuration.

### Language

The app auto-detects your system language. Change it from the **General** group of the Settings tab. The change takes effect on restart.

Available: Czech, Danish, Dutch, English, French, German, Hungarian, Italian, Norwegian, Polish, Slovak, Spanish, Swedish. See [TRANSLATING.md](TRANSLATING.md) to contribute a new language.

### Theme

Same group as the language selector. Pick **System default** (follows the OS color scheme), **Light**, or **Dark**. The change takes effect on restart. CLI `--light` / `--dark` flags override the saved setting for that run.

## Requirements

- Python 3.11+
- PyQt6 >= 6.6
- [pymyhondaplus](https://pypi.org/project/pymyhondaplus/) >= 5.10.1

### Optional

- `keyring` — for OS keyring integration (gnome-keyring, KDE Wallet, macOS Keychain). Without it, secrets are encrypted with a machine-derived key.

## Related projects

- [pymyhondaplus](https://github.com/enricobattocchi/pymyhondaplus) — Python client library and CLI for the Honda Connect Europe API
- [myhondaplus-homeassistant](https://github.com/enricobattocchi/myhondaplus-homeassistant) — Home Assistant integration

## License

GPL-3.0-or-later
