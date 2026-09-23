from __future__ import annotations

from typing import Any

from .models import (
    CalendarDay,
    Category,
    DailyHealth,
    FinanceAccount,
    FinanceTransaction,
    Habit,
    HabitLog,
    Journal,
    Task,
)
from .services.calendar_service import ResolvedCalendarDay
from .services.finance_service import minor_to_money


def category_data(category: Category) -> dict[str, Any]:
    return {
        "id": category.id,
        "scope": category.scope,
        "name": category.name,
        "sort_order": category.sort_order,
        "created_at": category.created_at,
        "updated_at": category.updated_at,
    }


def calendar_day_data(day: ResolvedCalendarDay | CalendarDay) -> dict[str, Any]:
    explicit = isinstance(day, CalendarDay) or day.explicit
    return {
        "date": day.date.isoformat(),
        "day_type": day.day_type,
        "holiday_name": day.holiday_name,
        "custom_label": day.custom_label,
        "note": day.note,
        "source": day.source,
        "explicit": explicit,
    }


def habit_data(habit: Habit) -> dict[str, Any]:
    return {
        "id": habit.id,
        "name": habit.name,
        "description": habit.description,
        "icon": habit.icon,
        "category": habit.category,
        "active": habit.active,
        "sort_order": habit.sort_order,
        "created_at": habit.created_at,
        "updated_at": habit.updated_at,
    }


def habit_log_data(log: HabitLog) -> dict[str, Any]:
    return {
        "id": log.id,
        "habit_id": log.habit_id,
        "date": log.date.isoformat(),
        "status": log.status,
        "value": log.value,
        "value_unit": log.value_unit,
        "note": log.note,
        "created_at": log.created_at,
        "updated_at": log.updated_at,
    }


def task_data(task: Task, *, target_date=None) -> dict[str, Any]:
    data = {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "category": task.category,
        "scheduled_date": (
            task.scheduled_date.isoformat() if task.scheduled_date else None
        ),
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "completed_at": task.completed_at,
        "sort_order": task.sort_order,
        "parent_id": task.parent_id,
        "archived_at": task.archived_at,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }
    if target_date is not None:
        data["date_match"] = {
            "scheduled": task.scheduled_date == target_date,
            "due": task.due_date == target_date,
            "overdue": (
                task.due_date is not None
                and task.due_date < target_date
                and task.status not in {"done", "cancelled"}
            ),
        }
    return data


def health_data(record: DailyHealth) -> dict[str, Any]:
    return {
        "id": record.id,
        "date": record.date.isoformat(),
        "weight_kg": record.weight_kg,
        "sleep_start": record.sleep_start,
        "sleep_end": record.sleep_end,
        "sleep_duration_minutes": record.sleep_duration_minutes,
        "sleep_duration_manual": record.sleep_duration_manual,
        "sleep_quality": record.sleep_quality,
        "energy_level": record.energy_level,
        "mood_level": record.mood_level,
        "body_status": record.body_status,
        "exercise_minutes": record.exercise_minutes,
        "note": record.note,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def journal_data(journal: Journal) -> dict[str, Any]:
    return {
        "id": journal.id,
        "date": journal.date.isoformat(),
        "content": journal.content,
        "created_at": journal.created_at,
        "updated_at": journal.updated_at,
    }


def finance_account_data(
    account: FinanceAccount, *, balance_minor: int | None = None
) -> dict[str, Any]:
    data = {
        "id": account.id,
        "name": account.name,
        "kind": account.kind,
        "account_type": account.account_type,
        "billing_day": account.billing_day,
        "currency": account.currency,
        "opening_balance": minor_to_money(account.opening_balance_minor),
        "active": account.active,
        "sort_order": account.sort_order,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }
    if balance_minor is not None:
        data["balance"] = minor_to_money(balance_minor)
    return data


def finance_transaction_data(transaction: FinanceTransaction) -> dict[str, Any]:
    return {
        "id": transaction.id,
        "date": transaction.date.isoformat(),
        "type": transaction.transaction_type,
        "amount": minor_to_money(transaction.amount_minor),
        "currency": "CNY",
        "from_account_id": transaction.from_account_id,
        "to_account_id": transaction.to_account_id,
        "category": transaction.category,
        "description": transaction.description,
        "note": transaction.note,
        "archived_at": transaction.archived_at,
        "created_at": transaction.created_at,
        "updated_at": transaction.updated_at,
    }


def finance_credit_cycle_data(cycle: dict[str, Any]) -> dict[str, Any]:
    return {
        "account": finance_account_data(cycle["account"]),
        "as_of": cycle["as_of"].isoformat(),
        "billing_day": cycle["billing_day"],
        "previous_cycle_start": cycle["previous_cycle_start"].isoformat(),
        "previous_statement_date": cycle["previous_statement_date"].isoformat(),
        "cycle_start": cycle["cycle_start"].isoformat(),
        "cycle_end": cycle["cycle_end"].isoformat(),
        "next_cycle_start": cycle["next_cycle_start"].isoformat(),
        "statement_amount": minor_to_money(cycle["statement_amount_minor"]),
        "repayments": minor_to_money(cycle["repayments_minor"]),
        "credits": minor_to_money(cycle["credits_minor"]),
        "amount_due": minor_to_money(cycle["amount_due_minor"]),
        "current_spending": minor_to_money(cycle["current_spending_minor"]),
        "outstanding_balance": minor_to_money(
            cycle["outstanding_balance_minor"]
        ),
        "status": cycle["status"],
    }


def finance_day_data(day: dict[str, Any]) -> dict[str, Any]:
    return {
        "currency": "CNY",
        "income": minor_to_money(day["income_minor"]),
        "expense": minor_to_money(day["expense_minor"]),
        "net_cashflow": minor_to_money(day["net_cashflow_minor"]),
        "transactions": [
            finance_transaction_data(item) for item in day["transactions"]
        ],
    }


def finance_summary_data(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "currency": "CNY",
        "date_from": (
            summary["date_from"].isoformat() if summary["date_from"] else None
        ),
        "date_to": summary["date_to"].isoformat() if summary["date_to"] else None,
        "income": minor_to_money(summary["income_minor"]),
        "expense": minor_to_money(summary["expense_minor"]),
        "net_cashflow": minor_to_money(summary["net_cashflow_minor"]),
        "total_assets": minor_to_money(summary["total_assets_minor"]),
        "total_liabilities": minor_to_money(summary["total_liabilities_minor"]),
        "net_worth": minor_to_money(summary["net_worth_minor"]),
        "accounts": [
            finance_account_data(account, balance_minor=balance)
            for account, balance in summary["accounts"]
        ],
    }
