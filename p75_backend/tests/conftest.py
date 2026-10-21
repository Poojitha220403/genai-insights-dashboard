"""Test fixtures: import app.py with the MySQL pool replaced by an in-memory fake."""
import hashlib
import importlib
import os
import sys
from pathlib import Path
from unittest import mock

import secrets

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

# Test-only account; the password is random per test run, never a real credential
TEST_USERNAME = "test-user"
TEST_PASSWORD = secrets.token_urlsafe(16)
TEST_USER = {"id": 1, "username": TEST_USERNAME,
             "password": hashlib.sha512(TEST_PASSWORD.encode()).hexdigest()}


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self._rows = []

    def execute(self, sql, params=()):
        sql = " ".join(sql.split())
        if sql.startswith("SELECT * FROM users WHERE username"):
            self._rows = [u for u in self.db["users"] if u["username"] == params[0]]
        elif "FROM content" in sql:
            page = sql.split("page_type = '")[1].split("'")[0]
            self._rows = sorted((c for c in self.db["content"] if c["page_type"] == page),
                                key=lambda c: c["order_id"])
        elif "FROM charts" in sql:
            page = sql.split("page_type = '")[1].split("'")[0]
            self._rows = sorted((c for c in self.db["charts"] if c["page_type"] == page),
                                key=lambda c: c["order_id"])
        else:
            self._rows = []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class FakeConnection:
    def __init__(self, db):
        self.db = db

    def cursor(self, dictionary=False):
        return FakeCursor(self.db)

    def commit(self):
        pass

    def close(self):
        pass


class FakePool:
    db = None
    fail = False

    def __init__(self, **kwargs):
        pass

    def get_connection(self):
        if FakePool.fail:
            raise RuntimeError("database unavailable")
        return FakeConnection(FakePool.db)


@pytest.fixture
def db():
    return {
        "users": [TEST_USER],
        "content": [
            {"id": 1, "page_type": "dashboard", "content": "{}", "html_content": "<p>GenAI</p>", "order_id": 1},
            {"id": 2, "page_type": "summary", "content": "{}", "html_content": "<p>intro</p>", "order_id": 1},
            {"id": 3, "page_type": "summary", "content": "{}", "html_content": "<p>outro</p>", "order_id": 3},
        ],
        "charts": [
            {"id": 10, "page_type": "summary", "chart_type": "bar", "chart_data": "[]", "order_id": 2},
            {"id": 11, "page_type": "reports", "chart_type": "line", "chart_data": "[]", "order_id": 1},
        ],
    }


@pytest.fixture
def app_module(db):
    FakePool.db = db
    FakePool.fail = False
    with mock.patch.dict(os.environ, {"JWT_SECRET_KEY": "t" * 40}), \
         mock.patch("mysql.connector.pooling.MySQLConnectionPool", FakePool):
        sys.modules.pop("app", None)
        module = importlib.import_module("app")
        module.app.config["TESTING"] = True
        yield module
    sys.modules.pop("app", None)


@pytest.fixture
def client(app_module):
    return app_module.app.test_client()


def credentials(username=TEST_USERNAME, password=TEST_PASSWORD):
    return {"username": username, "password": password}


@pytest.fixture
def auth_header(client):
    token = client.post("/login", json=credentials()).get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
