"""Desktop host components for the packaged Life OS application."""

from .host import calculate_window_geometry, run_desktop
from .server import LocalServerError, LocalWsgiServer

__all__ = [
    "LocalServerError",
    "LocalWsgiServer",
    "calculate_window_geometry",
    "run_desktop",
]
