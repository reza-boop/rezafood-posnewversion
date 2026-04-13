"""Repository package — one class per domain aggregate."""

from repositories.audit import AuditRepository
from repositories.base import BaseRepository
from repositories.discount import DiscountRepository
from repositories.order import OrderRepository
from repositories.product import ProductRepository
from repositories.report import ReportRepository
from repositories.user import UserRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "ProductRepository",
    "OrderRepository",
    "DiscountRepository",
    "AuditRepository",
    "ReportRepository",
]
