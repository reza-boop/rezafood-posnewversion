"""Smart launcher for RezaFood POS."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from runtime_bootstrap import (
    NO_GRAPHICAL_DISPLAY_REASON,
    TKINTER_MISSING_REASON,
    desktop_unavailable_message,
)


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


def choose_mode(preferred_mode: str | None = None) -> tuple[str, str | None]:
    mode = (preferred_mode or os.getenv("REZAFOOD_RUN_MODE", "auto")).strip().lower()
    if mode not in {"auto", "desktop", "web"}:
        raise ValueError("REZAFOOD_RUN_MODE must be one of: auto, desktop, web")

    if mode == "web":
        return "web", None

    if mode == "desktop":
        if not _tkinter_available():
            return "desktop", TKINTER_MISSING_REASON
        if not _has_graphical_display():
            return "desktop", NO_GRAPHICAL_DISPLAY_REASON
        return "desktop", None

    if not _tkinter_available():
        return "web", TKINTER_MISSING_REASON
    if not _has_graphical_display():
        return "web", NO_GRAPHICAL_DISPLAY_REASON
    return "desktop", None


def _run_desktop() -> None:
    from app import main as desktop_main

    desktop_main()


def _run_web(host: str | None = None, port: int | None = None) -> None:
    from web_app import main as web_main

    web_args: list[str] = []
    if host:
        web_args.extend(["--host", host])
    if port is not None:
        web_args.extend(["--port", str(port)])
    web_main(web_args)


def main(argv: Sequence[str] | None = None) -> None:
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
    parser.add_argument(
        "--host",
        help="Web host (used in web mode, default from REZAFOOD_WEB_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Web port (used in web mode, default from REZAFOOD_WEB_PORT)",
    )
    args = parser.parse_args(argv)

    preferred_mode: str | None = None
    if args.desktop and args.web:
        parser.error("Choose only one of --desktop or --web.")
    elif args.desktop:
        preferred_mode = "desktop"
    elif args.web:
        preferred_mode = "web"

    mode, reason = choose_mode(preferred_mode)
    if mode == "desktop":
        if reason:
            print(desktop_unavailable_message(reason), file=sys.stderr)
            raise SystemExit(1)
        _run_desktop()
        return

    if reason:
        print(f"{reason}\nStarting web mode instead.", file=sys.stderr)
    _run_web(args.host, args.port)


if __name__ == "__main__":
    main()
