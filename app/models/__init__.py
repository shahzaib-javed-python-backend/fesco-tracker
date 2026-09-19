"""
Models package — database models + Pydantic schemas.
"""

# ============================================================
# PYDANTIC SCHEMAS (API Response Models)
# ============================================================

from pydantic import BaseModel
from typing import List


class BillHistory(BaseModel):
    month: str
    units: int
    bill: int
    payment: int


class BillResponse(BaseModel):
    reference_no: str
    consumer_id: str
    name: str
    address: str
    bill_month: str | None = None
    reading_date: str | None = None
    due_date: str | None = None
    current_units: int
    current_bill: int
    grand_total: int
    history: List[BillHistory]


class AlertResponse(BaseModel):
    reference_no: str
    current_units: int
    status: str
    message: str
    color: str


# ============================================================
# DATABASE MODELS (SQLAlchemy)
# ============================================================

from app.models.user import User
from app.models.meter import Meter
from app.models.search import SearchHistory, CachedBill


__all__ = [
    # Pydantic schemas
    "BillHistory",
    "BillResponse",
    "AlertResponse",
    # Database models
    "User",
    "Meter",
    "SearchHistory",
    "CachedBill",
]