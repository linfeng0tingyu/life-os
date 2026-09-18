from __future__ import annotations

from typing import Any

from .models import CalendarDay, DailyHealth, Habit, HabitLog, Journal, Task
from .services.calendar_service import ResolvedCalendarDay


def calendar_day_data(day: ResolvedCalendarDay | CalendarDay) -> dict[str, Any]:
    explicit = isinstance(day, CalendarDay) or day.explicit
    return {
        "date": day.date.isoformat(),
        "day_type": day.day_type,
        "holiday_name": day.holiday_name,
        "custom_label": day.custom_label,
        "note": day.note,
        "source": day.source,
        "explicit": explicit,
    }


def habit_data(habit: Habit) -> dict[str, Any]:
    return {
        "id": habit.id,
        "name": habit.name,
        "description": habit.description,
        "icon": habit.icon,
        "category": habit.category,
        "active": habit.active,
        "sort_order": habit.sort_order,
        "created_at": habit.created_at,
        "updated_at": habit.updated_at,
    }


def habit_log_data(log: HabitLog) -> dict[str, Any]:
    return {
        "id": log.id,
        "habit_id": log.habit_id,
        "date": log.date.isoformat(),
        "status": log.status,
        "value": log.value,
        "value_unit": log.value_unit,
        "note": log.note,
        "created_at": log.created_at,
        "updated_at": log.updated_at,
    }


def task_data(task: Task, *, target_date=None) -> dict[str, Any]:
    data = {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "category": task.category,
        "scheduled_date": (
            task.scheduled_date.isoformat() if task.scheduled_date else None
        ),
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "completed_at": task.completed_at,
        "sort_order": task.sort_order,
        "parent_id": task.parent_id,
        "archived_at": task.archived_at,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }
    if target_date is not None:
        data["date_match"] = {
            "scheduled": task.scheduled_date == target_date,
            "due": task.due_date == target_date,
            "overdue": (
                task.due_date is not None
                and task.due_date < target_date
                and task.status not in {"done", "cancelled"}
            ),
        }
    return data


def health_data(record: DailyHealth) -> dict[str, Any]:
    return {
        "id": record.id,
        "date": record.date.isoformat(),
        "weight_kg": record.weight_kg,
        "sleep_start": record.sleep_start,
        "sleep_end": record.sleep_end,
        "sleep_duration_minutes": record.sleep_duration_minutes,
        "sleep_duration_manual": record.sleep_duration_manual,
        "sleep_quality": record.sleep_quality,
        "energy_level": record.energy_level,
        "mood_level": record.mood_level,
        "body_status": record.body_status,
        "exercise_minutes": record.exercise_minutes,
        "note": record.note,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def journal_data(journal: Journal) -> dict[str, Any]:
    return {
        "id": journal.id,
        "date": journal.date.isoformat(),
        "content": journal.content,
        "created_at": journal.created_at,
        "updated_at": journal.updated_at,
    }
