from __future__ import annotations

import json
import shutil
import sqlite3
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from life_os import create_app
from life_os.database import checkpoint_database
from life_os.extensions import db
from life_os.models import (
    CalendarDay,
    Category,
    DailyHealth,
    FinanceAccount,
    FinanceTransaction,
    Habit,
    HabitLog,
    Journal,
    Task,
)
from life_os.services.data_protection_service import (
    DataProtectionError,
    DataProtectionService,
    RESTORE_CONFIRMATION,
)


def _seed_all_domains(app) -> None:
    with app.app_context():
        habit = Habit(name="阅读中文", category="成长", active=True)
        account = FinanceAccount(
            name="日常银行卡",
            kind="asset",
            account_type="bank",
            currency="CNY",
            opening_balance_minor=12345,
            active=True,
        )
        db.session.add_all(
            [
                Category(scope="habit", name="成长"),
                habit,
                account,
                CalendarDay(
                    date=datetime(2026, 9, 22).date(),
                    day_type="workday",
                    custom_label="专注日",
                    source="manual",
                ),
                Task(title="整理资料", scheduled_date=datetime(2026, 9, 22).date()),
                DailyHealth(
                    date=datetime(2026, 9, 22).date(),
                    weight_kg=65.5,
                    sleep_duration_minutes=450,
                ),
                Journal(
                    date=datetime(2026, 9, 22).date(),
                    content="# 今日记录\n\n一切顺利。",
                ),
            ]
        )
        db.session.flush()
        db.session.add_all(
            [
                HabitLog(
                    habit_id=habit.id,
                    date=datetime(2026, 9, 22).date(),
                    status=True,
                ),
                FinanceTransaction(
                    date=datetime(2026, 9, 22).date(),
                    transaction_type="income",
                    amount_minor=8888,
                    category="工资",
                    description="九月收入",
                    to_account_id=account.id,
                ),
            ]
        )
        db.session.commit()


def test_consistent_backup_and_retention_policy(app, tmp_path: Path) -> None:
    _seed_all_domains(app)
    paths = app.extensions["life_os_runtime"]
    start = datetime(2026, 9, 22, 8, 0, tzinfo=timezone(timedelta(hours=8)))

    for offset in range(3):
        DataProtectionService.create_backup(
            paths,
            2,
            kind="manual",
            now=start + timedelta(seconds=offset),
        )

    backups = DataProtectionService.list_backups(paths)
    assert len(backups) == 2
    assert backups[0].filename.startswith("life-os-20260922-080002")
    for item in backups:
        with sqlite3.connect(paths.home / item.relative_path) as connection:
            assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert connection.execute(
                "SELECT name FROM habits"
            ).fetchone() == ("阅读中文",)
    assert not list(paths.backups_dir.glob(".*.tmp-wal"))
    assert not list(paths.backups_dir.glob(".*.tmp-shm"))


def test_daily_backup_runs_only_once_per_date(tmp_path: Path) -> None:
    runtime_home = tmp_path / "runtime"
    first = create_app(runtime_home=runtime_home, testing=False)
    checkpoint_database(first)
    second = create_app(runtime_home=runtime_home, testing=False)
    checkpoint_database(second)

    backups = list((runtime_home / "backups").glob("*-auto.db"))
    assert len(backups) == 1
    assert second.extensions["life_os_startup_backup"]["status"] == "current"


