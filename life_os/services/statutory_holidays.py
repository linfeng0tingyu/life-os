from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class StatutoryHoliday:
    day_type: str
    holiday_name: str | None = None
    custom_label: str | None = None
    notice: str | None = None


NOTICE_2025 = "国务院办公厅2025年部分节假日安排（国办发明电〔2024〕12号）"
NOTICE_2026 = "国务院办公厅2026年部分节假日安排（国办发明电〔2025〕7号）"
# Source notices:
# https://www.gov.cn/zhengce/zhengceku/202411/content_6986383.htm
# https://www.gov.cn/zhengce/content/202511/content_7047090.htm


def _date_range(start: str, end: str):
    current = date.fromisoformat(start)
    last = date.fromisoformat(end)
    while current <= last:
        yield current
        current += timedelta(days=1)


def _build_schedule() -> dict[date, StatutoryHoliday]:
    schedule: dict[date, StatutoryHoliday] = {}

    def rest(start: str, end: str, name: str, notice: str) -> None:
        for target in _date_range(start, end):
            schedule[target] = StatutoryHoliday(
                day_type="rest_day",
                holiday_name=name,
                notice=notice,
            )

    def adjusted_workday(value: str, notice: str) -> None:
        schedule[date.fromisoformat(value)] = StatutoryHoliday(
            day_type="workday",
            custom_label="调休上班",
            notice=notice,
        )

    rest("2025-01-01", "2025-01-01", "元旦", NOTICE_2025)
    rest("2025-01-28", "2025-02-04", "春节", NOTICE_2025)
    rest("2025-04-04", "2025-04-06", "清明节", NOTICE_2025)
    rest("2025-05-01", "2025-05-05", "劳动节", NOTICE_2025)
    rest("2025-05-31", "2025-06-02", "端午节", NOTICE_2025)
    rest("2025-10-01", "2025-10-08", "国庆·中秋", NOTICE_2025)
    for value in (
        "2025-01-26",
        "2025-02-08",
        "2025-04-27",
        "2025-09-28",
        "2025-10-11",
    ):
        adjusted_workday(value, NOTICE_2025)

    rest("2026-01-01", "2026-01-03", "元旦", NOTICE_2026)
    rest("2026-02-15", "2026-02-23", "春节", NOTICE_2026)
    rest("2026-04-04", "2026-04-06", "清明节", NOTICE_2026)
    rest("2026-05-01", "2026-05-05", "劳动节", NOTICE_2026)
    rest("2026-06-19", "2026-06-21", "端午节", NOTICE_2026)
    rest("2026-09-25", "2026-09-27", "中秋节", NOTICE_2026)
    rest("2026-10-01", "2026-10-07", "国庆节", NOTICE_2026)
    for value in (
        "2026-01-04",
        "2026-02-14",
        "2026-02-28",
        "2026-05-09",
        "2026-09-20",
        "2026-10-10",
    ):
        adjusted_workday(value, NOTICE_2026)

    return schedule


STATUTORY_HOLIDAYS = _build_schedule()


def get_statutory_holiday(value: date) -> StatutoryHoliday | None:
    return STATUTORY_HOLIDAYS.get(value)
