# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('store_profiles.db', '.'), ('C:\\Users\\Dell Optiplex 3070\\AppData\\Local\\Python\\pythoncore-3.14-64\\Lib\\site-packages\\tkinterdnd2', 'tkinterdnd2'), ('C:\\Users\\Dell Optiplex 3070\\AppData\\Local\\Python\\pythoncore-3.14-64\\Lib\\site-packages\\customtkinter', 'customtkinter')],
    hiddenimports=['tkinterdnd2', 'customtkinter', 'PIL', 'piexif'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='td geo tag',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='td geo tag',
)
