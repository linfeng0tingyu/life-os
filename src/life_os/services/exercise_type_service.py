from __future__ import annotations

from sqlalchemy import func, select

from life_os.extensions import db
from life_os.models import DailyHealthExerciseType, ExerciseType

from .common import (
    ConflictError,
    NotFoundError,
    ValidationError,
    integer_range,
    required_text,
    transactional,
)


class ExerciseTypeService:
    @staticmethod
    def list_types() -> list[ExerciseType]:
        return list(
            db.session.scalars(
                select(ExerciseType).order_by(
                    ExerciseType.sort_order, ExerciseType.name, ExerciseType.id
                )
            )
        )

    @staticmethod
    @transactional
    def create(name: str, *, sort_order: int | None = None) -> ExerciseType:
        normalized_name = required_text(name, "name", 100)
        existing = db.session.scalar(
            select(ExerciseType).where(ExerciseType.name == normalized_name)
        )
        if existing is not None:
            raise ConflictError("该运动种类已经存在。")
        normalized_order = (
            integer_range(sort_order, "sort_order", -1_000_000, 1_000_000)
            if sort_order is not None
            else int(db.session.scalar(select(func.max(ExerciseType.sort_order))) or 0)
            + 10
        )
        item = ExerciseType(name=normalized_name, sort_order=normalized_order)
        db.session.add(item)
        db.session.flush()
        return item

    @staticmethod
    @transactional
    def reorder(exercise_type_ids: object) -> list[ExerciseType]:
        if (
            not isinstance(exercise_type_ids, list)
            or any(
                isinstance(item, bool) or not isinstance(item, int)
                for item in exercise_type_ids
            )
            or len(exercise_type_ids) != len(set(exercise_type_ids))
        ):
            raise ValidationError("exercise_type_ids 必须是不重复的整数列表。")
        items = ExerciseTypeService.list_types()
        if set(exercise_type_ids) != {item.id for item in items}:
            raise ValidationError("exercise_type_ids 必须完整包含全部运动种类。")
        by_id = {item.id: item for item in items}
        ordered = [by_id[item_id] for item_id in exercise_type_ids]
        for index, item in enumerate(ordered, start=1):
            item.sort_order = index * 10
        db.session.flush()
        return ordered

    @staticmethod
    @transactional
    def delete(exercise_type_id: int) -> int:
        item = db.session.get(ExerciseType, exercise_type_id)
        if item is None:
            raise NotFoundError("运动种类不存在。")
        usage_count = int(
            db.session.scalar(
                select(func.count(DailyHealthExerciseType.id)).where(
                    DailyHealthExerciseType.exercise_type_id == item.id
                )
            )
            or 0
        )
        if usage_count:
            raise ConflictError(
                "该运动种类仍被节律记录使用，不能删除。",
                details={"usage_count": usage_count},
            )
        db.session.delete(item)
        return item.id

    @staticmethod
    def resolve_ids(value: object) -> list[ExerciseType]:
        if (
            not isinstance(value, list)
            or any(isinstance(item, bool) or not isinstance(item, int) for item in value)
            or len(value) != len(set(value))
        ):
            raise ValidationError("exercise_type_ids 必须是不重复的整数列表。")
        if not value:
            return []
        items = list(
            db.session.scalars(
                select(ExerciseType)
                .where(ExerciseType.id.in_(value))
                .order_by(
                    ExerciseType.sort_order, ExerciseType.name, ExerciseType.id
                )
            )
        )
        if {item.id for item in items} != set(value):
            raise ValidationError("所选运动种类不存在，请刷新后重试。")
        return items
