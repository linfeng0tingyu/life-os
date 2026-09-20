from __future__ import annotations

from flask.testing import FlaskClient


def create_task(client: FlaskClient, **overrides) -> dict:
    payload = {"title": "Task"} | overrides
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 201
    return response.get_json()["data"]


def test_task_crud_status_and_archive(client: FlaskClient) -> None:
    task = create_task(client, title=" Ship ", priority="high")
    assert task["title"] == "Ship"
    assert task["status"] == "todo"
    assert task["completed_at"] is None

    done = client.put(f"/api/tasks/{task['id']}", json={"status": "done"})
    assert done.status_code == 200
    assert done.get_json()["data"]["completed_at"] is not None
    reopened = client.put(f"/api/tasks/{task['id']}", json={"status": "doing"})
    assert reopened.get_json()["data"]["completed_at"] is None

    archived = client.delete(f"/api/tasks/{task['id']}")
    assert archived.status_code == 200
    assert archived.get_json()["data"]["archived_at"] is not None
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 200
    assert client.get("/api/tasks").get_json()["data"] == []
    assert len(client.get("/api/tasks?include_archived=true").get_json()["data"]) == 1
    assert client.put(f"/api/tasks/{task['id']}", json={"title": "No"}).status_code == 400

    restored = client.post(f"/api/tasks/{task['id']}/restore")
    assert restored.status_code == 200
    assert restored.get_json()["data"]["archived_at"] is None
    assert client.post(f"/api/tasks/{task['id']}/restore").status_code == 200
    assert [item["id"] for item in client.get("/api/tasks").get_json()["data"]] == [
        task["id"]
    ]


def test_task_filters_keep_date_relationships_distinguishable(
    client: FlaskClient,
) -> None:
    scheduled = create_task(client, title="Scheduled", scheduled_date="2026-09-18")
    due = create_task(client, title="Due", due_date="2026-09-18", status="doing")
    overdue = create_task(client, title="Overdue", due_date="2026-09-17")
    create_task(client, title="Done old", due_date="2026-09-17", status="done")
    create_task(client, title="Other", scheduled_date="2026-09-20")

    items = client.get("/api/tasks?date=2026-09-18").get_json()["data"]
    by_id = {item["id"]: item for item in items}
    assert set(by_id) == {scheduled["id"], due["id"], overdue["id"]}
    assert by_id[scheduled["id"]]["date_match"]["scheduled"] is True
    assert by_id[due["id"]]["date_match"]["due"] is True
    assert by_id[overdue["id"]]["date_match"]["overdue"] is True

    doing = client.get("/api/tasks?status=doing&date=2026-09-18").get_json()[
        "data"
    ]
    assert [item["id"] for item in doing] == [due["id"]]


def test_task_parent_cycle_and_failed_update_roll_back(client: FlaskClient) -> None:
    parent = create_task(client, title="Parent")
    child = create_task(client, title="Child", parent_id=parent["id"])
    response = client.put(
        f"/api/tasks/{parent['id']}",
        json={"title": "Changed", "parent_id": child["id"]},
    )
    assert response.status_code == 400
    parent_after = next(
        item
        for item in client.get("/api/tasks").get_json()["data"]
        if item["id"] == parent["id"]
    )
    assert parent_after["title"] == "Parent"
    assert parent_after["parent_id"] is None


def test_task_api_validation_and_not_found(client: FlaskClient) -> None:
    assert client.post("/api/tasks", json={"title": ""}).status_code == 400
    assert (
        client.post(
            "/api/tasks", json={"title": "Bad", "priority": "maximum"}
        ).status_code
        == 400
    )
    assert client.get("/api/tasks?status=unknown").status_code == 400
    assert client.get("/api/tasks?date=2026-02-30").status_code == 400
    assert client.put("/api/tasks/999", json={"title": "Missing"}).status_code == 404
    assert client.delete("/api/tasks/999").status_code == 404
    assert client.post("/api/tasks/999/restore").status_code == 404
