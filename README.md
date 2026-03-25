# My Honda+ for desktop

Unofficial desktop GUI for Honda Connect Europe (My Honda+). Control and monitor your Honda vehicle from your computer.

Built with PyQt6 and [pymyhondaplus](https://github.com/enricobattocchi/pymyhondaplus).

## Features

- **Vehicle dashboard** — battery level, range, charge status, plug status, charge limits, odometer
- **Location** — GPS coordinates with clickable OpenStreetMap link
- **Security** — door lock status, windows, hood, trunk, lights
- **Climate** — active/off status, cabin and interior temperature
- **Warnings** — active warning lamps
- **Remote commands** — lock/unlock, climate on/off/settings, charge on/off/limit, horn + lights, locate
- **Trip history** — monthly trip list with statistics, optional GPS locations, CSV export
- **Multi-vehicle support** — dropdown with vehicle name and plate number, auto-populated from your account
- **Secure storage** — tokens and device keys encrypted at rest via OS keyring or machine-derived key
- **Persistent login** — auto-refresh on expiry, no need to re-enter credentials
- **Lucide SVG icons** — crisp, theme-aware icons throughout the UI
- **Light/dark theme** — follows system theme, or force with `--light` / `--dark`
- **Multi-language** — English and Italian included, [easy to add more](TRANSLATING.md)

## Supported vehicles

Tested on Honda e. Should work with other Honda Connect Europe vehicles (e:Ny1, ZR-V, CR-V, Civic, HR-V, Jazz 2020+) — contributions welcome!

## Download

Pre-built binaries are available from the [latest release](https://github.com/enricobattocchi/myhondaplus-desktop/releases/latest):

| Platform | Download |
|----------|----------|
| macOS | `My-Honda-for-desktop-macOS.dmg` |
| Windows | `My-Honda-for-desktop-Windows.exe` |
| Linux | `My-Honda-for-desktop-Linux-x86_64.AppImage` |

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

# Force light or dark theme
myhondaplus-desktop --light
myhondaplus-desktop --dark
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

### Language

The app auto-detects your system language. To change it manually, open the About dialog (info button in the top bar) and select a language. The change takes effect on restart.

Available: English, Italian. See [TRANSLATING.md](TRANSLATING.md) to contribute a new language.

## Requirements

- Python 3.11+
- PyQt6 >= 6.6
- [pymyhondaplus](https://pypi.org/project/pymyhondaplus/) >= 3.0.0

### Optional

- `keyring` — for OS keyring integration (gnome-keyring, KDE Wallet, macOS Keychain). Without it, secrets are encrypted with a machine-derived key.

## Related projects

- [pymyhondaplus](https://github.com/enricobattocchi/pymyhondaplus) — Python client library and CLI for the Honda Connect Europe API
- [myhondaplus-homeassistant](https://github.com/enricobattocchi/myhondaplus-homeassistant) — Home Assistant integration

## Disclaimer

This project is **unofficial** and **not affiliated with, endorsed by, or connected to Honda Motor Co., Ltd.** in any way.

- Use at your own risk. The authors accept no responsibility for any damage to your vehicle, account, or warranty.
- Honda may change their API at any time, which could break this application without notice.
- Sending remote commands (lock, unlock, climate, charging) to your vehicle is your responsibility.
- This project does not store or transmit your credentials to any third party. Authentication is performed directly with Honda's servers. Tokens are encrypted at rest.

## License

GPL-3.0-or-later
