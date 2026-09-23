from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import or_, select

from life_os.extensions import db
from life_os.models import FinanceAccount, FinanceTransaction
from life_os.models.base import now_iso

from .common import (
    UNSET,
    NotFoundError,
    ValidationError,
    choice,
    optional_text,
    parse_life_date,
    required_text,
    transactional,
)


ACCOUNT_KINDS = {"asset", "liability"}
ACCOUNT_TYPES = {"cash", "bank", "credit", "investment", "other"}
TRANSACTION_TYPES = {"income", "expense", "transfer"}
MAX_MONEY_MINOR = 9_000_000_000_000_000
DEFAULT_CREDIT_BILLING_DAY = 18


def money_to_minor(value: object, field: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValidationError(f"{field} 必须是最多两位小数的金额。")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValidationError(f"{field} 不是有效金额。") from exc
    if not amount.is_finite():
        raise ValidationError(f"{field} 必须是有限金额。")
    try:
        quantized = amount.quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValidationError(f"{field} 超出支持范围。") from exc
    if amount != quantized:
        raise ValidationError(f"{field} 最多允许两位小数。")
    minor = int(quantized * 100)
    if positive and minor <= 0:
        raise ValidationError(f"{field} 必须大于 0。")
    if abs(minor) > MAX_MONEY_MINOR:
        raise ValidationError(f"{field} 超出支持范围。")
    return minor


def minor_to_money(value: int) -> str:
    return f"{Decimal(value) / 100:.2f}"


class FinanceService:
    @staticmethod
    def list_accounts(*, include_inactive: bool = False) -> list[FinanceAccount]:
        statement = select(FinanceAccount)
        if not include_inactive:
            statement = statement.where(FinanceAccount.active.is_(True))
        return list(
            db.session.scalars(
                statement.order_by(FinanceAccount.sort_order, FinanceAccount.id)
            )
        )

    @staticmethod
    @transactional
    def create_account(
        name: str,
        *,
        kind: str,
        account_type: str,
        opening_balance: object = "0.00",
        currency: str = "CNY",
        sort_order: int = 0,
        billing_day: object = None,
    ) -> FinanceAccount:
        normalized_kind = choice(kind, "kind", ACCOUNT_KINDS)
        normalized_type = choice(account_type, "account_type", ACCOUNT_TYPES)
        normalized_billing_day = FinanceService._normalize_billing_day(
            normalized_type, billing_day
        )
        FinanceService._validate_account_kind(normalized_kind, normalized_type)
        opening_minor = money_to_minor(opening_balance, "opening_balance")
        FinanceService._validate_opening_balance(normalized_kind, opening_minor)
        FinanceService._validate_currency(currency)
        FinanceService._validate_sort_order(sort_order)
        account = FinanceAccount(
            name=required_text(name, "name", 200),
            kind=normalized_kind,
            account_type=normalized_type,
            billing_day=normalized_billing_day,
            currency=currency,
            opening_balance_minor=opening_minor,
            active=True,
            sort_order=sort_order,
        )
        db.session.add(account)
        db.session.flush()
        return account

    @staticmethod
    @transactional
    def update_account(
        account_id: int,
        *,
        name: object = UNSET,
        kind: object = UNSET,
        account_type: object = UNSET,
        opening_balance: object = UNSET,
        active: object = UNSET,
        sort_order: object = UNSET,
        billing_day: object = UNSET,
    ) -> FinanceAccount:
        account = FinanceService._get_account(account_id)
        normalized_kind = (
            choice(kind, "kind", ACCOUNT_KINDS) if kind is not UNSET else account.kind
        )
        opening_minor = (
            money_to_minor(opening_balance, "opening_balance")
            if opening_balance is not UNSET
            else account.opening_balance_minor
        )
        normalized_type = (
            choice(account_type, "account_type", ACCOUNT_TYPES)
            if account_type is not UNSET
            else account.account_type
        )
        billing_value = billing_day if billing_day is not UNSET else (
            account.billing_day if normalized_type == "credit" else None
        )
        normalized_billing_day = FinanceService._normalize_billing_day(
            normalized_type, billing_value
        )
        FinanceService._validate_account_kind(normalized_kind, normalized_type)
        FinanceService._validate_opening_balance(normalized_kind, opening_minor)
        if name is not UNSET:
            account.name = required_text(name, "name", 200)
        if kind is not UNSET:
            account.kind = normalized_kind
        if account_type is not UNSET:
            account.account_type = normalized_type
        account.billing_day = normalized_billing_day
        if opening_balance is not UNSET:
            account.opening_balance_minor = opening_minor
        if active is not UNSET:
            if not isinstance(active, bool):
                raise ValidationError("active 必须是布尔值。")
            account.active = active
        if sort_order is not UNSET:
            FinanceService._validate_sort_order(sort_order)
            account.sort_order = sort_order
        db.session.flush()
        return account

    @staticmethod
    def list_transactions(
        *,
        value_date: date | str | None = None,
        transaction_type: str | None = None,
        account_id: int | None = None,
        include_archived: bool = False,
    ) -> list[FinanceTransaction]:
        statement = select(FinanceTransaction)
        if not include_archived:
            statement = statement.where(FinanceTransaction.archived_at.is_(None))
        if value_date is not None:
            statement = statement.where(
                FinanceTransaction.date == parse_life_date(value_date)
            )
        if transaction_type is not None:
            statement = statement.where(
                FinanceTransaction.transaction_type
                == choice(transaction_type, "type", TRANSACTION_TYPES)
            )
        if account_id is not None:
            normalized_account_id = FinanceService._validate_id(
                account_id, "account_id"
            )
            statement = statement.where(
                or_(
                    FinanceTransaction.from_account_id == normalized_account_id,
                    FinanceTransaction.to_account_id == normalized_account_id,
                )
            )
        return list(
            db.session.scalars(
                statement.order_by(FinanceTransaction.date.desc(), FinanceTransaction.id)
            )
        )

    @staticmethod
    @transactional
    def create_transaction(
        value_date: date | str,
        *,
        transaction_type: str,
        amount: object,
        from_account_id: int | None = None,
        to_account_id: int | None = None,
        category: str | None = None,
        description: str | None = None,
        note: str | None = None,
    ) -> FinanceTransaction:
        normalized_type = choice(
            transaction_type, "type", TRANSACTION_TYPES
        )
        from_account, to_account = FinanceService._validate_transaction_accounts(
            normalized_type, from_account_id, to_account_id, require_active=True
        )
        transaction = FinanceTransaction(
            date=parse_life_date(value_date),
            transaction_type=normalized_type,
            amount_minor=money_to_minor(amount, "amount", positive=True),
            from_account=from_account,
            to_account=to_account,
            category=optional_text(category, "category", 100),
            description=optional_text(description, "description", 300),
            note=optional_text(note, "note", 2000),
        )
        db.session.add(transaction)
        db.session.flush()
        return transaction

    @staticmethod
    @transactional
    def update_transaction(
        transaction_id: int,
        *,
        value_date: object = UNSET,
        transaction_type: object = UNSET,
        amount: object = UNSET,
        from_account_id: object = UNSET,
        to_account_id: object = UNSET,
        category: object = UNSET,
        description: object = UNSET,
        note: object = UNSET,
    ) -> FinanceTransaction:
        transaction = db.session.get(FinanceTransaction, transaction_id)
        if transaction is None:
            raise NotFoundError("财务流水不存在。")
        if transaction.archived_at is not None:
            raise ValidationError("已归档财务流水不能编辑。")

        normalized_type = (
            choice(transaction_type, "type", TRANSACTION_TYPES)
            if transaction_type is not UNSET
            else transaction.transaction_type
        )
        source_id = (
            from_account_id
            if from_account_id is not UNSET
            else transaction.from_account_id
        )
        target_id = (
            to_account_id if to_account_id is not UNSET else transaction.to_account_id
        )
        from_account, to_account = FinanceService._validate_transaction_accounts(
            normalized_type, source_id, target_id, require_active=False
        )
        transaction.transaction_type = normalized_type
        transaction.from_account = from_account
        transaction.to_account = to_account
        if value_date is not UNSET:
            transaction.date = parse_life_date(value_date, "date")
        if amount is not UNSET:
            transaction.amount_minor = money_to_minor(
                amount, "amount", positive=True
            )
        if category is not UNSET:
            transaction.category = optional_text(category, "category", 100)
        if description is not UNSET:
            transaction.description = optional_text(
                description, "description", 300
            )
        if note is not UNSET:
            transaction.note = optional_text(note, "note", 2000)
        db.session.flush()
        return transaction

    @staticmethod
    @transactional
    def archive_transaction(transaction_id: int) -> FinanceTransaction:
        transaction = db.session.get(FinanceTransaction, transaction_id)
        if transaction is None:
            raise NotFoundError("财务流水不存在。")
        if transaction.archived_at is None:
            transaction.archived_at = now_iso()
            db.session.flush()
        return transaction

    @staticmethod
    def day(value: date | str) -> dict:
        target = parse_life_date(value)
        transactions = FinanceService.list_transactions(value_date=target)
        income = sum(
            item.amount_minor
            for item in transactions
            if item.transaction_type == "income"
        )
        expense = sum(
            item.amount_minor
            for item in transactions
            if item.transaction_type == "expense"
        )
        return {
            "income_minor": income,
            "expense_minor": expense,
            "net_cashflow_minor": income - expense,
            "transactions": transactions,
        }

    @staticmethod
    def summary(
        *, date_from: date | str | None = None, date_to: date | str | None = None
    ) -> dict:
        start = (
            parse_life_date(date_from, "date_from")
            if date_from is not None
            else None
        )
        end = (
            parse_life_date(date_to, "date_to") if date_to is not None else None
        )
        if start and end and start > end:
            raise ValidationError("date_from 不能晚于 date_to。")

        accounts = FinanceService.list_accounts(include_inactive=True)
        balances = {account.id: account.opening_balance_minor for account in accounts}
        all_transactions = FinanceService.list_transactions()
        for item in all_transactions:
            if item.from_account_id is not None:
                balances[item.from_account_id] -= item.amount_minor
            if item.to_account_id is not None:
                balances[item.to_account_id] += item.amount_minor

        period_transactions = [
            item
            for item in all_transactions
            if (start is None or item.date >= start) and (end is None or item.date <= end)
        ]
        income = sum(
            item.amount_minor
            for item in period_transactions
            if item.transaction_type == "income"
        )
        expense = sum(
            item.amount_minor
            for item in period_transactions
            if item.transaction_type == "expense"
        )
        assets = sum(
            balances[account.id] for account in accounts if account.kind == "asset"
        )
        liabilities = sum(
            max(-balances[account.id], 0)
            for account in accounts
            if account.kind == "liability"
        )
        return {
            "date_from": start,
            "date_to": end,
            "income_minor": income,
            "expense_minor": expense,
            "net_cashflow_minor": income - expense,
            "total_assets_minor": assets,
            "total_liabilities_minor": liabilities,
            "net_worth_minor": sum(balances.values()),
            "accounts": [(account, balances[account.id]) for account in accounts],
        }

    @staticmethod
    def credit_card_cycle(
        account_id: int, *, as_of: date | str | None = None
    ) -> dict:
        account = FinanceService._get_account(account_id)
        if account.account_type != "credit":
            raise ValidationError("只有信用卡账户可以查看账期。")
        target = parse_life_date(as_of, "as_of") if as_of is not None else date.today()
        billing_day = account.billing_day or DEFAULT_CREDIT_BILLING_DAY
        candidate = _month_day(target.year, target.month, billing_day)
        cycle_end = candidate if target <= candidate else _shift_month_day(candidate, 1)
        previous_statement_date = _shift_month_day(cycle_end, -1)
        cycle_start = previous_statement_date + timedelta(days=1)
        previous_cycle_start = _shift_month_day(previous_statement_date, -1) + timedelta(
            days=1
        )
        next_cycle_start = cycle_end + timedelta(days=1)

        transactions = FinanceService.list_transactions(account_id=account.id)
        statement_balance = FinanceService._account_balance_through(
            account, transactions, previous_statement_date
        )
        balance = FinanceService._account_balance_through(account, transactions, target)
        cycle_transactions = [
            item for item in transactions if cycle_start <= item.date <= target
        ]
        current_spending = sum(
            item.amount_minor
            for item in cycle_transactions
            if item.transaction_type == "expense"
            and item.from_account_id == account.id
        )
        repayments = sum(
            item.amount_minor
            for item in cycle_transactions
            if item.transaction_type == "transfer"
            and item.to_account_id == account.id
        )
        credits = sum(
            item.amount_minor
            for item in cycle_transactions
            if item.transaction_type == "income"
            and item.to_account_id == account.id
        )
        statement_amount = max(-statement_balance, 0)
        amount_due = max(statement_amount - repayments - credits, 0)
        return {
            "account": account,
            "as_of": target,
            "billing_day": billing_day,
            "previous_cycle_start": previous_cycle_start,
            "previous_statement_date": previous_statement_date,
            "cycle_start": cycle_start,
            "cycle_end": cycle_end,
            "next_cycle_start": next_cycle_start,
            "statement_amount_minor": statement_amount,
            "repayments_minor": repayments,
            "credits_minor": credits,
            "amount_due_minor": amount_due,
            "current_spending_minor": current_spending,
            "outstanding_balance_minor": max(-balance, 0),
            "status": "paid" if amount_due == 0 else "unpaid",
        }

    @staticmethod
    def _account_balance_through(
        account: FinanceAccount,
        transactions: list[FinanceTransaction],
        through_date: date,
    ) -> int:
        balance = account.opening_balance_minor
        for item in transactions:
            if item.date > through_date:
                continue
            if item.from_account_id == account.id:
                balance -= item.amount_minor
            if item.to_account_id == account.id:
                balance += item.amount_minor
        return balance

    @staticmethod
    def _get_account(account_id: int, *, require_active: bool = False) -> FinanceAccount:
        normalized_id = FinanceService._validate_id(account_id, "account_id")
        account = db.session.get(FinanceAccount, normalized_id)
        if account is None:
            raise NotFoundError("财务账户不存在。")
        if require_active and not account.active:
            raise ValidationError("停用账户不能用于新财务流水。")
        return account

    @staticmethod
    def _validate_transaction_accounts(
        transaction_type: str,
        from_account_id: object,
        to_account_id: object,
        *,
        require_active: bool,
    ) -> tuple[FinanceAccount | None, FinanceAccount | None]:
        if transaction_type == "income":
            if from_account_id is not None or to_account_id is None:
                raise ValidationError("收入必须只提供 to_account_id。")
        elif transaction_type == "expense":
            if from_account_id is None or to_account_id is not None:
                raise ValidationError("支出必须只提供 from_account_id。")
        elif from_account_id is None or to_account_id is None:
            raise ValidationError("转账必须同时提供两个账户。")
        if (
            transaction_type == "transfer"
            and from_account_id == to_account_id
        ):
            raise ValidationError("转出与转入账户不能相同。")
        source = (
            FinanceService._get_account(
                from_account_id, require_active=require_active  # type: ignore[arg-type]
            )
            if from_account_id is not None
            else None
        )
        target = (
            FinanceService._get_account(
                to_account_id, require_active=require_active  # type: ignore[arg-type]
            )
            if to_account_id is not None
            else None
        )
        return source, target

    @staticmethod
    def _validate_opening_balance(kind: str, amount_minor: int) -> None:
        if kind == "asset" and amount_minor < 0:
            raise ValidationError("资产账户的 opening_balance 不能为负。")
        if kind == "liability" and amount_minor > 0:
            raise ValidationError("负债账户的 opening_balance 必须为零或负数。")

    @staticmethod
    def _validate_account_kind(kind: str, account_type: str) -> None:
        if account_type == "credit" and kind != "liability":
            raise ValidationError("信用卡必须使用负债账户性质。")

    @staticmethod
    def _normalize_billing_day(account_type: str, value: object) -> int | None:
        if account_type != "credit":
            if value is not None and value is not UNSET:
                raise ValidationError("billing_day 仅适用于信用卡账户。")
            return None
        if value is None or value is UNSET:
            return DEFAULT_CREDIT_BILLING_DAY
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 28:
            raise ValidationError("billing_day 必须是 1 到 28 的整数。")
        return value

    @staticmethod
    def _validate_currency(currency: object) -> None:
        if currency != "CNY":
            raise ValidationError("v0.1 只支持 CNY 汇总。")

    @staticmethod
    def _validate_sort_order(value: object) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError("sort_order 必须是整数。")

    @staticmethod
    def _validate_id(value: object, field: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValidationError(f"{field} 必须是正整数。")
        return value


def _month_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, monthrange(year, month)[1]))


def _shift_month_day(value: date, months: int) -> date:
    index = value.year * 12 + value.month - 1 + months
    year, zero_based_month = divmod(index, 12)
    return _month_day(year, zero_based_month + 1, value.day)
