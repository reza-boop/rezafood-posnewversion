"""Entry point for RezaFood POS v11.3.

Run with:
    python app.py
"""

from __future__ import annotations

import sys

from db import Database
from logger import logger
from utils import ensure_dirs


def main() -> None:
    """Initialise directories, database, and the Tkinter event loop."""
    try:
        import tkinter as tk
    except ModuleNotFoundError as exc:
        print(
            "Tkinter is not installed in this Python environment.\n"
            "Install Tkinter for your OS (for Debian/Ubuntu: sudo apt install python3-tk),\n"
            "or run the web mode instead with: python web_app.py",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    from ui.login import LoginWindow
    from ui.main import PosApp

    ensure_dirs()
    logger.info("RezaFood POS starting up.")

    db = Database()

    # The root window is hidden; it is used as a transient parent for the
    # login dialog and later replaced by the main application window.
    root = tk.Tk()
    root.withdraw()

    def on_login_success(user: dict) -> None:
        """Callback fired when the user authenticates successfully."""
        db.add_audit_log(user["id"], user["username"], "login", "")

        # Build a fresh Tk window for the main app
        app_root = tk.Tk()
        pos_app = PosApp(app_root, db, user)
        app_root.protocol("WM_DELETE_WINDOW", lambda: _on_close(app_root, pos_app))
        app_root.mainloop()

        # After the main window closes, re-open the login dialog so another
        # user can log in without restarting the process.
        _restart_login(root, db)

    def _on_close(window: tk.Tk, pos_app: PosApp) -> None:
        pos_app.shutdown()
        window.destroy()

    def _restart_login(parent: tk.Tk, database: Database) -> None:
        parent.deiconify()
        LoginWindow(parent, database, on_login_success)

    LoginWindow(root, db, on_login_success)
    root.mainloop()


if __name__ == "__main__":
    main()
