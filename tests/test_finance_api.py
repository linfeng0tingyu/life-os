from __future__ import annotations

from datetime import date

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
    restored = client.post(f"/api/finance/transactions/{expense['id']}/restore")
    assert restored.status_code == 200
    assert restored.get_json()["data"]["archived_at"] is None
    assert client.post("/api/finance/transactions/999/restore").status_code == 404


def test_balance_adjustment_creates_auditable_non_cashflow_transaction(
    client: FlaskClient,
) -> None:
    bank = create_account(client, "对账银行卡", opening_balance="100.00")
    assert client.post(
        "/api/finance/transactions",
        json={
            "date": "2026-09-27",
            "type": "expense",
            "amount": "20.00",
            "from_account_id": bank["id"],
        },
    ).status_code == 201

    adjusted = client.post(
        f"/api/finance/accounts/{bank['id']}/balance-adjustments",
        json={"target_balance": "125.50"},
    )
    assert adjusted.status_code == 201
    data = adjusted.get_json()["data"]
    assert data["previous_balance"] == "80.00"
    assert data["target_balance"] == "125.50"
    assert data["difference"] == "45.50"
    assert data["account"]["balance"] == "125.50"
    assert data["transaction"]["date"] == date.today().isoformat()
    assert data["transaction"]["type"] == "income"
    assert data["transaction"]["amount"] == "45.50"
    assert data["transaction"]["is_adjustment"] is True
    assert data["transaction"]["description"] == "账户金额调整"
    adjustment_id = data["transaction"]["id"]

    summary = client.get(
        "/api/finance/summary?date_from=2026-01-01&date_to=2026-12-31"
    ).get_json()["data"]
    assert summary["income"] == "0.00"
    assert summary["expense"] == "20.00"
    assert summary["net_cashflow"] == "-20.00"
    assert summary["accounts"][0]["balance"] == "125.50"

    filtered = client.get(
        "/api/finance/transactions?type=adjustment"
    ).get_json()["data"]
    assert [item["id"] for item in filtered] == [adjustment_id]
    assert client.get(
        "/api/finance/transactions?type=income"
    ).get_json()["data"] == []
    assert client.put(
        f"/api/finance/transactions/{adjustment_id}",
        json={"amount": "1.00"},
    ).status_code == 400
    assert client.post(
        f"/api/finance/accounts/{bank['id']}/balance-adjustments",
        json={"target_balance": "125.50"},
    ).status_code == 409

    assert client.delete(
        f"/api/finance/transactions/{adjustment_id}"
    ).status_code == 200
    reverted = client.get("/api/finance/summary").get_json()["data"]
    assert reverted["accounts"][0]["balance"] == "80.00"


def test_balance_adjustment_validates_account_and_target(client: FlaskClient) -> None:
    account = create_account(client, "停用账户", opening_balance="50.00")
    endpoint = f"/api/finance/accounts/{account['id']}/balance-adjustments"
    assert client.post(endpoint, json={"target_balance": "1.001"}).status_code == 400
    assert client.put(
        f"/api/finance/accounts/{account['id']}", json={"active": False}
    ).status_code == 200
    assert client.post(endpoint, json={"target_balance": "40.00"}).status_code == 400
    assert client.post(
        "/api/finance/accounts/999/balance-adjustments",
        json={"target_balance": "1.00"},
    ).status_code == 404


def test_balance_adjustment_supports_signed_liability_balances(
    client: FlaskClient,
) -> None:
    liability = create_account(
        client,
        "其他负债",
        kind="liability",
        account_type="other",
        opening_balance="-100.00",
    )
    endpoint = f"/api/finance/accounts/{liability['id']}/balance-adjustments"
    increased_debt = client.post(endpoint, json={"target_balance": "-150.00"})
    assert increased_debt.status_code == 201
    assert increased_debt.get_json()["data"]["difference"] == "-50.00"
    assert increased_debt.get_json()["data"]["transaction"]["type"] == "expense"

    reduced_debt = client.post(endpoint, json={"target_balance": "-40.00"})
    assert reduced_debt.status_code == 201
    assert reduced_debt.get_json()["data"]["difference"] == "110.00"
    assert reduced_debt.get_json()["data"]["transaction"]["type"] == "income"
    summary = client.get("/api/finance/summary").get_json()["data"]
    assert summary["total_liabilities"] == "40.00"
    assert summary["income"] == summary["expense"] == "0.00"


