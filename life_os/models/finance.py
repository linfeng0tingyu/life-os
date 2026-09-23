from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from life_os.extensions import db

from .base import TimestampMixin


class FinanceAccount(TimestampMixin, db.Model):
    __tablename__ = "finance_accounts"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('asset', 'liability')", name="ck_finance_accounts_kind"
        ),
        CheckConstraint(
            "account_type IN ('cash', 'bank', 'credit', 'investment', 'other')",
            name="ck_finance_accounts_type",
        ),
        CheckConstraint(
            "billing_day IS NULL OR billing_day BETWEEN 1 AND 28",
            name="ck_finance_accounts_billing_day",
        ),
        CheckConstraint("currency = 'CNY'", name="ck_finance_accounts_currency"),
        Index("ix_finance_accounts_active_sort", "active", "sort_order", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    billing_day: Mapped[int | None] = mapped_column(nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    opening_balance_minor: Mapped[int] = mapped_column(nullable=False, default=0)
    active: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="ck_finance_accounts_active"),
        nullable=False,
        default=True,
    )
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    outgoing_transactions: Mapped[list["FinanceTransaction"]] = relationship(
        foreign_keys="FinanceTransaction.from_account_id",
        back_populates="from_account",
    )
    incoming_transactions: Mapped[list["FinanceTransaction"]] = relationship(
        foreign_keys="FinanceTransaction.to_account_id",
        back_populates="to_account",
    )


class FinanceTransaction(TimestampMixin, db.Model):
    __tablename__ = "finance_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('income', 'expense', 'transfer')",
            name="ck_finance_transactions_type",
        ),
        CheckConstraint("amount_minor > 0", name="ck_finance_transactions_amount"),
        CheckConstraint(
            "(transaction_type = 'income' AND from_account_id IS NULL "
            "AND to_account_id IS NOT NULL) OR "
            "(transaction_type = 'expense' AND from_account_id IS NOT NULL "
            "AND to_account_id IS NULL) OR "
            "(transaction_type = 'transfer' AND from_account_id IS NOT NULL "
            "AND to_account_id IS NOT NULL "
            "AND from_account_id != to_account_id)",
            name="ck_finance_transactions_accounts",
        ),
        Index("ix_finance_transactions_date_archived", "date", "archived_at"),
        Index(
            "ix_finance_transactions_type_date",
            "transaction_type",
            "date",
            "archived_at",
        ),
        Index("ix_finance_transactions_from", "from_account_id", "date"),
        Index("ix_finance_transactions_to", "to_account_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_minor: Mapped[int] = mapped_column(nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    from_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("finance_accounts.id", ondelete="RESTRICT"), nullable=True
    )
    to_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("finance_accounts.id", ondelete="RESTRICT"), nullable=True
    )
    archived_at: Mapped[str | None] = mapped_column(String(40), nullable=True)

    from_account: Mapped[FinanceAccount | None] = relationship(
        foreign_keys=[from_account_id], back_populates="outgoing_transactions"
    )
    to_account: Mapped[FinanceAccount | None] = relationship(
        foreign_keys=[to_account_id], back_populates="incoming_transactions"
    )
