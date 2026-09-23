from __future__ import annotations

import re

from flask import Blueprint

from life_os.api import json_object, success_response
from life_os.serializers import calendar_day_data
from life_os.services.calendar_service import CalendarService
from life_os.services.common import ValidationError
from life_os.services.day_service import DayService


blueprint = Blueprint("calendar", __name__)
MONTH_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")
CALENDAR_FIELDS = {"day_type", "holiday_name", "custom_label", "note", "source"}


@blueprint.get("/api/calendar/month/<year_month>")
def get_month(year_month: str):
    match = MONTH_PATTERN.fullmatch(year_month)
    if match is None:
        raise ValidationError("month 必须使用 YYYY-MM 格式。")
    year, month = (int(part) for part in match.groups())
    days = DayService.month_overview(year, month)
    return success_response(
        {
            "month": year_month,
            "days": [
                {
                    **item["calendar_day"],
                    "has_data": item["has_data"],
                    "habit_summary": item["habit_summary"],
                }
                for item in days
            ],
        }
    )


@blueprint.put("/api/calendar/days/<value_date>")
def put_day(value_date: str):
    payload = json_object(allowed=CALENDAR_FIELDS, required={"day_type"})
    record = CalendarService.set_day(value_date, **payload)
    return success_response(calendar_day_data(record))


@blueprint.delete("/api/calendar/days/<value_date>")
def delete_day(value_date: str):
    record = CalendarService.clear_day(value_date)
    return success_response(
        {
            "date": record.date.isoformat(),
            "archived": True,
            "calendar_day": calendar_day_data(CalendarService.resolve(record.date)),
        }
    )
