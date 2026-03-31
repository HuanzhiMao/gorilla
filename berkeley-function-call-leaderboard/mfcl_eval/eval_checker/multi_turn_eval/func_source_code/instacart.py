"""
Instacart Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Store-based grocery shopping: user selects a store, then shops that store's inventory.
- Personal-shopper model with replacement preferences and delivery windows.
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


class InstacartError(Exception):
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
    "delivery_windows": {},
    "shoppers": {},
    "issues": {},
}


class InstacartAPI(PatchableMixin):
    """
    In-memory dummy implementation of an Instacart-like grocery delivery service.

    The store-based shopping model requires users to select a store first, then
    browse and add products from that store's inventory. A personal shopper picks
    and delivers the items within a chosen delivery window.
    """


    def __init__(self):
        self._id_counters = { "cart": 0, "order": 0, "address": 0, "payment": 0, "issue": 0, }
        self.profile: Dict[str, Any]
        self.cart: Dict[str, Any]
        self.orders: Dict[str, Dict[str, Any]]
        self.returns: Dict[str, Any]
        self.reviews: Dict[str, Any]
        self.products: Dict[str, Dict[str, Any]]
        self.offers: Dict[str, Any]
        self.shipping_options: Dict[str, Any]
        self.stores: Dict[str, Dict[str, Any]]
        self.store_inventory: Dict[str, Dict[str, Any]]
        self.delivery_windows: Dict[str, List[Dict[str, Any]]]
        self.shoppers: Dict[str, Dict[str, Any]]
        self.issues: Dict[str, Dict[str, Any]]
        self._api_description = (
            "This tool belongs to the Instacart grocery delivery system, which allows "
            "users to search stores, browse store-specific product inventories, manage "
            "carts with replacement preferences, select delivery windows, and place "
            "orders fulfilled by personal shoppers."
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
        self.delivery_windows = scenario.get("delivery_windows", DEFAULT_STATE_COPY["delivery_windows"])
        self.shoppers = scenario.get("shoppers", DEFAULT_STATE_COPY["shoppers"])
        self.issues = scenario.get("issues", DEFAULT_STATE_COPY["issues"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, InstacartAPI):
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
    # Internal mechanics
    # -----------------------------------------------------------------------

    def _require_store(self, store_id: str) -> Dict[str, Any]:
        store = self.stores.get(store_id)
        if not store:
            raise InstacartError(
                "STORE_NOT_FOUND",
                f"Store '{store_id}' not found.",
                suggested_action="Use search_stores() to find a valid store_id.",
                context={"store_id": store_id},
            )
        return store

    def _require_cart(self, cart_id: str) -> Dict[str, Any]:
        if not self.cart:
            raise InstacartError(
                "CART_NOT_FOUND",
                f"Cart '{cart_id}' not found.",
                suggested_action="Create the cart first with create_cart().",
                context={"cart_id": cart_id},
            )
        return self.cart

    def _require_order(self, order_id: str) -> Dict[str, Any]:
        order = self.orders.get(order_id)
        if not order:
            raise InstacartError(
                "ORDER_NOT_FOUND",
                f"Order '{order_id}' not found.",
                suggested_action="Use get_order_status() with a valid order_id.",
                context={"order_id": order_id},
            )
        return order

    def _get_store_product(self, store_id: str, product_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Return (product_record, inventory_entry) for a product in a store."""
        product = self.products.get(product_id)
        if not product:
            raise InstacartError(
                "PRODUCT_NOT_FOUND",
                f"Product '{product_id}' not found.",
                suggested_action="Use search_products() to find valid product_ids.",
                context={"product_id": product_id},
            )
        inv = self.store_inventory.get(store_id, {}).get(product_id)
        if not inv:
            raise InstacartError(
                "PRODUCT_NOT_IN_STORE",
                f"Product '{product_id}' is not available at store '{store_id}'.",
                suggested_action="Search for this product at a different store.",
                context={"store_id": store_id, "product_id": product_id},
            )
        return product, inv

    def _compute_cart_subtotal(self, cart: Dict[str, Any]) -> int:
        """Compute the subtotal in cents for all items in the cart."""
        store_id = cart["store_id"]
        total = 0
        for item in cart["items"]:
            inv = self.store_inventory.get(store_id, {}).get(item["product_id"])
            if not inv or inv.get("stock_level") == "out":
                continue
            price = int(inv.get("price", 0))
            total += price * int(item.get("quantity", 1))
        return max(0, total)

    def _pick_shopper(self) -> Optional[Dict[str, Any]]:
        """Assign an idle shopper, if available."""
        candidates = [s for s in self.shoppers.values() if s.get("active_order_id") is None]
        if not candidates:
            return None
        return self._rng.choice(candidates)

    # -----------------------------------------------------------------------
    # Store discovery
    # -----------------------------------------------------------------------

    def search_stores(
        self,
        location: Dict[str, float],
        query: str = "",
        store_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for nearby stores matching an optional text query and store type filter.

        Args:
            location (Dict[str, float]): Caller's coordinates as {"lat": float, "lng": float}.
            query (str): Free-text search matched against store name. Empty string matches all.
            store_type (str, optional): Filter by store type, e.g. "grocery", "pharmacy",
                "convenience", "wholesale". None returns all types.

        Returns:
            List[Dict[str, Any]]: Matching stores, each with fields:
                store_id (str), name (str), store_type (str), rating (float),
                is_open (bool), delivery_fee (int, cents), min_order (int, cents),
                distance_miles (float).
        """
        user_lat = float(location.get("lat", 0))
        user_lng = float(location.get("lng", 0))
        results = []
        for s in self.stores.values():
            if not _matches_query(s.get("name", ""), query):
                continue
            if store_type and s.get("store_type") != store_type:
                continue
            slat = float(s.get("lat", 0))
            slng = float(s.get("lng", 0))
            dist = _haversine_miles(user_lat, user_lng, slat, slng)
            results.append({
                "store_id": s["store_id"],
                "name": s["name"],
                "store_type": s.get("store_type", "grocery"),
                "rating": s.get("rating", 0.0),
                "is_open": s.get("is_open", False),
                "delivery_fee": s.get("delivery_fee", 0),
                "min_order": s.get("min_order", 0),
                "distance_miles": round(dist, 2),
            })
        results.sort(key=lambda x: x["distance_miles"])
        return results

    def get_store_details(self, store_id: str) -> Dict[str, Any]:
        """
        Retrieve full details for a specific store including hours, fees, and logo.

        Args:
            store_id (str): The unique store identifier.

        Returns:
            Dict[str, Any]:
                store_id (str), name (str), address (str), logo_url (str),
                store_type (str), rating (float), is_open (bool),
                delivery_fee (int, cents), min_order (int, cents),
                hours (Dict[str, str]): Operating hours by day.
        """
        store = self._require_store(store_id)
        return {
            "store_id": store["store_id"],
            "name": store["name"],
            "address": store.get("address", ""),
            "logo_url": store.get("logo_url", ""),
            "store_type": store.get("store_type", "grocery"),
            "rating": store.get("rating", 0.0),
            "is_open": store.get("is_open", False),
            "delivery_fee": store.get("delivery_fee", 0),
            "min_order": store.get("min_order", 0),
            "hours": deepcopy(store.get("hours", {})),
        }

    # -----------------------------------------------------------------------
    # Product search & browse
    # -----------------------------------------------------------------------

    def search_grocery_items(
        self,
        store_id: str,
        query: str = "",
        category: Optional[str] = None,
        in_stock_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Search for products within a specific store's inventory.

        Args:
            store_id (str): The store to search within.
            query (str): Free-text search matched against product name and brand.
                Empty string matches all products in the store.
            category (str, optional): Filter by product category, e.g. "dairy",
                "produce", "bakery", "beverages". None returns all categories.
            in_stock_only (bool): If True (default), exclude out-of-stock products.

        Returns:
            List[Dict[str, Any]]: Matching products, each with fields:
                product_id (str), name (str), brand (str), category (str),
                price (int, cents — store-specific), stock_level (str — "high", "low", "out"),
                unit (str), aisle (str).
        """
        self._require_store(store_id)
        inv_map = self.store_inventory.get(store_id, {})
        results = []
        for product_id, inv in inv_map.items():
            product = self.products.get(product_id)
            if not product:
                continue
            if in_stock_only and inv.get("stock_level") == "out":
                continue
            name = product.get("name", "")
            brand = product.get("brand", "")
            if not _matches_query(name, query) and not _matches_query(brand, query):
                continue
            if category and product.get("category") != category:
                continue
            results.append({
                "product_id": product_id,
                "name": name,
                "brand": brand,
                "category": product.get("category", ""),
                "price": inv.get("price", 0),
                "stock_level": inv.get("stock_level", "high"),
                "unit": product.get("unit", "each"),
                "aisle": inv.get("aisle", ""),
            })
        return results

    def get_grocery_details(self, store_id: str, product_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific product at a specific store, including
        store-specific pricing and stock level.

        Args:
            store_id (str): The store context for pricing and availability.
            product_id (str): The product to look up.

        Returns:
            Dict[str, Any]:
                product_id (str), name (str), brand (str), category (str),
                image_url (str), unit (str), per_unit_price (int, cents),
                price (int, cents — store-specific), stock_level (str),
                aisle (str), in_stock (bool).
        """
        product, inv = self._get_store_product(store_id, product_id)
        return {
            "product_id": product_id,
            "name": product.get("name", ""),
            "brand": product.get("brand", ""),
            "category": product.get("category", ""),
            "image_url": product.get("image_url", ""),
            "unit": product.get("unit", "each"),
            "per_unit_price": product.get("per_unit_price", 0),
            "price": inv.get("price", 0),
            "stock_level": inv.get("stock_level", "high"),
            "aisle": inv.get("aisle", ""),
            "in_stock": inv.get("stock_level", "high") != "out",
        }

    # -----------------------------------------------------------------------
    # Cart management
    # -----------------------------------------------------------------------

    def create_cart(self, store_id: str) -> str:
        """
        Create a new empty cart for the current user at a specific store. Each cart is tied
        to exactly one store. A user may have multiple carts for different stores.

        Args:
            store_id (str): The store to shop from. Must be currently open.

        Returns:
            str: The new cart_id.
        """
        store = self._require_store(store_id)
        if not store.get("is_open", False):
            raise InstacartError(
                "STORE_CLOSED",
                f"Store '{store_id}' is currently closed.",
                suggested_action="Choose another store or try again during open hours.",
                context={"store_id": store_id},
            )
        cart_id = self._new_id("cart")
        now = _utc_now_iso()
        self.cart = {
            "cart_id": cart_id,
            "store_id": store_id,
            "items": [],
            "created_at": now,
            "updated_at": now,
            "applied_coupon": None,
        }
        return cart_id

    def add_grocery_item(
        self,
        cart_id: str,
        product_id: str,
        quantity: int,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a product to the cart. The product must be in stock at the cart's store.

        Args:
            cart_id (str): Target cart.
            product_id (str): Product to add (from search_products() or get_product_details()).
            quantity (int): Number of units; must be >= 1.
            notes (str, optional): Special instructions for the shopper (e.g. "pick firm ones").

        Returns:
            Dict[str, Any]: Updated cart object including all items and computed subtotal.
        """
        cart = self._require_cart(cart_id)
        product, inv = self._get_store_product(cart["store_id"], product_id)
        if inv.get("stock_level") == "out":
            raise InstacartError(
                "PRODUCT_OUT_OF_STOCK",
                f"Product '{product_id}' is out of stock at this store.",
                suggested_action="Choose a different product or check another store.",
                context={"cart_id": cart_id, "product_id": product_id},
            )
        qty = int(quantity)
        if qty < 1:
            raise InstacartError(
                "INVALID_QUANTITY",
                "Quantity must be >= 1.",
                suggested_action="Provide a quantity of at least 1.",
                context={"quantity": quantity},
            )
        # Check if product already in cart; if so, update quantity
        for item in cart["items"]:
            if item["product_id"] == product_id:
                item["quantity"] += qty
                if notes is not None:
                    item["notes"] = notes
                cart["updated_at"] = _utc_now_iso()
                cart["subtotal"] = self._compute_cart_subtotal(cart)
                return deepcopy(cart)
        cart["items"].append({
            "product_id": product_id,
            "quantity": qty,
            "replacement_pref": "best_match",
            "notes": notes or "",
        })
        cart["updated_at"] = _utc_now_iso()
        cart["subtotal"] = self._compute_cart_subtotal(cart)
        return deepcopy(cart)

    def update_grocery_quantity(
        self,
        cart_id: str,
        product_id: str,
        quantity: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update the quantity or notes for an item already in the cart.

        Args:
            cart_id (str): Target cart.
            product_id (str): The product to update (must already be in the cart).
            quantity (int, optional): New quantity; must be >= 1.
                Use remove_from_cart() to delete an item entirely.
            notes (str, optional): Updated special instructions for the shopper.

        Returns:
            Dict[str, Any]: Updated cart object.
        """
        cart = self._require_cart(cart_id)
        found = None
        for item in cart["items"]:
            if item["product_id"] == product_id:
                found = item
                break
        if not found:
            raise InstacartError(
                "ITEM_NOT_IN_CART",
                f"Product '{product_id}' is not in cart '{cart_id}'.",
                suggested_action="Call get_cart() to see current items.",
                context={"cart_id": cart_id, "product_id": product_id},
            )
        if quantity is not None:
            q = int(quantity)
            if q < 1:
                raise InstacartError(
                    "INVALID_QUANTITY",
                    "Quantity must be >= 1. Use remove_from_cart() to remove an item.",
                    suggested_action="Provide quantity >= 1 or call remove_from_cart().",
                    context={"quantity": quantity},
                )
            found["quantity"] = q
        if notes is not None:
            found["notes"] = notes
        cart["updated_at"] = _utc_now_iso()
        cart["subtotal"] = self._compute_cart_subtotal(cart)
        return deepcopy(cart)

    def remove_grocery_item(self, cart_id: str, product_id: str) -> Dict[str, Any]:
        """
        Remove a product entirely from the cart.

        Args:
            cart_id (str): Target cart.
            product_id (str): The product to remove.

        Returns:
            Dict[str, Any]: Updated cart object.
        """
        cart = self._require_cart(cart_id)
        before = len(cart["items"])
        cart["items"] = [i for i in cart["items"] if i["product_id"] != product_id]
        if len(cart["items"]) == before:
            raise InstacartError(
                "ITEM_NOT_IN_CART",
                f"Product '{product_id}' is not in cart '{cart_id}'.",
                suggested_action="Call get_cart() to see current items.",
                context={"cart_id": cart_id, "product_id": product_id},
            )
        cart["updated_at"] = _utc_now_iso()
        cart["subtotal"] = self._compute_cart_subtotal(cart)
        return deepcopy(cart)

    def get_grocery_cart(self, cart_id: str) -> Dict[str, Any]:
        """
        Retrieve the current state of a cart with a freshly computed subtotal.

        Args:
            cart_id (str): Target cart.

        Returns:
            Dict[str, Any]: Cart object including items (List), subtotal (int, cents),
                applied_coupon (str | None), store_id (str), user_id (str).
        """
        cart = self._require_cart(cart_id)
        cart["subtotal"] = self._compute_cart_subtotal(cart)
        return deepcopy(cart)

    def set_replacement_preference(
        self,
        cart_id: str,
        product_id: str,
        preference: str,
        replacement_product_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Set the replacement preference for an item in the cart. If the shopper
        finds that the requested product is out of stock, this preference tells
        them what to do.

        Args:
            cart_id (str): Target cart.
            product_id (str): The product to set the preference for.
            preference (str): One of:
                "best_match" - shopper picks a similar replacement (default).
                "specific" - replace with replacement_product_id.
                "refund" - do not replace; refund the item.
                "contact_me" - shopper contacts the customer before deciding.
            replacement_product_id (str, optional): Required when preference is "specific".
                The product to substitute if the original is unavailable.

        Returns:
            Dict[str, Any]: Updated cart item with the new replacement preference.
        """
        cart = self._require_cart(cart_id)
        valid_prefs = {"best_match", "specific", "refund", "contact_me"}
        if preference not in valid_prefs:
            raise InstacartError(
                "INVALID_REPLACEMENT_PREFERENCE",
                f"Preference must be one of {valid_prefs}.",
                suggested_action=f"Use one of: {', '.join(sorted(valid_prefs))}.",
                context={"preference": preference},
            )
        if preference == "specific" and not replacement_product_id:
            raise InstacartError(
                "REPLACEMENT_PRODUCT_REQUIRED",
                "replacement_product_id is required when preference is 'specific'.",
                suggested_action="Provide a replacement_product_id.",
                context={"preference": preference},
            )
        found = None
        for item in cart["items"]:
            if item["product_id"] == product_id:
                found = item
                break
        if not found:
            raise InstacartError(
                "ITEM_NOT_IN_CART",
                f"Product '{product_id}' is not in cart '{cart_id}'.",
                suggested_action="Call get_cart() to see current items.",
                context={"cart_id": cart_id, "product_id": product_id},
            )
        found["replacement_pref"] = preference
        if preference == "specific":
            found["replacement_product_id"] = replacement_product_id
        else:
            found.pop("replacement_product_id", None)
        cart["updated_at"] = _utc_now_iso()
        return deepcopy(found)

    # -----------------------------------------------------------------------
    # Delivery windows
    # -----------------------------------------------------------------------

    def get_delivery_slots(self, store_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve available delivery time slots for a store.

        Args:
            store_id (str): The store to get delivery windows for.

        Returns:
            List[Dict[str, Any]]: Available windows, each with:
                window_id (str), start (str, ISO-8601), end (str, ISO-8601),
                fee (int, cents — extra fee on top of base delivery fee),
                available (bool).
        """
        self._require_store(store_id)
        windows = self.delivery_windows.get(store_id, [])
        return deepcopy(windows)

    # -----------------------------------------------------------------------
    # Coupons
    # -----------------------------------------------------------------------

    def redeem_coupon(self, cart_id: str, coupon_code: str) -> Dict[str, Any]:
        """
        Apply a coupon code to a cart. Validates eligibility without consuming
        the coupon (consumption happens at checkout).

        Args:
            cart_id (str): Target cart.
            coupon_code (str): The coupon code to apply.

        Returns:
            Dict[str, Any]:
                cart (Dict): Updated cart with applied_coupon set.
                coupon_status (Dict): valid (bool), reason (str — "OK" or error code such as
                    COUPON_NOT_FOUND, COUPON_EXPIRED, MIN_ORDER_NOT_MET, STORE_NOT_ELIGIBLE).
        """
        cart = self._require_cart(cart_id)
        subtotal = self._compute_cart_subtotal(cart)
        coupon = self.profile["promos"].get(coupon_code)
        if not coupon:
            # Try case-insensitive lookup
            for code, c in self.profile["promos"].items():
                if code.upper() == coupon_code.upper():
                    coupon = c
                    coupon_code = code
                    break
        if not coupon:
            return {
                "cart": deepcopy(cart),
                "coupon_status": {"valid": False, "reason": "COUPON_NOT_FOUND"},
            }
        # Check expiry
        expiry = coupon.get("expiry")
        if expiry:
            now_str = _utc_now_iso()
            if now_str > expiry:
                return {
                    "cart": deepcopy(cart),
                    "coupon_status": {"valid": False, "reason": "COUPON_EXPIRED"},
                }
        # Check min order
        min_order = int(coupon.get("min_order", 0))
        if subtotal < min_order:
            return {
                "cart": deepcopy(cart),
                "coupon_status": {"valid": False, "reason": "MIN_ORDER_NOT_MET"},
            }
        # Check store eligibility
        eligible_stores = coupon.get("applicable_store_ids")
        if eligible_stores and cart["store_id"] not in eligible_stores:
            return {
                "cart": deepcopy(cart),
                "coupon_status": {"valid": False, "reason": "STORE_NOT_ELIGIBLE"},
            }
        cart["applied_coupon"] = coupon_code
        cart["updated_at"] = _utc_now_iso()
        return {
            "cart": deepcopy(cart),
            "coupon_status": {"valid": True, "reason": "OK"},
        }

    def _compute_coupon_discount(self, coupon: Dict[str, Any], subtotal: int) -> int:
        """Compute the discount amount in cents for a coupon."""
        dtype = coupon.get("discount_type")
        dval = coupon.get("discount_value", 0)
        if dtype == "percent":
            return int(round(subtotal * (float(dval) / 100.0)))
        elif dtype == "flat":
            return int(dval)
        return 0

    # -----------------------------------------------------------------------
    # Checkout
    # -----------------------------------------------------------------------

    def checkout(
        self,
        cart_id: str,
        address_id: str,
        payment_method_id: str,
        delivery_window_id: str,
        tip: int = 200,
    ) -> str:
        """
        Submit a cart as a live order. Charges the payment method and assigns a
        personal shopper. The order begins in "pending" status and transitions to
        "shopping" once a shopper accepts.

        Args:
            cart_id (str): Cart to checkout; must be non-empty.
            address_id (str): Delivery address ID (from list_addresses()).
            payment_method_id (str): Payment method ID (from list_payment_methods()).
            delivery_window_id (str): Selected delivery window (from get_delivery_windows()).
            tip (int): Shopper tip in cents. Defaults to 200 (i.e. $2.00).

        Returns:
            str: The new order_id.
        """
        cart = self._require_cart(cart_id)
        store = self._require_store(cart["store_id"])

        if not cart["items"]:
            raise InstacartError(
                "EMPTY_CART",
                "Cannot checkout an empty cart.",
                suggested_action="Add items to the cart before calling checkout().",
                context={"cart_id": cart_id},
            )

        # Validate min order
        subtotal = self._compute_cart_subtotal(cart)
        min_order = int(store.get("min_order", 0))
        if subtotal < min_order:
            raise InstacartError(
                "BELOW_MIN_ORDER",
                f"Cart subtotal ({subtotal}) is below the store minimum ({min_order}).",
                suggested_action="Add more items to meet the minimum order requirement.",
                context={"subtotal": subtotal, "min_order": min_order},
            )

        # Validate address
        addr = self.profile["addresses"].get(address_id)
        if not addr:
            raise InstacartError(
                "ADDRESS_NOT_FOUND",
                f"Address '{address_id}' not found for this user.",
                suggested_action="Call list_addresses() to get valid address IDs.",
                context={"address_id": address_id},
            )

        # Validate payment method
        pm = self.profile["payment_methods"].get(payment_method_id)
        if not pm:
            raise InstacartError(
                "PAYMENT_METHOD_NOT_FOUND",
                f"Payment method '{payment_method_id}' not found for this user.",
                suggested_action="Call list_payment_methods() to get valid method IDs.",
                context={"payment_method_id": payment_method_id},
            )

        # Validate delivery window
        windows = self.delivery_windows.get(cart["store_id"], [])
        window = None
        for w in windows:
            if w.get("window_id") == delivery_window_id:
                window = w
                break
        if not window:
            raise InstacartError(
                "INVALID_DELIVERY_WINDOW",
                f"Delivery window '{delivery_window_id}' not found for this store.",
                suggested_action="Call get_delivery_windows() to see available slots.",
                context={"delivery_window_id": delivery_window_id, "store_id": cart["store_id"]},
            )
        if not window.get("available", True):
            raise InstacartError(
                "DELIVERY_WINDOW_UNAVAILABLE",
                "The selected delivery window is no longer available.",
                suggested_action="Choose a different delivery window.",
                context={"delivery_window_id": delivery_window_id},
            )

        # Compute total
        delivery_fee = int(store.get("delivery_fee", 0))
        window_fee = int(window.get("fee", 0))
        # Express members get free delivery on orders over threshold
        express_member = self.profile.get("membership", {}).get("express_member", False)
        express_threshold = 3500  # $35.00
        if express_member and subtotal >= express_threshold:
            delivery_fee = 0

        coupon_discount = 0
        coupon_code = cart.get("applied_coupon")
        if coupon_code and coupon_code in self.profile["promos"]:
            coupon_discount = self._compute_coupon_discount(self.profile["promos"][coupon_code], subtotal)

        tax = int(round(subtotal * 0.08))
        tip_cents = max(0, int(tip))
        total = max(0, subtotal + delivery_fee + window_fee + tax + tip_cents - coupon_discount)

        # Assign shopper
        shopper = self._pick_shopper()
        shopper_id = None
        if shopper:
            shopper_id = shopper["shopper_id"]
            shopper["active_order_id"] = None  # will be set below

        order_id = self._new_id("order")
        now = _utc_now_iso()

        order = {
            "order_id": order_id,
            "user_id": self.user_id,
            "store_id": cart["store_id"],
            "items": deepcopy(cart["items"]),
            "status": "pending",
            "delivery_window": deepcopy(window),
            "address_id": address_id,
            "payment_method_id": payment_method_id,
            "shopper_id": shopper_id,
            "tip": tip_cents,
            "pricing": {
                "subtotal": subtotal,
                "delivery_fee": delivery_fee,
                "window_fee": window_fee,
                "tax": tax,
                "tip": tip_cents,
                "coupon_discount": coupon_discount,
                "total": total,
            },
            "created_at": now,
            "updated_at": now,
        }
        self.orders[order_id] = order

        if shopper:
            shopper["active_order_id"] = order_id
            order["status"] = "shopping"
            order["updated_at"] = _utc_now_iso()

        # Mark delivery window as no longer available
        window["available"] = False

        return order_id

    # -----------------------------------------------------------------------
    # Order management
    # -----------------------------------------------------------------------

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get the current status and details of an order.

        Args:
            order_id (str): The order to query.

        Returns:
            Dict[str, Any]:
                order_id (str), status (str — one of: pending, shopping, checkout,
                    delivering, delivered, canceled), shopper (Dict | None),
                delivery_window (Dict), tip (int, cents), pricing (Dict).
        """
        order = self._require_order(order_id)
        shopper = None
        if order.get("shopper_id"):
            shopper = self.shoppers.get(order["shopper_id"])
            if shopper:
                shopper = {
                    "shopper_id": shopper["shopper_id"],
                    "name": shopper.get("name", ""),
                    "rating": shopper.get("rating", 0.0),
                }
        return {
            "order_id": order_id,
            "status": order.get("status"),
            "shopper": shopper,
            "delivery_window": deepcopy(order.get("delivery_window")),
            "tip": order.get("tip", 0),
            "pricing": deepcopy(order.get("pricing", {})),
        }

    def update_tip(self, order_id: str, new_tip: int) -> Dict[str, Any]:
        """
        Update the shopper tip for an order. Tips can be adjusted even after delivery
        (within a reasonable time window). The order total is recalculated.

        Args:
            order_id (str): The order to update the tip for.
            new_tip (int): New tip amount in cents; must be >= 0.

        Returns:
            Dict[str, Any]:
                order_id (str), old_tip (int), new_tip (int), new_total (int).
        """
        order = self._require_order(order_id)
        if order.get("status") == "canceled":
            raise InstacartError(
                "ORDER_CANCELED",
                "Cannot update tip on a canceled order.",
                suggested_action="This order has been canceled.",
                context={"order_id": order_id},
            )
        tip_cents = max(0, int(new_tip))
        old_tip = order.get("tip", 0)
        pricing = order.get("pricing", {})
        # Recalculate total
        old_total = pricing.get("total", 0)
        new_total = old_total - old_tip + tip_cents
        order["tip"] = tip_cents
        pricing["tip"] = tip_cents
        pricing["total"] = max(0, new_total)
        order["updated_at"] = _utc_now_iso()
        return {
            "order_id": order_id,
            "old_tip": old_tip,
            "new_tip": tip_cents,
            "new_total": pricing["total"],
        }

    def cancel_delivery(self, order_id: str, reason: str) -> Dict[str, Any]:
        """
        Cancel an active order. Cancellation is only possible before the shopper
        has completed shopping. A cancellation fee may apply if shopping has started.

        Args:
            order_id (str): The order to cancel.
            reason (str): Short description of why the order is being canceled.

        Returns:
            Dict[str, Any]:
                order_id (str), canceled (bool), fee (int, cancellation fee in cents).
        """
        order = self._require_order(order_id)
        status = order.get("status")
        if status in {"delivered", "canceled"}:
            return {
                "order_id": order_id,
                "canceled": False,
                "fee": 0,
                "reason": "NOT_CANCELABLE",
            }

        fee = 0
        if status in {"shopping", "checkout"}:
            fee = 1500  # $15 cancellation fee if shopper already started
        order["status"] = "canceled"
        order["updated_at"] = _utc_now_iso()
        order["cancel_reason"] = reason
        order["cancel_fee"] = fee

        # Release the shopper
        shopper_id = order.get("shopper_id")
        if shopper_id and shopper_id in self.shoppers:
            self.shoppers[shopper_id]["active_order_id"] = None

        return {"order_id": order_id, "canceled": True, "fee": fee}

    def rate_order(
        self,
        order_id: str,
        rating: int,
        comment: str = "",
    ) -> Dict[str, Any]:
        """
        Submit a star rating and optional feedback for a delivered order.

        Args:
            order_id (str): The order to rate.
            rating (int): Satisfaction score from 1 (worst) to 5 (best).
            comment (str): Free-text feedback. Defaults to empty string.

        Returns:
            Dict[str, Any]: The rating object that was recorded:
                order_id (str), rating (int), comment (str), created_at (str).
        """
        order = self._require_order(order_id)
        if order.get("status") != "delivered":
            raise InstacartError(
                "ORDER_NOT_DELIVERED",
                "Can only rate orders that have been delivered.",
                suggested_action="Wait until the order is delivered before rating.",
                context={"order_id": order_id, "status": order.get("status")},
            )
        r = int(rating)
        if r < 1 or r > 5:
            raise InstacartError(
                "INVALID_RATING",
                "Rating must be between 1 and 5.",
                suggested_action="Provide an integer rating in [1, 5].",
                context={"rating": rating},
            )
        now = _utc_now_iso()
        order["rating"] = {"rating": r, "comment": comment, "created_at": now}
        order["updated_at"] = now
        # Also update shopper rating (simple running average approximation)
        shopper_id = order.get("shopper_id")
        if shopper_id and shopper_id in self.shoppers:
            s = self.shoppers[shopper_id]
            old_rating = float(s.get("rating", 5.0))
            s["rating"] = round((old_rating + r) / 2.0, 2)
        return deepcopy(order["rating"])

    def report_issue(
        self,
        order_id: str,
        issue_type: str,
        description: str,
    ) -> str:
        """
        Report an issue with an order (e.g. wrong items, missing items, quality problems).

        Args:
            order_id (str): The order with the issue.
            issue_type (str): Issue category. Common values: "missing_item", "wrong_item",
                "damaged_item", "poor_quality", "late_delivery", "other".
            description (str): Detailed description of the problem.

        Returns:
            str: The new issue_id for tracking this support request.
        """
        order = self._require_order(order_id)
        valid_types = {"missing_item", "wrong_item", "damaged_item", "poor_quality", "late_delivery", "other"}
        if issue_type not in valid_types:
            raise InstacartError(
                "INVALID_ISSUE_TYPE",
                f"Issue type must be one of {valid_types}.",
                suggested_action=f"Use one of: {', '.join(sorted(valid_types))}.",
                context={"issue_type": issue_type},
            )
        issue_id = self._new_id("issue")
        self.issues[issue_id] = {
            "issue_id": issue_id,
            "order_id": order_id,
            "user_id": order["user_id"],
            "type": issue_type,
            "description": description,
            "status": "open",
            "resolution": None,
            "created_at": _utc_now_iso(),
        }
        return issue_id

    # -----------------------------------------------------------------------
    # Account: addresses
    # -----------------------------------------------------------------------

    def list_drop_off_addresses(self) -> List[Dict[str, Any]]:
        """
        List all delivery addresses saved to the current user's account.

        Returns:
            List[Dict[str, Any]]: Address objects, each with:
                address_id (str), label (str), street (str), city (str),
                state (str), zip (str), lat (float), lng (float),
                delivery_instructions (str).
        """
        results = []
        for addr in self.profile["addresses"].values():
            results.append(deepcopy(addr))
        return results

    def add_drop_off_address(
        self,
        label: str,
        street: str,
        city: str,
        state: str,
        zip_code: str,
        lat: float,
        lng: float,
        delivery_instructions: str = "",
    ) -> str:
        """
        Add a new delivery address to the current user's account.

        Args:
            label (str): Short label for the address (e.g. "Home", "Work").
            street (str): Street address.
            city (str): City name.
            state (str): State abbreviation (e.g. "CA").
            zip_code (str): ZIP code.
            lat (float): Latitude coordinate.
            lng (float): Longitude coordinate.
            delivery_instructions (str): Default delivery instructions for this address.

        Returns:
            str: The new address_id.
        """
        address_id = self._new_id("address")
        self.profile["addresses"][address_id] = {
            "address_id": address_id,
            "label": label,
            "street": street,
            "city": city,
            "state": state,
            "zip": zip_code,
            "lat": lat,
            "lng": lng,
            "delivery_instructions": delivery_instructions,
        }
        return address_id

    # -----------------------------------------------------------------------
    # Account: payment methods
    # -----------------------------------------------------------------------

    def list_payment_options(self) -> List[Dict[str, Any]]:
        """
        List all payment methods saved to the current user's account.

        Returns:
            List[Dict[str, Any]]: Payment method objects, each with:
                payment_method_id (str), type (str), last_four (str),
                is_default (bool).
        """
        results = []
        for pm in self.profile["payment_methods"].values():
            results.append({
                "payment_method_id": pm["payment_method_id"],
                "type": pm.get("type", "card"),
                "last_four": pm.get("last_four", ""),
                "is_default": pm.get("is_default", False),
            })
        return results

    def add_payment_option(
        self,
        card_number: str,
        expiration_date: str,
        cvv: str,
        billing_address: str,
    ) -> str:
        """
        Add a new credit or debit card as a payment method for the current user.

        Args:
            card_number (str): Full card number; only the last 4 digits are stored.
            expiration_date (str): Card expiry in MM/YY format (e.g. "09/27").
            cvv (str): Card security code (3 or 4 digits).
            billing_address (str): Billing address for the card.

        Returns:
            str: The new payment_method_id.
        """
        last_four = str(card_number).replace(" ", "")[-4:]
        pm_id = self._new_id("payment")
        existing = list(self.profile["payment_methods"].values())
        self.profile["payment_methods"][pm_id] = {
            "payment_method_id": pm_id,
            "type": "card",
            "last_four": last_four,
            "expiration_date": expiration_date,
            "billing_address": billing_address,
            "is_default": len(existing) == 0,  # First card is default
        }
        return pm_id
