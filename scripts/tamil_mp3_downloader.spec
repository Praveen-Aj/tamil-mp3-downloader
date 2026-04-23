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

def collect_folder(src_folder, dest_folder):
    """Walk src_folder and return a list of (absolute_src_path, dest_path_inside_exe) tuples."""
    out = []
    if not os.path.exists(src_folder):
        return out
    for root, dirs, files in os.walk(src_folder):
        for f in files:
            src_path = os.path.join(root, f)
            # compute relative path under src_folder
            rel_dir = os.path.relpath(root, src_folder)
            if rel_dir == '.':
                rel_dir = ''
            dest_path = os.path.join(dest_folder, rel_dir)
            out.append((src_path, dest_path))
    return out

# collect data files
datas = []
datas += collect_folder(os.path.join(ROOT_DIR, 'data'), 'data')
datas += collect_folder(os.path.join(ROOT_DIR, 'screenshots'), 'screenshots')

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
    [os.path.join(ROOT_DIR, 'gui.py')],
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
