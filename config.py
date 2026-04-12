"""Application-wide constants and theme configuration for RezaFood POS."""

APP_NAME = "RezaFood POS"
APP_VERSION = "11.3"

DB_NAME = "rezafood.db"
RECEIPTS_DIR = "receipts"
BACKUPS_DIR = "backups"
EXPORTS_DIR = "exports"

# ---------------------------------------------------------------------------
# Colour palette (dark Catppuccin-Mocha inspired)
# ---------------------------------------------------------------------------
THEME = {
    "bg": "#1e1e2e",
    "fg": "#cdd6f4",
    "accent": "#89b4fa",
    "accent2": "#a6e3a1",
    "danger": "#f38ba8",
    "warning": "#fab387",
    "surface": "#313244",
    "surface2": "#45475a",
    "button_bg": "#89b4fa",
    "button_fg": "#1e1e2e",
    "entry_bg": "#313244",
    "entry_fg": "#cdd6f4",
    "select_bg": "#585b70",
    "tree_bg": "#1e1e2e",
    "tree_fg": "#cdd6f4",
    "tree_heading_bg": "#313244",
    "tree_heading_fg": "#89b4fa",
    "tree_row_odd": "#1e1e2e",
    "tree_row_even": "#26273a",
    "green": "#a6e3a1",
    "red": "#f38ba8",
}

# ---------------------------------------------------------------------------
# Fonts (Segoe UI looks great on Windows; fallback to system font elsewhere)
# ---------------------------------------------------------------------------
FONT = {
    "default": ("Segoe UI", 10),
    "bold": ("Segoe UI", 10, "bold"),
    "heading": ("Segoe UI", 12, "bold"),
    "title": ("Segoe UI", 14, "bold"),
    "large": ("Segoe UI", 18, "bold"),
    "mono": ("Consolas", 10),
    "mono_small": ("Consolas", 9),
}

# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------
PAYMENT_METHODS = ["Cash", "Card", "QR/E-Wallet"]
ROLES = ["admin", "cashier"]
CATEGORIES = ["Food", "Beverage", "Snack", "Dessert", "Other"]
LOW_STOCK_THRESHOLD = 5
AUDIT_LOG_LIMIT = 500

# ---------------------------------------------------------------------------
# Security / session
# ---------------------------------------------------------------------------
SESSION_TIMEOUT_MINUTES = 15   # auto-logout after this many minutes idle
MAX_LOGIN_ATTEMPTS = 5         # failed logins before lockout
LOGIN_LOCKOUT_SECONDS = 300    # lockout duration in seconds (5 min)
MIN_PASSWORD_LENGTH = 6        # minimum password length enforced on new accounts

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE = "logs/rezafood.log"
