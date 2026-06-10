from __future__ import annotations

from collections.abc import Iterable

from cafe_order_kiosk.models import (
    MenuItem,
    MenuRating,
    MenuRatingSummary,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
)
from cafe_order_kiosk.utils import utc_now

DEFAULT_MENU: tuple[MenuItem, ...] = (
    MenuItem(id=1, name="Americano", price=3500, category="coffee"),
    MenuItem(id=2, name="Latte", price=4000, category="coffee"),
    MenuItem(id=3, name="Cappuccino", price=4200, category="coffee"),
    MenuItem(id=4, name="Cold Brew", price=4500, category="coffee"),
    MenuItem(id=5, name="Matcha Latte", price=4800, category="tea"),
    MenuItem(id=6, name="Chamomile Tea", price=3800, category="tea"),
    MenuItem(id=7, name="Lemonade", price=4200, category="juice"),
    MenuItem(id=8, name="Butter Croissant", price=3500, category="bakery"),
    MenuItem(id=9, name="Blueberry Muffin", price=3200, category="bakery"),
    MenuItem(id=10, name="Cheesecake", price=5200, category="dessert"),
)


class KioskStore:
    def __init__(self, menu_items: Iterable[MenuItem] | None = None) -> None:
        self._menu: dict[int, MenuItem] = {item.id: item for item in (menu_items or [])}
        self._orders: dict[int, Order] = {}
        self._ratings: dict[int, list[MenuRating]] = {}
        self._next_order_id = 1

    @classmethod
    def with_default_menu(cls) -> KioskStore:
        return cls(menu_items=DEFAULT_MENU)

    def list_menu(self, only_available: bool = True) -> list[MenuItem]:
        items: Iterable[MenuItem] = self._menu.values()
        if only_available:
            items = [item for item in items if item.is_available]
        return sorted(items, key=lambda item: item.id)

    def get_menu_item(self, menu_item_id: int) -> MenuItem | None:
        return self._menu.get(menu_item_id)

    def add_rating(
        self,
        menu_item_id: int,
        score: int,
        comment: str | None = None,
    ) -> MenuRating:
        menu_item = self._menu.get(menu_item_id)
        if menu_item is None:
            raise ValueError("Menu item not found")
        if not menu_item.is_available:
            raise ValueError("Menu item is not available")
        if score < 1 or score > 5:
            raise ValueError("Rating score must be between 1 and 5")

        normalized_comment = comment.strip() if comment else None
        if normalized_comment == "":
            normalized_comment = None

        rating = MenuRating(
            menu_item_id=menu_item_id,
            score=score,
            comment=normalized_comment,
        )
        self._ratings.setdefault(menu_item_id, []).append(rating)
        return rating

    def list_ratings(self, menu_item_id: int) -> list[MenuRating]:
        if menu_item_id not in self._menu:
            raise ValueError("Menu item not found")
        return list(self._ratings.get(menu_item_id, []))

    def get_menu_rating_summary(self, menu_item_id: int) -> MenuRatingSummary | None:
        if menu_item_id not in self._menu:
            raise ValueError("Menu item not found")

        ratings = self._ratings.get(menu_item_id, [])
        if not ratings:
            return None

        average = sum(rating.score for rating in ratings) / len(ratings)
        return MenuRatingSummary(
            menu_item_id=menu_item_id,
            average=average,
            count=len(ratings),
        )

    def get_best_menu_items(
        self,
        limit: int = 1,
    ) -> list[tuple[MenuItem, MenuRatingSummary]]:
        if limit < 1:
            raise ValueError("Limit must be at least 1")

        ranked_items: list[tuple[MenuItem, MenuRatingSummary]] = []
        for menu_item in self.list_menu():
            summary = self.get_menu_rating_summary(menu_item.id)
            if summary is not None:
                ranked_items.append((menu_item, summary))

        ranked_items.sort(
            key=lambda item_and_summary: (
                -item_and_summary[1].average,
                -item_and_summary[1].count,
                item_and_summary[0].id,
            )
        )
        return ranked_items[:limit]

    def create_order(self, note: str | None = None) -> Order:
        order_id = self._next_order_id
        self._next_order_id += 1

        order = Order(id=order_id, note=note)
        self._orders[order_id] = order
        return order

    def list_orders(self, status: OrderStatus | None = None) -> list[Order]:
        orders: Iterable[Order] = self._orders.values()
        if status is not None:
            orders = [order for order in orders if order.status == status]
        return sorted(orders, key=lambda order: order.id)

    def get_order(self, order_id: int) -> Order | None:
        return self._orders.get(order_id)

    def add_item(
        self,
        order_id: int,
        menu_item_id: int,
        quantity: int,
        options: list[str] | None = None,
    ) -> Order:
        order = self._require_order(order_id)
        if order.status is not OrderStatus.OPEN:
            raise ValueError("Order is not open")
        if quantity < 1:
            raise ValueError("Quantity must be at least 1")

        menu_item = self._menu.get(menu_item_id)
        if menu_item is None:
            raise ValueError("Menu item not found")
        if not menu_item.is_available:
            raise ValueError("Menu item is not available")

        order_item = OrderItem(
            menu_item_id=menu_item.id,
            name=menu_item.name,
            unit_price=menu_item.price,
            quantity=quantity,
            options=options or [],
        )
        order.items.append(order_item)
        return order

    def remove_item(self, order_id: int, line_index: int) -> Order:
        order = self._require_order(order_id)
        if order.status is not OrderStatus.OPEN:
            raise ValueError("Order is not open")
        if line_index < 1 or line_index > len(order.items):
            raise ValueError("Line item not found")

        order.items.pop(line_index - 1)
        return order

    def cancel_order(self, order_id: int) -> Order:
        order = self._require_order(order_id)
        if order.status is OrderStatus.CANCELED:
            return order
        if order.status is OrderStatus.PAID:
            raise ValueError("Paid order cannot be canceled")

        order.status = OrderStatus.CANCELED
        order.canceled_at = utc_now()
        return order

    def pay_order(self, order_id: int, method: str, amount: int) -> Order:
        order = self._require_order(order_id)
        if order.status is not OrderStatus.OPEN:
            raise ValueError("Order is not open")
        if not order.items:
            raise ValueError("Order has no items")
        if amount != order.total:
            raise ValueError("Payment amount does not match total")

        order.status = OrderStatus.PAID
        order.paid_at = utc_now()
        order.payment = Payment(method=method, amount=amount, paid_at=order.paid_at)
        return order

    def _require_order(self, order_id: int) -> Order:
        order = self._orders.get(order_id)
        if order is None:
            raise ValueError("Order not found")
        return order
