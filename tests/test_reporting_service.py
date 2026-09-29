from __future__ import annotations

from datetime import date

from flask.testing import FlaskClient
from sqlalchemy import text

from life_os.extensions import db
from life_os.services.habit_service import HabitService
from life_os.services.health_service import HealthService
from life_os.services.reporting_service import ReportingService, resolve_report_period


def test_report_periods_use_natural_boundaries_and_exclude_future_days() -> None:
    week = resolve_report_period("week", "2026-09-23", today=date(2026, 9, 23))
    month = resolve_report_period("month", "2026-09-23", today=date(2026, 9, 23))
    year = resolve_report_period("year", "2026-09-23", today=date(2026, 9, 23))

    assert (week.date_from, week.date_to, week.effective_date_to) == (
        date(2026, 9, 21),
        date(2026, 9, 27),
        date(2026, 9, 23),
    )
    assert (month.date_from, month.date_to) == (date(2026, 9, 1), date(2026, 9, 30))
    assert (year.date_from, year.date_to, year.granularity) == (
        date(2026, 1, 1),
        date(2026, 12, 31),
        "month",
    )


def test_habit_statistics_include_rate_streak_and_future_nulls(app_context) -> None:
    habit = HabitService.create("阅读")
    habit.created_at = "2026-09-22T08:00:00+08:00"
    db.session.flush()
    HabitService.set_log(habit.id, "2026-09-21", status=True)
    HabitService.set_log(habit.id, "2026-09-23", status=True)

    report = ReportingService.habit_statistics(
        "week", "2026-09-23", today=date(2026, 9, 23)
    )

    assert report["summary"] == {
        "tracked_habits": 1,
        "completed_logs": 2,
        "days_with_completion": 2,
    }
    assert [point["completed"] for point in report["series"]] == [1, 0, 1, None, None, None, None]
    row = report["habits"][0]
    assert row["eligible_days"] == 2
    assert row["completion_rate"] == 50.0
    assert row["current_streak"] == 1
    assert row["longest_streak"] == 1


def test_health_statistics_keep_missing_values_and_aggregate_recorded_values(app_context) -> None:
    HealthService.upsert(
        "2026-09-21",
        sleep_status="between_6_7_5",
        weight_kg=65.5,
        exercise_minutes=30,
        energy_level=3,
    )
    HealthService.upsert("2026-09-22", exercise_minutes=0, body_status="肩颈紧")
    HealthService.upsert(
        "2026-09-23",
        sleep_status="over_7_5",
        weight_kg=65,
        exercise_minutes=60,
        energy_level=5,
    )

    report = ReportingService.health_statistics(
        "week", "2026-09-23", today=date(2026, 9, 23)
    )

    assert report["summary"]["sleep_status"]["recorded_days"] == 2
    assert report["summary"]["sleep_status"]["counts"] == {
        "between_6_7_5": 1,
        "over_7_5": 1,
    }
    assert report["summary"]["exercise"]["total_minutes"] == 90
    assert report["summary"]["weight"]["change_kg"] == -0.5
    assert report["summary"]["energy"]["average"] == 4
    assert report["series"][1]["sleep_status"] is None
    assert report["series"][3]["recorded"] is False
    assert report["series"][3]["sleep_status"] is None


def test_reporting_endpoints_and_validation(client: FlaskClient) -> None:
    anchor = date.today().isoformat()
    habits = client.get(f"/api/habits/statistics?period=month&anchor={anchor}")
    health = client.get(f"/api/health/statistics?period=year&anchor={anchor}")

    assert habits.status_code == health.status_code == 200
    assert habits.get_json()["data"]["period"] == "month"
    assert health.get_json()["data"]["granularity"] == "month"
    assert client.get("/api/habits/statistics?period=quarter").status_code == 400


def test_reporting_queries_use_date_indexes_and_database_is_consistent(app_context) -> None:
    assert db.session.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"
    assert db.session.execute(text("PRAGMA foreign_key_check")).all() == []
    statements = {
        "journals": "SELECT date, updated_at FROM journals WHERE date BETWEEN '2026-09-01' AND '2026-09-30' ORDER BY date",
        "habit_logs": "SELECT * FROM habit_logs WHERE date BETWEEN '2026-09-01' AND '2026-09-30'",
        "daily_health": "SELECT * FROM daily_health WHERE date BETWEEN '2026-09-01' AND '2026-09-30' ORDER BY date",
    }
    for table, statement in statements.items():
        plan = " ".join(
            str(row[3])
            for row in db.session.execute(text(f"EXPLAIN QUERY PLAN {statement}"))
        )
        assert f"SEARCH {table}" in plan
        assert "INDEX" in plan
