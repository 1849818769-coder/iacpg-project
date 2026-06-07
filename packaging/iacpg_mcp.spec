# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the IACPG MCP server.

Build from the repository root:
  pyinstaller --clean --noconfirm packaging/iacpg_mcp.spec
"""

from PyInstaller.utils.hooks import collect_submodules
from pathlib import Path


ROOT = Path(SPECPATH).parent


hiddenimports = []
hiddenimports += collect_submodules("ice_core")
hiddenimports += [
    "chardet",
    "mcp",
    "networkx",
    "tree_sitter",
    "tree_sitter_c",
    "yaml",
]

datas = [
    (str(ROOT / "ice_core"), "ice_core"),
    (str(ROOT / "scripts"), "scripts"),
]

a = Analysis(
    [str(ROOT / "mcp_server.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="iacpg-mcp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="iacpg-mcp",
)
