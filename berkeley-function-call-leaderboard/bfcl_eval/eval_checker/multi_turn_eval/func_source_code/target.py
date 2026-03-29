"""
Target Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Target Circle loyalty program, RedCard 5% discount, Drive Up & Order Pickup,
  same-day delivery via Shipt, gift registry, and clippable Circle offers.
"""

from __future__ import annotations

import copy
import math
import random
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from .base_service import BaseServiceAPI


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


class TargetError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        suggested_action: str = "",
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.error = {
            "error_code": error_code,
            "message": message,
            "suggested_action": suggested_action,
            "context": context or {},
        }

    def to_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self.error)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, x))


def _matches_query(text: str, query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return True
    return q in (text or "").lower()


# ---------------------------------------------------------------------------
# Target API
# ---------------------------------------------------------------------------


DEFAULT_STATE = {
    "random_seed": 9012,
    "profile": {},
    "cart": {},
    "orders": {},
    "returns": {},
    "reviews": {},
    "products": {},
    "offers": {},
    "shipping_options": {},
    "stores": {},
    "store_inventory": {},
    "drive_up_times": {},
    "delivery_windows": {},
    "registries": {},
}


class TargetAPI(BaseServiceAPI):
    """
    In-memory dummy implementation of a Target-like retail shopping service.
    Supports product search, Target Circle loyalty (offers, points, birthday
    rewards), RedCard discount, Order Pickup & Drive Up, same-day delivery
    via Shipt, gift registries, and full order lifecycle management.
    """

    _STATE_KEYS = (
        "profile", "cart", "orders", "returns", "reviews",
        "products", "offers", "shipping_options",
        "stores", "store_inventory", "drive_up_times", "delivery_windows", "registries",
    )
    _ID_COUNTER_DEFAULTS = {
        "cart": 0,
        "order": 0,
        "return": 0,
        "review": 0,
        "address": 0,
        "payment": 0,
        "registry": 0,
    }
    _DEFAULT_SEED = 9012

    def __init__(self):
        super().__init__()
        self.profile: Dict[str, Any]
        self.stores: Dict[str, Dict[str, Any]]
        self.products: Dict[str, Dict[str, Any]]
        self.store_inventory: Dict[str, Dict[str, Any]]
        self.cart: Dict[str, Any]
        self.offers: Dict[str, Dict[str, Any]]
        self.shipping_options: Dict[str, Any]
        self.drive_up_times: Dict[str, List[Dict[str, Any]]]
        self.delivery_windows: Dict[str, List[Dict[str, Any]]]
        self.orders: Dict[str, Dict[str, Any]]
        self.returns: Dict[str, Dict[str, Any]]
        self.reviews: Dict[str, Dict[str, Any]]
        self.registries: Dict[str, Dict[str, Any]]
        self._api_description = (
            "This tool belongs to the Target shopping system, which allows users to "
            "search products, manage a shopping cart with multiple fulfillment options "
            "(shipping, order pickup, drive up, same-day delivery), use Target Circle "
            "loyalty offers, manage RedCard benefits, create gift registries, and "
            "handle the full order lifecycle."
        )


    def _load_scenario(
        self,
        scenario: Dict[str, Any],
        long_context: bool = False,
    ) -> None:
        """
        Load a scenario from the scenarios folder.
        Args:
            scenario (Dict[str, Any]): The scenario to load
        """
        DEFAULT_STATE_COPY = deepcopy(DEFAULT_STATE)
        self._random = random.Random(
            scenario.get("random_seed", DEFAULT_STATE_COPY["random_seed"])
        )
        self.profile = scenario.get("profile", DEFAULT_STATE_COPY["profile"])
        self.cart = scenario.get("cart", DEFAULT_STATE_COPY["cart"])
        self.orders = scenario.get("orders", DEFAULT_STATE_COPY["orders"])
        self.returns = scenario.get("returns", DEFAULT_STATE_COPY["returns"])
        self.reviews = scenario.get("reviews", DEFAULT_STATE_COPY["reviews"])
        self.products = scenario.get("products", DEFAULT_STATE_COPY["products"])
        self.offers = scenario.get("offers", DEFAULT_STATE_COPY["offers"])
        self.shipping_options = scenario.get("shipping_options", DEFAULT_STATE_COPY["shipping_options"])
        self.stores = scenario.get("stores", DEFAULT_STATE_COPY["stores"])
        self.store_inventory = scenario.get("store_inventory", DEFAULT_STATE_COPY["store_inventory"])
        self.drive_up_times = scenario.get("drive_up_times", DEFAULT_STATE_COPY["drive_up_times"])
        self.delivery_windows = scenario.get("delivery_windows", DEFAULT_STATE_COPY["delivery_windows"])
        self.registries = scenario.get("registries", DEFAULT_STATE_COPY["registries"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, TargetAPI):
            return False

        for attr_name in vars(self):
            if attr_name.startswith("_"):
                continue
            model_attr = getattr(self, attr_name)
            ground_truth_attr = getattr(value, attr_name)

            if model_attr != ground_truth_attr:
                return False

        return True

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _require_store(self, store_id: str) -> Dict[str, Any]:
        store = self.stores.get(store_id)
        if not store:
            raise TargetError(
                "STORE_NOT_FOUND",
                f"Store '{store_id}' not found.",
                suggested_action="Use set_preferred_store() or search for a valid store.",
                context={"store_id": store_id},
            )
        return store

    def _require_product(self, product_id: str) -> Dict[str, Any]:
        product = self.products.get(product_id)
        if not product:
            raise TargetError(
                "PRODUCT_NOT_FOUND",
                f"Product '{product_id}' not found.",
                suggested_action="Use search_products() to find valid product IDs.",
                context={"product_id": product_id},
            )
        return product

    def _require_order(self, order_id: str) -> Dict[str, Any]:
        order = self.orders.get(order_id)
        if not order:
            raise TargetError(
                "ORDER_NOT_FOUND",
                f"Order '{order_id}' not found.",
                suggested_action="Use get_order_details() with a valid order_id.",
                context={"order_id": order_id},
            )
        return order

    def _get_product_price(
        self, product: Dict[str, Any], context: str = "online"
    ) -> int:
        """Return the price in cents for a product. Target may have different
        online vs in-store prices."""
        if context == "in_store" and product.get("in_store_price") is not None:
            return int(product["in_store_price"])
        return int(product.get("price", 0))

    def _get_user_cart(self) -> Dict[str, Any]:
        """Return existing cart for the current user or create a new empty one."""
        if not self.cart.get("items") and self.cart.get("items") != []:
            self.cart["items"] = []
            self.cart["subtotal"] = 0
            self.cart["applied_promo"] = None
            self.cart["shipping_option"] = None
        return self.cart

    def _compute_cart_subtotal(self) -> int:
        """Compute the subtotal in cents for all items in the current user's cart."""
        cart = self._get_user_cart()
        total = 0
        for item in cart.get("items", []):
            product = self.products.get(item["product_id"])
            if not product:
                continue
            ft = item.get("fulfillment_type", "shipping")
            price_context = "in_store" if ft in ("order_pickup", "drive_up") else "online"
            price = self._get_product_price(product, price_context)
            total += price * int(item.get("quantity", 1))
        return max(0, total)

    def _compute_circle_discount(self) -> int:
        """Compute total discount from applied Circle offers."""
        cart = self._get_user_cart()
        discount = 0
        subtotal = self._compute_cart_subtotal()
        for offer_id in cart.get("circle_offers_applied", []):
            offer = self.offers.get(offer_id, {})
            dtype = offer.get("discount_type", "percent")
            dval = int(offer.get("discount_value", 0))
            if dtype == "percent":
                # Apply percent to applicable items only
                applicable_products = offer.get("applicable_product_ids", [])
                applicable_dept = offer.get("department")
                offer_subtotal = 0
                for item in cart.get("items", []):
                    product = self.products.get(item["product_id"], {})
                    if applicable_products and item["product_id"] in applicable_products:
                        ft = item.get("fulfillment_type", "shipping")
                        pc = "in_store" if ft in ("order_pickup", "drive_up") else "online"
                        offer_subtotal += self._get_product_price(product, pc) * item.get("quantity", 1)
                    elif applicable_dept and (product.get("department") or "").lower() == applicable_dept.lower():
                        ft = item.get("fulfillment_type", "shipping")
                        pc = "in_store" if ft in ("order_pickup", "drive_up") else "online"
                        offer_subtotal += self._get_product_price(product, pc) * item.get("quantity", 1)
                    elif not applicable_products and not applicable_dept:
                        ft = item.get("fulfillment_type", "shipping")
                        pc = "in_store" if ft in ("order_pickup", "drive_up") else "online"
                        offer_subtotal += self._get_product_price(product, pc) * item.get("quantity", 1)
                discount += int(round(offer_subtotal * (dval / 100.0)))
            elif dtype == "flat":
                discount += min(dval, subtotal)
        return discount

    # -----------------------------------------------------------------------
    # Product search & browse
    # -----------------------------------------------------------------------

    def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        department: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        rating_min: Optional[float] = None,
        sort_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for products matching a text query and optional filters.

        Args:
            query (str): Free-text search string matched against product name and
                description. Pass an empty string to match all products.
            category (str, optional): Filter by product category (e.g. "Beauty",
                "Home", "Electronics", "Toys").
            department (str, optional): Filter by Target department (e.g. "Apparel &
                Accessories", "Food & Beverage", "Household Essentials").
            min_price (int, optional): Minimum online price in cents (inclusive).
            max_price (int, optional): Maximum online price in cents (inclusive).
            rating_min (float, optional): Minimum average star rating (e.g. 4.0).
            sort_by (str, optional): Sort order. Supported values: "price_low",
                "price_high", "rating", "name". Defaults to relevance (unsorted).

        Returns:
            List[Dict[str, Any]]: Matching products, each with fields:
                product_id (str), name (str), brand (str), category (str),
                department (str), price (int, cents),
                in_store_price (int | None, cents), rating (float),
                review_count (int), options (List[str]).
        """
        results: List[Dict[str, Any]] = []
        for p in self.products.values():
            if not _matches_query(p.get("name", ""), query) and not _matches_query(
                p.get("description", ""), query
            ):
                continue
            if category and (p.get("category") or "").lower() != category.lower():
                continue
            if department and (p.get("department") or "").lower() != department.lower():
                continue
            price = self._get_product_price(p)
            if min_price is not None and price < int(min_price):
                continue
            if max_price is not None and price > int(max_price):
                continue
            if rating_min is not None and float(p.get("rating", 0.0)) < float(
                rating_min
            ):
                continue
            results.append(
                {
                    "product_id": p["product_id"],
                    "name": p.get("name", ""),
                    "brand": p.get("brand", ""),
                    "category": p.get("category", ""),
                    "department": p.get("department", ""),
                    "price": p.get("price", 0),
                    "in_store_price": p.get("in_store_price"),
                    "rating": p.get("rating", 0.0),
                    "review_count": p.get("review_count", 0),
                    "options": p.get("options", []),
                }
            )

        if sort_by == "price_low":
            results.sort(key=lambda x: int(x.get("price", 0)))
        elif sort_by == "price_high":
            results.sort(key=lambda x: int(x.get("price", 0)), reverse=True)
        elif sort_by == "rating":
            results.sort(key=lambda x: float(x.get("rating", 0.0)), reverse=True)
        elif sort_by == "name":
            results.sort(key=lambda x: (x.get("name") or "").lower())

        return results

    def get_product_details(self, product_id: str) -> Dict[str, Any]:
        """
        Retrieve full details for a specific product.

        Args:
            product_id (str): The unique product identifier.

        Returns:
            Dict[str, Any]: Product details including:
                product_id (str), name (str), brand (str), category (str),
                department (str), description (str), price (int, cents),
                in_store_price (int | None, cents), rating (float),
                review_count (int), options (List[str] -- "shipping",
                "order_pickup", "drive_up", "same_day_delivery").
        """
        product = self._require_product(product_id)
        return {
            "product_id": product["product_id"],
            "name": product.get("name", ""),
            "brand": product.get("brand", ""),
            "category": product.get("category", ""),
            "department": product.get("department", ""),
            "description": product.get("description", ""),
            "price": product.get("price", 0),
            "in_store_price": product.get("in_store_price"),
            "rating": product.get("rating", 0.0),
            "review_count": product.get("review_count", 0),
            "options": product.get("options", []),
        }

    def check_in_store_availability(
        self, product_id: str, store_id: str
    ) -> Dict[str, Any]:
        """
        Check whether a product is available at a specific Target store.

        Args:
            product_id (str): The product to check.
            store_id (str): The store to check inventory at.

        Returns:
            Dict[str, Any]:
                product_id (str), store_id (str), in_stock (bool),
                quantity (int), aisle (str), shelf (str), floor (str).
        """
        self._require_product(product_id)
        self._require_store(store_id)
        inv = self.store_inventory.get(store_id, {}).get(product_id, {})
        return {
            "product_id": product_id,
            "store_id": store_id,
            "in_stock": inv.get("in_stock", False),
            "quantity": inv.get("quantity", 0),
            "aisle": inv.get("aisle", ""),
            "shelf": inv.get("shelf", ""),
            "floor": inv.get("floor", "1"),
        }

    def find_in_store(
        self, product_id: str, store_id: str
    ) -> Dict[str, Any]:
        """
        Get the exact location of a product within a Target store, including
        aisle number, shelf position, and floor.

        Args:
            product_id (str): The product to locate.
            store_id (str): The store to search in.

        Returns:
            Dict[str, Any]:
                product_id (str), store_id (str), found (bool),
                aisle (str), shelf (str), floor (str),
                department_area (str -- the in-store area name).
        """
        self._require_product(product_id)
        store = self._require_store(store_id)
        inv = self.store_inventory.get(store_id, {}).get(product_id, {})
        product = self.products.get(product_id, {})

        if not inv or not inv.get("in_stock", False):
            return {
                "product_id": product_id,
                "store_id": store_id,
                "found": False,
                "aisle": "",
                "shelf": "",
                "floor": "",
                "department_area": "",
            }

        return {
            "product_id": product_id,
            "store_id": store_id,
            "found": True,
            "aisle": inv.get("aisle", ""),
            "shelf": inv.get("shelf", ""),
            "floor": inv.get("floor", "1"),
            "department_area": product.get("department", ""),
        }

    # -----------------------------------------------------------------------
    # Store management
    # -----------------------------------------------------------------------

    def set_preferred_store(self, store_id: str) -> Dict[str, Any]:
        """
        Set the current user's preferred Target store. This affects default pickup location
        and local availability checks.

        Args:
            store_id (str): The store to set as preferred.

        Returns:
            Dict[str, Any]:
                user_id (str), preferred_store_id (str), store_name (str).
        """
        user_id = self.user_id
        store = self._require_store(store_id)
        self.profile["preferred_store_id"] = store_id
        return {
            "user_id": user_id,
            "preferred_store_id": store_id,
            "store_name": store.get("name", ""),
        }

    def get_preferred_store(self) -> Dict[str, Any]:
        """
        Retrieve the current user's configured preferred Target store.

        Returns:
            Dict[str, Any]:
                user_id (str), preferred_store_id (str | None),
                store (Dict | None -- full store details if a preferred store is set).
        """
        user_id = self.user_id
        store_id = self.profile.get("preferred_store_id")
        store = self.stores.get(store_id) if store_id else None
        return {
            "user_id": user_id,
            "preferred_store_id": store_id,
            "store": deepcopy(store) if store else None,
        }

    # -----------------------------------------------------------------------
    # Cart management
    # -----------------------------------------------------------------------

    def add_to_cart(
        self,
        product_id: str,
        quantity: int,
        fulfillment_type: Optional[str] = None,
        store_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a product to the current user's shopping cart.

        Args:
            product_id (str): The product to add.
            quantity (int): Number of units to add; must be >= 1.
            fulfillment_type (str, optional): One of "shipping", "order_pickup",
                "drive_up", or "same_day_delivery". Defaults to "shipping".
            store_id (str, optional): Store ID for pickup/drive-up/same-day fulfillment.
                Required when fulfillment_type is not "shipping".

        Returns:
            Dict[str, Any]: Updated cart with fields:
                items (List[Dict]), circle_offers_applied (List[str]),
                subtotal (int, cents), updated_at (str, ISO-8601).
        """
        user_id = self.user_id
        product = self._require_product(product_id)
        qty = int(quantity)
        if qty < 1:
            raise TargetError(
                "INVALID_QUANTITY",
                "Quantity must be >= 1.",
                suggested_action="Provide a quantity of at least 1.",
                context={"quantity": quantity},
            )

        ft = fulfillment_type or "shipping"
        valid_types = ("shipping", "order_pickup", "drive_up", "same_day_delivery")
        if ft not in valid_types:
            raise TargetError(
                "INVALID_FULFILLMENT_TYPE",
                f"Fulfillment type '{ft}' is not valid. Must be one of {valid_types}.",
                suggested_action=f"Use one of: {', '.join(valid_types)}.",
                context={"fulfillment_type": ft},
            )

        if ft != "shipping":
            if not store_id:
                raise TargetError(
                    "STORE_REQUIRED",
                    f"A store_id is required for '{ft}' fulfillment.",
                    suggested_action="Provide a store_id or use set_preferred_store() first.",
                    context={"fulfillment_type": ft},
                )
            store = self._require_store(store_id)

            if ft == "drive_up" and not store.get("has_drive_up", False):
                raise TargetError(
                    "DRIVE_UP_NOT_AVAILABLE",
                    f"Store '{store_id}' does not support Drive Up.",
                    suggested_action="Choose a store with Drive Up or use Order Pickup instead.",
                    context={"store_id": store_id},
                )

            if ft == "order_pickup" and not store.get("has_order_pickup", True):
                raise TargetError(
                    "ORDER_PICKUP_NOT_AVAILABLE",
                    f"Store '{store_id}' does not support Order Pickup.",
                    suggested_action="Choose a different store.",
                    context={"store_id": store_id},
                )

            # Check store inventory for pickup/drive-up
            if ft in ("order_pickup", "drive_up"):
                inv = self.store_inventory.get(store_id, {}).get(product_id, {})
                if not inv.get("in_stock", False):
                    raise TargetError(
                        "OUT_OF_STOCK_AT_STORE",
                        f"Product '{product_id}' is out of stock at store '{store_id}'.",
                        suggested_action="Check availability at another store or use 'shipping'.",
                        context={"product_id": product_id, "store_id": store_id},
                    )
                available_qty = inv.get("quantity", 0)
                if qty > available_qty:
                    raise TargetError(
                        "INSUFFICIENT_STORE_QUANTITY",
                        f"Only {available_qty} units available at store '{store_id}'.",
                        suggested_action=f"Reduce quantity to {available_qty} or less.",
                        context={
                            "product_id": product_id,
                            "store_id": store_id,
                            "available": available_qty,
                            "requested": qty,
                        },
                    )

        cart = self._get_user_cart()
        line_id = f"tli_{len(cart['items']) + 1}"
        cart["items"].append(
            {
                "line_item_id": line_id,
                "product_id": product_id,
                "quantity": qty,
                "fulfillment_type": ft,
                "store_id": store_id,
            }
        )
        cart["subtotal"] = self._compute_cart_subtotal()
        return deepcopy(cart)

    def update_cart_item(
        self,
        line_item_id: str,
        quantity: Optional[int] = None,
        fulfillment_type: Optional[str] = None,
        store_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing item in the current user's cart.

        Args:
            line_item_id (str): The line item to update (from get_cart()).
            quantity (int, optional): New quantity; must be >= 1.
                Use remove_from_cart() to delete an item.
            fulfillment_type (str, optional): New fulfillment type.
            store_id (str, optional): New store for pickup/drive-up/delivery.

        Returns:
            Dict[str, Any]: Updated cart object.
        """
        user_id = self.user_id
        cart = self._get_user_cart()
        item = next(
            (i for i in cart["items"] if i.get("line_item_id") == line_item_id), None
        )
        if not item:
            raise TargetError(
                "LINE_ITEM_NOT_FOUND",
                f"Line item '{line_item_id}' not found in cart.",
                suggested_action="Call get_cart() to list valid line_item_id values.",
                context={"user_id": user_id, "line_item_id": line_item_id},
            )

        if quantity is not None:
            q = int(quantity)
            if q < 1:
                raise TargetError(
                    "INVALID_QUANTITY",
                    "Quantity must be >= 1. Use remove_from_cart() to remove.",
                    suggested_action="Provide quantity >= 1 or call remove_from_cart().",
                    context={"quantity": quantity},
                )
            item["quantity"] = q

        if fulfillment_type is not None:
            valid_types = ("shipping", "order_pickup", "drive_up", "same_day_delivery")
            if fulfillment_type not in valid_types:
                raise TargetError(
                    "INVALID_FULFILLMENT_TYPE",
                    f"Fulfillment type '{fulfillment_type}' is not valid.",
                    suggested_action=f"Use one of: {', '.join(valid_types)}.",
                    context={"fulfillment_type": fulfillment_type},
                )
            item["fulfillment_type"] = fulfillment_type

        if store_id is not None:
            self._require_store(store_id)
            item["store_id"] = store_id

        cart["subtotal"] = self._compute_cart_subtotal()
        return deepcopy(cart)

    def remove_from_cart(self, line_item_id: str) -> Dict[str, Any]:
        """
        Remove a line item from the current user's cart.

        Args:
            line_item_id (str): The line item to remove.

        Returns:
            Dict[str, Any]: Updated cart object.
        """
        user_id = self.user_id
        cart = self._get_user_cart()
        before = len(cart["items"])
        cart["items"] = [
            i for i in cart["items"] if i.get("line_item_id") != line_item_id
        ]
        if len(cart["items"]) == before:
            raise TargetError(
                "LINE_ITEM_NOT_FOUND",
                f"Line item '{line_item_id}' not found in cart.",
                suggested_action="Call get_cart() to list valid line_item_id values.",
                context={"user_id": user_id, "line_item_id": line_item_id},
            )
        cart["subtotal"] = self._compute_cart_subtotal()
        return deepcopy(cart)

    def get_cart(self) -> Dict[str, Any]:
        """
        Retrieve the current state of the current user's shopping cart with a freshly
        computed subtotal.

        Returns:
            Dict[str, Any]: Cart object including:
                items (List[Dict] -- each with line_item_id, product_id,
                quantity, fulfillment_type, store_id), circle_offers_applied (List[str]),
                subtotal (int, cents), applied_promo (str | None),
                shipping_option (str | None).
        """
        user_id = self.user_id
        cart = self._get_user_cart()
        cart["subtotal"] = self._compute_cart_subtotal()
        return deepcopy(cart)

    # -----------------------------------------------------------------------
    # Fulfillment
    # -----------------------------------------------------------------------

    def select_fulfillment(
        self, fulfillment_type: str, store_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Set a default fulfillment type for all items in the cart. Individual items
        can still be overridden via update_cart_item().

        Args:
            fulfillment_type (str): One of "shipping", "order_pickup", "drive_up",
                or "same_day_delivery".
            store_id (str, optional): Required for "order_pickup", "drive_up", or
                "same_day_delivery".

        Returns:
            Dict[str, Any]: Updated cart with all applicable items set to the chosen
                fulfillment type. Items that do not support the chosen type are
                flagged in a warnings list.
        """
        user_id = self.user_id
        valid_types = ("shipping", "order_pickup", "drive_up", "same_day_delivery")
        if fulfillment_type not in valid_types:
            raise TargetError(
                "INVALID_FULFILLMENT_TYPE",
                f"Fulfillment type '{fulfillment_type}' is not valid.",
                suggested_action=f"Use one of: {', '.join(valid_types)}.",
                context={"fulfillment_type": fulfillment_type},
            )
        if fulfillment_type != "shipping" and not store_id:
            raise TargetError(
                "STORE_REQUIRED",
                f"A store_id is required for '{fulfillment_type}' fulfillment.",
                suggested_action="Provide a store_id.",
                context={"fulfillment_type": fulfillment_type},
            )
        if store_id:
            self._require_store(store_id)

        cart = self._get_user_cart()
        warnings: List[Dict[str, str]] = []
        for item in cart["items"]:
            product = self.products.get(item["product_id"], {})
            supported = product.get("options", [])
            if fulfillment_type in supported:
                item["fulfillment_type"] = fulfillment_type
                if store_id:
                    item["store_id"] = store_id
            else:
                warnings.append(
                    {
                        "product_id": item["product_id"],
                        "message": f"Product does not support '{fulfillment_type}'. Kept current fulfillment.",
                    }
                )
        cart["subtotal"] = self._compute_cart_subtotal()
        return {"cart": deepcopy(cart), "warnings": warnings}

    def get_drive_up_times(self, store_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve available Drive Up time windows for a given Target store.

        Args:
            store_id (str): The store to check Drive Up times for.

        Returns:
            List[Dict[str, Any]]: Available Drive Up time slots, each with:
                slot_id (str), date (str, YYYY-MM-DD), start_time (str, HH:MM),
                end_time (str, HH:MM), available (bool).
        """
        store = self._require_store(store_id)
        if not store.get("has_drive_up", False):
            raise TargetError(
                "DRIVE_UP_NOT_AVAILABLE",
                f"Store '{store_id}' does not support Drive Up.",
                suggested_action="Choose a store with Drive Up capability.",
                context={"store_id": store_id},
            )
        slots = self.drive_up_times.get(store_id, [])
        return deepcopy(slots)

    def get_delivery_windows(self, store_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve available same-day delivery windows (via Shipt) for a given
        Target store area.

        Args:
            store_id (str): The store whose delivery area to check.

        Returns:
            List[Dict[str, Any]]: Available delivery windows, each with:
                window_id (str), date (str, YYYY-MM-DD), start_time (str, HH:MM),
                end_time (str, HH:MM), fee (int, cents), available (bool).
        """
        self._require_store(store_id)
        windows = self.delivery_windows.get(store_id, [])
        return deepcopy(windows)

    # -----------------------------------------------------------------------
    # Target Circle loyalty
    # -----------------------------------------------------------------------

    def get_circle_offers(self) -> List[Dict[str, Any]]:
        """
        Retrieve all available Target Circle offers for the current user. Includes both
        clipped and unclipped offers.

        Returns:
            List[Dict[str, Any]]: Offers, each with:
                offer_id (str), description (str), discount_type (str),
                discount_value (int), applicable_product_ids (List[str] | None),
                department (str | None), expiry (str), clipped (bool -- whether
                this user has clipped/saved the offer).
        """
        user_id = self.user_id
        if not self.profile.get("membership", {}).get("circle_member", False):
            raise TargetError(
                "NOT_CIRCLE_MEMBER",
                "User is not a Target Circle member.",
                suggested_action="Target Circle membership is required to view offers.",
                context={"user_id": user_id},
            )

        results: List[Dict[str, Any]] = []
        for offer_id, offer in self.offers.items():
            clipped = user_id in offer.get("clipped_by", [])
            results.append(
                {
                    "offer_id": offer_id,
                    "description": offer.get("description", ""),
                    "discount_type": offer.get("discount_type", "percent"),
                    "discount_value": offer.get("discount_value", 0),
                    "applicable_product_ids": offer.get("applicable_product_ids"),
                    "department": offer.get("department"),
                    "expiry": offer.get("expiry", ""),
                    "clipped": clipped,
                }
            )
        return results

    def apply_circle_offer(self, offer_id: str) -> Dict[str, Any]:
        """
        Clip and apply a Target Circle offer to the current user's cart. The offer must
        be valid and applicable to at least one item in the cart.

        Args:
            offer_id (str): The Circle offer to apply (from get_circle_offers()).

        Returns:
            Dict[str, Any]:
                applied (bool), offer_id (str), discount_preview (int, cents),
                reason (str -- "OK", "OFFER_NOT_FOUND", "OFFER_EXPIRED",
                "NOT_APPLICABLE", "ALREADY_APPLIED").
        """
        user_id = self.user_id
        if not self.profile.get("membership", {}).get("circle_member", False):
            raise TargetError(
                "NOT_CIRCLE_MEMBER",
                "User is not a Target Circle member.",
                suggested_action="Target Circle membership is required.",
                context={"user_id": user_id},
            )

        offer = self.offers.get(offer_id)
        if not offer:
            return {
                "applied": False,
                "offer_id": offer_id,
                "discount_preview": 0,
                "reason": "OFFER_NOT_FOUND",
            }

        # Check expiry
        expiry = offer.get("expiry")
        if expiry:
            try:
                exp_dt = datetime.fromisoformat(expiry)
                if exp_dt < datetime.now(timezone.utc):
                    return {
                        "applied": False,
                        "offer_id": offer_id,
                        "discount_preview": 0,
                        "reason": "OFFER_EXPIRED",
                    }
            except (ValueError, TypeError):
                pass

        cart = self._get_user_cart()

        # Check if already applied
        if offer_id in cart.get("circle_offers_applied", []):
            return {
                "applied": False,
                "offer_id": offer_id,
                "discount_preview": 0,
                "reason": "ALREADY_APPLIED",
            }

        # Check applicability
        applicable_products = offer.get("applicable_product_ids", [])
        applicable_dept = offer.get("department")
        cart_product_ids = [i["product_id"] for i in cart.get("items", [])]
        cart_depts = set()
        for item in cart.get("items", []):
            product = self.products.get(item["product_id"], {})
            dept = product.get("department", "")
            if dept:
                cart_depts.add(dept.lower())

        applicable = False
        if applicable_products:
            if any(pid in cart_product_ids for pid in applicable_products):
                applicable = True
        elif applicable_dept:
            if applicable_dept.lower() in cart_depts:
                applicable = True
        else:
            # General offer applies to everything
            if cart.get("items"):
                applicable = True

        if not applicable:
            return {
                "applied": False,
                "offer_id": offer_id,
                "discount_preview": 0,
                "reason": "NOT_APPLICABLE",
            }

        # Clip the offer
        if user_id not in offer.get("clipped_by", []):
            offer.setdefault("clipped_by", []).append(user_id)

        # Apply to cart
        cart.setdefault("circle_offers_applied", []).append(offer_id)

        discount = self._compute_circle_discount()
        return {
            "applied": True,
            "offer_id": offer_id,
            "discount_preview": discount,
            "reason": "OK",
        }

    def get_circle_points(self) -> Dict[str, Any]:
        """
        Retrieve the current user's Target Circle points balance and earnings summary.

        Returns:
            Dict[str, Any]:
                user_id (str), circle_member (bool), points_balance (int),
                lifetime_earnings (int), next_reward_threshold (int -- points
                needed for next $1 reward).
        """
        user_id = self.user_id
        membership = self.profile.get("membership", {})
        if not membership.get("circle_member", False):
            return {
                "user_id": user_id,
                "circle_member": False,
                "points_balance": 0,
                "lifetime_earnings": 0,
                "next_reward_threshold": 0,
            }

        points = membership.get("circle_points", 0)
        # Target Circle: 1% earnings, $1 reward per 5000 points (simplified)
        next_threshold = 5000 - (points % 5000) if points % 5000 != 0 else 0
        return {
            "user_id": user_id,
            "circle_member": True,
            "points_balance": points,
            "lifetime_earnings": membership.get("lifetime_circle_earnings", points),
            "next_reward_threshold": next_threshold,
        }

    # -----------------------------------------------------------------------
    # Checkout & orders
    # -----------------------------------------------------------------------

    def apply_promo_code(self, promo_code: str) -> Dict[str, Any]:
        """
        Apply a promotional code to the current user's cart.

        Args:
            promo_code (str): The promotional code to apply.

        Returns:
            Dict[str, Any]:
                valid (bool), reason (str -- "OK" or error code such as
                PROMO_NOT_FOUND, MIN_ORDER_NOT_MET, PROMO_EXPIRED),
                discount_preview (int, cents).
        """
        user_id = self.user_id
        cart = self._get_user_cart()
        subtotal = self._compute_cart_subtotal()

        promos = self.profile.get("promos", {})
        promo = promos.get((promo_code or "").upper())
        if not promo:
            for code, p in promos.items():
                if code.upper() == (promo_code or "").upper():
                    promo = p
                    break
        if not promo:
            return {"valid": False, "reason": "PROMO_NOT_FOUND", "discount_preview": 0}

        min_order = promo.get("min_order")
        if min_order is not None and subtotal < int(min_order):
            return {
                "valid": False,
                "reason": "MIN_ORDER_NOT_MET",
                "discount_preview": 0,
            }

        expiry = promo.get("expiry")
        if expiry:
            try:
                exp_dt = datetime.fromisoformat(expiry)
                if exp_dt < datetime.now(timezone.utc):
                    return {
                        "valid": False,
                        "reason": "PROMO_EXPIRED",
                        "discount_preview": 0,
                    }
            except (ValueError, TypeError):
                pass

        discount_type = promo.get("discount_type", "percent")
        discount_value = int(promo.get("discount_value", 0))
        if discount_type == "percent":
            discount_preview = int(round(subtotal * (discount_value / 100.0)))
        elif discount_type == "flat":
            discount_preview = min(discount_value, subtotal)
        elif discount_type == "free_shipping":
            discount_preview = 0
        else:
            discount_preview = 0

        cart["applied_promo"] = promo_code
        return {
            "valid": True,
            "reason": "OK",
            "discount_preview": discount_preview,
        }

    def place_order(
        self,
        payment_method_id: str,
        address_id: Optional[str] = None,
        delivery_window_id: Optional[str] = None,
        drive_up_slot_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Place an order from the current user's cart. Validates payment, computes
        pricing with tax, RedCard discount, Circle offer discounts, and any promo
        code, then creates the order.

        Args:
            payment_method_id (str): Payment method to charge
                (from list_payment_methods()).
            address_id (str, optional): Delivery address for shipping/same-day
                fulfillment (from list_addresses()). Required if any cart item uses
                "shipping" or "same_day_delivery" fulfillment.
            delivery_window_id (str, optional): Delivery window for same-day delivery
                (from get_delivery_windows()).
            drive_up_slot_id (str, optional): Drive Up time slot
                (from get_drive_up_times()).

        Returns:
            Dict[str, Any]:
                order_id (str), status (str), items (List), subtotal (int, cents),
                tax (int, cents), shipping_fee (int, cents), delivery_fee (int, cents),
                circle_discount (int, cents), promo_discount (int, cents),
                redcard_discount (int, cents), total (int, cents),
                circle_points_earned (int), fulfillment_type (str),
                placed_at (str, ISO-8601).
        """
        user_id = self.user_id
        cart = self._get_user_cart()

        if not cart.get("items"):
            raise TargetError(
                "EMPTY_CART",
                "Cannot place an order with an empty cart.",
                suggested_action="Add items to your cart before placing an order.",
                context={"user_id": user_id},
            )

        # Validate payment method
        pm = self.profile.get("payment_methods", {}).get(payment_method_id)
        if not pm:
            raise TargetError(
                "PAYMENT_METHOD_NOT_FOUND",
                f"Payment method '{payment_method_id}' not found for user.",
                suggested_action="Call list_payment_methods() to get valid method IDs.",
                context={"user_id": user_id, "payment_method_id": payment_method_id},
            )

        # Check gift card balance if paying with gift card
        if pm.get("type") == "gift_card":
            balance = pm.get("gift_card_balance", 0)
            subtotal = self._compute_cart_subtotal()
            if balance < subtotal:
                raise TargetError(
                    "INSUFFICIENT_GIFT_CARD_BALANCE",
                    f"Gift card balance ({balance} cents) is insufficient.",
                    suggested_action="Add another payment method or reduce your cart.",
                    context={"balance": balance, "cart_subtotal": subtotal},
                )

        # Determine fulfillment types and validate addresses
        fulfillment_types = set(
            i.get("fulfillment_type", "shipping") for i in cart["items"]
        )
        needs_address = bool(
            fulfillment_types.intersection({"shipping", "same_day_delivery"})
        )
        if needs_address:
            if not address_id:
                raise TargetError(
                    "ADDRESS_REQUIRED",
                    "A delivery address is required for shipping or same-day delivery.",
                    suggested_action="Provide an address_id from list_addresses().",
                    context={"user_id": user_id},
                )
            addr = self.profile.get("addresses", {}).get(address_id)
            if not addr:
                raise TargetError(
                    "ADDRESS_NOT_FOUND",
                    f"Address '{address_id}' not found for user.",
                    suggested_action="Call list_addresses() to get valid address IDs.",
                    context={"user_id": user_id, "address_id": address_id},
                )

        subtotal = self._compute_cart_subtotal()
        tax = int(round(subtotal * 0.0775))  # 7.75% sales tax

        # Shipping fee
        shipping_fee = 0
        if "shipping" in fulfillment_types:
            if subtotal >= 3500:  # Free shipping over $35
                shipping_fee = 0
            else:
                shipping_fee = 599  # $5.99 standard shipping

        # Delivery fee for same-day
        delivery_fee = 0
        if "same_day_delivery" in fulfillment_types:
            if delivery_window_id:
                # Find the delivery window fee
                for store_id_key, windows in self.delivery_windows.items():
                    for w in windows:
                        if w.get("window_id") == delivery_window_id:
                            delivery_fee = w.get("fee", 999)
                            break
            else:
                delivery_fee = 999  # Default $9.99 delivery fee

        # Circle offer discounts
        circle_discount = self._compute_circle_discount()

        # Promo code discount
        promo_discount = 0
        promo_code = cart.get("applied_promo")
        if promo_code:
            promos = self.profile.get("promos", {})
            promo = promos.get((promo_code or "").upper())
            if not promo:
                for code, p in promos.items():
                    if code.upper() == (promo_code or "").upper():
                        promo = p
                        break
            if promo:
                dtype = promo.get("discount_type", "percent")
                dval = int(promo.get("discount_value", 0))
                if dtype == "percent":
                    promo_discount = int(round(subtotal * (dval / 100.0)))
                elif dtype == "flat":
                    promo_discount = min(dval, subtotal)
                elif dtype == "free_shipping":
                    promo_discount = shipping_fee
                    shipping_fee = 0

        # RedCard 5% discount
        redcard_discount = 0
        membership = self.profile.get("membership", {})
        is_redcard = pm.get("type") == "red_card" or membership.get("red_card", False)
        if is_redcard:
            redcard_discount = int(round(subtotal * 0.05))
            shipping_fee = 0  # RedCard gets free shipping

        total_discount = circle_discount + promo_discount + redcard_discount
        total = max(0, subtotal + tax + shipping_fee + delivery_fee - total_discount)

        # Determine primary fulfillment type
        primary_ft = "shipping"
        if "order_pickup" in fulfillment_types:
            primary_ft = "order_pickup"
        elif "drive_up" in fulfillment_types:
            primary_ft = "drive_up"
        elif "same_day_delivery" in fulfillment_types:
            primary_ft = "same_day_delivery"

        order_id = self._new_id("order")
        now = _utc_now_iso()

        # Determine store_id
        store_id = None
        for item in cart["items"]:
            if item.get("store_id"):
                store_id = item["store_id"]
                break

        # Compute Circle points earned (1% of pre-tax subtotal)
        circle_points_earned = 0
        if membership.get("circle_member", False):
            circle_points_earned = int(round(subtotal / 100.0))
            membership["circle_points"] = membership.get("circle_points", 0) + circle_points_earned

        # Deduct gift card balance if applicable
        if pm.get("type") == "gift_card":
            pm["gift_card_balance"] = max(0, pm.get("gift_card_balance", 0) - total)

        self.orders[order_id] = {
            "order_id": order_id,
            "user_id": user_id,
            "items": deepcopy(cart["items"]),
            "status": "confirmed",
            "fulfillment_type": primary_ft,
            "store_id": store_id,
            "address_id": address_id,
            "delivery_window_id": delivery_window_id,
            "drive_up_slot_id": drive_up_slot_id,
            "payment_method_id": payment_method_id,
            "subtotal": subtotal,
            "tax": tax,
            "shipping_fee": shipping_fee,
            "delivery_fee": delivery_fee,
            "circle_discount": circle_discount,
            "promo_discount": promo_discount,
            "redcard_discount": redcard_discount,
            "total": total,
            "circle_points_earned": circle_points_earned,
            "promo_code": promo_code,
            "tracking": None,
            "placed_at": now,
            "updated_at": now,
        }

        # Clear the cart
        self.cart["items"] = []
        self.cart["subtotal"] = 0
        self.cart["applied_promo"] = None
        self.cart["shipping_option"] = None
        self.cart.pop("circle_offers_applied", None)

        # Reduce store inventory for pickup/drive-up items
        for item in self.orders[order_id]["items"]:
            sid = item.get("store_id")
            pid = item["product_id"]
            if sid and sid in self.store_inventory:
                inv = self.store_inventory[sid].get(pid, {})
                if inv:
                    inv["quantity"] = max(0, inv.get("quantity", 0) - item["quantity"])
                    if inv["quantity"] == 0:
                        inv["in_stock"] = False

        return {
            "order_id": order_id,
            "status": "confirmed",
            "items": deepcopy(self.orders[order_id]["items"]),
            "subtotal": subtotal,
            "tax": tax,
            "shipping_fee": shipping_fee,
            "delivery_fee": delivery_fee,
            "circle_discount": circle_discount,
            "promo_discount": promo_discount,
            "redcard_discount": redcard_discount,
            "total": total,
            "circle_points_earned": circle_points_earned,
            "fulfillment_type": primary_ft,
            "placed_at": now,
        }

    # -----------------------------------------------------------------------
    # Order management
    # -----------------------------------------------------------------------

    def get_order_details(self, order_id: str) -> Dict[str, Any]:
        """
        Retrieve full details for an order. The order must belong to the current user.

        Args:
            order_id (str): The order to retrieve.

        Returns:
            Dict[str, Any]: Order details including:
                order_id (str), user_id (str), items (List), status (str -- one of
                "confirmed", "processing", "shipped", "ready_for_pickup",
                "ready_for_drive_up", "picked_up", "delivered", "canceled",
                "returned"), fulfillment_type (str), store_id (str | None),
                tracking (str | None), subtotal (int), tax (int), shipping_fee (int),
                delivery_fee (int), circle_discount (int), promo_discount (int),
                redcard_discount (int), total (int), circle_points_earned (int),
                placed_at (str), updated_at (str).
        """
        order = self._require_order(order_id)
        if order.get("user_id") != self.user_id:
            raise PermissionError("You do not have permission to access this resource.")
        return deepcopy(order)

    def cancel_order(self, order_id: str, reason: str) -> Dict[str, Any]:
        """
        Cancel an order. Only orders in "confirmed" or "processing" status can
        be canceled. The order must belong to the current user.

        Args:
            order_id (str): The order to cancel.
            reason (str): Short description of why the order is being canceled.

        Returns:
            Dict[str, Any]:
                order_id (str), canceled (bool), status (str),
                refund_amount (int, cents), circle_points_reversed (int).
        """
        order = self._require_order(order_id)
        if order.get("user_id") != self.user_id:
            raise PermissionError("You do not have permission to access this resource.")
        status = order.get("status")
        if status not in ("confirmed", "processing"):
            return {
                "order_id": order_id,
                "canceled": False,
                "status": status,
                "refund_amount": 0,
                "circle_points_reversed": 0,
                "message": f"Cannot cancel order in '{status}' status.",
            }

        refund = order.get("total", 0)
        points_to_reverse = order.get("circle_points_earned", 0)

        order["status"] = "canceled"
        order["updated_at"] = _utc_now_iso()
        order["cancel_reason"] = reason

        # Reverse Circle points
        membership = self.profile.get("membership", {})
        if points_to_reverse > 0:
            membership["circle_points"] = max(
                0, membership.get("circle_points", 0) - points_to_reverse
            )

        # Restore store inventory for pickup/drive-up items
        for item in order.get("items", []):
            sid = item.get("store_id")
            pid = item["product_id"]
            if sid and sid in self.store_inventory:
                inv = self.store_inventory[sid].get(pid, {})
                if inv:
                    inv["quantity"] = inv.get("quantity", 0) + item["quantity"]
                    inv["in_stock"] = True

        # Refund gift card if applicable
        pm_id = order.get("payment_method_id")
        if pm_id:
            pm = self.profile.get("payment_methods", {}).get(pm_id, {})
            if pm.get("type") == "gift_card":
                pm["gift_card_balance"] = pm.get("gift_card_balance", 0) + refund

        return {
            "order_id": order_id,
            "canceled": True,
            "status": "canceled",
            "refund_amount": refund,
            "circle_points_reversed": points_to_reverse,
        }

    def start_return(
        self,
        order_id: str,
        product_id: str,
        reason: str,
        return_method: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initiate a return for a product from a completed order. The order must
        belong to the current user.

        Args:
            order_id (str): The order containing the product to return.
            product_id (str): The specific product to return.
            reason (str): Reason for the return (e.g. "defective", "wrong_item",
                "changed_mind", "not_as_described").
            return_method (str, optional): How the return is handled. One of
                "in_store" (return at any Target store), "mail" (ship it back),
                or "drive_up" (drop off via Drive Up). Defaults to "in_store".

        Returns:
            Dict[str, Any]:
                return_id (str), order_id (str), product_id (str),
                reason (str), method (str), status (str -- "initiated"),
                refund_amount (int, cents).
        """
        order = self._require_order(order_id)
        if order.get("user_id") != self.user_id:
            raise PermissionError("You do not have permission to access this resource.")
        if order.get("status") not in ("delivered", "picked_up", "shipped"):
            raise TargetError(
                "ORDER_NOT_ELIGIBLE_FOR_RETURN",
                f"Order in '{order.get('status')}' status cannot be returned.",
                suggested_action="Only delivered, picked up, or shipped orders can be returned.",
                context={"order_id": order_id, "status": order.get("status")},
            )

        order_item = next(
            (i for i in order.get("items", []) if i.get("product_id") == product_id),
            None,
        )
        if not order_item:
            raise TargetError(
                "PRODUCT_NOT_IN_ORDER",
                f"Product '{product_id}' not found in order '{order_id}'.",
                suggested_action="Check order items via get_order_details().",
                context={"order_id": order_id, "product_id": product_id},
            )

        method = return_method or "in_store"
        if method not in ("in_store", "mail", "drive_up"):
            raise TargetError(
                "INVALID_RETURN_METHOD",
                f"Return method '{method}' is not valid. Use 'in_store', 'mail', or 'drive_up'.",
                suggested_action="Use 'in_store', 'mail', or 'drive_up'.",
                context={"return_method": method},
            )

        product = self.products.get(product_id, {})
        ft = order_item.get("fulfillment_type", "shipping")
        price_context = "in_store" if ft in ("order_pickup", "drive_up") else "online"
        refund_amount = self._get_product_price(product, price_context) * order_item.get(
            "quantity", 1
        )

        return_id = self._new_id("return")
        self.returns[return_id] = {
            "return_id": return_id,
            "order_id": order_id,
            "product_id": product_id,
            "user_id": order.get("user_id"),
            "reason": reason,
            "method": method,
            "status": "initiated",
            "refund_amount": refund_amount,
            "created_at": _utc_now_iso(),
        }

        return {
            "return_id": return_id,
            "order_id": order_id,
            "product_id": product_id,
            "reason": reason,
            "method": method,
            "status": "initiated",
            "refund_amount": refund_amount,
        }

    # -----------------------------------------------------------------------
    # Reviews
    # -----------------------------------------------------------------------

    def get_reviews(
        self,
        product_id: str,
        rating_filter: Optional[int] = None,
        verified_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve reviews for a product with optional filtering.

        Args:
            product_id (str): The product to get reviews for.
            rating_filter (int, optional): If provided, only return reviews with
                this exact star rating (1-5).
            verified_only (bool): If True, only return reviews from verified
                purchasers. Defaults to False.

        Returns:
            List[Dict[str, Any]]: Reviews, each with:
                review_id (str), product_id (str), user_id (str), rating (int),
                title (str), body (str), verified (bool), created_at (str).
        """
        self._require_product(product_id)
        results: List[Dict[str, Any]] = []
        for review in self.reviews.values():
            if review.get("product_id") != product_id:
                continue
            if rating_filter is not None and review.get("rating") != int(
                rating_filter
            ):
                continue
            if verified_only and not review.get("verified", False):
                continue
            results.append(deepcopy(review))
        results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return results

    def write_review(
        self,
        product_id: str,
        rating: int,
        title: str,
        body: str,
    ) -> Dict[str, Any]:
        """
        Write a review for a product. The review is automatically marked as
        verified if the current user has purchased the product from Target.

        Args:
            product_id (str): The product being reviewed.
            rating (int): Star rating from 1 (worst) to 5 (best).
            title (str): Review title / headline.
            body (str): Review body text.

        Returns:
            Dict[str, Any]: The created review with:
                review_id (str), product_id (str), user_id (str), rating (int),
                title (str), body (str), verified (bool), created_at (str).
        """
        user_id = self.user_id
        self._require_product(product_id)
        r = int(rating)
        if r < 1 or r > 5:
            raise TargetError(
                "INVALID_RATING",
                "Rating must be between 1 and 5.",
                suggested_action="Provide an integer rating in [1, 5].",
                context={"rating": rating},
            )
        if not title or not title.strip():
            raise TargetError(
                "TITLE_REQUIRED",
                "Review title cannot be empty.",
                suggested_action="Provide a non-empty title.",
                context={},
            )

        verified = False
        for order in self.orders.values():
            if order.get("user_id") == user_id and order.get("status") in (
                "delivered",
                "picked_up",
            ):
                if any(
                    i.get("product_id") == product_id
                    for i in order.get("items", [])
                ):
                    verified = True
                    break

        review_id = self._new_id("review")
        review = {
            "review_id": review_id,
            "product_id": product_id,
            "user_id": user_id,
            "rating": r,
            "title": title.strip(),
            "body": body.strip(),
            "verified": verified,
            "created_at": _utc_now_iso(),
        }
        self.reviews[review_id] = review

        product = self.products.get(product_id, {})
        old_count = product.get("review_count", 0)
        old_rating = product.get("rating", 0.0)
        new_count = old_count + 1
        new_rating = round(((old_rating * old_count) + r) / new_count, 1)
        product["review_count"] = new_count
        product["rating"] = new_rating

        return deepcopy(review)

    # -----------------------------------------------------------------------
    # Account & addresses
    # -----------------------------------------------------------------------

    def list_addresses(self) -> List[Dict[str, Any]]:
        """
        List all delivery addresses saved to the current user's account.

        Returns:
            List[Dict[str, Any]]: Addresses, each with:
                address_id (str), name (str), street (str),
                city (str), state (str), zip (str), is_default (bool).
        """
        user_id = self.user_id
        results: List[Dict[str, Any]] = []
        for addr in self.profile.get("addresses", {}).values():
            results.append(deepcopy(addr))
        return results

    def add_address(
        self,
        name: str,
        street: str,
        city: str,
        state: str,
        zip_code: str,
        is_default: bool = False,
    ) -> Dict[str, Any]:
        """
        Add a new delivery address to the current user's account.

        Args:
            name (str): Label for the address (e.g. "Home", "Work").
            street (str): Street address line.
            city (str): City name.
            state (str): State abbreviation (e.g. "MN", "CA").
            zip_code (str): ZIP code.
            is_default (bool): Whether to set this as the default address.
                Defaults to False.

        Returns:
            Dict[str, Any]: The created address with address_id.
        """
        user_id = self.user_id
        if not street or not city or not state or not zip_code:
            raise TargetError(
                "INVALID_ADDRESS",
                "Street, city, state, and zip_code are required.",
                suggested_action="Provide all required address fields.",
                context={},
            )

        address_id = self._new_id("address")
        addresses = self.profile.setdefault("addresses", {})
        if is_default:
            for addr in addresses.values():
                addr["is_default"] = False

        addr = {
            "address_id": address_id,
            "name": name.strip(),
            "street": street.strip(),
            "city": city.strip(),
            "state": state.strip().upper(),
            "zip": zip_code.strip(),
            "is_default": bool(is_default),
        }
        addresses[address_id] = addr

        return deepcopy(addr)

    def list_payment_methods(self) -> List[Dict[str, Any]]:
        """
        List all payment methods saved to the current user's account.

        Returns:
            List[Dict[str, Any]]: Payment methods, each with:
                method_id (str), type (str -- "credit", "debit",
                "red_card", "gift_card"), last_four (str), is_default (bool),
                gift_card_balance (int | None, cents -- only for gift cards).
        """
        user_id = self.user_id
        results: List[Dict[str, Any]] = []
        for pm in self.profile.get("payment_methods", {}).values():
            result = deepcopy(pm)
            # Only show gift card balance for gift cards
            if result.get("type") != "gift_card":
                result.pop("gift_card_balance", None)
            results.append(result)
        return results

    def add_payment_method(
        self,
        card_type: str,
        card_number: str,
        expiry: Optional[str] = None,
        is_default: bool = False,
        gift_card_balance: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Add a new payment method to the current user's account.

        Args:
            card_type (str): Type of payment -- "credit", "debit", "red_card",
                or "gift_card".
            card_number (str): Full card number; only the last 4 digits are stored.
            expiry (str, optional): Card expiry in MM/YY format (e.g. "08/27").
                Not required for gift cards.
            is_default (bool): Whether to set this as the default payment method.
                Defaults to False.
            gift_card_balance (int, optional): Initial balance in cents for gift
                cards. Required when card_type is "gift_card".

        Returns:
            Dict[str, Any]: The created payment method with method_id.
        """
        user_id = self.user_id
        valid_types = ("credit", "debit", "red_card", "gift_card")
        if card_type not in valid_types:
            raise TargetError(
                "INVALID_CARD_TYPE",
                f"Card type '{card_type}' is not valid. Use one of {valid_types}.",
                suggested_action=f"Use one of: {', '.join(valid_types)}.",
                context={"card_type": card_type},
            )

        if card_type == "gift_card" and gift_card_balance is None:
            raise TargetError(
                "GIFT_CARD_BALANCE_REQUIRED",
                "A gift_card_balance is required when adding a gift card.",
                suggested_action="Provide the gift card balance in cents.",
                context={"card_type": card_type},
            )

        last_four = str(card_number).replace(" ", "").replace("-", "")[-4:]
        payment_id = self._new_id("payment")

        payment_methods = self.profile.setdefault("payment_methods", {})
        if is_default:
            for pm in payment_methods.values():
                pm["is_default"] = False

        pm: Dict[str, Any] = {
            "method_id": payment_id,
            "type": card_type,
            "last_four": last_four,
            "is_default": bool(is_default),
        }
        if expiry:
            pm["expiry"] = expiry
        if card_type == "gift_card":
            pm["gift_card_balance"] = int(gift_card_balance or 0)

        payment_methods[payment_id] = pm

        if card_type == "red_card":
            self.profile.setdefault("membership", {})["red_card"] = True

        return deepcopy(pm)
