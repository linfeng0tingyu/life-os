from __future__ import annotations

import csv
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable, Sequence

from life_os.database import MINIMUM_MIGRATABLE_VERSION, SCHEMA_VERSION
from life_os.runtime import RuntimePaths

from .common import ConflictError, NotFoundError, ValidationError
from .journal_asset_service import JournalAssetService


BACKUP_PATTERN = re.compile(
    r"^life-os-(?:\d{8}-auto|\d{8}-\d{6}-\d{6}-manual)\.db$"
)
RESTORE_CONFIRMATION = "恢复此备份"
_operation_lock = threading.RLock()


class DataProtectionError(RuntimeError):
    """Raised when backup, export, or offline restore cannot finish safely."""


@dataclass(frozen=True, slots=True)
class BackupRecord:
    filename: str
    relative_path: str
    created_at: str
    size_bytes: int
    kind: str


@dataclass(frozen=True, slots=True)
class BackupResult:
    backup: BackupRecord
    created: bool
    removed_count: int


@dataclass(frozen=True, slots=True)
class ExportSpec:
    filename: str
    query: str
    headers: tuple[str, ...]
    transform: Callable[[Sequence[object]], Sequence[object]] | None = None


EXPORT_SPECS = (
    ExportSpec(
        "calendar_days.csv",
        "SELECT id, date, day_type, holiday_name, custom_label, note, source, "
        "archived_at, created_at, updated_at FROM calendar_days ORDER BY date, id",
        (
            "id", "date", "day_type", "holiday_name", "custom_label", "note",
            "source", "archived_at", "created_at", "updated_at",
        ),
    ),
    ExportSpec(
        "categories.csv",
        "SELECT id, scope, name, sort_order, created_at, updated_at "
        "FROM categories ORDER BY scope, sort_order, id",
        ("id", "scope", "name", "sort_order", "created_at", "updated_at"),
    ),
    ExportSpec(
        "habits.csv",
        "SELECT id, name, description, icon, category, active, sort_order, "
        "created_at, updated_at FROM habits ORDER BY sort_order, id",
        (
            "id", "name", "description", "icon", "category", "active",
            "sort_order", "created_at", "updated_at",
        ),
    ),
    ExportSpec(
        "habit_logs.csv",
        "SELECT id, habit_id, date, status, value, value_unit, note, created_at, "
        "updated_at FROM habit_logs ORDER BY date, habit_id, id",
        (
            "id", "habit_id", "date", "status", "value", "value_unit", "note",
            "created_at", "updated_at",
        ),
    ),
    ExportSpec(
        "tasks.csv",
        "SELECT id, title, description, status, priority, category, scheduled_date, "
        "due_date, completed_at, sort_order, parent_id, archived_at, created_at, "
        "updated_at FROM tasks ORDER BY id",
        (
            "id", "title", "description", "status", "priority", "category",
            "scheduled_date", "due_date", "completed_at", "sort_order",
            "parent_id", "archived_at", "created_at", "updated_at",
        ),
    ),
    ExportSpec(
        "health.csv",
        "SELECT id, date, weight_kg, sleep_start, sleep_end, "
        "sleep_duration_minutes, sleep_duration_manual, sleep_quality, "
        "energy_level, mood_level, body_status, exercise_minutes, note, "
        "created_at, updated_at FROM daily_health ORDER BY date, id",
        (
            "id", "date", "weight_kg", "sleep_start", "sleep_end",
            "sleep_duration_minutes", "sleep_duration_manual", "sleep_quality",
            "energy_level", "mood_level", "body_status", "exercise_minutes",
            "note", "created_at", "updated_at",
        ),
    ),
    ExportSpec(
        "finance_accounts.csv",
        "SELECT id, name, kind, account_type, currency, opening_balance_minor, "
        "active, sort_order, created_at, updated_at FROM finance_accounts "
        "ORDER BY sort_order, id",
        (
            "id", "name", "kind", "account_type", "currency",
            "opening_balance", "active", "sort_order", "created_at", "updated_at",
        ),
        lambda row: (*row[:5], _minor_to_amount(row[5]), *row[6:]),
    ),
    ExportSpec(
        "finance_transactions.csv",
        "SELECT id, date, transaction_type, amount_minor, 'CNY', category, "
        "description, note, from_account_id, to_account_id, archived_at, "
        "created_at, updated_at FROM finance_transactions ORDER BY date, id",
        (
            "id", "date", "transaction_type", "amount", "currency", "category",
            "description", "note", "from_account_id", "to_account_id",
            "archived_at", "created_at", "updated_at",
        ),
        lambda row: (*row[:3], _minor_to_amount(row[3]), *row[4:]),
    ),
)


