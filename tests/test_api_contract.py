from __future__ import annotations

from pathlib import Path

from flask.testing import FlaskClient

from life_os.database import SCHEMA_VERSION
from life_os.services.common import ConflictError


def assert_error(response, status: int, code: str) -> dict:
    assert response.status_code == status
    assert response.content_type == "application/json"
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["error"]["code"] == code
    assert isinstance(payload["error"]["details"], dict)
    assert "X-Request-ID" in response.headers
    return payload


def test_unknown_api_path_uses_json_error_contract(client: FlaskClient) -> None:
    assert_error(client.get("/api/does-not-exist"), 404, "not_found")


def test_malformed_json_and_wrong_media_type_are_rejected(client: FlaskClient) -> None:
    malformed = client.post(
        "/api/habits", data='{"name":', content_type="application/json"
    )
    assert_error(malformed, 400, "invalid_json")

    wrong_media = client.post(
        "/api/habits", data='{"name":"Read"}', content_type="text/plain"
    )
    assert_error(wrong_media, 415, "unsupported_media_type")

    assert client.get("/api/habits").get_json()["data"] == []


def test_unknown_and_read_only_fields_are_rejected(client: FlaskClient) -> None:
    response = client.post("/api/habits", json={"name": "Read", "id": 42})
    payload = assert_error(response, 400, "validation_error")
    assert payload["error"]["details"] == {"unknown_fields": ["id"]}


def test_invalid_date_is_a_validation_error(client: FlaskClient) -> None:
    payload = assert_error(
        client.get("/api/day/2026-02-30"), 400, "validation_error"
    )
    assert "date" in payload["error"]["message"]


def test_system_info_has_versions_and_no_absolute_runtime_path(
    client: FlaskClient,
) -> None:
    response = client.get("/api/system/info")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["version"]
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["runtime"]["portable"] is True
    assert data["runtime"]["database"] == "database/life.db"
    assert data["capabilities"]["backup"] is False
    assert not Path(data["runtime"]["database"]).is_absolute()
    serialized = response.get_data(as_text=True)
    assert "SQLALCHEMY_DATABASE_URI" not in serialized
    assert "LIFE_OS_HOME" not in serialized


def test_conflict_uses_409_contract(client: FlaskClient, monkeypatch) -> None:
    from life_os.routes.habits import HabitService

    def raise_conflict(**_payload):
        raise ConflictError("数据冲突。")

    monkeypatch.setattr(HabitService, "create", raise_conflict)
    assert_error(client.post("/api/habits", json={"name": "Read"}), 409, "conflict")


def test_internal_error_hides_exception_details(client: FlaskClient, monkeypatch) -> None:
    from life_os.routes.habits import HabitService

    def raise_internal(**_payload):
        raise RuntimeError("E:\\private\\life.db secret traceback marker")

    monkeypatch.setattr(HabitService, "create", raise_internal)
    response = client.post("/api/habits", json={"name": "Read"})
    assert_error(response, 500, "internal_error")
    body = response.get_data(as_text=True)
    assert "private" not in body
    assert "traceback" not in body.lower()
