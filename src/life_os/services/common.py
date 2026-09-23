from __future__ import annotations

import re
from datetime import date, datetime
from functools import wraps
from typing import Callable, ParamSpec, TypeVar

from sqlalchemy.exc import IntegrityError

from life_os.extensions import db


P = ParamSpec("P")
R = TypeVar("R")
UNSET = object()
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class DomainError(RuntimeError):
    """Base exception for domain-level failures."""

    def __init__(self, message: str, *, details: dict[str, object] | None = None):
        super().__init__(message)
        self.details = details or {}


class ValidationError(DomainError):
    """Raised when input violates a domain rule."""


class NotFoundError(DomainError):
    """Raised when a requested domain object does not exist."""


class ConflictError(DomainError):
    """Raised when a database constraint rejects an otherwise valid action."""


def transactional(function: Callable[P, R]) -> Callable[P, R]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            result = function(*args, **kwargs)
            db.session.commit()
            return result
        except IntegrityError as exc:
            db.session.rollback()
            raise ConflictError("数据约束冲突，操作未保存。") from exc
        except Exception:
            db.session.rollback()
            raise

    return wrapped


def parse_life_date(value: date | str, field: str = "date") -> date:
    if isinstance(value, datetime):
        raise ValidationError(f"{field} 必须是生活日期，不包含时间。")
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value):
        raise ValidationError(f"{field} 必须使用 YYYY-MM-DD 格式。")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field} 不是有效日历日期。") from exc


def parse_aware_datetime(value: str, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValidationError(f"{field} 必须是 ISO 8601 时间字符串。")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field} 不是有效的 ISO 8601 时间。") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValidationError(f"{field} 必须包含 UTC 偏移。")
    return parsed


def required_text(value: object, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} 必须是字符串。")
    normalized = value.strip()
    if not normalized:
        raise ValidationError(f"{field} 不能为空。")
    if len(normalized) > maximum:
        raise ValidationError(f"{field} 最多允许 {maximum} 个字符。")
    return normalized


def optional_text(value: object, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{field} 必须是字符串或 null。")
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > maximum:
        raise ValidationError(f"{field} 最多允许 {maximum} 个字符。")
    return normalized


def choice(value: object, field: str, allowed: set[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        values = "、".join(sorted(allowed))
        raise ValidationError(f"{field} 必须是以下值之一：{values}。")
    return value


def integer_range(
    value: object, field: str, minimum: int, maximum: int
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field} 必须是整数。")
    if not minimum <= value <= maximum:
        raise ValidationError(f"{field} 必须在 {minimum} 到 {maximum} 之间。")
    return value


def optional_float(
    value: object, field: str, minimum: float | None = None
) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} 必须是数值或 null。")
    normalized = float(value)
    if minimum is not None and normalized < minimum:
        raise ValidationError(f"{field} 不能小于 {minimum}。")
    return normalized
