from __future__ import annotations

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


def test_daily_transactions_filter_and_archive(app_context: None) -> None:
    cash = FinanceService.create_account(
        "Cash", kind="asset", account_type="cash"
    )
    transaction = FinanceService.create_transaction(
        "2026-09-18",
        transaction_type="expense",
        amount="12.34",
        from_account_id=cash.id,
    )
    FinanceService.create_transaction(
        "2026-09-19",
        transaction_type="income",
        amount="20.00",
        to_account_id=cash.id,
    )
    day = FinanceService.day("2026-09-18")
    assert day["expense_minor"] == 1234
    assert [item.id for item in day["transactions"]] == [transaction.id]

    FinanceService.archive_transaction(transaction.id)
    assert FinanceService.day("2026-09-18")["transactions"] == []
    assert len(FinanceService.list_transactions(include_archived=True)) == 2


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
