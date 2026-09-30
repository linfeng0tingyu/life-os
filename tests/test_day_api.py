from __future__ import annotations

from datetime import date

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
        "finance",
    }
    assert data["date"] == "2026-09-18"
    assert data["habits"] == []
    assert data["tasks"] == {
        "scheduled": [],
        "due": [],
        "ongoing": [],
        "overdue": [],
    }
    assert data["health"] is None
    assert data["journal"] is None
    assert data["finance"] == {
        "currency": "CNY",
        "income": "0.00",
        "expense": "0.00",
        "net_cashflow": "0.00",
        "transactions": [],
    }


def test_day_aggregates_only_target_date(client: FlaskClient, monkeypatch) -> None:
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
    client.post(
        "/api/tasks",
        json={
            "title": "Ongoing",
            "scheduled_date": "2026-09-17",
            "due_date": "2026-09-19",
        },
    )
    client.put("/api/health/2026-09-18", json={"energy_level": 4})
    monkeypatch.setattr("life_os.routes.journal.local_today", lambda: date(2026, 9, 18))
    client.put("/api/journal/2026-09-18", json={"content": "Target"})
    monkeypatch.setattr("life_os.routes.journal.local_today", lambda: date(2026, 9, 19))
    client.put("/api/journal/2026-09-19", json={"content": "Other"})

    data = client.get("/api/day/2026-09-18").get_json()["data"]
    assert data["calendar_day"]["holiday_name"] == "自定义休息日"
    assert data["habits"][0]["log"]["status"] is True
    assert [task["title"] for task in data["tasks"]["scheduled"]] == ["Plan"]
    assert [task["title"] for task in data["tasks"]["due"]] == ["Due"]
    assert [task["title"] for task in data["tasks"]["overdue"]] == ["Late"]
    assert [task["title"] for task in data["tasks"]["ongoing"]] == ["Ongoing"]
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


def test_day_default_excludes_unrelated_tasks(
    client: FlaskClient,
) -> None:
    client.post(
        "/api/tasks",
        json={"title": "Today", "scheduled_date": "2026-09-18"},
    )
    client.post(
        "/api/tasks",
        json={"title": "Future", "scheduled_date": "2026-10-01"},
    )
    client.post("/api/tasks", json={"title": "Undated"})

    tasks = client.get("/api/day/2026-09-18").get_json()["data"]["tasks"]
    titles = {
        task["title"]
        for group in tasks.values()
        for task in group
    }
    assert titles == {"Today"}


def test_completed_task_remains_in_day_data_for_calendar_history(
    client: FlaskClient,
) -> None:
    completed = client.post(
        "/api/tasks",
        json={"title": "Completed", "scheduled_date": "2026-09-18"},
    ).get_json()["data"]
    client.put(f"/api/tasks/{completed['id']}", json={"status": "done"})

    tasks = client.get("/api/day/2026-09-18").get_json()["data"]["tasks"]
    assert tasks["scheduled"][0]["id"] == completed["id"]
    assert tasks["scheduled"][0]["status"] == "done"


def test_completed_interval_task_remains_in_day_data_for_calendar_history(
    client: FlaskClient,
) -> None:
    completed = client.post(
        "/api/tasks",
        json={
            "title": "Completed interval",
            "scheduled_date": "2026-09-17",
            "due_date": "2026-09-19",
        },
    ).get_json()["data"]
    client.put(f"/api/tasks/{completed['id']}", json={"status": "done"})

    tasks = client.get("/api/day/2026-09-18").get_json()["data"]["tasks"]
    assert tasks["ongoing"][0]["id"] == completed["id"]
    assert tasks["ongoing"][0]["status"] == "done"
