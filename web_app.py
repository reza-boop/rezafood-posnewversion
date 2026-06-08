"""Web entry point for RezaFood POS (mobile-friendly)."""

from __future__ import annotations

import os
import secrets
from typing import Any

from flask import Flask, flash, redirect, render_template, request, session, url_for

from config import ORDER_TYPES, PAYMENT_METHODS
from db import Database
from logger import logger
from services.order_service import OrderService
from services.product_service import ProductService
from utils import check_password, ensure_dirs

app = Flask(__name__)
secret_key = os.getenv("REZAFOOD_WEB_SECRET")
if not secret_key:
    secret_key = secrets.token_hex(32)
    logger.warning(
        "REZAFOOD_WEB_SECRET is not set; using an ephemeral secret key."
    )
app.secret_key = secret_key

ensure_dirs()
db = Database()
order_service = OrderService(db)
product_service = ProductService(db)
RECENT_ORDERS_LIMIT = 10


def _current_user() -> dict[str, Any] | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return {
        "id": int(user_id),
        "username": str(session.get("username", "")),
        "role": str(session.get("role", "cashier")),
    }


@app.get("/login")
def login_page() -> str:
    if _current_user():
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.post("/login")
def login_submit() -> str:
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    user = db.get_user_by_username(username)
    if not user or not check_password(password, user["password_hash"]):
        flash("نام کاربری یا رمز عبور اشتباه است.")
        return redirect(url_for("login_page"))

    session["user_id"] = int(user["id"])
    session["username"] = str(user["username"])
    session["role"] = str(user["role"])
    return redirect(url_for("dashboard"))


@app.post("/logout")
def logout() -> str:
    session.clear()
    return redirect(url_for("login_page"))


@app.get("/")
def dashboard() -> str:
    user = _current_user()
    if not user:
        return redirect(url_for("login_page"))

    products = product_service.get_all_products()
    orders = db.get_all_orders()[:RECENT_ORDERS_LIMIT]
    return render_template(
        "dashboard.html",
        user=user,
        products=products,
        orders=orders,
        payment_methods=PAYMENT_METHODS,
        order_types=ORDER_TYPES,
    )


@app.post("/orders")
def create_order() -> str:
    user = _current_user()
    if not user:
        return redirect(url_for("login_page"))

    payment_method = request.form.get("payment_method", "")
    order_type = request.form.get("order_type", "")
    product_ids = request.form.getlist("product_id")
    quantities = request.form.getlist("quantity")

    products_by_id = {
        int(product["id"]): product
        for product in product_service.get_all_products()
    }

    items: list[dict[str, Any]] = []
    for pid_raw, qty_raw in zip(product_ids, quantities):
        try:
            pid = int(pid_raw)
            qty = int(qty_raw)
        except ValueError:
            continue

        if qty <= 0 or pid not in products_by_id:
            continue

        product = products_by_id[pid]
        unit_price = float(product["price"])
        items.append(
            {
                "product_id": pid,
                "product_name": product["name"],
                "quantity": qty,
                "unit_price": unit_price,
                "applied_vat_rate": float(product["vat_rate"]),
                "subtotal": round(unit_price * qty, 2),
            }
        )

    if not items:
        flash("حداقل یک آیتم با تعداد معتبر انتخاب کنید.")
        return redirect(url_for("dashboard"))

    try:
        order_id = order_service.place_order(
            cashier_id=user["id"],
            cashier_name=user["username"],
            payment_method=payment_method,
            items=items,
            discount_amount=0.0,
            order_type=order_type,
        )
    except ValueError as exc:
        flash(str(exc))
        return redirect(url_for("dashboard"))

    db.add_audit_log(user["id"], user["username"], "web_create_order", f"order_id={order_id}")
    flash(f"سفارش #{order_id} با موفقیت ثبت شد.")
    return redirect(url_for("dashboard"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def main() -> None:
    app.run(
        host=os.getenv("REZAFOOD_WEB_HOST", "127.0.0.1"),
        port=int(os.getenv("REZAFOOD_WEB_PORT", "8000")),
        debug=False,
    )


if __name__ == "__main__":
    main()