def test_finance_update_without_note_preserves_legacy_note(client: FlaskClient) -> None:
    bank = create_account(client, "Bank")
    created = client.post(
        "/api/finance/transactions",
        json={
            "date": "2026-09-18",
            "type": "expense",
            "amount": "12.00",
            "from_account_id": bank["id"],
            "description": "午餐",
            "note": "旧版本备注",
        },
    ).get_json()["data"]

    updated = client.put(
        f"/api/finance/transactions/{created['id']}",
        json={"description": "工作餐"},
    ).get_json()["data"]

    assert updated["description"] == "工作餐"
    assert updated["note"] == "旧版本备注"


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
    assert client.get("/api/finance/reports").status_code == 400
    assert client.get(
        "/api/finance/reports?date_from=2026-09-19&date_to=2026-09-18"
    ).status_code == 400
    assert client.put("/api/finance/transactions/999", json={"amount": "1.00"}).status_code == 404


def test_finance_reports_api_serializes_date_category_and_asset_totals(
    client: FlaskClient,
) -> None:
    bank = create_account(client, "报表银行卡", opening_balance="100.00")
    assert client.post(
        "/api/finance/transactions",
        json={
            "date": "2026-09-18",
            "type": "income",
            "amount": "50.00",
            "to_account_id": bank["id"],
            "category": "工资",
        },
    ).status_code == 201
    assert client.post(
        "/api/finance/transactions",
        json={
            "date": "2026-09-19",
            "type": "expense",
            "amount": "12.50",
            "from_account_id": bank["id"],
        },
    ).status_code == 201

    response = client.get(
        "/api/finance/reports?date_from=2026-09-18&date_to=2026-09-20"
    )
    assert response.status_code == 200
    report = response.get_json()["data"]
    assert report["date_from"] == "2026-09-18"
    assert report["date_to"] == "2026-09-20"
    assert report["income"] == "50.00"
    assert report["expense"] == "12.50"
    assert report["net_cashflow"] == "37.50"
    assert report["total_assets"] == "137.50"
    assert report["net_worth"] == "137.50"
    assert report["by_date"][0]["total_assets"] == "150.00"
    assert report["by_date"][1]["total_assets"] == "137.50"
    assert report["by_category"] == [
        {
            "category": "工资",
            "income": "50.00",
            "expense": "0.00",
            "net_cashflow": "50.00",
            "transaction_count": 1,
        },
        {
            "category": "未分类",
            "income": "0.00",
            "expense": "12.50",
            "net_cashflow": "-12.50",
            "transaction_count": 1,
        },
    ]
    assert report["category_series"] == [
        {
            "category": "工资",
            "points": [
                {
                    "date": "2026-09-18", "income": "50.00",
                    "expense": "0.00", "net_cashflow": "50.00",
                },
                {
                    "date": "2026-09-19", "income": "0.00",
                    "expense": "0.00", "net_cashflow": "0.00",
                },
                {
                    "date": "2026-09-20", "income": "0.00",
                    "expense": "0.00", "net_cashflow": "0.00",
                },
            ],
        },
        {
            "category": "未分类",
            "points": [
                {
                    "date": "2026-09-18", "income": "0.00",
                    "expense": "0.00", "net_cashflow": "0.00",
                },
                {
                    "date": "2026-09-19", "income": "0.00",
                    "expense": "12.50", "net_cashflow": "-12.50",
                },
                {
                    "date": "2026-09-20", "income": "0.00",
                    "expense": "0.00", "net_cashflow": "0.00",
                },
            ],
        },
    ]


def test_finance_transactions_can_search_category_and_include_archived(
    client: FlaskClient,
) -> None:
    account = create_account(client, "搜索账户", opening_balance="100.00")
    lunch = client.post(
        "/api/finance/transactions",
        json={
            "date": "2026-09-23",
            "type": "expense",
            "amount": "10.00",
            "from_account_id": account["id"],
            "category": "午餐餐饮",
        },
    ).get_json()["data"]
    client.post(
        "/api/finance/transactions",
        json={
            "date": "2026-09-24",
            "type": "expense",
            "amount": "20.00",
            "from_account_id": account["id"],
            "category": "交通",
        },
    )
    assert client.delete(f"/api/finance/transactions/{lunch['id']}").status_code == 200

    assert client.get(
        "/api/finance/transactions?category=午餐"
    ).get_json()["data"] == []
    matches = client.get(
        "/api/finance/transactions?category=午餐&include_archived=true"
    ).get_json()["data"]
    assert [item["id"] for item in matches] == [lunch["id"]]
    assert matches[0]["date"] == "2026-09-23"


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
