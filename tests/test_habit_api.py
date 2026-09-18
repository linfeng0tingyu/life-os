from __future__ import annotations

from flask.testing import FlaskClient


def create_habit(client: FlaskClient, name: str = "Read", sort_order: int = 0) -> dict:
    response = client.post(
        "/api/habits", json={"name": name, "sort_order": sort_order}
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def test_habit_crud_filter_and_defaults(client: FlaskClient) -> None:
    second = create_habit(client, " Second ", 2)
    first = create_habit(client, "First", 1)
    assert second["name"] == "Second"
    assert second["active"] is True

    listed = client.get("/api/habits").get_json()["data"]
    assert [habit["id"] for habit in listed] == [first["id"], second["id"]]

    updated = client.put(
        f"/api/habits/{first['id']}", json={"active": False, "icon": "book"}
    )
    assert updated.status_code == 200
    assert [h["id"] for h in client.get("/api/habits").get_json()["data"]] == [
        second["id"]
    ]
    all_habits = client.get("/api/habits?include_inactive=true").get_json()["data"]
    assert {habit["id"] for habit in all_habits} == {first["id"], second["id"]}
    assert client.get("/api/habits?include_inactive=yes").status_code == 400


def test_habit_log_put_is_idempotent_and_allows_inactive_habit(
    client: FlaskClient,
) -> None:
    habit = create_habit(client)
    client.put(f"/api/habits/{habit['id']}", json={"active": False})
    path = f"/api/habits/{habit['id']}/log/2026-09-18"
    first = client.put(path, json={"status": True, "value": 20, "value_unit": "min"})
    second = client.put(path, json={"status": False, "note": "rest"})
    assert first.status_code == second.status_code == 200
    assert first.get_json()["data"]["id"] == second.get_json()["data"]["id"]
    assert second.get_json()["data"]["status"] is False


def test_habit_api_not_found_and_validation(client: FlaskClient) -> None:
    assert client.post("/api/habits", json={"name": "  "}).status_code == 400
    assert client.put("/api/habits/999", json={"active": False}).status_code == 404
    assert (
        client.put(
            "/api/habits/999/log/2026-09-18", json={"status": True}
        ).status_code
        == 404
    )
