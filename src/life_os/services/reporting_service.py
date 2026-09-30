from __future__ import annotations

import calendar
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

from sqlalchemy import select

from life_os.extensions import db
from life_os.models import DailyHealth, Habit, HabitLog

from .common import ValidationError, choice, parse_life_date


REPORT_PERIODS = {"week", "month", "year"}


@dataclass(frozen=True, slots=True)
class ReportPeriod:
    name: str
    anchor: date
    date_from: date
    date_to: date
    effective_date_to: date | None
    granularity: str

    def data(self) -> dict[str, object]:
        return {
            "period": self.name,
            "anchor": self.anchor.isoformat(),
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
            "effective_date_to": (
                self.effective_date_to.isoformat()
                if self.effective_date_to is not None
                else None
            ),
            "granularity": self.granularity,
        }


def resolve_report_period(
    period: object,
    anchor: date | str | None,
    *,
    today: date | None = None,
) -> ReportPeriod:
    normalized_period = choice(period, "period", REPORT_PERIODS)
    current = today or date.today()
    target = parse_life_date(anchor, "anchor") if anchor is not None else current
    if normalized_period == "week":
        date_from = target - timedelta(days=target.weekday())
        date_to = date_from + timedelta(days=6)
        granularity = "day"
    elif normalized_period == "month":
        date_from = target.replace(day=1)
        date_to = target.replace(day=calendar.monthrange(target.year, target.month)[1])
        granularity = "day"
    else:
        date_from = date(target.year, 1, 1)
        date_to = date(target.year, 12, 31)
        granularity = "month"
    effective_date_to = min(date_to, current) if date_from <= current else None
    return ReportPeriod(
        normalized_period,
        target,
        date_from,
        date_to,
        effective_date_to,
        granularity,
    )


