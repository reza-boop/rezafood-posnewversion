# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for RezaFood POS
# Build with:  pyinstaller rezafood.spec

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[str(Path('.').resolve())],
    binaries=[],
    datas=[],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.simpledialog',
        'tkinter.filedialog',
        'sqlite3',
        'bcrypt',
        'hmac',
        'hashlib',
        'zipfile',
        'threading',
        'json',
        'csv',
        'logging',
        'logging.handlers',
        'ui',
        'ui.login',
        'ui.main',
        'ui.dialogs',
        'ui.widgets',
        'ui.tabs',
        'ui.tabs.pos',
        'ui.tabs.orders',
        'ui.tabs.dashboard',
        'ui.tabs.products',
        'ui.tabs.users',
        'ui.tabs.audit',
        'ui.tabs.settings',
        'services',
        'services.order_service',
        'services.product_service',
        'services.report_service',
        'services.backup_service',
        'services.sync_service',
        'repositories',
        'repositories.base',
        'repositories.user',
        'repositories.product',
        'repositories.order',
        'repositories.discount',
        'repositories.audit',
        'repositories.report',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'mypy', 'flake8', 'ruff'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RezaFood-POS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # No black console window — GUI only
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,            # Replace with 'assets/icon.ico' if you add an icon
)
