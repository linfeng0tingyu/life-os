from __future__ import annotations

from sqlalchemy import func, select

from life_os.extensions import db
from life_os.models import Category, FinanceTransaction, Habit, Task

from .common import (
    ConflictError,
    NotFoundError,
    ValidationError,
    choice,
    integer_range,
    optional_text,
    required_text,
    transactional,
)


CATEGORY_SCOPES = {"task", "habit", "finance"}


class CategoryService:
    @staticmethod
    def list_categories(scope: str) -> list[Category]:
        normalized_scope = choice(scope, "scope", CATEGORY_SCOPES)
        return list(
            db.session.scalars(
                select(Category)
                .where(Category.scope == normalized_scope)
                .order_by(Category.sort_order, Category.name, Category.id)
            )
        )

    @staticmethod
    @transactional
    def create(
        scope: str, name: str, *, sort_order: int | None = None
    ) -> Category:
        normalized_scope = choice(scope, "scope", CATEGORY_SCOPES)
        normalized_name = required_text(name, "name", 100)
        existing = db.session.scalar(
            select(Category).where(
                Category.scope == normalized_scope,
                Category.name == normalized_name,
            )
        )
        if existing is not None:
            raise ConflictError("该分类已经存在。")
        normalized_order = (
            integer_range(sort_order, "sort_order", -1_000_000, 1_000_000)
            if sort_order is not None
            else int(
                db.session.scalar(
                    select(func.max(Category.sort_order)).where(
                        Category.scope == normalized_scope
                    )
                )
                or 0
            )
            + 10
        )
        category = Category(
            scope=normalized_scope,
            name=normalized_name,
            sort_order=normalized_order,
        )
        db.session.add(category)
        db.session.flush()
        return category

    @staticmethod
    @transactional
    def reorder(scope: str, category_ids: object) -> list[Category]:
        normalized_scope = choice(scope, "scope", CATEGORY_SCOPES)
        if (
            not isinstance(category_ids, list)
            or any(isinstance(item, bool) or not isinstance(item, int) for item in category_ids)
            or len(category_ids) != len(set(category_ids))
        ):
            raise ValidationError("category_ids 必须是不重复的整数列表。")
        categories = CategoryService.list_categories(normalized_scope)
        if set(category_ids) != {category.id for category in categories}:
            raise ValidationError("category_ids 必须完整包含当前作用域的全部分类。")
        by_id = {category.id: category for category in categories}
        ordered = [by_id[category_id] for category_id in category_ids]
        for index, category in enumerate(ordered, start=1):
            category.sort_order = index * 10
        db.session.flush()
        return ordered

    @staticmethod
    @transactional
    def delete(category_id: int) -> int:
        category = db.session.get(Category, category_id)
        if category is None:
            raise NotFoundError("分类不存在。")
        usage_count = CategoryService._usage_count(category)
        if usage_count:
            references = CategoryService._usage_references(category)
            raise ConflictError(
                "该分类仍被现有记录使用，不能删除。",
                details={
                    "usage_count": usage_count,
                    "scope": category.scope,
                    "references": references,
                    "references_truncated": usage_count > len(references),
                },
            )
        db.session.delete(category)
        return category_id

    @staticmethod
    def _usage_count(category: Category) -> int:
        model_by_scope = {
            "task": Task,
            "habit": Habit,
            "finance": FinanceTransaction,
        }
        model = model_by_scope[category.scope]
        category_column = model.category
        return int(
            db.session.scalar(
                select(func.count(model.id)).where(
                    func.lower(category_column) == category.name.lower()
                )
            )
            or 0
        )

    @staticmethod
    def _usage_references(category: Category, *, limit: int = 20) -> list[dict]:
        normalized_name = category.name.lower()
        if category.scope == "task":
            items = list(
                db.session.scalars(
                    select(Task)
                    .where(func.lower(Task.category) == normalized_name)
                    .order_by(Task.id.desc())
                    .limit(limit)
                )
            )
            return [
                {
                    "kind": "task",
                    "id": item.id,
                    "label": item.title,
                    "date": (
                        item.scheduled_date.isoformat()
                        if item.scheduled_date
                        else item.due_date.isoformat() if item.due_date else None
                    ),
                    "status": item.status,
                    "archived": item.archived_at is not None,
                }
                for item in items
            ]
        if category.scope == "habit":
            items = list(
                db.session.scalars(
                    select(Habit)
                    .where(func.lower(Habit.category) == normalized_name)
                    .order_by(Habit.id.desc())
                    .limit(limit)
                )
            )
            return [
                {
                    "kind": "habit",
                    "id": item.id,
                    "label": item.name,
                    "date": None,
                    "status": "active" if item.active else "inactive",
                    "archived": False,
                }
                for item in items
            ]

        items = list(
            db.session.scalars(
                select(FinanceTransaction)
                .where(func.lower(FinanceTransaction.category) == normalized_name)
                .order_by(FinanceTransaction.date.desc(), FinanceTransaction.id.desc())
                .limit(limit)
            )
        )
        type_labels = {"income": "收入", "expense": "支出", "transfer": "转账"}
        return [
            {
                "kind": "finance_transaction",
                "id": item.id,
                "label": item.description or type_labels[item.transaction_type],
                "date": item.date.isoformat(),
                "status": item.transaction_type,
                "archived": item.archived_at is not None,
                "amount": f"{item.amount_minor / 100:.2f}",
            }
            for item in items
        ]

    @staticmethod
    def normalize_assignment(scope: str, value: object) -> str | None:
        normalized_scope = choice(scope, "scope", CATEGORY_SCOPES)
        normalized_name = optional_text(value, "category", 100)
        if normalized_name is None:
            return None
        category = db.session.scalar(
            select(Category).where(
                Category.scope == normalized_scope,
                Category.name == normalized_name,
            )
        )
        if category is None:
            raise ValidationError("所选分类不存在，请先创建分类。")
        return category.name
