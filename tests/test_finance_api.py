from __future__ import annotations

from flask.testing import FlaskClient


def create_account(
    client: FlaskClient,
    name: str,
    *,
    kind: str = "asset",
    account_type: str = "bank",
    opening_balance: str = "0.00",
    billing_day: int | None = None,
) -> dict:
    payload = {
        "name": name,
        "kind": kind,
        "account_type": account_type,
        "opening_balance": opening_balance,
    }
    if billing_day is not None:
        payload["billing_day"] = billing_day
    response = client.post(
        "/api/finance/accounts",
        json=payload,
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


def test_credit_card_billing_cycle_and_repayment_roll_forward(
    client: FlaskClient,
) -> None:
    bank = create_account(client, "还款卡", opening_balance="1000.00")
    card = create_account(
        client,
        "信用卡",
        kind="liability",
        account_type="credit",
        billing_day=18,
    )
    assert card["billing_day"] == 18

    for value_date, amount in (("2026-08-19", "100.00"), ("2026-09-18", "50.00")):
        assert client.post(
            "/api/finance/transactions",
            json={
                "date": value_date,
                "type": "expense",
                "amount": amount,
                "from_account_id": card["id"],
                "category": "信用卡消费",
            },
        ).status_code == 201
    assert client.post(
        "/api/finance/transactions",
        json={
            "date": "2026-09-19",
            "type": "expense",
            "amount": "25.00",
            "from_account_id": card["id"],
        },
    ).status_code == 201
    assert client.post(
        "/api/finance/transactions",
        json={
            "date": "2026-09-20",
            "type": "transfer",
            "amount": "150.00",
            "from_account_id": bank["id"],
            "to_account_id": card["id"],
            "description": "信用卡还款",
        },
    ).status_code == 201

    cycle = client.get(
        f"/api/finance/credit-cards/{card['id']}/cycle?as_of=2026-09-20"
    ).get_json()["data"]
    assert cycle["previous_cycle_start"] == "2026-08-19"
    assert cycle["previous_statement_date"] == "2026-09-18"
    assert cycle["cycle_start"] == "2026-09-19"
    assert cycle["cycle_end"] == "2026-10-18"
    assert cycle["next_cycle_start"] == "2026-10-19"
    assert cycle["statement_amount"] == "150.00"
    assert cycle["repayments"] == "150.00"
    assert cycle["amount_due"] == "0.00"
    assert cycle["current_spending"] == "25.00"
    assert cycle["outstanding_balance"] == "25.00"
    assert cycle["status"] == "paid"

    assert client.post(
        "/api/finance/transactions",
        json={
            "date": "2026-10-19",
            "type": "expense",
            "amount": "40.00",
            "from_account_id": card["id"],
        },
    ).status_code == 201
    next_cycle = client.get(
        f"/api/finance/credit-cards/{card['id']}/cycle?as_of=2026-10-19"
    ).get_json()["data"]
    assert next_cycle["cycle_start"] == "2026-10-19"
    assert next_cycle["cycle_end"] == "2026-11-18"
    assert next_cycle["statement_amount"] == "25.00"
    assert next_cycle["current_spending"] == "40.00"
    year_boundary = client.get(
        f"/api/finance/credit-cards/{card['id']}/cycle?as_of=2027-01-19"
    ).get_json()["data"]
    assert year_boundary["previous_cycle_start"] == "2026-12-19"
    assert year_boundary["previous_statement_date"] == "2027-01-18"
    assert year_boundary["cycle_start"] == "2027-01-19"
    assert year_boundary["cycle_end"] == "2027-02-18"
    assert year_boundary["next_cycle_start"] == "2027-02-19"
    assert client.get(
        f"/api/finance/credit-cards/{card['id']}/cycle?as_of=not-a-date"
    ).status_code == 400


def test_credit_card_account_validation(client: FlaskClient) -> None:
    default_day = create_account(
        client, "默认账单日", kind="liability", account_type="credit"
    )
    assert default_day["billing_day"] == 18
    changed_day = client.put(
        f"/api/finance/accounts/{default_day['id']}", json={"billing_day": 20}
    )
    assert changed_day.status_code == 200
    assert changed_day.get_json()["data"]["billing_day"] == 20
    converted = client.put(
        f"/api/finance/accounts/{default_day['id']}",
        json={"account_type": "other"},
    )
    assert converted.status_code == 200
    assert converted.get_json()["data"]["billing_day"] is None
    assert client.post(
        "/api/finance/accounts",
        json={
            "name": "非法账单日",
            "kind": "liability",
            "account_type": "credit",
            "billing_day": 29,
        },
    ).status_code == 400
    assert client.post(
        "/api/finance/accounts",
        json={
            "name": "错误性质",
            "kind": "asset",
            "account_type": "credit",
        },
    ).status_code == 400
    bank = create_account(client, "普通银行卡")
    assert client.put(
        f"/api/finance/accounts/{bank['id']}", json={"billing_day": 18}
    ).status_code == 400
    assert client.get(
        f"/api/finance/credit-cards/{bank['id']}/cycle"
    ).status_code == 400
