"""Shared PyInstaller invocation for release workflows."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

PACKAGE_ROOT = Path("src/myhondaplus_desktop")
ENTRYPOINT = PACKAGE_ROOT / "__main__.py"
DATA_DIRS = [
    ("icons", "myhondaplus_desktop/icons"),
    ("translations", "myhondaplus_desktop/translations"),
]
HIDDEN_IMPORTS = [
    "myhondaplus_desktop",
    "myhondaplus_desktop.app",
    "myhondaplus_desktop.config",
    "myhondaplus_desktop.i18n",
    "myhondaplus_desktop.icons",
    "myhondaplus_desktop.session",
    "myhondaplus_desktop.workers",
    "myhondaplus_desktop.widgets",
    "myhondaplus_desktop.widgets.dashboard",
    "myhondaplus_desktop.widgets.login",
    "myhondaplus_desktop.widgets.schedules",
    "myhondaplus_desktop.widgets.status_bar",
    "myhondaplus_desktop.widgets.trips",
    "pymyhondaplus",
    "pymyhondaplus.api",
    "pymyhondaplus.auth",
    "pymyhondaplus.storage",
]


def build_pyinstaller_command(name: str, *, icon: str = "", onefile: bool = False) -> list[str]:
    data_sep = ";" if os.name == "nt" else ":"
    command = [
        "pyinstaller",
        "--name",
        name,
        "--windowed",
    ]
    if onefile:
        command.append("--onefile")
    if icon:
        command.extend(["--icon", icon])
    for src_dir, dest_dir in DATA_DIRS:
        command.extend([
            "--add-data",
            f"{PACKAGE_ROOT / src_dir}{data_sep}{dest_dir}",
        ])
    for module in HIDDEN_IMPORTS:
        command.extend(["--hidden-import", module])
    command.append(str(ENTRYPOINT))
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="PyInstaller app name")
    parser.add_argument("--icon", default="", help="Optional icon file path")
    parser.add_argument("--onefile", action="store_true", help="Build a single-file executable")
    args = parser.parse_args()

    command = build_pyinstaller_command(args.name, icon=args.icon, onefile=args.onefile)
    print("Running:", " ".join(command))
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
