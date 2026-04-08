"""Minimal smoke checks for packaged desktop bundles."""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path

REQUIRED_RESOURCE_DIRS = [
    Path("myhondaplus_desktop/icons"),
    Path("myhondaplus_desktop/translations"),
]


def bundle_contains_resources(bundle_root: Path) -> bool:
    for rel_path in REQUIRED_RESOURCE_DIRS:
        if not any(path.is_dir() for path in bundle_root.rglob(str(rel_path))):
            return False
    return True


def smoke_run_executable(executable: Path, *, timeout_seconds: float = 3.0) -> None:
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    process = subprocess.Popen(
        [str(executable)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        time.sleep(timeout_seconds)
        return_code = process.poll()
        if return_code is not None and return_code != 0:
            stdout, stderr = process.communicate(timeout=1)
            details = []
            if stdout.strip():
                details.append(f"stdout:\n{stdout.strip()}")
            if stderr.strip():
                details.append(f"stderr:\n{stderr.strip()}")
            detail_text = ""
            if details:
                detail_text = "\n\n" + "\n\n".join(details)
            raise RuntimeError(
                f"Packaged app exited early with code {return_code}{detail_text}"
            )
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", required=True, help="Path to the built app directory")
    parser.add_argument("--executable", required=True, help="Path to the built executable")
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="Only validate bundle contents without launching the executable",
    )
    args = parser.parse_args()

    bundle_root = Path(args.bundle_root)
    executable = Path(args.executable)

    if not bundle_root.is_dir():
        raise SystemExit(f"Bundle root not found: {bundle_root}")
    if not executable.is_file():
        raise SystemExit(f"Executable not found: {executable}")
    if not bundle_contains_resources(bundle_root):
        raise SystemExit("Required packaged resources are missing")

    if not args.skip_run:
        smoke_run_executable(executable)

    print(f"Bundle smoke check passed for {bundle_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
