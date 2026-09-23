from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3

import pytest
from flask import Flask
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from life_os import create_app
from life_os.database import DatabaseVersionError, SCHEMA_VERSION, checkpoint_database
from life_os.extensions import db
from life_os.models import DailyHealth, HabitLog, SchemaMeta
from life_os.services import HabitService, JournalService


EXPECTED_TABLES = {
    "calendar_days",
    "categories",
    "daily_health",
    "finance_accounts",
    "finance_transactions",
    "habit_logs",
    "habits",
    "journals",
    "schema_meta",
    "tasks",
}


def test_database_initializes_schema_and_version(app: Flask) -> None:
    with app.app_context():
        assert EXPECTED_TABLES <= set(inspect(db.engine).get_table_names())
        version = db.session.get(SchemaMeta, "schema_version")
        assert version is not None
        assert version.value == str(SCHEMA_VERSION)


def test_sqlite_pragmas_are_enabled(app: Flask) -> None:
    with app.app_context():
        foreign_keys = db.session.execute(text("PRAGMA foreign_keys")).scalar_one()
        busy_timeout = db.session.execute(text("PRAGMA busy_timeout")).scalar_one()
        journal_mode = db.session.execute(text("PRAGMA journal_mode")).scalar_one()
        assert foreign_keys == 1
        assert busy_timeout == 5000
        assert journal_mode.lower() == "wal"


def test_database_persists_across_app_restart(tmp_path: Path) -> None:
    runtime_home = tmp_path / "runtime"
    first_app = create_app(runtime_home=runtime_home, testing=True)
    with first_app.app_context():
        JournalService.upsert("2026-09-18", "persistent")
    checkpoint_database(first_app)

    second_app = create_app(runtime_home=runtime_home, testing=True)
    with second_app.app_context():
        journal = JournalService.get("2026-09-18")
        assert journal is not None
        assert journal.content == "persistent"


def test_incompatible_schema_version_stops_startup(tmp_path: Path) -> None:
    runtime_home = tmp_path / "runtime"
    first_app = create_app(runtime_home=runtime_home, testing=True)
    with first_app.app_context():
        version = db.session.get(SchemaMeta, "schema_version")
        assert version is not None
        version.value = "999"
        db.session.commit()
    checkpoint_database(first_app)

    with pytest.raises(DatabaseVersionError, match="不兼容"):
        create_app(runtime_home=runtime_home, testing=True)


def test_schema_v1_is_migrated_to_v5_without_losing_data(tmp_path: Path) -> None:
    runtime_home = tmp_path / "runtime"
    first_app = create_app(runtime_home=runtime_home, testing=True)
    with first_app.app_context():
        JournalService.upsert("2026-09-18", "keep me")
        db.session.execute(text("DROP TABLE finance_transactions"))
        db.session.execute(text("DROP TABLE finance_accounts"))
        db.session.execute(
            text("UPDATE schema_meta SET value = '1' WHERE key = 'schema_version'")
        )
        db.session.commit()
    checkpoint_database(first_app)

    migrated_app = create_app(runtime_home=runtime_home, testing=True)
    with migrated_app.app_context():
        tables = set(inspect(db.engine).get_table_names())
        assert {"finance_accounts", "finance_transactions"} <= tables
        assert db.session.get(SchemaMeta, "schema_version").value == "5"
        assert JournalService.get("2026-09-18").content == "keep me"


def test_schema_v2_migration_preserves_existing_category_values(
    tmp_path: Path,
) -> None:
    runtime_home = tmp_path / "runtime"
    first_app = create_app(runtime_home=runtime_home, testing=True)
    with first_app.app_context():
        db.session.execute(
            text(
                "INSERT INTO tasks "
                "(title, status, priority, category, sort_order, created_at, updated_at) "
                "VALUES ('旧任务', 'todo', 'normal', '工作', 0, 'now', 'now')"
            )
        )
        db.session.execute(
            text(
                "INSERT INTO habits "
                "(name, category, active, sort_order, created_at, updated_at) "
                "VALUES ('旧习惯', '健康', 1, 0, 'now', 'now')"
            )
        )
        db.session.execute(text("DROP TABLE categories"))
        db.session.execute(
            text("UPDATE schema_meta SET value = '2' WHERE key = 'schema_version'")
        )
        db.session.commit()
    checkpoint_database(first_app)

    migrated_app = create_app(runtime_home=runtime_home, testing=True)
    with migrated_app.app_context():
        rows = db.session.execute(
            text("SELECT scope, name FROM categories ORDER BY scope, name")
        ).all()
        assert rows == [("habit", "健康"), ("task", "工作")]
        assert db.session.get(SchemaMeta, "schema_version").value == "5"


