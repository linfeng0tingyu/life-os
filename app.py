from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path

# Production startup must not scatter Python bytecode caches beside source files.
sys.dont_write_bytecode = True

from life_os import __version__, create_app
from life_os.database import (
    DatabaseInitializationError,
    checkpoint_database,
)
from life_os.instance_lock import InstanceLock, InstanceLockError
from life_os.network import PortUnavailableError, ensure_port_available
from life_os.runtime import (
    RuntimeSetupError,
    initialize_runtime,
    resolve_runtime_paths,
)
from life_os.settings import SettingsError
from life_os.services.data_protection_service import (
    DataProtectionError,
    DataProtectionService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local Life OS server.")
    parser.add_argument(
        "--home",
        type=Path,
        help="Absolute LIFE_OS_HOME path. Overrides the environment variable.",
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="Do not open the browser automatically."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate and initialize the runtime, then exit.",
    )
    parser.add_argument(
        "--restore",
        metavar="BACKUP_FILENAME",
        help="Restore a validated backup before starting the application.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = None
    if args.home is not None:
        expanded_home = args.home.expanduser()
        if not expanded_home.is_absolute():
            print("错误：--home 必须使用绝对路径。", file=sys.stderr)
            return 2
        os.environ["LIFE_OS_HOME"] = str(expanded_home.resolve(strict=False))

    try:
        if args.restore:
            paths = resolve_runtime_paths()
            initialize_runtime(paths, __version__)
            instance_lock = InstanceLock(paths.lock_file)
            instance_lock.acquire()
            try:
                result = DataProtectionService.restore_immediately(
                    paths, args.restore
                )
            finally:
                instance_lock.release()
            print(
                "Life OS 恢复完成："
                f"{result['backup_file']}；恢复前副本：{result['safety_copy']}"
            )
            return 0

        app = create_app(acquire_lock=True)
        settings = app.extensions["life_os_settings"]
        paths = app.extensions["life_os_runtime"]

        if args.check:
            print(f"Life OS runtime ready: {paths.home}")
            app.extensions["life_os_instance_lock"].release()
            return 0

        ensure_port_available(settings.host, settings.port)
        url = f"http://{settings.host}:{settings.port}"
        if settings.open_browser and not args.no_browser:
            threading.Timer(0.8, lambda: webbrowser.open(url)).start()

        app.run(
            host=settings.host,
            port=settings.port,
            debug=settings.debug,
            use_reloader=False,
            threaded=True,
        )
        return 0
    except (
        RuntimeSetupError,
        SettingsError,
        InstanceLockError,
        PortUnavailableError,
        DatabaseInitializationError,
        DataProtectionError,
    ) as exc:
        print(f"Life OS 启动失败：{exc}", file=sys.stderr)
        return 1
    finally:
        if app is not None:
            try:
                checkpoint_database(app)
            except DatabaseInitializationError as exc:
                print(f"Life OS 关闭警告：{exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