class DataProtectionService:
    @staticmethod
    def create_backup(
        paths: RuntimePaths,
        retention_count: int,
        *,
        kind: str = "manual",
        now: datetime | None = None,
    ) -> BackupResult:
        if kind not in {"auto", "manual"}:
            raise ValidationError("备份类型无效。")
        if not 1 <= retention_count <= 3650:
            raise ValidationError("备份保留数量必须在 1 到 3650 之间。")
        moment = now or datetime.now().astimezone()
        if moment.tzinfo is None:
            moment = moment.astimezone()
        if kind == "auto":
            filename = f"life-os-{moment:%Y%m%d}-auto.db"
        else:
            filename = f"life-os-{moment:%Y%m%d-%H%M%S-%f}-manual.db"
        destination = paths.backups_dir / filename

        with _operation_lock:
            if kind == "auto" and destination.is_file():
                removed = DataProtectionService._prune(paths, retention_count)
                return BackupResult(
                    DataProtectionService._record(paths, destination),
                    False,
                    removed,
                )
            try:
                DataProtectionService._atomic_backup(
                    paths.database_file, destination
                )
                os.utime(
                    destination,
                    (moment.timestamp(), moment.timestamp()),
                )
                removed = DataProtectionService._prune(paths, retention_count)
            except (OSError, sqlite3.Error) as exc:
                raise DataProtectionError(
                    "数据库备份失败，主数据库未被修改。"
                ) from exc
        return BackupResult(
            DataProtectionService._record(paths, destination), True, removed
        )

    @staticmethod
    def list_backups(paths: RuntimePaths) -> list[BackupRecord]:
        records = [
            DataProtectionService._record(paths, path)
            for path in paths.backups_dir.iterdir()
            if path.is_file() and BACKUP_PATTERN.fullmatch(path.name)
        ]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    @staticmethod
    def export_all(
        paths: RuntimePaths,
        *,
        app_version: str,
        schema_version: int,
        include_zip: bool = True,
        now: datetime | None = None,
    ) -> dict[str, object]:
        if not isinstance(include_zip, bool):
            raise ValidationError("include_zip 必须是布尔值。")
        moment = now or datetime.now().astimezone()
        if moment.tzinfo is None:
            moment = moment.astimezone()
        name = f"export-{moment:%Y%m%d-%H%M%S-%f}"
        incomplete = paths.exports_dir / f".{name}.incomplete"
        destination = paths.exports_dir / name
        snapshot = paths.temp_dir / f".{name}.db"
        zip_path = paths.exports_dir / f"{name}.zip"
        row_counts: dict[str, int] = {}

        with _operation_lock:
            try:
                incomplete.mkdir(parents=False, exist_ok=False)
                DataProtectionService._atomic_backup(
                    paths.database_file, snapshot
                )
                with closing(sqlite3.connect(snapshot)) as connection:
                    for spec in EXPORT_SPECS:
                        rows = connection.execute(spec.query).fetchall()
                        DataProtectionService._write_csv(
                            incomplete / spec.filename,
                            spec.headers,
                            rows,
                            transform=spec.transform,
                        )
                        row_counts[spec.filename] = len(rows)
                    journal_count = DataProtectionService._export_journals(
                        paths, connection, incomplete / "journal"
                    )
                    row_counts["journal"] = journal_count

                manifest = {
                    "application": "Life OS",
                    "app_version": app_version,
                    "schema_version": schema_version,
                    "exported_at": moment.isoformat(timespec="seconds"),
                    "encoding": "CSV UTF-8 with BOM; Markdown UTF-8",
                    "finance_amount_unit": "CNY yuan with two decimals",
                    "row_counts": row_counts,
                }
                DataProtectionService._write_json(
                    incomplete / "manifest.json", manifest
                )
                os.replace(incomplete, destination)
                if include_zip:
                    DataProtectionService._write_zip(destination, zip_path)
            except Exception as exc:
                if incomplete.exists():
                    shutil.rmtree(incomplete, ignore_errors=True)
                if destination.exists():
                    shutil.rmtree(destination, ignore_errors=True)
                zip_path.unlink(missing_ok=True)
                raise DataProtectionError(
                    "全量导出失败，未完成的导出已清理。"
                ) from exc
            finally:
                snapshot.unlink(missing_ok=True)
                DataProtectionService._remove_sqlite_sidecars(snapshot)

        files = sum(1 for path in destination.rglob("*") if path.is_file())
        result: dict[str, object] = {
            "created_at": moment.isoformat(timespec="seconds"),
            "relative_path": destination.relative_to(paths.home).as_posix(),
            "file_count": files,
            "row_counts": row_counts,
            "zip_relative_path": None,
        }
        if include_zip:
            result["zip_relative_path"] = zip_path.relative_to(paths.home).as_posix()
        return result

    @staticmethod
    def schedule_restore(
        paths: RuntimePaths,
        filename: str,
        confirmation: str,
    ) -> dict[str, object]:
        if confirmation != RESTORE_CONFIRMATION:
            raise ValidationError(f"confirmation 必须填写“{RESTORE_CONFIRMATION}”。")
        backup = DataProtectionService._resolve_backup(paths, filename)
        if paths.pending_restore_file.exists():
            raise ConflictError("已经有一个待执行的恢复请求。")
        try:
            schema_version = DataProtectionService._validate_database(backup)
            requested_at = datetime.now().astimezone().isoformat(timespec="seconds")
            DataProtectionService._write_json(
                paths.pending_restore_file,
                {"backup_file": backup.name, "requested_at": requested_at},
            )
        except (OSError, sqlite3.Error) as exc:
            raise DataProtectionError("备份校验失败，未安排恢复。") from exc
        return {
            "status": "pending_restart",
            "backup_file": backup.name,
            "schema_version": schema_version,
            "requested_at": requested_at,
        }

    @staticmethod
    def restore_status(paths: RuntimePaths) -> dict[str, object]:
        return {
            "pending": DataProtectionService._read_json(
                paths.pending_restore_file
            ),
            "last_result": DataProtectionService._read_json(
                paths.restore_result_file
            ),
        }

    @staticmethod
    def cancel_pending_restore(paths: RuntimePaths) -> bool:
        existed = paths.pending_restore_file.is_file()
        paths.pending_restore_file.unlink(missing_ok=True)
        return existed

    @staticmethod
    def restore_immediately(
        paths: RuntimePaths, filename: str
    ) -> dict[str, object]:
        backup = DataProtectionService._resolve_backup(paths, filename)
        try:
            DataProtectionService._validate_database(backup)
            safety_path = DataProtectionService._restore_database(paths, backup)
            result: dict[str, object] = {
                "status": "restored",
                "backup_file": filename,
                "requested_at": datetime.now().astimezone().isoformat(
                    timespec="seconds"
                ),
                "completed_at": datetime.now().astimezone().isoformat(
                    timespec="seconds"
                ),
                "safety_copy": safety_path,
            }
            DataProtectionService._write_json(
                paths.restore_result_file, result
            )
            paths.pending_restore_file.unlink(missing_ok=True)
            return result
        except (
            OSError,
            sqlite3.Error,
            DataProtectionError,
            ValidationError,
            NotFoundError,
        ) as exc:
            raise DataProtectionError(
                f"离线恢复失败：{exc}"
            ) from exc

    @staticmethod
    def process_pending_restore(paths: RuntimePaths) -> dict[str, object] | None:
        pending = DataProtectionService._read_json(paths.pending_restore_file)
        if pending is None:
            return None
        requested_at = pending.get("requested_at")
        filename = pending.get("backup_file")
        result: dict[str, object]
        try:
            if not isinstance(filename, str):
                raise ValidationError("待恢复记录缺少备份文件名。")
            backup = DataProtectionService._resolve_backup(paths, filename)
            DataProtectionService._validate_database(backup)
            safety_path = DataProtectionService._restore_database(paths, backup)
            result = {
                "status": "restored",
                "backup_file": filename,
                "requested_at": requested_at,
                "completed_at": datetime.now().astimezone().isoformat(
                    timespec="seconds"
                ),
                "safety_copy": safety_path,
            }
        except Exception as exc:
            result = {
                "status": "failed",
                "backup_file": filename,
                "requested_at": requested_at,
                "completed_at": datetime.now().astimezone().isoformat(
                    timespec="seconds"
                ),
                "message": str(exc),
            }
        finally:
            try:
                DataProtectionService._write_json(
                    paths.restore_result_file, result
                )
            finally:
                paths.pending_restore_file.unlink(missing_ok=True)
        return result

    @staticmethod
    def _restore_database(paths: RuntimePaths, backup: Path) -> str | None:
        stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
        safety_dir = paths.backups_dir / "restore-safety" / stamp
        staged: Path | None = None
        moved: list[tuple[Path, Path]] = []
        replacement_installed = False
        try:
            with tempfile.NamedTemporaryFile(
                prefix=".life-os-restore-",
                suffix=".db",
                dir=paths.database_dir,
                delete=False,
            ) as handle:
                staged = Path(handle.name)
            DataProtectionService._copy_database(backup, staged)
            DataProtectionService._validate_database(staged)

            current_files = (
                paths.database_file,
                Path(f"{paths.database_file}-wal"),
                Path(f"{paths.database_file}-shm"),
            )
            existing = [path for path in current_files if path.exists()]
            if existing:
                safety_dir.mkdir(parents=True, exist_ok=False)
                for current in existing:
                    safety = safety_dir / current.name
                    os.replace(current, safety)
                    moved.append((current, safety))
            os.replace(staged, paths.database_file)
            staged = None
            replacement_installed = True
            DataProtectionService._validate_database(paths.database_file)
        except Exception as exc:
            if replacement_installed:
                paths.database_file.unlink(missing_ok=True)
            for current, safety in reversed(moved):
                if safety.exists():
                    os.replace(safety, current)
            raise DataProtectionError(
                "恢复失败，原数据库已保持或回滚。"
            ) from exc
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)
        if not moved:
            return None
        return safety_dir.relative_to(paths.home).as_posix()

    @staticmethod
    def _resolve_backup(paths: RuntimePaths, filename: str) -> Path:
        if (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or not BACKUP_PATTERN.fullmatch(filename)
        ):
            raise ValidationError("备份文件名无效。")
        path = paths.backups_dir / filename
        if not path.is_file():
            raise NotFoundError("备份文件不存在。")
        return path

    @staticmethod
    def _atomic_backup(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=destination.parent,
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
            DataProtectionService._copy_database(source, temporary)
            DataProtectionService._validate_database(temporary)
            os.replace(temporary, destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
                DataProtectionService._remove_sqlite_sidecars(temporary)

    @staticmethod
    def _copy_database(source: Path, destination: Path) -> None:
        source_uri = f"{source.resolve(strict=True).as_uri()}?mode=ro"
        with closing(
            sqlite3.connect(source_uri, uri=True, timeout=5.0)
        ) as source_db:
            source_db.execute("PRAGMA busy_timeout = 5000")
            with closing(
                sqlite3.connect(destination, timeout=5.0)
            ) as target_db:
                source_db.backup(target_db)
                target_db.commit()
                target_db.execute("PRAGMA journal_mode = DELETE")

    @staticmethod
    def _remove_sqlite_sidecars(path: Path) -> None:
        for suffix in ("-wal", "-shm"):
            path.with_name(f"{path.name}{suffix}").unlink(missing_ok=True)

    @staticmethod
    def _validate_database(path: Path) -> int:
        uri = f"{path.resolve(strict=True).as_uri()}?mode=ro"
        with closing(
            sqlite3.connect(uri, uri=True, timeout=5.0)
        ) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            if result is None or result[0] != "ok":
                raise DataProtectionError("SQLite 完整性检查未通过。")
            row = connection.execute(
                "SELECT value FROM schema_meta WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                raise DataProtectionError("备份缺少 schema_version。")
            try:
                version = int(row[0])
            except (TypeError, ValueError) as exc:
                raise DataProtectionError("备份 schema_version 无效。") from exc
            if not MINIMUM_MIGRATABLE_VERSION <= version <= SCHEMA_VERSION:
                raise DataProtectionError("备份数据库版本与当前程序不兼容。")
            return version

    @staticmethod
    def _prune(paths: RuntimePaths, retention_count: int) -> int:
        backups = sorted(
            (
                path
                for path in paths.backups_dir.iterdir()
                if path.is_file() and BACKUP_PATTERN.fullmatch(path.name)
            ),
            key=lambda path: (path.stat().st_mtime_ns, path.name),
            reverse=True,
        )
        removed = 0
        for path in backups[retention_count:]:
            path.unlink()
            removed += 1
        return removed

    @staticmethod
    def _record(paths: RuntimePaths, path: Path) -> BackupRecord:
        stat = path.stat()
        kind = "auto" if path.name.endswith("-auto.db") else "manual"
        return BackupRecord(
            filename=path.name,
            relative_path=path.relative_to(paths.home).as_posix(),
            created_at=datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(
                timespec="seconds"
            ),
            size_bytes=stat.st_size,
            kind=kind,
        )

    @staticmethod
    def _write_csv(
        path: Path,
        headers: Iterable[str],
        rows: Iterable[Sequence[object]],
        *,
        transform: Callable[[Sequence[object]], Sequence[object]] | None = None,
    ) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(headers)
            for row in rows:
                values = transform(row) if transform is not None else row
                writer.writerow(DataProtectionService._csv_value(value) for value in values)
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _csv_value(value: object) -> object:
        if value is None:
            return ""
        if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
            return f"'{value}"
        return value

    @staticmethod
    def _export_journals(
        paths: RuntimePaths,
        connection: sqlite3.Connection,
        directory: Path,
    ) -> int:
        directory.mkdir(parents=True, exist_ok=True)
        rows = connection.execute(
            "SELECT date, content FROM journals ORDER BY date"
        ).fetchall()
        for value_date, content in rows:
            rendered = JournalAssetService.render_self_contained(paths, content)
            target = directory / f"{value_date}.md"
            with target.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(rendered)
                if rendered and not rendered.endswith("\n"):
                    handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        return len(rows)

    @staticmethod
    def _write_json(path: Path, value: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=path.parent,
                delete=False,
            ) as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            os.replace(temporary, path)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _read_json(path: Path) -> dict[str, object] | None:
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"status": "invalid", "message": "状态文件无法读取。"}
        return value if isinstance(value, dict) else {
            "status": "invalid",
            "message": "状态文件格式无效。",
        }

    @staticmethod
    def _write_zip(directory: Path, destination: Path) -> None:
        temporary = destination.with_name(f".{destination.name}.tmp")
        try:
            with zipfile.ZipFile(
                temporary, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                for path in sorted(directory.rglob("*")):
                    if path.is_file():
                        archive.write(
                            path,
                            arcname=(
                                f"{directory.name}/"
                                f"{path.relative_to(directory).as_posix()}"
                            ),
                        )
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)


def _minor_to_amount(value: object) -> Decimal:
    return (Decimal(int(value)) / Decimal(100)).quantize(Decimal("0.01"))
