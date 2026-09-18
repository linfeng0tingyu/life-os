from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from flask import Flask

from .runtime import RuntimePaths
from .settings import AppSettings


def configure_logging(
    app: Flask, paths: RuntimePaths, settings: AppSettings
) -> None:
    for handler in tuple(app.logger.handlers):
        app.logger.removeHandler(handler)
        handler.close()

    file_handler = RotatingFileHandler(
        paths.log_file,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    file_handler.setLevel(getattr(logging, settings.log_level))

    app.logger.setLevel(getattr(logging, settings.log_level))
    app.logger.addHandler(file_handler)
    app.logger.propagate = False

