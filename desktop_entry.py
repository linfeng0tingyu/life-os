from __future__ import annotations

import argparse
import ctypes
import os
import sys
from pathlib import Path

# Do not scatter Python bytecode beside source files in diagnostic mode.
sys.dont_write_bytecode = True

from life_os.database import DatabaseInitializationError
from life_os.desktop import LocalServerError, run_desktop
from life_os.instance_lock import InstanceLockError
from life_os.runtime import RuntimeSetupError
from life_os.settings import SettingsError


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Life OS as a desktop app.")
    parser.add_argument(
        "--home",
        type=Path,
        help="Absolute LIFE_OS_HOME path. Overrides the environment variable.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Initialize and validate the packaged runtime, then exit.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runtime_home: Path | None = None
    if args.home is not None:
        runtime_home = args.home.expanduser()
        if not runtime_home.is_absolute():
            return _startup_failure("--home 必须使用绝对路径。")
        runtime_home = runtime_home.resolve(strict=False)

    try:
        return run_desktop(
            runtime_home=runtime_home,
            check_only=args.check,
        )
    except (
        RuntimeSetupError,
        SettingsError,
        InstanceLockError,
        DatabaseInitializationError,
        LocalServerError,
    ) as exc:
        return _startup_failure(str(exc))
    except Exception as exc:
        return _startup_failure(f"发生未预期错误：{type(exc).__name__}")


def _startup_failure(message: str) -> int:
    full_message = f"Life OS 启动失败：\n\n{message}"
    print(full_message, file=sys.stderr)
    if os.name == "nt" and getattr(sys, "frozen", False):
        try:
            ctypes.windll.user32.MessageBoxW(
                None,
                full_message,
                "Life OS 启动失败",
                0x10,
            )
        except (AttributeError, OSError):
            pass
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
