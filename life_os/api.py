from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from flask import jsonify, request
from werkzeug.exceptions import UnsupportedMediaType

from .services.common import ValidationError


def success_response(data: Any, *, status: int = 200):
    return jsonify({"success": True, "data": data}), status


def error_response(
    code: str,
    message: str,
    *,
    status: int,
    details: dict[str, Any] | None = None,
):
    return (
        jsonify(
            {
                "success": False,
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or {},
                },
            }
        ),
        status,
    )


def json_object(
    *,
    allowed: Iterable[str],
    required: Iterable[str] = (),
    require_any: bool = False,
) -> dict[str, Any]:
    if not request.is_json:
        raise UnsupportedMediaType(
            description="请求必须使用 application/json。"
        )
    payload = request.get_json(silent=False)
    if not isinstance(payload, dict):
        raise ValidationError("JSON 请求体必须是对象。")

    allowed_fields = set(allowed)
    unknown = sorted(set(payload) - allowed_fields)
    if unknown:
        raise ValidationError(
            "请求包含不支持的字段。", details={"unknown_fields": unknown}
        )

    missing = sorted(set(required) - set(payload))
    if missing:
        raise ValidationError(
            "请求缺少必填字段。", details={"missing_fields": missing}
        )
    if require_any and not payload:
        raise ValidationError("请求至少需要提供一个可更新字段。")
    return payload


def query_bool(name: str, *, default: bool = False) -> bool:
    value = request.args.get(name)
    if value is None:
        return default
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValidationError(
        f"{name} 必须是 true 或 false。", details={"field": name}
    )