class ReportingService:
    @staticmethod
    def habit_statistics(
        period: object,
        anchor: date | str | None = None,
        *,
        today: date | None = None,
    ) -> dict[str, object]:
        bounds = resolve_report_period(period, anchor, today=today)
        habits = list(db.session.scalars(select(Habit).order_by(Habit.sort_order, Habit.id)))
        logs: list[HabitLog] = []
        if bounds.effective_date_to is not None:
            logs = list(
                db.session.scalars(
                    select(HabitLog).where(
                        HabitLog.date.between(
                            bounds.date_from, bounds.effective_date_to
                        )
                    )
                )
            )
        completed_by_habit: dict[int, set[date]] = defaultdict(set)
        completed_by_date: dict[date, int] = defaultdict(int)
        for log in logs:
            if not log.status:
                continue
            completed_by_habit[log.habit_id].add(log.date)
            completed_by_date[log.date] += 1

        relevant = [
            habit
            for habit in habits
            if habit.active or habit.id in completed_by_habit
        ]
        habit_rows = [
            ReportingService._habit_row(habit, completed_by_habit[habit.id], bounds)
            for habit in relevant
        ]
        result = bounds.data()
        result.update(
            {
                "summary": {
                    "tracked_habits": len(relevant),
                    "completed_logs": sum(completed_by_date.values()),
                    "days_with_completion": len(completed_by_date),
                },
                "series": ReportingService._habit_series(
                    bounds, completed_by_date
                ),
                "habits": habit_rows,
                "completion_rate_note": (
                    "启用习惯按创建后已过自然日计算日历坚持率；"
                    "停用习惯因缺少历史停用日期，仅展示实际完成记录。"
                ),
            }
        )
        return result

    @staticmethod
    def health_statistics(
        period: object,
        anchor: date | str | None = None,
        *,
        today: date | None = None,
    ) -> dict[str, object]:
        bounds = resolve_report_period(period, anchor, today=today)
        records: list[DailyHealth] = []
        if bounds.effective_date_to is not None:
            records = list(
                db.session.scalars(
                    select(DailyHealth)
                    .where(
                        DailyHealth.date.between(
                            bounds.date_from, bounds.effective_date_to
                        )
                    )
                    .order_by(DailyHealth.date)
                )
            )
        result = bounds.data()
        result.update(
            {
                "summary": ReportingService._health_summary(records),
                "series": ReportingService._health_series(bounds, records),
            }
        )
        return result

    @staticmethod
    def _habit_row(
        habit: Habit,
        completed_dates: set[date],
        bounds: ReportPeriod,
    ) -> dict[str, object]:
        eligible_days = 0
        completion_rate: float | None = None
        if habit.active and bounds.effective_date_to is not None:
            created_date = ReportingService._created_date(habit.created_at)
            eligible_from = max(bounds.date_from, created_date)
            if eligible_from <= bounds.effective_date_to:
                eligible_days = (bounds.effective_date_to - eligible_from).days + 1
                eligible_completed = sum(
                    eligible_from <= day <= bounds.effective_date_to
                    for day in completed_dates
                )
                completion_rate = round(
                    eligible_completed * 100 / eligible_days, 1
                )
        return {
            "id": habit.id,
            "name": habit.name,
            "category": habit.category,
            "active": habit.active,
            "completed_days": len(completed_dates),
            "eligible_days": eligible_days if habit.active else None,
            "completion_rate": completion_rate,
            "current_streak": ReportingService._current_streak(
                completed_dates, bounds.effective_date_to
            ),
            "longest_streak": ReportingService._longest_streak(completed_dates),
        }

    @staticmethod
    def _habit_series(
        bounds: ReportPeriod,
        completed_by_date: dict[date, int],
    ) -> list[dict[str, object]]:
        if bounds.granularity == "day":
            return [
                {
                    "date": day.isoformat(),
                    "completed": (
                        completed_by_date.get(day, 0)
                        if bounds.effective_date_to is not None
                        and day <= bounds.effective_date_to
                        else None
                    ),
                }
                for day in ReportingService._days(bounds.date_from, bounds.date_to)
            ]
        monthly_completed: dict[int, int] = defaultdict(int)
        monthly_days: dict[int, set[date]] = defaultdict(set)
        for day, count in completed_by_date.items():
            monthly_completed[day.month] += count
            monthly_days[day.month].add(day)
        return [
            {
                "month": f"{bounds.date_from.year}-{month:02d}",
                "completed": (
                    monthly_completed.get(month, 0)
                    if bounds.effective_date_to is not None
                    and date(bounds.date_from.year, month, 1)
                    <= bounds.effective_date_to
                    else None
                ),
                "days_with_completion": len(monthly_days.get(month, set())),
            }
            for month in range(1, 13)
        ]

    @staticmethod
    def _health_summary(records: list[DailyHealth]) -> dict[str, object]:
        sleep_status = Counter(
            record.sleep_status for record in records if record.sleep_status
        )
        exercise_types = Counter(
            item.name for record in records for item in record.exercise_types
        )
        weights = [record for record in records if record.weight_kg is not None]
        exercise = [
            record.exercise_minutes
            for record in records
            if record.exercise_minutes is not None
        ]
        energy = [
            record.energy_level
            for record in records
            if record.energy_level is not None
        ]
        mood = [
            record.mood_level
            for record in records
            if record.mood_level is not None
        ]
        body_records = [record for record in records if record.body_status]
        first_weight = weights[0].weight_kg if weights else None
        last_weight = weights[-1].weight_kg if weights else None
        return {
            "recorded_days": len(records),
            "sleep_status": {
                "recorded_days": sum(sleep_status.values()),
                "counts": dict(sleep_status),
            },
            "weight": {
                "recorded_days": len(weights),
                "first_kg": first_weight,
                "last_kg": last_weight,
                "change_kg": (
                    round(last_weight - first_weight, 2)
                    if first_weight is not None and last_weight is not None
                    else None
                ),
                "minimum_kg": (
                    min(record.weight_kg for record in weights) if weights else None
                ),
                "maximum_kg": (
                    max(record.weight_kg for record in weights) if weights else None
                ),
            },
            "exercise": {
                "recorded_days": len(exercise),
                "total_minutes": sum(exercise),
                "average_minutes": ReportingService._average(exercise),
                "active_days": sum(value > 0 for value in exercise),
            },
            "exercise_types": {
                "recorded_days": sum(bool(record.exercise_types) for record in records),
                "counts": dict(exercise_types),
            },
            "energy": {
                "recorded_days": len(energy),
                "average": ReportingService._average(energy),
            },
            "mood": {
                "recorded_days": len(mood),
                "average": ReportingService._average(mood),
            },
            "body_status": {
                "recorded_days": len(body_records),
                "recent": [
                    {"date": record.date.isoformat(), "text": record.body_status}
                    for record in reversed(body_records[-5:])
                ],
            },
        }

    @staticmethod
    def _health_series(
        bounds: ReportPeriod,
        records: list[DailyHealth],
    ) -> list[dict[str, object]]:
        if bounds.granularity == "day":
            by_date = {record.date: record for record in records}
            return [
                ReportingService._daily_health_point(day, by_date.get(day))
                for day in ReportingService._days(bounds.date_from, bounds.date_to)
            ]
        by_month: dict[int, list[DailyHealth]] = defaultdict(list)
        for record in records:
            by_month[record.date.month].append(record)
        points = []
        for month in range(1, 13):
            point = ReportingService._monthly_health_point(
                bounds.date_from.year, month, by_month.get(month, [])
            )
            if (
                bounds.effective_date_to is None
                or date(bounds.date_from.year, month, 1) > bounds.effective_date_to
            ):
                point.update(
                    {
                        "recorded_days": 0,
                        "sleep_status_counts": {},
                        "exercise_type_counts": {},
                        "average_weight_kg": None,
                        "last_weight_kg": None,
                        "exercise_minutes": None,
                        "average_energy": None,
                        "average_mood": None,
                        "body_status_days": 0,
                    }
                )
            points.append(point)
        return points

    @staticmethod
    def _daily_health_point(
        day: date, record: DailyHealth | None
    ) -> dict[str, object]:
        return {
            "date": day.isoformat(),
            "recorded": record is not None,
            "sleep_status": record.sleep_status if record else None,
            "weight_kg": record.weight_kg if record else None,
            "exercise_minutes": record.exercise_minutes if record else None,
            "exercise_types": (
                [item.name for item in record.exercise_types] if record else []
            ),
            "energy_level": record.energy_level if record else None,
            "mood_level": record.mood_level if record else None,
            "body_status": record.body_status if record else None,
        }

    @staticmethod
    def _monthly_health_point(
        year: int,
        month: int,
        records: list[DailyHealth],
    ) -> dict[str, object]:
        sleep_status = Counter(
            record.sleep_status for record in records if record.sleep_status
        )
        weights = [
            record.weight_kg for record in records if record.weight_kg is not None
        ]
        exercise = [
            record.exercise_minutes
            for record in records
            if record.exercise_minutes is not None
        ]
        energy = [
            record.energy_level
            for record in records
            if record.energy_level is not None
        ]
        mood = [
            record.mood_level
            for record in records
            if record.mood_level is not None
        ]
        exercise_types = Counter(
            item.name for record in records for item in record.exercise_types
        )
        return {
            "month": f"{year}-{month:02d}",
            "recorded_days": len(records),
            "sleep_status_counts": dict(sleep_status),
            "exercise_type_counts": dict(exercise_types),
            "average_weight_kg": ReportingService._average(weights),
            "last_weight_kg": weights[-1] if weights else None,
            "exercise_minutes": sum(exercise),
            "average_energy": ReportingService._average(energy),
            "average_mood": ReportingService._average(mood),
            "body_status_days": sum(bool(record.body_status) for record in records),
        }

    @staticmethod
    def _average(values: Iterable[int | float]) -> float | None:
        items = list(values)
        return round(sum(items) / len(items), 1) if items else None

    @staticmethod
    def _days(start: date, end: date) -> Iterable[date]:
        current = start
        while current <= end:
            yield current
            current += timedelta(days=1)

    @staticmethod
    def _created_date(value: str) -> date:
        try:
            return datetime.fromisoformat(value).date()
        except (TypeError, ValueError) as exc:
            raise ValidationError("习惯创建时间无效，无法生成统计。") from exc

    @staticmethod
    def _current_streak(values: set[date], end: date | None) -> int:
        if end is None:
            return 0
        streak = 0
        current = end
        while current in values:
            streak += 1
            current -= timedelta(days=1)
        return streak

    @staticmethod
    def _longest_streak(values: set[date]) -> int:
        longest = 0
        current = 0
        previous: date | None = None
        for day in sorted(values):
            current = current + 1 if previous == day - timedelta(days=1) else 1
            longest = max(longest, current)
            previous = day
        return longest
