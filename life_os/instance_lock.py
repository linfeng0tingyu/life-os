from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO


class InstanceLockError(RuntimeError):
    """Raised when another process already owns the runtime lock."""


class InstanceLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: BinaryIO | None = None
        self._locked = False

    @property
    def locked(self) -> bool:
        return self._locked

    def acquire(self) -> None:
        if self._locked:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)

        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise InstanceLockError(
                "另一个 Life OS 进程正在使用同一个 LIFE_OS_HOME。"
            ) from exc

        self._handle = handle
        self._locked = True

    def release(self) -> None:
        if not self._locked or self._handle is None:
            return

        try:
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None
            self._locked = False

    def __enter__(self) -> "InstanceLock":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()

