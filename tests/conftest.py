from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from life_os import create_app


@pytest.fixture
def app(tmp_path: Path) -> Flask:
    return create_app(runtime_home=tmp_path / "runtime", testing=True)


@pytest.fixture
def app_context(app: Flask) -> Iterator[None]:
    with app.app_context():
        yield


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()
