from __future__ import annotations

from flask.testing import FlaskClient


def create_account(
    client: FlaskClient,
    name: str,
    *,
    kind: str = "asset",
    account_type: str = "bank",
    opening_balance: str = "0.00",
) -> dict:
    response = client.post(
        "/api/finance/accounts",
        json={
            "name": name,
            "kind": kind,
            "account_type": account_type,
            "opening_balance": opening_balance,
        },
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def test_finance_account_crud_and_validation(client: FlaskClient) -> None:
    bank = create_account(client, " Bank ", opening_balance="100.00")
    assert bank["name"] == "Bank"
    assert bank["currency"] == "CNY"
    updated = client.put(
        f"/api/finance/accounts/{bank['id']}",
        json={"active": False, "sort_order": 2},
    )
    assert updated.status_code == 200
    assert client.get("/api/finance/accounts").get_json()["data"] == []
    assert len(
        client.get("/api/finance/accounts?include_inactive=true").get_json()[
            "data"
        ]
    ) == 1
    assert (
        client.post(
            "/api/finance/accounts",
            json={"name": "USD", "kind": "asset", "account_type": "bank", "currency": "USD"},
        ).status_code
        == 400
    )


def test_finance_transactions_summary_and_day_aggregation(client: FlaskClient) -> None:
    bank = create_account(client, "Bank", opening_balance="1000.00")
    card = create_account(
        client,
        "Card",
        kind="liability",
        account_type="credit",
        opening_balance="-300.00",
    )
    income = client.post(
        "/api/finance/transactions",
        json={
            "date": "2026-09-18",
            "type": "income",
            "amount": "250.00",
            "to_account_id": bank["id"],
            "category": "工资",
        },
    )
    assert income.status_code == 201
    expense = client.post(
        "/api/finance/transactions",
        json={
            "date": "2026-09-18",
            "type": "expense",
            "amount": "20.50",
            "from_account_id": bank["id"],
        },
    ).get_json()["data"]
    client.post(
        "/api/finance/transactions",
        json={
            "date": "2026-09-19",
            "type": "transfer",
            "amount": "100.00",
            "from_account_id": bank["id"],
            "to_account_id": card["id"],
        },
    )

    day = client.get("/api/day/2026-09-18").get_json()["data"]["finance"]
    assert day["income"] == "250.00"
    assert day["expense"] == "20.50"
    assert day["net_cashflow"] == "229.50"
    assert len(day["transactions"]) == 2

    summary = client.get(
        "/api/finance/summary?date_from=2026-09-18&date_to=2026-09-18"
    ).get_json()["data"]
    assert summary["income"] == "250.00"
    assert summary["expense"] == "20.50"
    assert summary["net_worth"] == "929.50"
    balances = {item["name"]: item["balance"] for item in summary["accounts"]}
    assert balances == {"Bank": "1129.50", "Card": "-200.00"}

    filtered = client.get(
        f"/api/finance/transactions?date=2026-09-18&account_id={bank['id']}"
    ).get_json()["data"]
    assert len(filtered) == 2
    archived = client.delete(f"/api/finance/transactions/{expense['id']}")
    assert archived.status_code == 200
    assert archived.get_json()["data"]["archived_at"] is not None


def test_finance_api_rejects_invalid_transactions_and_ranges(
    client: FlaskClient,
) -> None:
    bank = create_account(client, "Bank")
    invalid = client.post(
        "/api/finance/transactions",
        json={
            "date": "2026-09-18",
            "type": "income",
            "amount": "1.001",
            "to_account_id": bank["id"],
        },
    )
    assert invalid.status_code == 400
    assert client.get("/api/finance/transactions?account_id=x").status_code == 400
    assert (
        client.get(
            "/api/finance/summary?date_from=2026-09-19&date_to=2026-09-18"
        ).status_code
        == 400
    )
    assert client.get("/api/finance/summary?date_from=").status_code == 400
    assert client.put("/api/finance/transactions/999", json={"amount": "1.00"}).status_code == 404
