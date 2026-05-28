"""Local FastAPI server for the Pensieve dashboard."""

from pensieve.api.server import app, create_app

__all__ = ["app", "create_app"]
