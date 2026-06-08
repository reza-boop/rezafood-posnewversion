"""Shared runtime settings and startup messages."""

from __future__ import annotations

import os

TKINTER_MISSING_REASON = "Tkinter is not installed in this Python environment."
NO_GRAPHICAL_DISPLAY_REASON = "No graphical desktop session was detected."
WEB_HOST_ENV = "REZAFOOD_WEB_HOST"
WEB_PORT_ENV = "REZAFOOD_WEB_PORT"
DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8000


def desktop_unavailable_message(reason: str) -> str:
    return (
        f"{reason}\n"
        "Install Tkinter for your OS (for Debian/Ubuntu: sudo apt install python3-tk),\n"
        "or run the smart launcher with: python launcher.py"
    )


def resolve_web_bind(
    host_override: str | None = None,
    port_override: int | None = None,
) -> tuple[str, int]:
    raw_host = (
        host_override
        if host_override is not None
        else os.getenv(WEB_HOST_ENV, DEFAULT_WEB_HOST)
    )
    host = raw_host.strip() or DEFAULT_WEB_HOST

    if port_override is None:
        port_raw = os.getenv(WEB_PORT_ENV, str(DEFAULT_WEB_PORT))
    else:
        port_raw = str(port_override)

    try:
        port = int(port_raw)
    except ValueError as exc:
        raise ValueError(f"{WEB_PORT_ENV} must be a valid integer between 1 and 65535.") from exc

    if not 1 <= port <= 65535:
        raise ValueError(f"{WEB_PORT_ENV} must be between 1 and 65535.")

    return host, port
