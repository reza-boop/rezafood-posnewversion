# RezaFood POS v11.3

A modular **Tkinter + SQLite** Point-of-Sale application for Windows (also
runs on macOS and Linux with Python 3.10+).

---

## Project structure

```
rezafood-posnewversion/
├── app.py            ← entry point  (run this)
├── config.py         ← constants, theme colours, fonts
├── utils.py          ← helpers: time, money, hashing, printing, CSV
├── db.py             ← Database class (SQLite CRUD)
├── receipts.py       ← ReceiptBuilder
├── ui/
│   ├── __init__.py
│   ├── login.py      ← LoginWindow
│   ├── dialogs.py    ← ProductDialog, UserDialog
│   └── main.py       ← PosApp (all tabs)
├── requirements.txt
└── .gitignore
```

Runtime directories (created automatically, excluded from git):

| Directory  | Contents                       |
|------------|--------------------------------|
| `receipts/`| Plain-text receipt files       |
| `backups/` | Timestamped SQLite DB backups  |
| `exports/` | CSV exports                    |

---

## Requirements

- Python **3.9** or newer
- `tkinter` — included with the official Python installer on Windows
- `bcrypt` *(optional)* — for stronger password hashing

---

## Installation (Windows)

1. **Install Python** from <https://www.python.org/downloads/> (tick
   *"Add Python to PATH"* during setup).

2. **Clone or download** this repository.

3. Open **Command Prompt** or **PowerShell** in the project folder.

4. *(Optional but recommended)* Create a virtual environment:

   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```

5. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

6. **Run the application**:

   ```powershell
   python app.py
   ```

---

## Default credentials

| Username | Password  | Role  |
|----------|-----------|-------|
| `admin`  | `admin123`| admin |

Change the admin password from the **Users** tab after first login.

---

## Features

| Feature | Role |
|---------|------|
| Login / session management | all |
| POS cart, checkout, receipt print | cashier + admin |
| Order history, detail view, reprint | cashier + admin |
| Dashboard stats (today revenue, top products, low stock) | cashier + admin |
| Products CRUD | admin |
| Users CRUD | admin |
| Audit log view & CSV export | admin |
| DB backup | admin |
| CSV export (orders, products) | admin |

---

## Database

The SQLite database file **`rezafood.db`** is created automatically in the
working directory on first run.  It is excluded from version control via
`.gitignore`.

---

## Running on Linux / macOS

The application works on any platform with Python + tkinter installed.  On
Debian/Ubuntu install tkinter with:

```bash
sudo apt install python3-tk
```

Then run as usual:

```bash
python app.py
```

---

## Web mode (Android-friendly)

You can also run a mobile-friendly web version and open it from Android:

```bash
REZAFOOD_WEB_SECRET="change-this-secret" REZAFOOD_WEB_HOST="0.0.0.0" python web_app.py
```

Then open this address in your phone browser (same Wi-Fi network):

```text
http://<YOUR_COMPUTER_IP>:8000
```

Default login:

- Username: `admin`
- Password: `admin123`
