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


def test_categories_can_be_reordered_with_complete_scoped_order(
    client: FlaskClient,
) -> None:
    first = client.post(
        "/api/categories", json={"scope": "task", "name": "工作"}
    ).get_json()["data"]
    second = client.post(
        "/api/categories", json={"scope": "task", "name": "家庭"}
    ).get_json()["data"]
    third = client.post(
        "/api/categories", json={"scope": "task", "name": "学习"}
    ).get_json()["data"]
    client.post(
        "/api/categories", json={"scope": "habit", "name": "健康"}
    )

    reordered = client.put(
        "/api/categories/order",
        json={
            "scope": "task",
            "category_ids": [third["id"], first["id"], second["id"]],
        },
    )
    assert reordered.status_code == 200
    assert [item["name"] for item in reordered.get_json()["data"]] == [
        "学习",
        "工作",
        "家庭",
    ]
    assert [
        item["name"]
        for item in client.get("/api/categories?scope=task").get_json()["data"]
    ] == ["学习", "工作", "家庭"]

    incomplete = client.put(
        "/api/categories/order",
        json={"scope": "task", "category_ids": [third["id"], first["id"]]},
    )
    duplicate = client.put(
        "/api/categories/order",
        json={
            "scope": "task",
            "category_ids": [third["id"], third["id"], second["id"]],
        },
    )
    assert incomplete.status_code == duplicate.status_code == 400


def test_categories_delete_only_when_no_records_reference_them(
    client: FlaskClient,
) -> None:
    unused = client.post(
        "/api/categories", json={"scope": "habit", "name": "暂不用"}
    ).get_json()["data"]
    deleted = client.delete(f"/api/categories/{unused['id']}")
    assert deleted.status_code == 200
    assert deleted.get_json()["data"] == {"id": unused["id"], "deleted": True}

    used = client.post(
        "/api/categories", json={"scope": "task", "name": "历史分类"}
    ).get_json()["data"]
    task = client.post(
        "/api/tasks", json={"title": "保留历史", "category": "历史分类"}
    ).get_json()["data"]
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 200

    conflict = client.delete(f"/api/categories/{used['id']}")
    assert conflict.status_code == 409
    assert conflict.get_json()["error"]["details"] == {
        "scope": "task",
        "usage_count": 1,
    }
    assert client.delete("/api/categories/999999").status_code == 404

    used_habit = client.post(
        "/api/categories", json={"scope": "habit", "name": "健康历史"}
    ).get_json()["data"]
    assert client.post(
        "/api/habits", json={"name": "散步", "category": "健康历史"}
    ).status_code == 201
    assert client.delete(f"/api/categories/{used_habit['id']}").status_code == 409

    used_finance = client.post(
        "/api/categories", json={"scope": "finance", "name": "餐饮历史"}
    ).get_json()["data"]
    account = client.post(
        "/api/finance/accounts",
        json={
            "name": "现金",
            "kind": "asset",
            "account_type": "cash",
            "opening_balance": "100.00",
        },
    ).get_json()["data"]
    assert client.post(
        "/api/finance/transactions",
        json={
            "date": "2026-09-24",
            "type": "expense",
            "amount": "10.00",
            "from_account_id": account["id"],
            "category": "餐饮历史",
        },
    ).status_code == 201
    assert client.delete(f"/api/categories/{used_finance['id']}").status_code == 409

    assert [
        item["name"]
        for item in client.get("/api/categories?scope=task").get_json()["data"]
    ] == ["历史分类"]
