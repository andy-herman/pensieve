"""Entry point for the installed Pensieve backend (pensieve-server.exe).

PyInstaller builds this into ``server/pensieve-server.exe``; the desktop
launcher (``Pensieve.exe``) starts it hidden. Before handing over to
``pensieve serve`` it:

- creates the per-user data folder (``%LOCALAPPDATA%\\Pensieve\\data``),
- seeds generic starter goals and strands on first run (never overwrites),
- points the embedding model at the copy bundled in the installer, so the
  first launch works offline and downloads nothing.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def _bundle_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _prepare() -> None:
    from pensieve.config import get_settings

    settings = get_settings()
    data = Path(settings.data_dir)
    data.mkdir(parents=True, exist_ok=True)
    starter = _bundle_dir() / "starter-data"
    for name in ("connect-goals.json", "samples.json"):
        if not (data / name).exists() and (starter / name).exists():
            shutil.copyfile(starter / name, data / name)

    model = _bundle_dir() / "onnx_models" / "all-MiniLM-L6-v2"
    if (model / "onnx" / "model.onnx").is_file():
        from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

        ONNXMiniLM_L6_V2.DOWNLOAD_PATH = model


def main() -> None:
    _prepare()
    from pensieve.cli import app

    # Pensieve.exe passes --port; anything else falls through to `serve`.
    sys.argv = ["pensieve", "serve", *sys.argv[1:]]
    app()


if __name__ == "__main__":
    main()
