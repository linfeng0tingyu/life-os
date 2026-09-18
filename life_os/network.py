from __future__ import annotations

import socket


class PortUnavailableError(RuntimeError):
    """Raised when the configured local listening port is unavailable."""


def ensure_port_available(host: str, port: int) -> None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((host, port))
    except OSError as exc:
        raise PortUnavailableError(
            f"本机端口 {host}:{port} 已被占用或不可用。"
        ) from exc
    finally:
        probe.close()

