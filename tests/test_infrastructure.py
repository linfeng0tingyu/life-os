from __future__ import annotations

import socket
from pathlib import Path

import pytest

from life_os import create_app
from life_os.instance_lock import InstanceLock, InstanceLockError
from life_os.network import PortUnavailableError, ensure_port_available


def test_health_endpoint_and_log_are_runtime_local(tmp_path: Path) -> None:
    runtime_home = tmp_path / "runtime"
    app = create_app(runtime_home=runtime_home, testing=True)

    response = app.test_client().get("/api/system/health")

    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "ok"
    assert (runtime_home / "logs" / "app.log").is_file()
    assert set(tmp_path.iterdir()) == {runtime_home}


def test_database_engine_points_inside_runtime_and_initializes_database(
    tmp_path: Path,
) -> None:
    runtime_home = tmp_path / "runtime"
    app = create_app(runtime_home=runtime_home, testing=True)
    database_url = app.config["SQLALCHEMY_DATABASE_URI"]

    assert Path(database_url.database) == runtime_home / "database" / "life.db"
    assert (runtime_home / "database" / "life.db").is_file()


def test_api_404_uses_json_contract(tmp_path: Path) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    response = app.test_client().get("/api/not-found")

    assert response.status_code == 404
    assert response.get_json()["success"] is False


def test_frontend_shell_supports_versioned_local_assets(tmp_path: Path) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    response = app.test_client().get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-cache"
    assert '<meta name="life-os-version" content="0.1.0-dev">' in html
    assert "/static/css/tokens.css?v=0.1.0-dev" in html
    assert "/static/css/base.css?v=0.1.0-dev" in html
    assert "/static/css/layout.css?v=0.1.0-dev" in html
    assert "/static/css/components.css?v=0.1.0-dev" in html
    assert "/static/css/pages/today.css?v=0.1.0-dev" in html
    assert 'type="module" src="/static/js/app.js?v=0.1.0-dev"' in html
    assert "data-calendar-grid" in html
    assert "data-day-marker-form" in html
    assert "http://" not in html
    assert "https://" not in html


@pytest.mark.parametrize(
    "asset",
    [
        "css/tokens.css",
        "css/base.css",
        "css/layout.css",
        "css/components.css",
        "css/pages/today.css",
        "js/app.js",
        "js/api/client.js",
        "js/components/dom.js",
        "js/components/day-summary.js",
        "js/features/calendar.js",
        "js/pages/today.js",
        "js/utils/date.js",
    ],
)
def test_m4_local_frontend_assets_are_served(tmp_path: Path, asset: str) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    response = app.test_client().get(f"/static/{asset}")

    assert response.status_code == 200
    assert response.data


def test_second_instance_cannot_take_same_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / "runtime" / "temp" / "life-os.lock"
    first = InstanceLock(lock_path)
    second = InstanceLock(lock_path)
    first.acquire()
    try:
        with pytest.raises(InstanceLockError):
            second.acquire()
    finally:
        first.release()

    second.acquire()
    second.release()


def test_occupied_port_is_rejected() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        with pytest.raises(PortUnavailableError):
            ensure_port_available("127.0.0.1", port)
    finally:
        listener.close()
