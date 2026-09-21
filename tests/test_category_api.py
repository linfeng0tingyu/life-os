from __future__ import annotations

from flask.testing import FlaskClient


def test_categories_are_scoped_sorted_and_case_insensitive_unique(
    client: FlaskClient,
) -> None:
    later = client.post(
        "/api/categories",
        json={"scope": "task", "name": "工作", "sort_order": 20},
    )
    earlier = client.post(
        "/api/categories",
        json={"scope": "task", "name": "家庭", "sort_order": 10},
    )
    habit = client.post(
        "/api/categories",
        json={"scope": "habit", "name": "健康"},
    )
    finance = client.post(
        "/api/categories",
        json={"scope": "finance", "name": "餐饮"},
    )

    assert later.status_code == earlier.status_code == habit.status_code == finance.status_code == 201
    task_items = client.get("/api/categories?scope=task").get_json()["data"]
    assert [item["name"] for item in task_items] == ["家庭", "工作"]
    habit_items = client.get(
        "/api/categories?scope=habit"
    ).get_json()["data"]
    assert [item["name"] for item in habit_items] == ["健康"]
    finance_items = client.get(
        "/api/categories?scope=finance"
    ).get_json()["data"]
    assert [item["name"] for item in finance_items] == ["餐饮"]

    duplicate = client.post(
        "/api/categories", json={"scope": "task", "name": "工作"}
    )
    assert duplicate.status_code == 409

    client.post(
        "/api/categories", json={"scope": "task", "name": "Focus"}
    )
    duplicate_case = client.post(
        "/api/categories", json={"scope": "task", "name": "focus"}
    )
    assert duplicate_case.status_code == 409


def test_categories_validate_scope_and_item_assignment(client: FlaskClient) -> None:
    assert client.get("/api/categories").status_code == 400
    assert client.get("/api/categories?scope=unknown").status_code == 400
    assert client.post(
        "/api/categories", json={"scope": "task", "name": "  "}
    ).status_code == 400

    unknown_task = client.post(
        "/api/tasks", json={"title": "事项", "category": "未创建"}
    )
    unknown_habit = client.post(
        "/api/habits", json={"name": "习惯", "category": "未创建"}
    )
    assert unknown_task.status_code == unknown_habit.status_code == 400

    client.post(
        "/api/categories", json={"scope": "task", "name": "工作"}
    )
    client.post(
        "/api/categories", json={"scope": "habit", "name": "健康"}
    )
    task = client.post(
        "/api/tasks", json={"title": "事项", "category": "工作"}
    )
    habit = client.post(
        "/api/habits", json={"name": "习惯", "category": "健康"}
    )
    assert task.status_code == habit.status_code == 201
    assert task.get_json()["data"]["category"] == "工作"
    assert habit.get_json()["data"]["category"] == "健康"
