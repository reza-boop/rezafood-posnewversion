from __future__ import annotations

from types import SimpleNamespace

import pytest

import web_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(web_app.app, "secret_key", "test-secret")
    web_app.app.config.update(TESTING=True)
    with web_app.app.test_client() as test_client:
        yield test_client


class TestConfigureAppSecret:
    def test_requires_secret_for_non_local_host(self, monkeypatch):
        monkeypatch.delenv("REZAFOOD_WEB_SECRET", raising=False)

        with pytest.raises(RuntimeError, match="REZAFOOD_WEB_SECRET must be set"):
            web_app.configure_app_secret("0.0.0.0")

    def test_allows_ephemeral_secret_for_loopback(self, monkeypatch):
        monkeypatch.delenv("REZAFOOD_WEB_SECRET", raising=False)
        monkeypatch.setattr(web_app.secrets, "token_hex", lambda size: "local-secret")

        web_app.configure_app_secret("127.0.0.1")

        assert web_app.app.secret_key == "local-secret"


class TestDashboard:
    def test_dashboard_uses_recent_orders_query(self, client, monkeypatch):
        called = {}

        monkeypatch.setattr(
            web_app,
            "product_service",
            SimpleNamespace(get_all_products=lambda: []),
        )
        monkeypatch.setattr(
            web_app,
            "db",
            SimpleNamespace(
                get_recent_orders=lambda limit: (
                    called.setdefault("limit", limit),
                    [],
                )[1]
            ),
        )

        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "admin"
            session["role"] = "admin"

        response = client.get("/")

        assert response.status_code == 200
        assert called["limit"] == web_app.RECENT_ORDERS_LIMIT


class TestCreateOrder:
    def test_rejects_mismatched_product_and_quantity_lists(self, client, monkeypatch):
        monkeypatch.setattr(
            web_app,
            "product_service",
            SimpleNamespace(get_all_products=lambda: []),
        )

        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "admin"
            session["role"] = "admin"

        response = client.post(
            "/orders",
            data={
                "payment_method": "Cash",
                "order_type": "Take Away",
                "product_id": ["1", "2"],
                "quantity": ["1"],
            },
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")

        with client.session_transaction() as session:
            assert session["_flashes"] == [("message", web_app.INVALID_ORDER_FORM_MESSAGE)]
