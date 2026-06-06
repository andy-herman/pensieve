"""Local FastAPI server for the Pensieve dashboard."""

from pensieve.api.server import create_app

__all__ = ["app", "create_app"]


def __getattr__(name: str):
    # Lazily expose `app` so importing the package doesn't build the app
    # (and open the Chroma store). uvicorn / callers access it on demand.
    if name == "app":
        from pensieve.api import server

        return server.app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
