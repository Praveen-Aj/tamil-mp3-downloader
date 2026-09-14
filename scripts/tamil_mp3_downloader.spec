# -*- mode: python ; coding: utf-8 -*-
"""
Compatibility-focused PyInstaller spec for tamil-mp3-downloader
This spec does not rely on Tree or other helpers that may move between PyInstaller versions.
It walks the `data/` and `screenshots/` folders and creates a list of (src, dest) file tuples.
Build with:
    pyinstaller tamil_mp3_downloader.spec
"""

import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE

block_cipher = None
ROOT_DIR = os.path.abspath(os.getcwd())

# read version from VERSION file if present
_version = '0.0.0'
try:
    version_file = os.path.join(ROOT_DIR, 'VERSION')
    if os.path.exists(version_file):
        with open(version_file, 'r', encoding='utf-8') as vf:
            _v = vf.read().strip()
            if _v:
                _version = _v
except Exception:
    pass

EXE_NAME = f"tamil-mp3-downloader-v{_version}"

# collect data files
datas = []

hiddenimports = [
    'bs4',
    'requests',
    'colorama',
    'clint',
]

binaries = []
aria2_path = os.path.join(ROOT_DIR, 'aria2c.exe')
if os.path.exists(aria2_path):
    binaries.append((aria2_path, '.'))

a = Analysis(
    [os.path.join(ROOT_DIR, 'main.py')],
    pathex=[ROOT_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name=EXE_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
