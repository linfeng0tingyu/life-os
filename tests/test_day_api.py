from __future__ import annotations

from flask.testing import FlaskClient


def test_empty_day_has_stable_shape(client: FlaskClient) -> None:
    response = client.get("/api/day/2026-09-18")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert set(data) == {
        "date",
        "calendar_day",
        "habits",
        "tasks",
        "health",
        "journal",
    }
    assert data["date"] == "2026-09-18"
    assert data["habits"] == []
    assert data["tasks"] == {"scheduled": [], "due": [], "overdue": []}
    assert data["health"] is None
    assert data["journal"] is None


def test_day_aggregates_only_target_date(client: FlaskClient) -> None:
    habit = client.post("/api/habits", json={"name": "Exercise"}).get_json()[
        "data"
    ]
    client.put(
        f"/api/habits/{habit['id']}/log/2026-09-18",
        json={"status": True},
    )
    client.put(
        "/api/calendar/days/2026-09-18",
        json={"day_type": "rest_day", "holiday_name": "自定义休息日"},
    )
    client.post(
        "/api/tasks", json={"title": "Plan", "scheduled_date": "2026-09-18"}
    )
    client.post(
        "/api/tasks", json={"title": "Due", "due_date": "2026-09-18"}
    )
    client.post(
        "/api/tasks", json={"title": "Late", "due_date": "2026-09-17"}
    )
    client.put("/api/health/2026-09-18", json={"energy_level": 4})
    client.put("/api/journal/2026-09-18", json={"content": "Target"})
    client.put("/api/journal/2026-09-19", json={"content": "Other"})

    data = client.get("/api/day/2026-09-18").get_json()["data"]
    assert data["calendar_day"]["holiday_name"] == "自定义休息日"
    assert data["habits"][0]["log"]["status"] is True
    assert [task["title"] for task in data["tasks"]["scheduled"]] == ["Plan"]
    assert [task["title"] for task in data["tasks"]["due"]] == ["Due"]
    assert [task["title"] for task in data["tasks"]["overdue"]] == ["Late"]
    assert data["health"]["energy_level"] == 4
    assert data["journal"]["content"] == "Target"

    next_day = client.get("/api/day/2026-09-19").get_json()["data"]
    assert next_day["health"] is None
    assert next_day["journal"]["content"] == "Other"
    assert next_day["habits"][0]["log"]["status"] is False


def test_archived_task_is_excluded_from_day(client: FlaskClient) -> None:
    task = client.post(
        "/api/tasks", json={"title": "Archive", "due_date": "2026-09-18"}
    ).get_json()["data"]
    client.delete(f"/api/tasks/{task['id']}")
    data = client.get("/api/day/2026-09-18").get_json()["data"]
    assert data["tasks"]["due"] == []
