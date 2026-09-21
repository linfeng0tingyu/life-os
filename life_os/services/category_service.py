from __future__ import annotations

from sqlalchemy import select

from life_os.extensions import db
from life_os.models import Category

from .common import (
    ConflictError,
    ValidationError,
    choice,
    integer_range,
    optional_text,
    required_text,
    transactional,
)


CATEGORY_SCOPES = {"task", "habit"}


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
    def create(scope: str, name: str, *, sort_order: int = 0) -> Category:
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
        category = Category(
            scope=normalized_scope,
            name=normalized_name,
            sort_order=integer_range(
                sort_order, "sort_order", -1_000_000, 1_000_000
            ),
        )
        db.session.add(category)
        db.session.flush()
        return category

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
