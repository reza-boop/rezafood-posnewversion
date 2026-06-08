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


class TestReportsPage:
    def _login_as(self, client, role: str = "admin") -> None:
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "admin"
            sess["role"] = role

    def _make_report_service(self):
        return SimpleNamespace(
            daily_revenue=lambda days=30: [],
            revenue_by_payment=lambda: [],
            sales_by_category=lambda: [],
            top_cashiers=lambda limit=5: [],
            hourly_distribution=lambda: [],
        )

    def test_redirects_unauthenticated(self, client):
        response = client.get("/reports")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_admin_can_access_reports(self, client, monkeypatch):
        monkeypatch.setattr(web_app, "report_service", self._make_report_service())
        self._login_as(client, "admin")
        response = client.get("/reports")
        assert response.status_code == 200
        assert "گزارش" in response.data.decode()

    def test_non_admin_is_redirected(self, client, monkeypatch):
        monkeypatch.setattr(web_app, "report_service", self._make_report_service())
        self._login_as(client, "cashier")
        response = client.get("/reports")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")

    def test_hourly_distribution_padded_to_24_hours(self, client, monkeypatch):
        stub = self._make_report_service()
        stub.hourly_distribution = lambda: [{"hour": 10, "orders": 5}]
        monkeypatch.setattr(web_app, "report_service", stub)
        self._login_as(client, "admin")
        response = client.get("/reports")
        assert response.status_code == 200
        body = response.data.decode()
        # All 24 hour labels should be present in the rendered JSON
        for h in range(24):
            assert f'"hour": {h}' in body

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
