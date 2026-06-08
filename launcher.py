"""Smart launcher for RezaFood POS."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional, Sequence, Tuple


def _tkinter_available() -> bool:
    try:
        import tkinter  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


def _has_graphical_display() -> bool:
    if sys.platform.startswith("linux"):
        return bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))
    return True


def choose_mode(preferred_mode: Optional[str] = None) -> Tuple[str, Optional[str]]:
    mode = (preferred_mode or os.getenv("REZAFOOD_RUN_MODE", "auto")).strip().lower()
    if mode not in {"auto", "desktop", "web"}:
        raise ValueError("REZAFOOD_RUN_MODE must be one of: auto, desktop, web")

    if mode == "web":
        return "web", None

    if mode == "desktop":
        if not _tkinter_available():
            return "desktop", "Tkinter is not installed in this Python environment."
        if not _has_graphical_display():
            return "desktop", "No graphical desktop session was detected."
        return "desktop", None

    if not _tkinter_available():
        return "web", "Tkinter is not installed in this Python environment."
    if not _has_graphical_display():
        return "web", "No graphical desktop session was detected."
    return "desktop", None


def _run_desktop() -> None:
    from app import main as desktop_main

    desktop_main()


def _run_web() -> None:
    from web_app import main as web_main

    web_main()


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Run RezaFood POS")
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="Force desktop mode",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Force web mode",
    )
    args = parser.parse_args(argv)

    preferred_mode: Optional[str] = None
    if args.desktop and args.web:
        parser.error("Choose only one of --desktop or --web.")
    elif args.desktop:
        preferred_mode = "desktop"
    elif args.web:
        preferred_mode = "web"

    mode, reason = choose_mode(preferred_mode)
    if mode == "desktop":
        if reason:
            print(
                f"{reason}\n"
                "Install Tkinter for your OS (for Debian/Ubuntu: sudo apt install python3-tk),\n"
                "or run the web mode instead with: python launcher.py --web",
                file=sys.stderr,
            )
            raise SystemExit(1)
        _run_desktop()
        return

    if reason:
        print(f"{reason}\nStarting web mode instead.", file=sys.stderr)
    _run_web()


if __name__ == "__main__":
    main()