def test_schema_v3_migration_adds_finance_scope_and_backfills_categories(
    tmp_path: Path,
) -> None:
    runtime_home = tmp_path / "runtime"
    first_app = create_app(runtime_home=runtime_home, testing=True)
    with first_app.app_context():
        db.session.execute(
            text(
                "INSERT INTO finance_accounts "
                "(name, kind, account_type, currency, opening_balance_minor, "
                "active, sort_order, created_at, updated_at) "
                "VALUES ('现金', 'asset', 'cash', 'CNY', 0, 1, 0, 'now', 'now')"
            )
        )
        account_id = db.session.execute(
            text("SELECT id FROM finance_accounts WHERE name = '现金'")
        ).scalar_one()
        db.session.execute(
            text(
                "INSERT INTO finance_transactions "
                "(date, transaction_type, amount_minor, category, from_account_id, "
                "created_at, updated_at) "
                "VALUES ('2026-09-21', 'expense', 100, '餐饮', :account_id, "
                "'now', 'now')"
            ),
            {"account_id": account_id},
        )
        db.session.execute(text("DROP TABLE categories"))
        db.session.execute(
            text(
                "CREATE TABLE categories ("
                "id INTEGER NOT NULL PRIMARY KEY, scope VARCHAR(20) NOT NULL, "
                "name VARCHAR(100) COLLATE NOCASE NOT NULL, sort_order INTEGER NOT NULL, "
                "created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL, "
                "CHECK (scope IN ('task', 'habit')), UNIQUE (scope, name))"
            )
        )
        db.session.execute(
            text("UPDATE schema_meta SET value = '3' WHERE key = 'schema_version'")
        )
        db.session.commit()
    checkpoint_database(first_app)

    migrated_app = create_app(runtime_home=runtime_home, testing=True)
    with migrated_app.app_context():
        rows = db.session.execute(
            text("SELECT scope, name FROM categories ORDER BY scope, name")
        ).all()
        assert rows == [("finance", "餐饮")]
        assert db.session.get(SchemaMeta, "schema_version").value == "5"
        db.session.execute(
            text(
                "INSERT INTO categories "
                "(scope, name, sort_order, created_at, updated_at) "
                "VALUES ('finance', '交通', 0, 'now', 'now')"
            )
        )
        db.session.commit()


def test_schema_v4_migration_adds_credit_billing_day(tmp_path: Path) -> None:
    runtime_home = tmp_path / "runtime"
    first_app = create_app(runtime_home=runtime_home, testing=True)
    with first_app.app_context():
        db.session.execute(text("DROP TABLE finance_transactions"))
        db.session.execute(text("DROP TABLE finance_accounts"))
        db.session.execute(
            text(
                "CREATE TABLE finance_accounts ("
                "id INTEGER NOT NULL PRIMARY KEY, name VARCHAR(200) NOT NULL, "
                "kind VARCHAR(20) NOT NULL, account_type VARCHAR(20) NOT NULL, "
                "currency VARCHAR(3) NOT NULL, opening_balance_minor INTEGER NOT NULL, "
                "active BOOLEAN NOT NULL, sort_order INTEGER NOT NULL, "
                "created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL)"
            )
        )
        db.session.execute(
            text(
                "INSERT INTO finance_accounts "
                "(name, kind, account_type, currency, opening_balance_minor, active, "
                "sort_order, created_at, updated_at) VALUES "
                "('旧信用卡', 'liability', 'credit', 'CNY', -10000, 1, 0, 'now', 'now')"
            )
        )
        db.session.execute(
            text("UPDATE schema_meta SET value = '4' WHERE key = 'schema_version'")
        )
        db.session.commit()
    checkpoint_database(first_app)

    migrated_app = create_app(runtime_home=runtime_home, testing=True)
    with migrated_app.app_context():
        row = db.session.execute(
            text(
                "SELECT name, billing_day FROM finance_accounts "
                "WHERE account_type = 'credit'"
            )
        ).one()
        assert row == ("旧信用卡", 18)
        assert db.session.get(SchemaMeta, "schema_version").value == "5"


def test_existing_unversioned_database_stops_startup(tmp_path: Path) -> None:
    runtime_home = tmp_path / "runtime"
    database_dir = runtime_home / "database"
    database_dir.mkdir(parents=True)
    connection = sqlite3.connect(database_dir / "life.db")
    connection.execute("CREATE TABLE unknown_data (id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()

    with pytest.raises(DatabaseVersionError, match="缺少 schema_meta"):
        create_app(runtime_home=runtime_home, testing=True)


def test_foreign_key_constraint_is_enforced(app_context: None) -> None:
    db.session.add(
        HabitLog(habit_id=999999, date=date(2026, 9, 18), status=True)
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_database_check_constraint_rejects_invalid_health_score(
    app_context: None,
) -> None:
    db.session.add(DailyHealth(date=date(2026, 9, 18), mood_level=6))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_unique_habit_log_constraint(app_context: None) -> None:
    habit = HabitService.create("阅读")
    HabitService.set_log(habit.id, "2026-09-18", status=True)
    db.session.add(
        HabitLog(habit_id=habit.id, date=date(2026, 9, 18), status=False)
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
