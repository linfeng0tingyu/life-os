from __future__ import annotations

import calendar
from datetime import date

from sqlalchemy import or_, select

from life_os.extensions import db
from life_os.models import (
    CalendarDay,
    DailyHealth,
    FinanceTransaction,
    HabitLog,
    Journal,
    Task,
)
from life_os.serializers import (
    calendar_day_data,
    finance_day_data,
    habit_data,
    habit_log_data,
    health_data,
    journal_data,
    task_data,
)

from .calendar_service import CalendarService
from .common import parse_life_date
from .finance_service import FinanceService
from .habit_service import HabitService
from .health_service import HealthService
from .journal_service import JournalService
from .task_service import TaskService


class DayService:
    @staticmethod
    def aggregate(value: date | str) -> dict:
        target = parse_life_date(value)
        habits = HabitService.list_habits()
        habit_ids = [habit.id for habit in habits]
        logs = {}
        if habit_ids:
            logs = {
                log.habit_id: log
                for log in db.session.scalars(
                    select(HabitLog).where(
                        HabitLog.date == target,
                        HabitLog.habit_id.in_(habit_ids),
                    )
                )
            }

        tasks = TaskService.list_tasks(value_date=target)
        scheduled = [task_data(task) for task in tasks if task.scheduled_date == target]
        due = [task_data(task) for task in tasks if task.due_date == target]
        overdue = [
            task_data(task)
            for task in tasks
            if task.due_date is not None
            and task.due_date < target
            and task.status not in {"done", "cancelled"}
        ]
        health = HealthService.get(target)
        journal = JournalService.get(target)
        finance = FinanceService.day(target)

        return {
            "date": target.isoformat(),
            "calendar_day": calendar_day_data(CalendarService.resolve(target)),
            "habits": [
                {
                    "habit": habit_data(habit),
                    "log": (
                        habit_log_data(logs[habit.id])
                        if habit.id in logs
                        else {
                            "id": None,
                            "habit_id": habit.id,
                            "date": target.isoformat(),
                            "status": False,
                            "value": None,
                            "value_unit": None,
                            "note": None,
                            "created_at": None,
                            "updated_at": None,
                        }
                    ),
                }
                for habit in habits
            ],
            "tasks": {
                "scheduled": scheduled,
                "due": due,
                "overdue": overdue,
            },
            "health": health_data(health) if health else None,
            "journal": journal_data(journal) if journal else None,
            "finance": finance_day_data(finance),
        }

    @staticmethod
    def month_overview(year: int, month: int) -> list[dict]:
        days = CalendarService.list_month(year, month)
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        active_habits = HabitService.list_habits()
        active_habit_ids = {habit.id for habit in active_habits}

        habit_logs = list(
            db.session.scalars(
                select(HabitLog).where(HabitLog.date.between(first_day, last_day))
            )
        )
        data_dates = {log.date for log in habit_logs}
        completed_by_date: dict[date, int] = {}
        for log in habit_logs:
            if log.habit_id in active_habit_ids and log.status:
                completed_by_date[log.date] = completed_by_date.get(log.date, 0) + 1

        data_dates.update(
            db.session.scalars(
                select(CalendarDay.date).where(
                    CalendarDay.date.between(first_day, last_day),
                    CalendarDay.archived_at.is_(None),
                )
            )
        )
        tasks = db.session.scalars(
            select(Task).where(
                Task.archived_at.is_(None),
                or_(
                    Task.scheduled_date.between(first_day, last_day),
                    Task.due_date.between(first_day, last_day),
                ),
            )
        )
        for task in tasks:
            if task.scheduled_date and first_day <= task.scheduled_date <= last_day:
                data_dates.add(task.scheduled_date)
            if task.due_date and first_day <= task.due_date <= last_day:
                data_dates.add(task.due_date)
        for model in (DailyHealth, Journal, FinanceTransaction):
            statement = select(model.date).where(model.date.between(first_day, last_day))
            if model is FinanceTransaction:
                statement = statement.where(model.archived_at.is_(None))
            data_dates.update(db.session.scalars(statement))

        return [
            {
                "calendar_day": calendar_day_data(day),
                "has_data": day.date in data_dates,
                "habit_summary": {
                    "completed": completed_by_date.get(day.date, 0),
                    "total": len(active_habits),
                },
            }
            for day in days
        ]
