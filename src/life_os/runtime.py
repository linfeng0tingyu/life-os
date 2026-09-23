from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


RUNTIME_FORMAT_VERSION = 1
RUNTIME_DIRECTORY_NAMES = (
    "config",
    "database",
    "backups",
    "exports",
    "attachments",
    "cache",
    "logs",
    "temp",
)


class RuntimeSetupError(RuntimeError):
    """Raised when the portable runtime directory cannot be used safely."""


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    home: Path
    config_dir: Path
    database_dir: Path
    backups_dir: Path
    exports_dir: Path
    attachments_dir: Path
    cache_dir: Path
    webview_cache_dir: Path
    logs_dir: Path
    temp_dir: Path
    settings_file: Path
    metadata_file: Path
    database_file: Path
    log_file: Path
    lock_file: Path
    pending_restore_file: Path
    restore_result_file: Path

    @classmethod
    def from_home(cls, home: Path) -> "RuntimePaths":
        resolved_home = home.resolve(strict=False)
        return cls(
            home=resolved_home,
            config_dir=resolved_home / "config",
            database_dir=resolved_home / "database",
            backups_dir=resolved_home / "backups",
            exports_dir=resolved_home / "exports",
            attachments_dir=resolved_home / "attachments",
            cache_dir=resolved_home / "cache",
            webview_cache_dir=resolved_home / "cache" / "webview",
            logs_dir=resolved_home / "logs",
            temp_dir=resolved_home / "temp",
            settings_file=resolved_home / "config" / "settings.json",
            metadata_file=resolved_home / "metadata.json",
            database_file=resolved_home / "database" / "life.db",
            log_file=resolved_home / "logs" / "app.log",
            lock_file=resolved_home / "temp" / "life-os.lock",
            pending_restore_file=resolved_home / "temp" / "pending-restore.json",
            restore_result_file=resolved_home / "temp" / "restore-result.json",
        )

    @property
    def managed_directories(self) -> tuple[Path, ...]:
        return (
            self.config_dir,
            self.database_dir,
            self.backups_dir,
            self.exports_dir,
            self.attachments_dir,
            self.cache_dir,
            self.webview_cache_dir,
            self.logs_dir,
            self.temp_dir,
        )

    @property
    def managed_files(self) -> tuple[Path, ...]:
        return (
            self.settings_file,
            self.metadata_file,
            self.database_file,
            self.log_file,
            self.lock_file,
            self.pending_restore_file,
            self.restore_result_file,
        )

    def assert_contained(self) -> None:
        resolved_home = self.home.resolve(strict=False)
        for path in (*self.managed_directories, *self.managed_files):
            try:
                path.resolve(strict=False).relative_to(resolved_home)
            except ValueError as exc:
                raise RuntimeSetupError(
                    f"运行时路径越过 LIFE_OS_HOME：{path}"
                ) from exc


def resolve_runtime_paths(
    project_root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> RuntimePaths:
    environment = os.environ if env is None else env
    configured_home = environment.get("LIFE_OS_HOME", "").strip()

    if configured_home:
        home = Path(configured_home).expanduser()
        if not home.is_absolute():
            raise RuntimeSetupError("LIFE_OS_HOME 必须是绝对路径。")
    else:
        root = (
            project_root.resolve(strict=False)
            if project_root is not None
            else resolve_program_root()
        )
        home = root / "life-os-data"

    paths = RuntimePaths.from_home(home)
    paths.assert_contained()
    return paths


def resolve_program_root() -> Path:
    """Return the source root or the directory containing a frozen executable."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve(strict=False).parent
    return Path(__file__).resolve().parents[2]


def initialize_runtime(paths: RuntimePaths, app_version: str) -> RuntimePaths:
    if paths.home.exists() and not paths.home.is_dir():
        raise RuntimeSetupError(f"LIFE_OS_HOME 不是目录：{paths.home}")

    try:
        paths.home.mkdir(parents=True, exist_ok=True)
        for directory in paths.managed_directories:
            directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeSetupError(
            f"无法创建 LIFE_OS_HOME 或其子目录：{paths.home}"
        ) from exc

    paths.assert_contained()
    for directory in (paths.home, *paths.managed_directories):
        _verify_write_access(directory)

    _ensure_json_file(paths.settings_file, default_settings_document())
    _ensure_metadata(paths.metadata_file, app_version)
    return paths


def default_settings_document() -> dict[str, Any]:
    return {
        "settings_version": 1,
        "server": {
            "host": "127.0.0.1",
            "port": 5000,
            "debug": False,
            "open_browser": True,
        },
        "backup": {"retention_count": 30},
        "logging": {
            "level": "INFO",
            "max_bytes": 2_097_152,
            "backup_count": 5,
        },
    }


def _verify_write_access(directory: Path) -> None:
    probe_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".life-os-write-test-", dir=directory, delete=False
        ) as probe:
            probe.write(b"ok")
            probe.flush()
            os.fsync(probe.fileno())
            probe_path = Path(probe.name)
    except OSError as exc:
        raise RuntimeSetupError(f"运行时目录不可写：{directory}") from exc
    finally:
        if probe_path is not None:
            try:
                probe_path.unlink(missing_ok=True)
            except OSError as exc:
                raise RuntimeSetupError(
                    f"无法清理运行时目录中的测试文件：{probe_path}"
                ) from exc


def _ensure_json_file(path: Path, default_value: dict[str, Any]) -> None:
    if not path.exists():
        _atomic_write_json(path, default_value)
        return

    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeSetupError(f"运行时 JSON 文件无效或不可读：{path}") from exc
    if not isinstance(value, dict):
        raise RuntimeSetupError(f"运行时 JSON 文件必须包含对象：{path}")


def _ensure_metadata(path: Path, app_version: str) -> None:
    if not path.exists():
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        _atomic_write_json(
            path,
            {
                "application": "Life OS",
                "app_version_created_with": app_version,
                "runtime_format_version": RUNTIME_FORMAT_VERSION,
                "created_at": now,
            },
        )
        return

    try:
        with path.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeSetupError(f"运行时元数据无效或不可读：{path}") from exc

    if metadata.get("runtime_format_version") != RUNTIME_FORMAT_VERSION:
        raise RuntimeSetupError(
            "LIFE_OS_HOME 的运行时格式版本与当前程序不兼容。"
        )


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    temporary_path: Path | None = None
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
            temporary_path = Path(handle.name)
        os.replace(temporary_path, path)
    except OSError as exc:
        raise RuntimeSetupError(f"无法写入运行时文件：{path}") from exc
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)
