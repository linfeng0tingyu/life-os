from __future__ import annotations

import http.client
import socket
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from life_os import create_app
from life_os.desktop.host import calculate_window_geometry, run_desktop
from life_os.desktop.server import LocalWsgiServer
from life_os.instance_lock import InstanceLock
from life_os.runtime import resolve_runtime_paths


class FakeWindow:
    def __init__(self) -> None:
        self.size: tuple[int, int] | None = None
        self.position: tuple[int, int] | None = None

    def resize(self, width: int, height: int) -> None:
        self.size = (width, height)

    def move(self, x: int, y: int) -> None:
        self.position = (x, y)


class FakeWebview:
    def __init__(self) -> None:
        self.settings = {
            "ALLOW_DOWNLOADS": True,
            "ALLOW_FILE_URLS": True,
            "OPEN_DEVTOOLS_IN_DEBUG": True,
            "REMOTE_DEBUGGING_PORT": 9222,
        }
        self.screens = [SimpleNamespace(width=1920, height=1080)]
        self.window = FakeWindow()
        self.window_call: tuple[tuple[Any, ...], dict[str, Any]] | None = None
        self.start_call: dict[str, Any] | None = None

    def create_window(self, *args: Any, **kwargs: Any) -> FakeWindow:
        self.window_call = (args, kwargs)
        return self.window

    def start(self, func, *, args, **kwargs: Any) -> None:
        self.start_call = kwargs
        func(*args)


class FakeServer:
    instances: list["FakeServer"] = []

    def __init__(self, _application) -> None:
        self.url = "http://127.0.0.1:54321"
        self.started = False
        self.stopped = False
        self.instances.append(self)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class FailingStopServer(FakeServer):
    def stop(self) -> None:
        super().stop()
        raise RuntimeError("server stop failed")


def test_window_geometry_adapts_and_centers() -> None:
    assert calculate_window_geometry(1920, 1080) == (1440, 929, 240, 75)
    assert calculate_window_geometry(1366, 768) == (1175, 660, 95, 54)


def test_desktop_host_uses_rest_url_and_runtime_local_webview_storage(
    tmp_path: Path,
) -> None:
    FakeServer.instances.clear()
    fake_webview = FakeWebview()
    runtime_home = tmp_path / "portable"

    result = run_desktop(
        runtime_home=runtime_home,
        webview_module=fake_webview,
        server_factory=FakeServer,
    )

    assert result == 0
    assert FakeServer.instances[0].started is True
    assert FakeServer.instances[0].stopped is True
    assert fake_webview.window_call is not None
    args, kwargs = fake_webview.window_call
    assert args[:2] == ("Life OS", "http://127.0.0.1:54321")
    assert "js_api" not in kwargs
    assert fake_webview.start_call == {
        "gui": "edgechromium",
        "debug": False,
        "private_mode": False,
        "storage_path": str(runtime_home / "cache" / "webview"),
    }
    assert fake_webview.window.size == (1440, 929)
    assert fake_webview.window.position == (240, 75)
    assert (runtime_home / "cache" / "webview").is_dir()

    lock = InstanceLock(runtime_home / "temp" / "life-os.lock")
    lock.acquire()
    lock.release()


def test_check_only_initializes_and_releases_runtime(tmp_path: Path) -> None:
    runtime_home = tmp_path / "runtime"
    assert run_desktop(runtime_home=runtime_home, check_only=True) == 0
    assert (runtime_home / "database" / "life.db").is_file()
    assert (runtime_home / "cache" / "webview").is_dir()

    lock = InstanceLock(runtime_home / "temp" / "life-os.lock")
    lock.acquire()
    lock.release()


def test_runtime_lock_is_released_when_server_stop_fails(
    tmp_path: Path,
) -> None:
    runtime_home = tmp_path / "runtime"

    with pytest.raises(RuntimeError, match="server stop failed"):
        run_desktop(
            runtime_home=runtime_home,
            webview_module=FakeWebview(),
            server_factory=FailingStopServer,
        )

    lock = InstanceLock(runtime_home / "temp" / "life-os.lock")
    lock.acquire()
    lock.release()


def test_frozen_default_home_is_next_to_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "portable" / "LifeOS.exe"
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(executable))

    paths = resolve_runtime_paths(env={})

    assert paths.home == executable.parent / "life-os-data"


def test_waitress_server_uses_random_loopback_port_and_stops(
    tmp_path: Path,
) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    server = LocalWsgiServer(app, startup_timeout=3.0)

    server.start()
    port = server.port
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
    connection.request("GET", "/api/system/health")
    response = connection.getresponse()
    response.read()
    connection.close()

    assert response.status == 200
    assert server.url == f"http://127.0.0.1:{port}"
    assert server.running is True

    server.stop()

    assert server.running is False
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(0.25)
    try:
        assert probe.connect_ex(("127.0.0.1", port)) != 0
    finally:
        probe.close()
