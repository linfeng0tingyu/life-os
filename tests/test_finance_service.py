from __future__ import annotations

from datetime import date

import pytest

from life_os.services.common import ValidationError
from life_os.services.finance_service import FinanceService, minor_to_money


def test_accounts_and_overall_summary_use_exact_minor_units(app_context: None) -> None:
    bank = FinanceService.create_account(
        "Bank", kind="asset", account_type="bank", opening_balance="1000.00"
    )
    credit = FinanceService.create_account(
        "Card", kind="liability", account_type="credit", opening_balance="-500.00"
    )
    FinanceService.create_transaction(
        "2026-09-18",
        transaction_type="income",
        amount="200.10",
        to_account_id=bank.id,
        category="salary",
    )
    FinanceService.create_transaction(
        "2026-09-18",
        transaction_type="expense",
        amount="50.05",
        from_account_id=bank.id,
        category="food",
    )
    FinanceService.create_transaction(
        "2026-09-19",
        transaction_type="transfer",
        amount="100.00",
        from_account_id=bank.id,
        to_account_id=credit.id,
    )

    summary = FinanceService.summary(
        date_from="2026-09-18", date_to="2026-09-18"
    )
    balances = {account.id: balance for account, balance in summary["accounts"]}
    assert balances == {bank.id: 105005, credit.id: -40000}
    assert summary["income_minor"] == 20010
    assert summary["expense_minor"] == 5005
    assert summary["net_cashflow_minor"] == 15005
    assert summary["total_assets_minor"] == 105005
    assert summary["total_liabilities_minor"] == 40000
    assert summary["net_worth_minor"] == 65005
    assert minor_to_money(summary["net_worth_minor"]) == "650.05"


def test_summary_uses_database_aggregation_instead_of_loading_all_transactions(
    app_context: None, monkeypatch
) -> None:
    account = FinanceService.create_account(
        "Cash", kind="asset", account_type="cash", opening_balance="10.00"
    )
    FinanceService.create_transaction(
        "2026-09-18",
        transaction_type="expense",
        amount="2.00",
        from_account_id=account.id,
    )

    monkeypatch.setattr(
        FinanceService,
        "list_transactions",
        staticmethod(lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("loaded all rows"))),
    )

    summary = FinanceService.summary()
    assert summary["expense_minor"] == 200
    assert summary["accounts"][0][1] == 800


def test_finance_report_groups_cashflow_and_tracks_daily_assets(
    app_context: None,
) -> None:
    bank = FinanceService.create_account(
        "Bank", kind="asset", account_type="bank", opening_balance="1000.00"
    )
    card = FinanceService.create_account(
        "Card", kind="liability", account_type="credit", opening_balance="-300.00"
    )
    FinanceService.create_transaction(
        "2026-09-17",
        transaction_type="income",
        amount="100.00",
        to_account_id=bank.id,
        category="工资",
    )
    FinanceService.create_transaction(
        "2026-09-18",
        transaction_type="expense",
        amount="20.00",
        from_account_id=bank.id,
        category="餐饮",
    )
    FinanceService.create_transaction(
        "2026-09-18",
        transaction_type="expense",
        amount="50.00",
        from_account_id=card.id,
        category="餐饮",
    )
    FinanceService.create_transaction(
        "2026-09-19",
        transaction_type="income",
        amount="200.00",
        to_account_id=bank.id,
        category="工资",
    )
    FinanceService.create_transaction(
        "2026-09-19",
        transaction_type="transfer",
        amount="100.00",
        from_account_id=bank.id,
        to_account_id=card.id,
    )

    report = FinanceService.report(
        date_from="2026-09-18", date_to="2026-09-20"
    )

    assert report["income_minor"] == 20000
    assert report["expense_minor"] == 7000
    assert report["net_cashflow_minor"] == 13000
    assert [point["date"].isoformat() for point in report["by_date"]] == [
        "2026-09-18",
        "2026-09-19",
        "2026-09-20",
    ]
    assert report["by_date"][0] == {
        "date": date(2026, 9, 18),
        "income_minor": 0,
        "expense_minor": 7000,
        "net_cashflow_minor": -7000,
        "total_assets_minor": 108000,
        "total_liabilities_minor": 35000,
        "net_worth_minor": 73000,
    }
    assert report["by_date"][1]["total_assets_minor"] == 118000
    assert report["by_date"][1]["total_liabilities_minor"] == 25000
    assert report["by_date"][1]["net_worth_minor"] == 93000
    assert report["by_date"][2]["total_assets_minor"] == 118000
    assert report["by_category"] == [
        {
            "category": "工资",
            "income_minor": 20000,
            "expense_minor": 0,
            "transaction_count": 1,
            "net_cashflow_minor": 20000,
        },
        {
            "category": "餐饮",
            "income_minor": 0,
            "expense_minor": 7000,
            "transaction_count": 2,
            "net_cashflow_minor": -7000,
        },
    ]
    assert report["category_series"][0]["category"] == "工资"
    assert [
        point["income_minor"]
        for point in report["category_series"][0]["points"]
    ] == [0, 20000, 0]
    assert report["category_series"][1]["category"] == "餐饮"
    assert [
        point["expense_minor"]
        for point in report["category_series"][1]["points"]
    ] == [7000, 0, 0]