def test_backup_failure_leaves_main_database_readable(
    app, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_all_domains(app)
    paths = app.extensions["life_os_runtime"]
    before = paths.database_file.read_bytes()

    def fail_copy(_source: Path, _destination: Path) -> None:
        raise sqlite3.OperationalError("simulated failure")

    monkeypatch.setattr(DataProtectionService, "_copy_database", fail_copy)
    with pytest.raises(DataProtectionError, match="主数据库未被修改"):
        DataProtectionService.create_backup(paths, 30)

    assert paths.database_file.read_bytes() == before
    with app.app_context():
        assert db.session.scalar(select(Habit.name)) == "阅读中文"


def test_export_all_writes_bom_csv_markdown_manifest_and_zip(app) -> None:
    _seed_all_domains(app)
    paths = app.extensions["life_os_runtime"]
    result = DataProtectionService.export_all(
        paths,
        app_version="test-version",
        schema_version=4,
        include_zip=True,
        now=datetime(2026, 9, 22, 9, 30, tzinfo=timezone(timedelta(hours=8))),
    )

    export_dir = paths.home / result["relative_path"]
    assert (export_dir / "habits.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    assert "阅读中文" in (export_dir / "habits.csv").read_text(encoding="utf-8-sig")
    accounts = (export_dir / "finance_accounts.csv").read_text(
        encoding="utf-8-sig"
    )
    transactions = (export_dir / "finance_transactions.csv").read_text(
        encoding="utf-8-sig"
    )
    assert "123.45" in accounts
    assert "88.88" in transactions
    assert "# 今日记录" in (export_dir / "journal" / "2026-09-22.md").read_text(
        encoding="utf-8"
    )
    manifest = json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 4
    assert manifest["row_counts"]["journal"] == 1
    zip_path = paths.home / result["zip_relative_path"]
    with zipfile.ZipFile(zip_path) as archive:
        assert any(name.endswith("/health.csv") for name in archive.namelist())
        assert any(name.endswith("/journal/2026-09-22.md") for name in archive.namelist())


def test_scheduled_restore_replaces_database_and_keeps_safety_copy(app) -> None:
    paths = app.extensions["life_os_runtime"]
    with app.app_context():
        db.session.add(Habit(name="备份时名称"))
        db.session.commit()
    backup = DataProtectionService.create_backup(paths, 30).backup
    with app.app_context():
        habit = db.session.scalar(select(Habit))
        assert habit is not None
        habit.name = "恢复前名称"
        db.session.commit()

    DataProtectionService.schedule_restore(
        paths, backup.filename, RESTORE_CONFIRMATION
    )
    checkpoint_database(app)
    result = DataProtectionService.process_pending_restore(paths)

    assert result is not None
    assert result["status"] == "restored"
    assert result["safety_copy"]
    assert (paths.home / result["safety_copy"] / "life.db").is_file()
    restored = create_app(runtime_home=paths.home, testing=True)
    with restored.app_context():
        assert db.session.scalar(select(Habit.name)) == "备份时名称"


def test_offline_restore_can_replace_a_corrupted_main_database(app) -> None:
    paths = app.extensions["life_os_runtime"]
    with app.app_context():
        db.session.add(Habit(name="可恢复记录"))
        db.session.commit()
    backup = DataProtectionService.create_backup(paths, 30).backup
    checkpoint_database(app)
    paths.database_file.write_bytes(b"not a sqlite database")

    result = DataProtectionService.restore_immediately(paths, backup.filename)

    assert result["status"] == "restored"
    recovered = create_app(runtime_home=paths.home, testing=True)
    with recovered.app_context():
        assert db.session.scalar(select(Habit.name)) == "可恢复记录"


def test_closed_runtime_can_move_to_a_different_absolute_path(tmp_path: Path) -> None:
    original_home = tmp_path / "old-place" / "life-data"
    original = create_app(runtime_home=original_home, testing=True)
    with original.app_context():
        db.session.add(Habit(name="随目录迁移"))
        db.session.commit()
    checkpoint_database(original)

    moved_home = tmp_path / "new-place" / "portable-life-data"
    shutil.copytree(original_home, moved_home)
    migrated = create_app(runtime_home=moved_home, testing=True)
    with migrated.app_context():
        assert db.session.scalar(select(Habit.name)) == "随目录迁移"
    assert str(original_home) not in moved_home.joinpath("config", "settings.json").read_text(
        encoding="utf-8"
    )
