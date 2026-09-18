from __future__ import annotations

from flask import Blueprint

from life_os.api import success_response
from life_os.services.day_service import DayService


blueprint = Blueprint("day", __name__)


@blueprint.get("/api/day/<value_date>")
def get_day(value_date: str):
    return success_response(DayService.aggregate(value_date))
