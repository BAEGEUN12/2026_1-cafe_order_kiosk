
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from cafe_order_kiosk.utils import utc_now


class OrderStatus(str, Enum):
    OPEN = "open"
    PAID = "paid"
    CANCELED = "canceled"


@dataclass(frozen=True)
class MenuItem:
    id: int
    name: str
    price: int
    category: str | None = None
    description: str | None = None
    is_available: bool = True


@dataclass(frozen=True)
class MenuRating:
    menu_item_id: int
    score: int
    comment: str | None = None
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class MenuRatingSummary:
    menu_item_id: int
    average: float
    count: int


@dataclass
class OrderItem:
    menu_item_id: int
    name: str
    unit_price: int
    quantity: int
    options: list[str] = field(default_factory=list)

    @property
    def line_total(self) -> int:
        return self.unit_price * self.quantity


@dataclass(frozen=True)
class Payment:
    method: str
    amount: int
    paid_at: datetime


@dataclass
class Order:
    id: int
    items: list[OrderItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.OPEN
    created_at: datetime = field(default_factory=utc_now)
    paid_at: datetime | None = None
    canceled_at: datetime | None = None
    note: str | None = None
    payment: Payment | None = None

    @property
    def total(self) -> int:
        return sum(item.line_total for item in self.items)
