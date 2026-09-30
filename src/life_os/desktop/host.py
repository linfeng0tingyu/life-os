from __future__ import annotations

import os
import logging
from pathlib import Path
from threading import Event, Lock
from typing import Any

from flask import Flask

from life_os import create_app
from life_os.database import checkpoint_database

from .server import LocalWsgiServer


WINDOW_TITLE = "Life OS"
WINDOW_BACKGROUND = "#f5f3ed"
WINDOW_CONTROL_TIMEOUT_SECONDS = 2.0
logger = logging.getLogger("life_os")


def _windows_action(callback: Any) -> Any:
    """Create a WinForms delegate lazily after pywebview selects its backend."""
    from System import Action

    return Action(callback)


def _set_window_on_top_safely(window: Any, enabled: bool) -> None:
    """Set TopMost on the owning WinForms UI thread without blocking it."""
    if os.name != "nt":
        window.on_top = enabled
        return

    native = getattr(window, "native", None)
    if native is None:
        raise RuntimeError("native window is not ready")
    if bool(getattr(native, "IsDisposed", False)) or bool(
        getattr(native, "Disposing", False)
    ):
        raise RuntimeError("native window is closing")

    if not bool(getattr(native, "InvokeRequired", False)):
        native.TopMost = enabled
        return

    completed = Event()
    failure: list[BaseException] = []
    cancelled = Event()

    def apply() -> None:
        try:
            if not cancelled.is_set():
                native.TopMost = enabled
        except BaseException as exc:
            failure.append(exc)
        finally:
            completed.set()

    native.BeginInvoke(_windows_action(apply))
    if not completed.wait(WINDOW_CONTROL_TIMEOUT_SECONDS):
        cancelled.set()
        raise TimeoutError("native window did not respond in time")
    if failure:
        raise RuntimeError("native window rejected the request") from failure[0]


class DesktopWindowApi:
    """Expose only non-business desktop window controls to the local UI."""

    def __init__(self) -> None:
        self._window: Any | None = None
        self._on_top = False
        self._lock = Lock()

    def _bind(self, window: Any) -> None:
        self._window = window

    def set_window_on_top(self, enabled: bool) -> dict[str, bool | str]:
        if not isinstance(enabled, bool):
            return {
                "success": False,
                "on_top": self._on_top,
                "error": "invalid_argument",
            }
        if self._window is None:
            return {
                "success": False,
                "on_top": self._on_top,
                "error": "window_not_ready",
            }
        if not self._lock.acquire(timeout=WINDOW_CONTROL_TIMEOUT_SECONDS):
            return {
                "success": False,
                "on_top": self._on_top,
                "error": "window_control_busy",
            }
        try:
            _set_window_on_top_safely(self._window, enabled)
            self._on_top = enabled
            logger.info("Desktop window on-top state changed enabled=%s", enabled)
            return {"success": True, "on_top": self._on_top, "error": ""}
        except BaseException:
            logger.exception("Desktop window on-top change failed enabled=%s", enabled)
            return {
                "success": False,
                "on_top": self._on_top,
                "error": "window_control_failed",
            }
        finally:
            self._lock.release()


def calculate_window_geometry(
    screen_width: int,
    screen_height: int,
) -> tuple[int, int, int, int]:
    """Return a centered, resolution-aware window rectangle."""
    usable_width = max(640, screen_width - 64)
    usable_height = max(480, screen_height - 64)
    width = min(1440, usable_width, max(900, round(screen_width * 0.86)))
    height = min(1000, usable_height, max(640, round(screen_height * 0.86)))
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    return width, height, x, y


def run_desktop(
    *,
    runtime_home: Path | None = None,
    check_only: bool = False,
    webview_module: Any | None = None,
    server_factory: type[LocalWsgiServer] = LocalWsgiServer,
) -> int:
    app: Flask | None = None
    server: LocalWsgiServer | None = None
    try:
        app = create_app(
            runtime_home=runtime_home,
            acquire_lock=True,
        )
        if check_only:
            return 0

        if webview_module is None:
            import webview as webview_module

        server = server_factory(app)
        server.start()

        window_api = DesktopWindowApi()
        window = webview_module.create_window(
            WINDOW_TITLE,
            server.url,
            width=1280,
            height=800,
            min_size=(720, 540),
            resizable=True,
            background_color=WINDOW_BACKGROUND,
            text_select=True,
            js_api=window_api,
        )
        window_api._bind(window)
        webview_module.settings["ALLOW_DOWNLOADS"] = False
        webview_module.settings["ALLOW_FILE_URLS"] = False
        webview_module.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
        webview_module.settings["REMOTE_DEBUGGING_PORT"] = None

        gui = "edgechromium" if os.name == "nt" else None
        webview_module.start(
            _adapt_window,
            args=(window, webview_module),
            gui=gui,
            debug=False,
            private_mode=False,
            storage_path=str(
                app.extensions["life_os_runtime"].webview_cache_dir
            ),
        )
        return 0
    finally:
        stop_error: BaseException | None = None
        try:
            if server is not None:
                server.stop()
        except BaseException as exc:
            stop_error = exc

        try:
            if app is not None:
                checkpoint_database(app)
        finally:
            if app is not None:
                instance_lock = app.extensions.get("life_os_instance_lock")
                if instance_lock is not None:
                    instance_lock.release()

        if stop_error is not None:
            raise stop_error


def _adapt_window(window: Any, webview_module: Any) -> None:
    screens = getattr(webview_module, "screens", ())
    if not screens:
        return
    screen = screens[0]
    width, height, x, y = calculate_window_geometry(
        int(screen.width), int(screen.height)
    )
    window.resize(width, height)
    window.move(x, y)
