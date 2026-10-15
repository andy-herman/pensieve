# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the installed Pensieve backend (server/pensieve-server.exe).
# Built by desktop/installer/build-installer.ps1 with an x64 Python, so the same
# installer runs natively on x64 PCs and under emulation on ARM64 PCs.
#
# Bundled next to the code (resolved from pensieve.config.REPO_ROOT, which is
# PyInstaller's _internal folder at runtime):
#   frontend-proto/   the dashboard
#   prompts/          LLM prompts
#   starter-data/     generic goals + strands seeded into the user's data folder
#   onnx_models/      the MiniLM embedding model (no first-run download)

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

REPO = Path(SPECPATH).resolve().parent.parent
MODEL = Path(os.environ["PENSIEVE_MODEL_DIR"])  # .../all-MiniLM-L6-v2 (contains onnx/)

datas = [
    (str(REPO / "frontend-proto"), "frontend-proto"),
    (str(REPO / "prompts"), "prompts"),
    (str(REPO / "desktop" / "installer" / "starter-data"), "starter-data"),
    (str(MODEL / "onnx"), "onnx_models/all-MiniLM-L6-v2/onnx"),
]
binaries = []
hiddenimports = collect_submodules("pensieve") + collect_submodules("uvicorn")

# Packages that import submodules or read package data dynamically.
for pkg in (
    "chromadb",
    "onnxruntime",
    "tokenizers",
    "copilot",
    "msal",
    "msal_extensions",
    "docx",
    "pypdf",
    "multipart",
    "posthog",
    "opentelemetry",
    "pydantic_settings",
):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(REPO / "desktop" / "installer" / "server_main.py")],
    pathex=[str(REPO)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        "tkinter", "matplotlib", "IPython", "jupyter", "notebook", "pytest", "ruff",
        "PyQt5", "PyQt6", "PySide2", "PySide6", "scipy", "pandas.tests", "numpy.tests",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pensieve-server",
    icon=str(REPO / "desktop" / "pensieve.ico"),
    console=True,  # the launcher starts it with no window and captures its output
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="server")
