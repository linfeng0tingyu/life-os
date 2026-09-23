from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from flask import Flask

from life_os import create_app
from life_os.database import checkpoint_database

from .server import LocalWsgiServer


WINDOW_TITLE = "Life OS"
WINDOW_BACKGROUND = "#f5f3ed"


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

        window = webview_module.create_window(
            WINDOW_TITLE,
            server.url,
            width=1280,
            height=800,
            min_size=(720, 540),
            resizable=True,
            background_color=WINDOW_BACKGROUND,
            text_select=True,
        )
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
