import importlib
import os
import sys
from unittest import mock

import pytest

from conftest import TEST_PASSWORD, TEST_USERNAME, FakePool, credentials


def test_health(client):
    assert client.get("/").get_json() == {"msg": "Welcome to P75 Backend!"}


@pytest.mark.parametrize("payload", [{}, {"username": TEST_USERNAME}, {"password": TEST_PASSWORD}])
def test_login_rejects_missing_fields(client, payload):
    assert client.post("/login", json=payload).status_code == 400


def test_login_rejects_wrong_password(client):
    response = client.post("/login", json=credentials(password=TEST_PASSWORD + "-wrong"))
    assert response.status_code == 401


def test_login_rejects_unknown_user(client):
    response = client.post("/login", json=credentials(username="nobody"))
    assert response.status_code == 401


def test_login_issues_jwt(client):
    response = client.post("/login", json=credentials())
    assert response.status_code == 200
    assert response.get_json()["access_token"].count(".") == 2


@pytest.mark.parametrize("path", ["/dashboard", "/summary", "/reports", "/admin/contents/summary"])
def test_protected_routes_require_jwt(client, path):
    assert client.get(path).status_code == 401


def test_protected_routes_reject_bad_token(client):
    response = client.get("/dashboard", headers={"Authorization": "Bearer not.a.token"})
    assert response.status_code == 422


def test_dashboard_returns_content(client, auth_header):
    body = client.get("/dashboard", headers=auth_header).get_json()
    assert body["logged_in_as"] == TEST_USERNAME
    assert [c["html_content"] for c in body["contents"]] == ["<p>GenAI</p>"]


def test_summary_interleaves_content_and_charts_by_order(client, auth_header):
    items = client.get("/summary", headers=auth_header).get_json()["items"]
    assert [i["type"] for i in items] == ["content", "chart", "content"]
    assert [i["data"]["order_id"] for i in items] == [1, 2, 3]


def test_reports_returns_charts(client, auth_header):
    items = client.get("/reports", headers=auth_header).get_json()["items"]
    assert items == [{"type": "chart", "data": {"id": 11, "page_type": "reports", "chart_type": "line",
                                                 "chart_data": "[]", "order_id": 1}}]


@pytest.mark.parametrize("path", ["/dashboard", "/summary", "/reports"])
def test_database_outage_returns_500(client, auth_header, path):
    FakePool.fail = True
    response = client.get(path, headers=auth_header)
    assert response.status_code == 500
    assert response.get_json() == {"msg": "Internal server error"}


def test_app_refuses_to_start_without_jwt_secret():
    env = {k: v for k, v in os.environ.items() if k != "JWT_SECRET_KEY"}
    with mock.patch.dict(os.environ, env, clear=True), \
         mock.patch("mysql.connector.pooling.MySQLConnectionPool", FakePool), \
         mock.patch("dotenv.load_dotenv"):
        sys.modules.pop("app", None)
        with pytest.raises(KeyError, match="JWT_SECRET_KEY"):
            importlib.import_module("app")
    sys.modules.pop("app", None)
