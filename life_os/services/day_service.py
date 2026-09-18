from __future__ import annotations

from datetime import date

from sqlalchemy import select

from life_os.extensions import db
from life_os.models import HabitLog
from life_os.serializers import (
    calendar_day_data,
    habit_data,
    habit_log_data,
    health_data,
    journal_data,
    task_data,
)

from .calendar_service import CalendarService
from .common import parse_life_date
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
        }
