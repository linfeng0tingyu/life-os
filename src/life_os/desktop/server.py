from __future__ import annotations

import http.client
import socket
import threading
import time
from collections.abc import Callable
from typing import Any

from flask import Flask


LOOPBACK_HOST = "127.0.0.1"


class LocalServerError(RuntimeError):
    """Raised when the private desktop HTTP service cannot start or stop."""


class LocalWsgiServer:
    """Run Waitress on an atomically reserved loopback port."""

    def __init__(
        self,
        application: Flask,
        *,
        server_factory: Callable[..., Any] | None = None,
        startup_timeout: float = 8.0,
        shutdown_timeout: float = 5.0,
    ) -> None:
        self.application = application
        self.host = LOOPBACK_HOST
        self.startup_timeout = startup_timeout
        self.shutdown_timeout = shutdown_timeout
        self._thread: threading.Thread | None = None
        self._run_error: BaseException | None = None
        self._stopped = False

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(
                    socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1
                )
            listener.bind((self.host, 0))
            self.port = int(listener.getsockname()[1])

            if server_factory is None:
                from waitress.server import create_server

                server_factory = create_server

            self._server = server_factory(
                application,
                sockets=[listener],
                threads=4,
                asyncore_loop_timeout=0.1,
                clear_untrusted_proxy_headers=True,
                expose_tracebacks=False,
                ident="Life OS",
            )
        except BaseException:
            listener.close()
            raise

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        if self._stopped:
            raise LocalServerError("本地服务已经停止，不能重复启动。")

        self._thread = threading.Thread(
            target=self._run,
            name="life-os-waitress",
            daemon=True,
        )
        self._thread.start()
        self._wait_until_ready()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True

        stop_error: BaseException | None = None
        try:
            self._server.close()
        except BaseException as exc:
            stop_error = exc

        dispatcher = getattr(self._server, "task_dispatcher", None)
        if dispatcher is not None:
            try:
                dispatcher.shutdown(
                    cancel_pending=True,
                    timeout=self.shutdown_timeout,
                )
            except BaseException as exc:
                stop_error = stop_error or exc

        if self._thread is not None:
            self._thread.join(timeout=self.shutdown_timeout)
            if self._thread.is_alive():
                raise LocalServerError("本地服务未能在限定时间内停止。")
        if stop_error is not None:
            raise LocalServerError("本地服务停止时发生错误。") from stop_error

    def _run(self) -> None:
        try:
            self._server.run()
        except BaseException as exc:
            self._run_error = exc

    def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if self._run_error is not None:
                raise LocalServerError("本地服务启动失败。") from self._run_error
            if not self.running:
                raise LocalServerError("本地服务在就绪前意外退出。")
            if self._health_check():
                return
            time.sleep(0.05)

        self.stop()
        raise LocalServerError("等待本地服务就绪超时。")

    def _health_check(self) -> bool:
        connection = http.client.HTTPConnection(
            self.host,
            self.port,
            timeout=0.25,
        )
        try:
            connection.request("GET", "/api/system/health")
            response = connection.getresponse()
            response.read()
            return response.status == 200
        except OSError:
            return False
        finally:
            connection.close()