def test_finance_report_uses_database_rows_and_validates_range(
    app_context: None, monkeypatch
) -> None:
    FinanceService.create_account(
        "Cash", kind="asset", account_type="cash", opening_balance="10.00"
    )
    monkeypatch.setattr(
        FinanceService,
        "list_transactions",
        staticmethod(
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("loaded transaction entities")
            )
        ),
    )

    report = FinanceService.report(
        date_from="2026-09-18", date_to="2026-09-18"
    )
    assert report["total_assets_minor"] == 1000
    with pytest.raises(ValidationError, match="不能晚于"):
        FinanceService.report(date_from="2026-09-19", date_to="2026-09-18")


def test_finance_report_excludes_adjustments_from_cashflow_but_tracks_balance(
    app_context: None,
) -> None:
    account = FinanceService.create_account(
        "Checked balance", kind="asset", account_type="bank", opening_balance="100.00"
    )
    result = FinanceService.adjust_account_balance(
        account.id, target_balance="125.50"
    )
    target = date.today().isoformat()

    report = FinanceService.report(date_from=target, date_to=target)

    assert result["difference_minor"] == 2550
    assert report["income_minor"] == 0
    assert report["expense_minor"] == 0
    assert report["net_cashflow_minor"] == 0
    assert report["total_assets_minor"] == 12550
    assert report["by_date"][0]["total_assets_minor"] == 12550
    assert report["by_category"] == []


def test_daily_transactions_filter_and_archive(app_context: None) -> None:
    cash = FinanceService.create_account(
        "Cash", kind="asset", account_type="cash"
    )
    transaction = FinanceService.create_transaction(
        "2026-09-18",
        transaction_type="expense",
        amount="12.34",
        from_account_id=cash.id,
        category="Lunch",
    )
    income = FinanceService.create_transaction(
        "2026-09-19",
        transaction_type="income",
        amount="20.00",
        to_account_id=cash.id,
        category="Salary",
    )
    day = FinanceService.day("2026-09-18")
    assert day["expense_minor"] == 1234
    assert [item.id for item in day["transactions"]] == [transaction.id]

    FinanceService.archive_transaction(transaction.id)
    assert FinanceService.day("2026-09-18")["transactions"] == []
    assert len(FinanceService.list_transactions(include_archived=True)) == 2
    assert FinanceService.list_transactions(category="missing") == []
    assert [
        item.id
        for item in FinanceService.list_transactions(
            category="lUn", include_archived=True
        )
    ] == [transaction.id]
    assert [
        item.id for item in FinanceService.list_transactions(category="Sala")
    ] == [income.id]
    restored = FinanceService.restore_transaction(transaction.id)
    assert restored.archived_at is None
    assert [
        item.id for item in FinanceService.list_transactions(category=None)
    ] == [income.id, transaction.id]


@pytest.mark.parametrize(
    ("kind", "opening_balance"), [("asset", "-1.00"), ("liability", "1.00")]
)
def test_account_opening_balance_sign_is_validated(
    app_context: None, kind: str, opening_balance: str
) -> None:
    with pytest.raises(ValidationError):
        FinanceService.create_account(
            "Invalid",
            kind=kind,
            account_type="other",
            opening_balance=opening_balance,
        )


def test_transaction_rules_and_money_precision_are_validated(
    app_context: None,
) -> None:
    cash = FinanceService.create_account(
        "Cash", kind="asset", account_type="cash"
    )
    with pytest.raises(ValidationError, match="两位小数"):
        FinanceService.create_transaction(
            "2026-09-18",
            transaction_type="expense",
            amount="1.001",
            from_account_id=cash.id,
        )
    with pytest.raises(ValidationError, match="支持范围"):
        FinanceService.create_transaction(
            "2026-09-18",
            transaction_type="expense",
            amount="1e100000",
            from_account_id=cash.id,
        )
    with pytest.raises(ValidationError, match="只提供 from_account_id"):
        FinanceService.create_transaction(
            "2026-09-18",
            transaction_type="expense",
            amount="1.00",
            to_account_id=cash.id,
        )
    with pytest.raises(ValidationError, match="不能相同"):
        FinanceService.create_transaction(
            "2026-09-18",
            transaction_type="transfer",
            amount="1.00",
            from_account_id=cash.id,
            to_account_id=cash.id,
        )
