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


def test_database_engine_points_inside_runtime_without_creating_database(
    tmp_path: Path,
) -> None:
    runtime_home = tmp_path / "runtime"
    app = create_app(runtime_home=runtime_home, testing=True)
    database_url = app.config["SQLALCHEMY_DATABASE_URI"]

    assert Path(database_url.database) == runtime_home / "database" / "life.db"
    assert not (runtime_home / "database" / "life.db").exists()


def test_api_404_uses_json_contract(tmp_path: Path) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    response = app.test_client().get("/api/not-found")

    assert response.status_code == 404
    assert response.get_json()["success"] is False


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
