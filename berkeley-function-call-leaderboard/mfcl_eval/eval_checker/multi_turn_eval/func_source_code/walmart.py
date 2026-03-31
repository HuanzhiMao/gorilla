"""
Walmart Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Store-aware shopping: fulfillment options, pickup slots, rollback pricing,
  Walmart+ membership, and substitution preferences.
"""

from __future__ import annotations

import copy
import math
import random
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from .server_patch_mixin import PatchableMixin


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


class WalmartError(Exception):
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


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles."""
    r_km = 6371.0
    p = math.pi / 180.0
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r_km * c * 0.621371


# ---------------------------------------------------------------------------
# Walmart API
# ---------------------------------------------------------------------------


DEFAULT_STATE = {
    "random_seed": 5678,
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
    "pickup_slots": {},
}


class WalmartAPI(PatchableMixin):
    """
    In-memory dummy implementation of a Walmart-like retail shopping service.
    Supports product search, store-aware inventory, multiple fulfillment types
    (shipping, pickup, delivery), Walmart+ membership, rollback pricing,
    substitution preferences, and full order lifecycle management.
    """


    def __init__(self):
        self._id_counters = { "cart": 0, "order": 0, "return": 0, "review": 0, "address": 0, "payment": 0, }
        self.profile: Dict[str, Any]
        self.cart: Dict[str, Any]
        self.orders: Dict[str, Dict[str, Any]]
        self.returns: Dict[str, Dict[str, Any]]
        self.reviews: Dict[str, Dict[str, Any]]
        self.products: Dict[str, Dict[str, Any]]
        self.offers: Dict[str, Any]
        self.shipping_options: Dict[str, Any]
        self.stores: Dict[str, Dict[str, Any]]
        self.store_inventory: Dict[str, Dict[str, Any]]
        self.pickup_slots: Dict[str, List[Dict[str, Any]]]
        self._api_description = (
            "This tool belongs to the Walmart shopping system, which allows users to "
            "search products, manage a shopping cart with multiple fulfillment options "
            "(shipping, store pickup, local delivery), place orders, handle returns, "
            "and manage account details including Walmart+ membership benefits."
        )


    def _new_id(self, prefix: str) -> str:
        """Generate the next sequential ID for *prefix* (e.g. ``order_1``)."""
        self._id_counters[prefix] = self._id_counters.get(prefix, 0) + 1
        return f"{prefix}_{self._id_counters[prefix]}"

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
        self.pickup_slots = scenario.get("pickup_slots", DEFAULT_STATE_COPY["pickup_slots"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, WalmartAPI):
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
            raise WalmartError(
                "STORE_NOT_FOUND",
                f"Store '{store_id}' not found.",
                suggested_action="Use set_home_store() or search for a valid store.",
                context={"store_id": store_id},
            )
        return store

    def _require_product(self, product_id: str) -> Dict[str, Any]:
        product = self.products.get(product_id)
        if not product:
            raise WalmartError(
                "PRODUCT_NOT_FOUND",
                f"Product '{product_id}' not found.",
                suggested_action="Use search_products() to find valid product IDs.",
                context={"product_id": product_id},
            )
        return product

    def _require_order(self, order_id: str) -> Dict[str, Any]:
        order = self.orders.get(order_id)
        if not order:
            raise WalmartError(
                "ORDER_NOT_FOUND",
                f"Order '{order_id}' not found.",
                suggested_action="Use get_order_details() with a valid order_id.",
                context={"order_id": order_id},
            )
        return order

    def _get_effective_price(
        self, product: Dict[str, Any], store_id: Optional[str] = None
    ) -> int:
        """Return the effective price in cents for a product, considering rollback
        pricing and store-level price overrides."""
        if store_id and store_id in self.store_inventory:
            inv = self.store_inventory[store_id].get(product.get("product_id", ""), {})
            override = inv.get("price_override")
            if override is not None:
                return int(override)
        if product.get("rollback_price") is not None:
            return int(product["rollback_price"])
        return int(product.get("price", 0))

    def _get_user_cart(self) -> Dict[str, Any]:
        """Return the cart, ensuring it has the expected keys."""
        if "items" not in self.cart:
            self.cart["items"] = []
        if "subtotal" not in self.cart:
            self.cart["subtotal"] = 0
        if "applied_promo" not in self.cart:
            self.cart["applied_promo"] = None
        if "shipping_option" not in self.cart:
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
            price = self._get_effective_price(product, item.get("store_id"))
            total += price * int(item.get("quantity", 1))
        return max(0, total)

    # -----------------------------------------------------------------------
    # Product search & browse
    # -----------------------------------------------------------------------

    def browse_products(
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
            category (str, optional): Filter by product category (e.g. "Electronics",
                "Grocery", "Clothing").
            department (str, optional): Filter by store department (e.g. "Pharmacy",
                "Garden Center", "Auto & Tires").
            min_price (int, optional): Minimum price in cents (inclusive).
            max_price (int, optional): Maximum price in cents (inclusive).
            rating_min (float, optional): Minimum average star rating (e.g. 4.0).
            sort_by (str, optional): Sort order. Supported values: "price_low",
                "price_high", "rating", "name". Defaults to relevance (unsorted).

        Returns:
            List[Dict[str, Any]]: Matching products, each with fields:
                product_id (str), name (str), brand (str), category (str),
                department (str), price (int, cents), rollback_price (int | None,
                cents), rating (float), review_count (int),
                options (List[str]).
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
            price = self._get_effective_price(p)
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
                    "rollback_price": p.get("rollback_price"),
                    "rating": p.get("rating", 0.0),
                    "review_count": p.get("review_count", 0),
                    "options": p.get("options", []),
                }
            )

        if sort_by == "price_low":
            results.sort(key=lambda x: self._get_effective_price({"price": x["price"], "rollback_price": x["rollback_price"], "product_id": x["product_id"]}))
        elif sort_by == "price_high":
            results.sort(key=lambda x: self._get_effective_price({"price": x["price"], "rollback_price": x["rollback_price"], "product_id": x["product_id"]}), reverse=True)
        elif sort_by == "rating":
            results.sort(key=lambda x: float(x.get("rating", 0.0)), reverse=True)
        elif sort_by == "name":
            results.sort(key=lambda x: (x.get("name") or "").lower())

        return results

    def get_item_details(self, product_id: str) -> Dict[str, Any]:
        """
        Retrieve full details for a specific product.

        Args:
            product_id (str): The unique product identifier.

        Returns:
            Dict[str, Any]: Product details including:
                product_id (str), name (str), brand (str), category (str),
                department (str), description (str), price (int, cents),
                rollback_price (int | None, cents), effective_price (int, cents),
                rating (float), review_count (int),
                options (List[str] -- "shipping", "pickup", "delivery").
        """
        product = self._require_product(product_id)
        effective = self._get_effective_price(product)
        return {
            "product_id": product["product_id"],
            "name": product.get("name", ""),
            "brand": product.get("brand", ""),
            "category": product.get("category", ""),
            "department": product.get("department", ""),
            "description": product.get("description", ""),
            "price": product.get("price", 0),
            "rollback_price": product.get("rollback_price"),
            "effective_price": effective,
            "rating": product.get("rating", 0.0),
            "review_count": product.get("review_count", 0),
            "options": product.get("options", []),
        }

    def check_store_availability(
        self, product_id: str, store_id: str
    ) -> Dict[str, Any]:
        """
        Check whether a product is available at a specific Walmart store, including
        aisle location and quantity on hand.

        Args:
            product_id (str): The product to check.
            store_id (str): The store to check inventory at.

        Returns:
            Dict[str, Any]:
                product_id (str), store_id (str), in_stock (bool),
                quantity (int), aisle (str), section (str),
                price_override (int | None, cents -- store-specific price if different).
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
            "section": inv.get("section", ""),
            "price_override": inv.get("price_override"),
        }

    # -----------------------------------------------------------------------
    # Store management
    # -----------------------------------------------------------------------

    def set_home_store(self, store_id: str) -> Dict[str, Any]:
        """
        Set the current user's preferred home store. This affects local pricing, availability
        checks, and default pickup location.

        Args:
            store_id (str): The store to set as the home store.

        Returns:
            Dict[str, Any]:
                user_id (str), home_store_id (str), store_name (str).
        """
        user_id = self.user_id
        store = self._require_store(store_id)
        self.profile["home_store_id"] = store_id
        return {
            "user_id": user_id,
            "home_store_id": store_id,
            "store_name": store.get("name", ""),
        }

    def get_home_store(self) -> Dict[str, Any]:
        """
        Retrieve the current user's configured home store.

        Returns:
            Dict[str, Any]:
                user_id (str), home_store_id (str | None),
                store (Dict | None -- full store details if a home store is set).
        """
        user_id = self.user_id
        store_id = self.profile.get("home_store_id")
        store = self.stores.get(store_id) if store_id else None
        return {
            "user_id": user_id,
            "home_store_id": store_id,
            "store": deepcopy(store) if store else None,
        }

    # -----------------------------------------------------------------------
    # Cart management
    # -----------------------------------------------------------------------

    def add_item_to_basket(
        self,
        product_id: str,
        quantity: int,
        fulfillment_type: Optional[str] = None,
        store_id: Optional[str] = None,
        substitution_pref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a product to the current user's shopping cart.

        Args:
            product_id (str): The product to add.
            quantity (int): Number of units to add; must be >= 1.
            fulfillment_type (str, optional): One of "shipping", "pickup", or
                "delivery". Defaults to "shipping" if not provided.
            store_id (str, optional): Store ID for pickup/delivery fulfillment.
                Required when fulfillment_type is "pickup" or "delivery".
            substitution_pref (str, optional): Substitution preference for
                pickup/delivery orders. One of "allow_substitution",
                "no_substitution", or "contact_me". Defaults to "allow_substitution".

        Returns:
            Dict[str, Any]: Updated cart with fields:
                user_id (str), items (List[Dict]), subtotal (int, cents),
                updated_at (str, ISO-8601).
        """
        user_id = self.user_id
        product = self._require_product(product_id)
        qty = int(quantity)
        if qty < 1:
            raise WalmartError(
                "INVALID_QUANTITY",
                "Quantity must be >= 1.",
                suggested_action="Provide a quantity of at least 1.",
                context={"quantity": quantity},
            )

        ft = fulfillment_type or "shipping"
        if ft not in ("shipping", "pickup", "delivery"):
            raise WalmartError(
                "INVALID_FULFILLMENT_TYPE",
                f"Fulfillment type '{ft}' is not valid. Must be 'shipping', 'pickup', or 'delivery'.",
                suggested_action="Use 'shipping', 'pickup', or 'delivery'.",
                context={"fulfillment_type": ft},
            )

        if ft in ("shipping",) and ft not in product.get("options", []):
            raise WalmartError(
                "FULFILLMENT_NOT_AVAILABLE",
                f"Product '{product_id}' does not support '{ft}' fulfillment.",
                suggested_action=f"Check product options: {product.get('options', [])}.",
                context={"product_id": product_id, "fulfillment_type": ft},
            )

        if ft in ("pickup", "delivery"):
            if not store_id:
                raise WalmartError(
                    "STORE_REQUIRED",
                    f"A store_id is required for '{ft}' fulfillment.",
                    suggested_action="Provide a store_id or use set_home_store() first.",
                    context={"fulfillment_type": ft},
                )
            self._require_store(store_id)
            inv = self.store_inventory.get(store_id, {}).get(product_id, {})
            if not inv.get("in_stock", False):
                raise WalmartError(
                    "OUT_OF_STOCK_AT_STORE",
                    f"Product '{product_id}' is out of stock at store '{store_id}'.",
                    suggested_action="Check availability at another store or use 'shipping' fulfillment.",
                    context={"product_id": product_id, "store_id": store_id},
                )
            available_qty = inv.get("quantity", 0)
            if qty > available_qty:
                raise WalmartError(
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

        sub_pref = substitution_pref or "allow_substitution"
        if sub_pref not in ("allow_substitution", "no_substitution", "contact_me"):
            raise WalmartError(
                "INVALID_SUBSTITUTION_PREF",
                f"Substitution preference '{sub_pref}' is not valid.",
                suggested_action="Use 'allow_substitution', 'no_substitution', or 'contact_me'.",
                context={"substitution_pref": sub_pref},
            )

        cart = self._get_user_cart()
        line_id = f"wli_{len(cart['items']) + 1}"
        cart["items"].append(
            {
                "line_item_id": line_id,
                "product_id": product_id,
                "quantity": qty,
                "fulfillment_type": ft,
                "store_id": store_id,
                "substitution_pref": sub_pref if ft in ("pickup", "delivery") else None,
            }
        )
        cart["updated_at"] = _utc_now_iso()
        cart["subtotal"] = self._compute_cart_subtotal()
        return deepcopy(cart)

    def update_basket_item(
        self,
        line_item_id: str,
        quantity: Optional[int] = None,
        fulfillment_type: Optional[str] = None,
        store_id: Optional[str] = None,
        substitution_pref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing item in the current user's cart.

        Args:
            line_item_id (str): The line item to update (from get_cart()).
            quantity (int, optional): New quantity; must be >= 1.
                Use remove_from_cart() to delete an item.
            fulfillment_type (str, optional): New fulfillment type.
            store_id (str, optional): New store for pickup/delivery.
            substitution_pref (str, optional): New substitution preference.

        Returns:
            Dict[str, Any]: Updated cart object.
        """
        user_id = self.user_id
        cart = self._get_user_cart()
        item = next(
            (i for i in cart["items"] if i.get("line_item_id") == line_item_id), None
        )
        if not item:
            raise WalmartError(
                "LINE_ITEM_NOT_FOUND",
                f"Line item '{line_item_id}' not found in cart.",
                suggested_action="Call get_cart() to list valid line_item_id values.",
                context={"user_id": user_id, "line_item_id": line_item_id},
            )

        if quantity is not None:
            q = int(quantity)
            if q < 1:
                raise WalmartError(
                    "INVALID_QUANTITY",
                    "Quantity must be >= 1. Use remove_from_cart() to remove.",
                    suggested_action="Provide quantity >= 1 or call remove_from_cart().",
                    context={"quantity": quantity},
                )
            item["quantity"] = q

        if fulfillment_type is not None:
            if fulfillment_type not in ("shipping", "pickup", "delivery"):
                raise WalmartError(
                    "INVALID_FULFILLMENT_TYPE",
                    f"Fulfillment type '{fulfillment_type}' is not valid.",
                    suggested_action="Use 'shipping', 'pickup', or 'delivery'.",
                    context={"fulfillment_type": fulfillment_type},
                )
            item["fulfillment_type"] = fulfillment_type

        if store_id is not None:
            self._require_store(store_id)
            item["store_id"] = store_id

        if substitution_pref is not None:
            if substitution_pref not in (
                "allow_substitution",
                "no_substitution",
                "contact_me",
            ):
                raise WalmartError(
                    "INVALID_SUBSTITUTION_PREF",
                    f"Substitution preference '{substitution_pref}' is not valid.",
                    suggested_action="Use 'allow_substitution', 'no_substitution', or 'contact_me'.",
                    context={"substitution_pref": substitution_pref},
                )
            item["substitution_pref"] = substitution_pref

        cart["updated_at"] = _utc_now_iso()
        cart["subtotal"] = self._compute_cart_subtotal()
        return deepcopy(cart)

    def remove_item_from_basket(self, line_item_id: str) -> Dict[str, Any]:
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
            raise WalmartError(
                "LINE_ITEM_NOT_FOUND",
                f"Line item '{line_item_id}' not found in cart.",
                suggested_action="Call get_cart() to list valid line_item_id values.",
                context={"user_id": user_id, "line_item_id": line_item_id},
            )
        cart["updated_at"] = _utc_now_iso()
        cart["subtotal"] = self._compute_cart_subtotal()
        return deepcopy(cart)

    def get_basket(self) -> Dict[str, Any]:
        """
        Retrieve the current state of the current user's shopping cart with a freshly
        computed subtotal.

        Returns:
            Dict[str, Any]: Cart object including:
                user_id (str), items (List[Dict] -- each with line_item_id, product_id,
                quantity, fulfillment_type, store_id, substitution_pref),
                subtotal (int, cents), updated_at (str, ISO-8601).
        """
        user_id = self.user_id
        cart = self._get_user_cart()
        cart["subtotal"] = self._compute_cart_subtotal()
        return deepcopy(cart)

    # -----------------------------------------------------------------------
    # Fulfillment & pickup
    # -----------------------------------------------------------------------

    def choose_fulfillment(
        self, fulfillment_type: str, store_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Set a default fulfillment type for all items in the cart. Individual items
        can still be overridden via update_cart_item().

        Args:
            fulfillment_type (str): One of "shipping", "pickup", or "delivery".
            store_id (str, optional): Required for "pickup" or "delivery".

        Returns:
            Dict[str, Any]: Updated cart with all items set to the chosen
                fulfillment type. Items that do not support the chosen type are
                flagged in a warnings list.
        """
        user_id = self.user_id
        if fulfillment_type not in ("shipping", "pickup", "delivery"):
            raise WalmartError(
                "INVALID_FULFILLMENT_TYPE",
                f"Fulfillment type '{fulfillment_type}' is not valid.",
                suggested_action="Use 'shipping', 'pickup', or 'delivery'.",
                context={"fulfillment_type": fulfillment_type},
            )
        if fulfillment_type in ("pickup", "delivery") and not store_id:
            raise WalmartError(
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
        cart["updated_at"] = _utc_now_iso()
        cart["subtotal"] = self._compute_cart_subtotal()
        return {"cart": deepcopy(cart), "warnings": warnings}

    def get_pickup_slots(self, store_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve available pickup time slots for a given store.

        Args:
            store_id (str): The store to check pickup slots for.

        Returns:
            List[Dict[str, Any]]: Available pickup slots, each with:
                slot_id (str), date (str, YYYY-MM-DD), start_time (str, HH:MM),
                end_time (str, HH:MM), available (bool).
        """
        self._require_store(store_id)
        slots = self.pickup_slots.get(store_id, [])
        return deepcopy(slots)

    def reserve_pickup_slot(
        self, store_id: str, slot_id: str
    ) -> Dict[str, Any]:
        """
        Reserve a pickup time slot for the current user's order at a specific store.

        Args:
            store_id (str): The store where pickup will occur.
            slot_id (str): The specific time slot to reserve (from get_pickup_slots()).

        Returns:
            Dict[str, Any]:
                reserved (bool), slot_id (str), store_id (str),
                date (str), start_time (str), end_time (str).
        """
        user_id = self.user_id
        self._require_store(store_id)
        slots = self.pickup_slots.get(store_id, [])
        slot = next((s for s in slots if s.get("slot_id") == slot_id), None)
        if not slot:
            raise WalmartError(
                "SLOT_NOT_FOUND",
                f"Pickup slot '{slot_id}' not found at store '{store_id}'.",
                suggested_action="Call get_pickup_slots() to see available slots.",
                context={"store_id": store_id, "slot_id": slot_id},
            )
        if not slot.get("available", False):
            raise WalmartError(
                "SLOT_UNAVAILABLE",
                f"Pickup slot '{slot_id}' is no longer available.",
                suggested_action="Choose a different available slot.",
                context={"slot_id": slot_id},
            )
        slot["available"] = False
        slot["reserved_by"] = user_id
        return {
            "reserved": True,
            "slot_id": slot_id,
            "store_id": store_id,
            "date": slot.get("date", ""),
            "start_time": slot.get("start_time", ""),
            "end_time": slot.get("end_time", ""),
        }

    # -----------------------------------------------------------------------
    # Checkout & orders
    # -----------------------------------------------------------------------

    def redeem_promo_code(self, promo_code: str) -> Dict[str, Any]:
        """
        Apply a promotional code to the current user's cart. Validates eligibility without
        consuming usage -- usage is consumed on place_order().

        Args:
            promo_code (str): The promotional code to apply.

        Returns:
            Dict[str, Any]:
                valid (bool), reason (str -- "OK" or an error code such as
                PROMO_NOT_FOUND, MIN_ORDER_NOT_MET, PROMO_EXPIRED,
                DEPARTMENT_NOT_ELIGIBLE), discount_preview (int, cents -- estimated
                discount amount, 0 if invalid).
        """
        user_id = self.user_id
        cart = self._get_user_cart()
        subtotal = self._compute_cart_subtotal()

        promo = self.profile["promos"].get((promo_code or "").upper())
        if not promo:
            for code, p in self.profile["promos"].items():
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

        applicable_depts = promo.get("applicable_departments")
        if applicable_depts:
            cart_depts = set()
            for item in cart.get("items", []):
                product = self.products.get(item["product_id"], {})
                dept = product.get("department", "")
                if dept:
                    cart_depts.add(dept.lower())
            valid_depts = {d.lower() for d in applicable_depts}
            if not cart_depts.intersection(valid_depts):
                return {
                    "valid": False,
                    "reason": "DEPARTMENT_NOT_ELIGIBLE",
                    "discount_preview": 0,
                }

        discount_type = promo.get("discount_type", "percent")
        discount_value = int(promo.get("discount_value", 0))
        if discount_type == "percent":
            discount_preview = int(round(subtotal * (discount_value / 100.0)))
        elif discount_type == "flat":
            discount_preview = min(discount_value, subtotal)
        elif discount_type == "free_shipping":
            discount_preview = 0  # Actual savings computed at checkout
        else:
            discount_preview = 0

        cart["applied_promo_code"] = promo_code
        cart["updated_at"] = _utc_now_iso()
        return {
            "valid": True,
            "reason": "OK",
            "discount_preview": discount_preview,
        }

    def submit_order(
        self,
        payment_method_id: str,
        address_id: Optional[str] = None,
        pickup_slot_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Place an order from the current user's cart. Validates payment, computes
        pricing with tax and any applicable Walmart+ benefits, and creates the order.

        Args:
            payment_method_id (str): Payment method to charge
                (from list_payment_methods()).
            address_id (str, optional): Delivery address for shipping/delivery
                fulfillment (from list_addresses()). Required if any item uses
                "shipping" or "delivery" fulfillment.
            pickup_slot_id (str, optional): Reserved pickup slot ID for pickup orders.

        Returns:
            Dict[str, Any]:
                order_id (str), status (str), items (List), subtotal (int, cents),
                tax (int, cents), shipping_fee (int, cents), discount (int, cents),
                total (int, cents), fulfillment_type (str),
                estimated_delivery (str | None), placed_at (str, ISO-8601).
        """
        user_id = self.user_id
        cart = self._get_user_cart()

        if not cart.get("items"):
            raise WalmartError(
                "EMPTY_CART",
                "Cannot place an order with an empty cart.",
                suggested_action="Add items to your cart before placing an order.",
                context={"user_id": user_id},
            )

        # Validate payment method
        pm = self.profile["payment_methods"].get(payment_method_id)
        if not pm:
            raise WalmartError(
                "PAYMENT_METHOD_NOT_FOUND",
                f"Payment method '{payment_method_id}' not found for user.",
                suggested_action="Call list_payment_methods() to get valid method IDs.",
                context={"user_id": user_id, "payment_method_id": payment_method_id},
            )

        # Determine primary fulfillment type from cart items
        fulfillment_types = set(
            i.get("fulfillment_type", "shipping") for i in cart["items"]
        )
        needs_address = bool(fulfillment_types.intersection({"shipping", "delivery"}))
        if needs_address:
            if not address_id:
                raise WalmartError(
                    "ADDRESS_REQUIRED",
                    "A delivery address is required for shipping or delivery orders.",
                    suggested_action="Provide an address_id from list_addresses().",
                    context={"user_id": user_id},
                )
            addr = self.profile["addresses"].get(address_id)
            if not addr:
                raise WalmartError(
                    "ADDRESS_NOT_FOUND",
                    f"Address '{address_id}' not found for user.",
                    suggested_action="Call list_addresses() to get valid address IDs.",
                    context={"user_id": user_id, "address_id": address_id},
                )

        subtotal = self._compute_cart_subtotal()
        tax = int(round(subtotal * 0.0825))  # 8.25% sales tax

        # Shipping fee
        is_walmart_plus = self.profile.get("membership", {}).get("walmart_plus", False)
        shipping_fee = 0
        if "shipping" in fulfillment_types:
            if subtotal >= 3500:  # Free shipping over $35
                shipping_fee = 0
            elif is_walmart_plus:
                shipping_fee = 0  # Free shipping for Walmart+ members
            else:
                shipping_fee = 599  # $5.99 standard shipping

        # Apply promo discount
        discount = 0
        promo_code = cart.get("applied_promo_code")
        if promo_code:
            promo = self.profile["promos"].get((promo_code or "").upper())
            if not promo:
                for code, p in self.profile["promos"].items():
                    if code.upper() == (promo_code or "").upper():
                        promo = p
                        break
            if promo:
                dtype = promo.get("discount_type", "percent")
                dval = int(promo.get("discount_value", 0))
                if dtype == "percent":
                    discount = int(round(subtotal * (dval / 100.0)))
                elif dtype == "flat":
                    discount = min(dval, subtotal)
                elif dtype == "free_shipping":
                    discount = shipping_fee
                    shipping_fee = 0

        total = max(0, subtotal + tax + shipping_fee - discount)

        primary_ft = "shipping"
        if "pickup" in fulfillment_types:
            primary_ft = "pickup"
        elif "delivery" in fulfillment_types:
            primary_ft = "delivery"

        order_id = self._new_id("order")
        now = _utc_now_iso()

        # Determine store_id for pickup/delivery
        store_id = None
        for item in cart["items"]:
            if item.get("store_id"):
                store_id = item["store_id"]
                break

        estimated_delivery = None
        if primary_ft == "shipping":
            if is_walmart_plus:
                estimated_delivery = "2-3 business days"
            else:
                estimated_delivery = "5-7 business days"
        elif primary_ft == "delivery":
            estimated_delivery = "Same day or next day"

        self.orders[order_id] = {
            "order_id": order_id,
            "user_id": user_id,
            "items": deepcopy(cart["items"]),
            "status": "confirmed",
            "fulfillment_type": primary_ft,
            "store_id": store_id,
            "address_id": address_id,
            "pickup_slot_id": pickup_slot_id,
            "payment_method_id": payment_method_id,
            "subtotal": subtotal,
            "tax": tax,
            "shipping_fee": shipping_fee,
            "discount": discount,
            "total": total,
            "promo_code": promo_code,
            "tracking": None,
            "placed_at": now,
            "updated_at": now,
            "estimated_delivery": estimated_delivery,
        }

        # Clear the cart
        self.cart["items"] = []
        self.cart["subtotal"] = 0
        self.cart["applied_promo"] = None
        self.cart["shipping_option"] = None

        # Reduce store inventory for pickup/delivery items
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
            "discount": discount,
            "total": total,
            "fulfillment_type": primary_ft,
            "estimated_delivery": estimated_delivery,
            "placed_at": now,
        }

    # -----------------------------------------------------------------------
    # Order management
    # -----------------------------------------------------------------------

    def get_purchase_details(self, order_id: str) -> Dict[str, Any]:
        """
        Retrieve full details for an order. The order must belong to the current user.

        Args:
            order_id (str): The order to retrieve.

        Returns:
            Dict[str, Any]: Order details including:
                order_id (str), user_id (str), items (List), status (str -- one of
                "confirmed", "processing", "shipped", "ready_for_pickup",
                "picked_up", "delivered", "canceled", "returned"),
                fulfillment_type (str), store_id (str | None), tracking (str | None),
                subtotal (int), tax (int), shipping_fee (int), discount (int),
                total (int), estimated_delivery (str | None),
                placed_at (str), updated_at (str).
        """
        order = self._require_order(order_id)
        if order.get("user_id") != self.user_id:
            raise PermissionError("You do not have permission to access this resource.")
        return deepcopy(order)

    def cancel_purchase(self, order_id: str, reason: str) -> Dict[str, Any]:
        """
        Cancel an order. Only orders in "confirmed" or "processing" status can
        be canceled. The order must belong to the current user.

        Args:
            order_id (str): The order to cancel.
            reason (str): Short description of why the order is being canceled.

        Returns:
            Dict[str, Any]:
                order_id (str), canceled (bool), status (str),
                refund_amount (int, cents -- full refund amount if canceled).
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
                "message": f"Cannot cancel order in '{status}' status. Only 'confirmed' or 'processing' orders can be canceled.",
            }

        refund = order.get("total", 0)
        order["status"] = "canceled"
        order["updated_at"] = _utc_now_iso()
        order["cancel_reason"] = reason

        # Restore store inventory for pickup/delivery items
        for item in order.get("items", []):
            sid = item.get("store_id")
            pid = item["product_id"]
            if sid and sid in self.store_inventory:
                inv = self.store_inventory[sid].get(pid, {})
                if inv:
                    inv["quantity"] = inv.get("quantity", 0) + item["quantity"]
                    inv["in_stock"] = True

        return {
            "order_id": order_id,
            "canceled": True,
            "status": "canceled",
            "refund_amount": refund,
        }

    def initiate_return(
        self,
        order_id: str,
        product_id: str,
        reason: str,
        return_method: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initiate a return for a product from a completed order. Walmart allows
        returns to any store regardless of how the item was purchased. The order
        must belong to the current user.

        Args:
            order_id (str): The order containing the product to return.
            product_id (str): The specific product to return.
            reason (str): Reason for the return (e.g. "defective", "wrong_item",
                "changed_mind", "not_as_described").
            return_method (str, optional): How the return is handled. One of
                "store" (return to any Walmart store) or "mail" (ship it back).
                Defaults to "store".

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
            raise WalmartError(
                "ORDER_NOT_ELIGIBLE_FOR_RETURN",
                f"Order in '{order.get('status')}' status cannot be returned.",
                suggested_action="Only delivered, picked up, or shipped orders can be returned.",
                context={"order_id": order_id, "status": order.get("status")},
            )

        # Find the item in the order
        order_item = next(
            (i for i in order.get("items", []) if i.get("product_id") == product_id),
            None,
        )
        if not order_item:
            raise WalmartError(
                "PRODUCT_NOT_IN_ORDER",
                f"Product '{product_id}' not found in order '{order_id}'.",
                suggested_action="Check order items via get_order_details().",
                context={"order_id": order_id, "product_id": product_id},
            )

        method = return_method or "store"
        if method not in ("store", "mail"):
            raise WalmartError(
                "INVALID_RETURN_METHOD",
                f"Return method '{method}' is not valid. Use 'store' or 'mail'.",
                suggested_action="Use 'store' or 'mail'.",
                context={"return_method": method},
            )

        product = self.products.get(product_id, {})
        refund_amount = self._get_effective_price(
            product, order_item.get("store_id")
        ) * order_item.get("quantity", 1)

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

    def get_item_reviews(
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

    def submit_review(
        self,
        product_id: str,
        rating: int,
        title: str,
        body: str,
    ) -> Dict[str, Any]:
        """
        Write a review for a product. The review is automatically marked as
        verified if the current user has purchased the product.

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
            raise WalmartError(
                "INVALID_RATING",
                "Rating must be between 1 and 5.",
                suggested_action="Provide an integer rating in [1, 5].",
                context={"rating": rating},
            )
        if not title or not title.strip():
            raise WalmartError(
                "TITLE_REQUIRED",
                "Review title cannot be empty.",
                suggested_action="Provide a non-empty title.",
                context={},
            )

        # Check if user purchased this product (for verified badge)
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

        # Update product rating
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

    def list_shipping_addresses(self) -> List[Dict[str, Any]]:
        """
        List all delivery addresses saved to the current user's account.

        Returns:
            List[Dict[str, Any]]: Addresses, each with:
                address_id (str), user_id (str), name (str), street (str),
                city (str), state (str), zip (str), is_default (bool).
        """
        results: List[Dict[str, Any]] = []
        for addr in self.profile["addresses"].values():
            results.append(deepcopy(addr))
        return results

    def add_shipping_address(
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
            state (str): State abbreviation (e.g. "TX", "CA").
            zip_code (str): ZIP code.
            is_default (bool): Whether to set this as the default address.
                Defaults to False.

        Returns:
            Dict[str, Any]: The created address with address_id.
        """
        user_id = self.user_id
        if not street or not city or not state or not zip_code:
            raise WalmartError(
                "INVALID_ADDRESS",
                "Street, city, state, and zip_code are required.",
                suggested_action="Provide all required address fields.",
                context={},
            )

        address_id = self._new_id("address")
        if is_default:
            # Unset other defaults
            for addr in self.profile["addresses"].values():
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
        self.profile["addresses"][address_id] = addr

        return deepcopy(addr)

    def list_wallet_payments(self) -> List[Dict[str, Any]]:
        """
        List all payment methods saved to the current user's account.

        Returns:
            List[Dict[str, Any]]: Payment methods, each with:
                method_id (str), user_id (str), type (str -- "credit", "debit"),
                last_four (str), is_default (bool).
        """
        results: List[Dict[str, Any]] = []
        for pm in self.profile["payment_methods"].values():
            results.append(deepcopy(pm))
        return results

    def add_wallet_payment(
        self,
        card_type: str,
        card_number: str,
        expiry: str,
        is_default: bool = False,
    ) -> Dict[str, Any]:
        """
        Add a new payment method to the current user's account.

        Args:
            card_type (str): Type of card -- "credit" or "debit".
            card_number (str): Full card number; only the last 4 digits are stored.
            expiry (str): Card expiry in MM/YY format (e.g. "08/27").
            is_default (bool): Whether to set this as the default payment method.
                Defaults to False.

        Returns:
            Dict[str, Any]: The created payment method with method_id.
        """
        user_id = self.user_id
        if card_type not in ("credit", "debit"):
            raise WalmartError(
                "INVALID_CARD_TYPE",
                f"Card type '{card_type}' is not valid. Use 'credit' or 'debit'.",
                suggested_action="Use 'credit' or 'debit'.",
                context={"card_type": card_type},
            )

        last_four = str(card_number).replace(" ", "").replace("-", "")[-4:]
        payment_id = self._new_id("payment")

        if is_default:
            for pm in self.profile["payment_methods"].values():
                pm["is_default"] = False

        pm = {
            "method_id": payment_id,
            "type": card_type,
            "last_four": last_four,
            "expiry": expiry,
            "is_default": bool(is_default),
        }
        self.profile["payment_methods"][payment_id] = pm

        return deepcopy(pm)
