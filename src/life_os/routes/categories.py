from __future__ import annotations

from flask import Blueprint, request

from life_os.api import json_object, success_response
from life_os.serializers import category_data
from life_os.services.category_service import CategoryService
from life_os.services.common import ValidationError


blueprint = Blueprint("categories", __name__)


@blueprint.get("/api/categories")
def get_categories():
    scope = request.args.get("scope")
    if scope is None:
        raise ValidationError("scope 为必填查询参数。")
    categories = CategoryService.list_categories(scope)
    return success_response([category_data(category) for category in categories])


@blueprint.post("/api/categories")
def post_category():
    payload = json_object(
        allowed={"scope", "name", "sort_order"},
        required={"scope", "name"},
    )
    category = CategoryService.create(**payload)
    return success_response(category_data(category), status=201)
