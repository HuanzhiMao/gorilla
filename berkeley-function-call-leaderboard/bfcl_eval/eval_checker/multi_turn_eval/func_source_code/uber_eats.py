"""
UberEats Order Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Single-user perspective: profile replaces users dict; no cart abstraction.
"""

from __future__ import annotations

import copy
import random
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .server_patch_mixin import PatchableMixin


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


class UberEatsError(Exception):
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


# ---------------------------------------------------------------------------
# UberEats API
# ---------------------------------------------------------------------------


DEFAULT_STATE = {
    "random_seed": 5678,
    "profile": {},
    "orders": {},
    "restaurants": {},
    "menu": {},
    "offers": {},
    "delivery_tracking": {},
    "grocery_stores": {},
    "grocery_catalog": {},
    "group_orders": {},
}


class UberEatsAPI(PatchableMixin):
    """
    In-memory dummy implementation of a UberEats-like food delivery service.
    Single-user perspective: profile represents the current user.
    """


    def __init__(self):
        self._id_counters = {"order": 0}
        self.profile: Dict[str, Any] = {}
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.restaurants: Dict[str, Dict[str, Any]] = {}
        self.menu: Dict[str, Dict[str, Any]] = {}
        self.offers: Dict[str, Dict[str, Any]] = {}
        self.delivery_tracking: Dict[str, Dict[str, Any]] = {}
        self.grocery_stores: Dict[str, Dict[str, Any]] = {}
        self.grocery_catalog: Dict[str, Dict[str, Any]] = {}
        self.group_orders: Dict[str, Dict[str, Any]] = {}
        self._api_description = (
            "This tool belongs to the UberEats food delivery ordering system, which allows "
            "users to browse restaurants, view menus, place and track food delivery orders, "
            "manage their profile and payment methods, and apply promotional offers."
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
        # self.user_id is referenced by several public methods and patches (e.g.,
        # error contexts). It is not guaranteed to be present in every scenario
        # file, so we fall back to a safe default to avoid AttributeError.
        self.user_id = scenario.get("user_id", "user_1")
        self.profile = scenario.get("profile", DEFAULT_STATE_COPY["profile"])
        self.orders = scenario.get("orders", DEFAULT_STATE_COPY["orders"])
        self.restaurants = scenario.get("restaurants", DEFAULT_STATE_COPY["restaurants"])
        self.menu = scenario.get("menu", DEFAULT_STATE_COPY["menu"])
        self.offers = scenario.get("offers", DEFAULT_STATE_COPY["offers"])
        self.delivery_tracking = scenario.get("delivery_tracking", DEFAULT_STATE_COPY["delivery_tracking"])
        self.grocery_stores = scenario.get("grocery_stores", DEFAULT_STATE_COPY["grocery_stores"])
        self.grocery_catalog = scenario.get("grocery_catalog", DEFAULT_STATE_COPY["grocery_catalog"])
        self.group_orders = scenario.get("group_orders", DEFAULT_STATE_COPY["group_orders"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, UberEatsAPI):
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

    def _require_restaurant(self, restaurant_id: str) -> Dict[str, Any]:
        r = self.restaurants.get(restaurant_id)
        if not r:
            raise UberEatsError(
                "RESTAURANT_NOT_FOUND",
                f"Restaurant '{restaurant_id}' not found.",
                suggested_action="Use search_restaurants() to find a valid restaurant_id.",
                context={"restaurant_id": restaurant_id},
            )
        return r

    def _require_order(self, order_id: str) -> Dict[str, Any]:
        o = self.orders.get(order_id)
        if not o:
            raise UberEatsError(
                "ORDER_NOT_FOUND",
                f"Order '{order_id}' not found.",
                suggested_action="Use get_order_history() to see valid order IDs.",
                context={"order_id": order_id},
            )
        return o

    def _require_menu_item(self, item_id: str) -> Dict[str, Any]:
        item = self.menu.get(item_id)
        if not item:
            raise UberEatsError(
                "ITEM_NOT_FOUND",
                f"Menu item '{item_id}' not found.",
                suggested_action="Use get_menu() to see available items.",
                context={"item_id": item_id},
            )
        return item

    def _require_address(self, address_id: str) -> Dict[str, Any]:
        for addr in self.profile.get("address", []):
            if addr.get("address_id") == address_id:
                return addr
        raise UberEatsError(
            "ADDRESS_NOT_FOUND",
            f"Address '{address_id}' not found in profile.",
            suggested_action="Add the address with add_address() or check get_profile().",
            context={"address_id": address_id},
        )

    def _require_payment_method(self, method_id: str) -> Dict[str, Any]:
        for m in self.profile.get("payment_method", []):
            if m.get("method_id") == method_id:
                return m
        raise UberEatsError(
            "PAYMENT_METHOD_NOT_FOUND",
            f"Payment method '{method_id}' not found in profile.",
            suggested_action="Use list_payment_methods() to see valid method IDs.",
            context={"method_id": method_id},
        )

    # -----------------------------------------------------------------------
    # Profile & account
    # -----------------------------------------------------------------------

    def get_eater_profile(self) -> Dict[str, Any]:
        """
        Retrieve the current user's profile information.

        Returns:
            Dict[str, Any]: Profile with fields:
                name (str), email (str), phone (str),
                address (List[Dict] — saved delivery addresses),
                payment_method (List[Dict] — saved payment methods),
                promo (List[str] — offer_ids in the promo wallet),
                uber_one (bool — Uber One membership status).
        """
        return deepcopy(self.profile)

    def update_profile(
        self,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update basic profile fields for the current user.

        Args:
            name (str, optional): New display name.
            email (str, optional): New email address.
            phone (str, optional): New phone number.

        Returns:
            Dict[str, Any]: Updated profile.
        """
        if name is not None:
            self.profile["name"] = name
        if email is not None:
            self.profile["email"] = email
        if phone is not None:
            self.profile["phone"] = phone
        return deepcopy(self.profile)

    def register_delivery_address(
        self,
        street: str,
        city: str,
        state: str,
        zip_code: str,
        set_as_default: bool = False,
    ) -> Dict[str, Any]:
        """
        Add a new delivery address to the user's profile.

        Args:
            street (str): Street address (e.g. "123 Main St, Apt 4B").
            city (str): City name.
            state (str): State abbreviation (e.g. "CA").
            zip_code (str): ZIP code.
            set_as_default (bool): If True, mark this as the default delivery address.
                Defaults to False.

        Returns:
            Dict[str, Any]: Updated profile.
        """
        addresses = self.profile.setdefault("address", [])
        address_id = f"addr_{len(addresses) + 1}"
        if set_as_default:
            for a in addresses:
                a["is_default"] = False
        addresses.append(
            {
                "address_id": address_id,
                "street": street,
                "city": city,
                "state": state,
                "zip": zip_code,
                "is_default": set_as_default,
            }
        )
        return deepcopy(self.profile)

    def remove_address(self, address_id: str) -> Dict[str, Any]:
        """
        Remove a saved delivery address from the user's profile.

        Args:
            address_id (str): The address to remove.

        Returns:
            Dict[str, Any]: Updated profile.
        """
        self._require_address(address_id)
        self.profile["address"] = [
            a
            for a in self.profile.get("address", [])
            if a.get("address_id") != address_id
        ]
        return deepcopy(self.profile)

    def set_default_address(self, address_id: str) -> Dict[str, Any]:
        """
        Mark an address as the default delivery address.

        Args:
            address_id (str): The address to set as default.

        Returns:
            Dict[str, Any]: Updated profile.
        """
        self._require_address(address_id)
        for a in self.profile.get("address", []):
            a["is_default"] = a.get("address_id") == address_id
        return deepcopy(self.profile)

    def get_registered_payments(self) -> List[Dict[str, Any]]:
        """
        List all payment methods saved to the user's profile.

        Returns:
            List[Dict[str, Any]]: Payment methods, each with:
                method_id (str), type (str), last4 (str),
                expiration_date (str), name (str), is_default (bool).
        """
        return deepcopy(self.profile.get("payment_method", []))

    def register_payment_method(
        self,
        card_number: str,
        expiration_date: str,
        cvv: str,
        name: str,
    ) -> str:
        """
        Add a new credit or debit card as a payment method.

        Args:
            card_number (str): Full card number; only the last 4 digits are stored.
            expiration_date (str): Card expiry in MM/YY format (e.g. "08/27").
            cvv (str): Card security code (3 or 4 digits); not stored.
            name (str): Cardholder name as it appears on the card.

        Returns:
            str: The new method_id assigned to this payment method.
        """
        methods = self.profile.setdefault("payment_method", [])
        last4 = str(card_number).replace(" ", "")[-4:]
        method_id = f"pm_{len(methods) + 1}"
        methods.append(
            {
                "method_id": method_id,
                "type": "card",
                "last4": last4,
                "expiration_date": expiration_date,
                "name": name,
                "is_default": len(methods) == 0,
            }
        )
        return method_id

    def set_default_payment_method(self, method_id: str) -> List[Dict[str, Any]]:
        """
        Mark a payment method as the default for future orders.

        Args:
            method_id (str): The payment method to mark as default.

        Returns:
            List[Dict[str, Any]]: Updated list of all payment methods.
        """
        self._require_payment_method(method_id)
        for m in self.profile.get("payment_method", []):
            m["is_default"] = m.get("method_id") == method_id
        return deepcopy(self.profile.get("payment_method", []))

    # -----------------------------------------------------------------------
    # Restaurant & menu browsing
    # -----------------------------------------------------------------------

    def search_restaurants(
        self,
        query: str = "",
        category: Optional[str] = None,
        open_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Search for restaurants by name or category.

        Args:
            query (str): Text matched against restaurant name. Empty string matches all.
            category (str, optional): Filter by cuisine category (e.g. "pizza", "sushi", "burgers").
            open_only (bool): If True, return only currently open restaurants. Defaults to False.

        Returns:
            List[Dict[str, Any]]: Matching restaurants, each with:
                restaurant_id (str), name (str), category (str),
                rating (float), address (str), is_open (bool).
        """
        q = (query or "").strip().lower()
        out = []
        for r in self.restaurants.values():
            if q and q not in (r.get("name") or "").lower():
                continue
            if category and category.lower() != (r.get("category") or "").lower():
                continue
            if open_only and not r.get("is_open", False):
                continue
            out.append(
                {
                    "restaurant_id": r["restaurant_id"],
                    "name": r.get("name"),
                    "category": r.get("category"),
                    "rating": r.get("rating"),
                    "address": r.get("address"),
                    "is_open": r.get("is_open"),
                }
            )
        return out

    def get_restaurant(self, restaurant_id: str) -> Dict[str, Any]:
        """
        Retrieve full details for a restaurant, including a brief menu summary.

        Args:
            restaurant_id (str): The restaurant to look up.

        Returns:
            Dict[str, Any]: restaurant_id (str), name (str), category (str),
                rating (float), address (str), is_open (bool),
                menu (List[Dict] — item_id, name, price for each menu item).
        """
        r = self._require_restaurant(restaurant_id)
        return deepcopy(r)

    def get_menu(self, restaurant_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve the full menu for a restaurant.

        Args:
            restaurant_id (str): The restaurant whose menu to fetch.

        Returns:
            List[Dict[str, Any]]: Menu items, each with:
                item_id (str), name (str), category (str), price (float),
                options (List[Dict] — selectable add-ons or variants),
                available (bool).
        """
        self._require_restaurant(restaurant_id)
        items = [
            item
            for item in self.menu.values()
            if item.get("restaurant_id") == restaurant_id
        ]
        return deepcopy(items)

    # -----------------------------------------------------------------------
    # Order management
    # -----------------------------------------------------------------------

    def submit_food_order(
        self,
        restaurant_id: str,
        items: List[Dict[str, Any]],
        delivery_address_id: str,
        payment_method_id: str,
        tip: float = 0.0,
        offer_id: Optional[str] = None,
    ) -> str:
        """
        Place a food delivery order directly (no cart required).

        Args:
            restaurant_id (str): The restaurant to order from. Must be open.
            items (List[Dict]): Items to order. Each dict requires:
                item_id (str), quantity (int >= 1).
                Optional: selected_options (List), special_instructions (str).
            delivery_address_id (str): Address ID from your profile to deliver to.
            payment_method_id (str): Payment method ID from your profile to charge.
            tip (float): Courier tip in dollars. Defaults to 0.0.
            offer_id (str, optional): Offer ID from your promo wallet to apply.

        Returns:
            str: The new order_id. The order begins in "preparing" status.
        """
        restaurant = self._require_restaurant(restaurant_id)
        if not restaurant.get("is_open", False):
            raise UberEatsError(
                "RESTAURANT_CLOSED",
                "Restaurant is currently closed.",
                suggested_action="Choose another restaurant or try again during open hours.",
                context={"restaurant_id": restaurant_id},
            )
        if not items:
            raise UberEatsError(
                "EMPTY_ORDER",
                "Cannot place an order with no items.",
                suggested_action="Provide at least one item.",
                context={},
            )

        address = self._require_address(delivery_address_id)
        self._require_payment_method(payment_method_id)

        # Validate and enrich items
        enriched_items = []
        subtotal = 0.0
        for entry in items:
            item_id = entry.get("item_id")
            item = self._require_menu_item(item_id)
            if not item.get("available", True):
                raise UberEatsError(
                    "ITEM_UNAVAILABLE",
                    f"Item '{item_id}' is currently unavailable.",
                    suggested_action="Choose a different item from get_menu().",
                    context={"item_id": item_id},
                )
            if item.get("restaurant_id") != restaurant_id:
                raise UberEatsError(
                    "ITEM_NOT_FROM_RESTAURANT",
                    f"Item '{item_id}' does not belong to restaurant '{restaurant_id}'.",
                    suggested_action="Only order items from the selected restaurant.",
                    context={"item_id": item_id, "restaurant_id": restaurant_id},
                )
            qty = max(1, int(entry.get("quantity", 1)))
            price = float(item.get("price", 0.0))
            subtotal += price * qty
            enriched_items.append(
                {
                    "item_id": item_id,
                    "name": item.get("name"),
                    "price": price,
                    "quantity": qty,
                    "selected_options": entry.get("selected_options", []),
                    "special_instructions": entry.get("special_instructions", ""),
                }
            )

        # Compute fees
        delivery_fee = round(float(restaurant.get("delivery_fee", 2.99)), 2)
        service_fee = round(subtotal * 0.10, 2)
        tax = round(subtotal * 0.095, 2)
        tip_amount = round(max(0.0, float(tip)), 2)

        # Apply offer
        applied_promo = None
        discount = 0.0
        if offer_id:
            offer = self.offers.get(offer_id)
            if not offer:
                raise UberEatsError(
                    "OFFER_NOT_FOUND",
                    f"Offer '{offer_id}' not found.",
                    suggested_action="Check get_available_offers() for valid offer IDs.",
                    context={"offer_id": offer_id},
                )
            profile_promos = self.profile.get("promo", [])
            if offer_id not in profile_promos:
                raise UberEatsError(
                    "OFFER_NOT_IN_WALLET",
                    f"Offer '{offer_id}' is not in your promo wallet.",
                    suggested_action="Only offers in your promo wallet can be applied.",
                    context={"offer_id": offer_id},
                )
            min_order = float(offer.get("min_order", 0.0))
            if subtotal < min_order:
                raise UberEatsError(
                    "OFFER_MIN_ORDER_NOT_MET",
                    f"Order subtotal ${subtotal:.2f} is below the minimum ${min_order:.2f} for this offer.",
                    suggested_action="Add more items to meet the minimum order requirement.",
                    context={
                        "offer_id": offer_id,
                        "min_order": min_order,
                        "subtotal": subtotal,
                    },
                )
            if offer.get("uber_one") and not self.profile.get("uber_one", False):
                raise UberEatsError(
                    "UBER_ONE_REQUIRED",
                    "This offer requires an active Uber One membership.",
                    suggested_action="Subscribe to Uber One to use this offer.",
                    context={"offer_id": offer_id},
                )
            discount = round(float(offer.get("discount", 0.0)), 2)
            applied_promo = {"offer_id": offer_id, "discount": discount}
            # Consume the offer from wallet
            self.profile["promo"] = [o for o in profile_promos if o != offer_id]

        total = round(
            max(
                0.0, subtotal + delivery_fee + service_fee + tax + tip_amount - discount
            ),
            2,
        )
        order_id = self._new_id("order")
        now = _utc_now_iso()

        self.orders[order_id] = {
            "order_id": order_id,
            "restaurant_id": restaurant_id,
            "restaurant_name": restaurant.get("name"),
            "items": enriched_items,
            "fees": {
                "delivery_fee": delivery_fee,
                "service_fee": service_fee,
                "tax": tax,
                "tip": tip_amount,
            },
            "total": total,
            "status": "preparing",
            "created_at": now,
            "applied_promo": applied_promo,
            "delivery_address": {
                "street": address.get("street"),
                "city": address.get("city"),
                "state": address.get("state"),
                "zip": address.get("zip"),
            },
            "eta_min": 30,
        }

        self.delivery_tracking[order_id] = {
            "order_id": order_id,
            "courier_name": "Pending assignment",
            "status": "preparing",
            "eta_min": 30,
            "current_stage": "restaurant_preparing",
        }

        return order_id

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Retrieve full details for a specific order.

        Args:
            order_id (str): The order to look up.

        Returns:
            Dict[str, Any]: order_id (str), restaurant_id (str), restaurant_name (str),
                items (List[Dict]), fees (Dict with delivery_fee/service_fee/tax/tip),
                total (float), status (str), created_at (str),
                applied_promo (Dict | None — offer_id and discount),
                delivery_address (Dict), eta_min (int).
        """
        o = self._require_order(order_id)
        return deepcopy(o)

    def get_order_history(self) -> List[Dict[str, Any]]:
        """
        Retrieve a summary list of all orders, newest first.

        Returns:
            List[Dict[str, Any]]: Orders sorted by creation time (newest first), each with:
                order_id (str), restaurant_name (str), total (float),
                status (str), created_at (str).
        """
        summaries = [
            {
                "order_id": o["order_id"],
                "restaurant_name": o.get("restaurant_name"),
                "total": o.get("total"),
                "status": o.get("status"),
                "created_at": o.get("created_at"),
            }
            for o in self.orders.values()
        ]
        return sorted(summaries, key=lambda x: x.get("created_at", ""), reverse=True)

    def cancel_food_order(self, order_id: str, reason: str) -> Dict[str, Any]:
        """
        Cancel an active order. A small fee applies if food is already being prepared.

        Args:
            order_id (str): The order to cancel.
            reason (str): Brief reason for cancellation.

        Returns:
            Dict[str, Any]:
                order_id (str), canceled (bool — False if already in terminal state),
                fee (float — cancellation fee in dollars, 0.0 if free).
        """
        o = self._require_order(order_id)
        status = o.get("status")
        if status in {"delivered", "canceled", "refunded"}:
            return {
                "order_id": order_id,
                "canceled": False,
                "fee": 0.0,
                "reason": "NOT_CANCELABLE",
            }

        fee = 1.99 if status == "preparing" else 0.0
        o["status"] = "canceled"
        o["cancel_reason"] = reason

        tracking = self.delivery_tracking.get(order_id)
        if tracking:
            tracking["status"] = "canceled"
            tracking["current_stage"] = "canceled"

        return {"order_id": order_id, "canceled": True, "fee": fee}

    def track_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get real-time delivery tracking for an order.

        Args:
            order_id (str): The order to track.

        Returns:
            Dict[str, Any]: order_id (str), courier_name (str), status (str),
                eta_min (int), current_stage (str — one of: restaurant_preparing /
                courier_assigned / courier_picking_up / en_route / delivered / canceled).
        """
        self._require_order(order_id)
        tracking = self.delivery_tracking.get(order_id)
        if not tracking:
            raise UberEatsError(
                "TRACKING_NOT_FOUND",
                f"No tracking information found for order '{order_id}'.",
                suggested_action="Ensure the order was placed successfully.",
                context={"order_id": order_id},
            )
        return deepcopy(tracking)

    def rate_order(
        self,
        order_id: str,
        rating: int,
        comment: str = "",
    ) -> Dict[str, Any]:
        """
        Submit a rating and optional comment for a completed order.

        Args:
            order_id (str): The delivered order to rate.
            rating (int): Overall satisfaction score from 1 (worst) to 5 (best).
            comment (str): Free-text review. Defaults to empty string.

        Returns:
            Dict[str, Any]: Updated order object including the submitted rating.
        """
        o = self._require_order(order_id)
        if o.get("status") != "delivered":
            raise UberEatsError(
                "ORDER_NOT_DELIVERED",
                "Orders can only be rated after delivery is complete.",
                suggested_action="Wait until the order status is 'delivered'.",
                context={"order_id": order_id, "status": o.get("status")},
            )
        r = int(rating)
        if r < 1 or r > 5:
            raise UberEatsError(
                "INVALID_RATING",
                "Rating must be between 1 and 5.",
                suggested_action="Provide an integer rating in [1, 5].",
                context={"rating": rating},
            )
        o["rating"] = {"rating": r, "comment": comment}
        return deepcopy(o)

    # -----------------------------------------------------------------------
    # Offers & membership
    # -----------------------------------------------------------------------

    def get_available_offers(self) -> List[Dict[str, Any]]:
        """
        Retrieve all available promotional offers and indicate which are in the user's wallet.

        Returns:
            List[Dict[str, Any]]: Offers, each with:
                offer_id (str), discount (float — dollar amount off), min_order (float),
                uber_one (bool — Uber One membership required to use),
                in_wallet (bool — True if this offer is already in your promo wallet).
        """
        wallet = set(self.profile.get("promo", []))
        return [
            {
                "offer_id": o["offer_id"],
                "discount": o.get("discount"),
                "min_order": o.get("min_order"),
                "uber_one": o.get("uber_one", False),
                "in_wallet": o["offer_id"] in wallet,
            }
            for o in self.offers.values()
        ]

    def get_uber_one_status(self) -> Dict[str, Any]:
        """
        Retrieve Uber One membership status and associated benefits.

        Returns:
            Dict[str, Any]:
                uber_one (bool): Whether the user has an active Uber One subscription.
                benefits (List[str]): Active benefit descriptions (empty list if no membership).
        """
        uber_one = bool(self.profile.get("uber_one", False))
        benefits = (
            [
                "$0 delivery fee on eligible orders",
                "5% off eligible orders",
                "priority support",
            ]
            if uber_one
            else []
        )
        return {"uber_one": uber_one, "benefits": benefits}

    # -----------------------------------------------------------------------
    # Grocery delivery
    # -----------------------------------------------------------------------

    def search_grocery_stores(
        self,
        query: str = "",
        category: Optional[str] = None,
        open_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Search for grocery stores by name or category.

        Args:
            query (str): Text matched against store name. Empty string matches all.
            category (str, optional): Filter by store category (e.g. "organic", "convenience", "supermarket").
            open_only (bool): If True, return only currently open stores. Defaults to False.

        Returns:
            List[Dict[str, Any]]: Matching stores, each with:
                store_id (str), name (str), category (str),
                rating (float), address (str), is_open (bool).
        """
        q = (query or "").strip().lower()
        out = []
        for s in self.grocery_stores.values():
            if q and q not in (s.get("name") or "").lower():
                continue
            if category and category.lower() != (s.get("category") or "").lower():
                continue
            if open_only and not s.get("is_open", False):
                continue
            out.append(
                {
                    "store_id": s["store_id"],
                    "name": s.get("name"),
                    "category": s.get("category"),
                    "rating": s.get("rating"),
                    "address": s.get("address"),
                    "is_open": s.get("is_open"),
                }
            )
        return out

    def get_grocery_catalog(
        self,
        store_id: str,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Browse a grocery store's product catalog, optionally filtered by aisle/category.

        Args:
            store_id (str): The grocery store whose catalog to fetch.
            category (str, optional): Filter by product category/aisle (e.g. "produce", "dairy", "snacks").

        Returns:
            List[Dict[str, Any]]: Products, each with:
                item_id (str), name (str), category (str), price (float),
                unit (str — e.g. "each", "lb", "oz"), available (bool).
        """
        store = self.grocery_stores.get(store_id)
        if not store:
            raise UberEatsError(
                "STORE_NOT_FOUND",
                f"Grocery store '{store_id}' not found.",
                suggested_action="Use search_grocery_stores() to find valid store IDs.",
                context={"store_id": store_id},
            )
        items = [
            item
            for item in self.grocery_catalog.values()
            if item.get("store_id") == store_id
            and (not category or (item.get("category") or "").lower() == category.lower())
        ]
        return deepcopy(items)

    def set_substitution_preference(
        self,
        order_id: str,
        item_id: str,
        preference: str,
        substitute_item_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Set the substitution preference for an item in a grocery order.

        Args:
            order_id (str): The grocery order to update.
            item_id (str): The item to set the preference for.
            preference (str): One of "refund", "substitute", or "contact_me".
            substitute_item_id (str, optional): Required when preference is "substitute".
                The item to substitute with if the original is unavailable.

        Returns:
            Dict[str, Any]: Updated substitution preferences for the order, with:
                order_id (str), item_id (str), preference (str),
                substitute_item_id (str | None).
        """
        o = self._require_order(order_id)
        valid_prefs = {"refund", "substitute", "contact_me"}
        if preference not in valid_prefs:
            raise UberEatsError(
                "INVALID_PREFERENCE",
                f"Preference must be one of {valid_prefs}, got '{preference}'.",
                suggested_action="Use 'refund', 'substitute', or 'contact_me'.",
                context={"preference": preference},
            )
        if preference == "substitute" and not substitute_item_id:
            raise UberEatsError(
                "SUBSTITUTE_REQUIRED",
                "A substitute_item_id is required when preference is 'substitute'.",
                suggested_action="Provide substitute_item_id from the grocery catalog.",
                context={"preference": preference},
            )
        # Verify item is in the order
        found = False
        for item in o.get("items", []):
            if item.get("item_id") == item_id:
                found = True
                break
        if not found:
            raise UberEatsError(
                "ITEM_NOT_IN_ORDER",
                f"Item '{item_id}' is not part of order '{order_id}'.",
                suggested_action="Check the order items with get_order().",
                context={"order_id": order_id, "item_id": item_id},
            )

        subs = o.setdefault("substitution_preferences", {})
        subs[item_id] = {
            "preference": preference,
            "substitute_item_id": substitute_item_id,
        }
        return {
            "order_id": order_id,
            "item_id": item_id,
            "preference": preference,
            "substitute_item_id": substitute_item_id,
        }

    # -----------------------------------------------------------------------
    # Group orders
    # -----------------------------------------------------------------------

    def create_group_order(
        self,
        restaurant_id: str,
        deadline_minutes: int = 30,
    ) -> Dict[str, Any]:
        """
        Create a new group order session for a restaurant.

        Args:
            restaurant_id (str): The restaurant to create a group order for. Must be open.
            deadline_minutes (int): Minutes until the group order closes for new items.
                Defaults to 30.

        Returns:
            Dict[str, Any]: group_order_id (str), restaurant_id (str),
                restaurant_name (str), status (str — "open"),
                deadline_minutes (int), participants (List), created_at (str).
        """
        restaurant = self._require_restaurant(restaurant_id)
        if not restaurant.get("is_open", False):
            raise UberEatsError(
                "RESTAURANT_CLOSED",
                "Restaurant is currently closed.",
                suggested_action="Choose another restaurant or try again during open hours.",
                context={"restaurant_id": restaurant_id},
            )
        group_order_id = self._new_id("group_order")
        now = _utc_now_iso()
        host_name = self.profile.get("name", "Host")

        self.group_orders[group_order_id] = {
            "group_order_id": group_order_id,
            "restaurant_id": restaurant_id,
            "restaurant_name": restaurant.get("name"),
            "status": "open",
            "deadline_minutes": deadline_minutes,
            "host": host_name,
            "participants": [
                {"name": host_name, "items": []}
            ],
            "created_at": now,
        }
        return deepcopy(self.group_orders[group_order_id])

    def join_group_order(
        self,
        group_order_id: str,
        participant_name: str,
    ) -> Dict[str, Any]:
        """
        Join an existing group order session.

        Args:
            group_order_id (str): The group order to join.
            participant_name (str): Display name of the participant joining.

        Returns:
            Dict[str, Any]: Updated group order with the new participant added.
        """
        go = self.group_orders.get(group_order_id)
        if not go:
            raise UberEatsError(
                "GROUP_ORDER_NOT_FOUND",
                f"Group order '{group_order_id}' not found.",
                suggested_action="Check the group order ID and try again.",
                context={"group_order_id": group_order_id},
            )
        if go.get("status") != "open":
            raise UberEatsError(
                "GROUP_ORDER_CLOSED",
                f"Group order '{group_order_id}' is no longer accepting participants.",
                suggested_action="The group order has already been finalized or closed.",
                context={"group_order_id": group_order_id, "status": go.get("status")},
            )
        # Check for duplicate name
        for p in go.get("participants", []):
            if p.get("name") == participant_name:
                raise UberEatsError(
                    "PARTICIPANT_ALREADY_JOINED",
                    f"Participant '{participant_name}' has already joined this group order.",
                    suggested_action="Use a different name or add items directly.",
                    context={"group_order_id": group_order_id, "participant_name": participant_name},
                )
        go["participants"].append({"name": participant_name, "items": []})
        return deepcopy(go)

    def add_group_order_items(
        self,
        group_order_id: str,
        participant_name: str,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Add items to a group order on behalf of a participant.

        Args:
            group_order_id (str): The group order to add items to.
            participant_name (str): The participant adding items.
            items (List[Dict]): Items to add. Each dict requires:
                item_id (str), quantity (int >= 1).
                Optional: selected_options (List), special_instructions (str).

        Returns:
            Dict[str, Any]: Updated group order.
        """
        go = self.group_orders.get(group_order_id)
        if not go:
            raise UberEatsError(
                "GROUP_ORDER_NOT_FOUND",
                f"Group order '{group_order_id}' not found.",
                suggested_action="Check the group order ID and try again.",
                context={"group_order_id": group_order_id},
            )
        if go.get("status") != "open":
            raise UberEatsError(
                "GROUP_ORDER_CLOSED",
                f"Group order '{group_order_id}' is no longer accepting items.",
                suggested_action="The group order has already been finalized.",
                context={"group_order_id": group_order_id, "status": go.get("status")},
            )
        # Find participant
        participant = None
        for p in go.get("participants", []):
            if p.get("name") == participant_name:
                participant = p
                break
        if not participant:
            raise UberEatsError(
                "PARTICIPANT_NOT_FOUND",
                f"Participant '{participant_name}' has not joined this group order.",
                suggested_action="Join the group order first with join_group_order().",
                context={"group_order_id": group_order_id, "participant_name": participant_name},
            )
        if not items:
            raise UberEatsError(
                "EMPTY_ITEMS",
                "No items provided.",
                suggested_action="Provide at least one item.",
                context={},
            )
        restaurant_id = go["restaurant_id"]
        for entry in items:
            item_id = entry.get("item_id")
            item = self._require_menu_item(item_id)
            if not item.get("available", True):
                raise UberEatsError(
                    "ITEM_UNAVAILABLE",
                    f"Item '{item_id}' is currently unavailable.",
                    suggested_action="Choose a different item from get_menu().",
                    context={"item_id": item_id},
                )
            if item.get("restaurant_id") != restaurant_id:
                raise UberEatsError(
                    "ITEM_NOT_FROM_RESTAURANT",
                    f"Item '{item_id}' does not belong to restaurant '{restaurant_id}'.",
                    suggested_action="Only order items from the group order's restaurant.",
                    context={"item_id": item_id, "restaurant_id": restaurant_id},
                )
            qty = max(1, int(entry.get("quantity", 1)))
            participant["items"].append(
                {
                    "item_id": item_id,
                    "name": item.get("name"),
                    "price": float(item.get("price", 0.0)),
                    "quantity": qty,
                    "selected_options": entry.get("selected_options", []),
                    "special_instructions": entry.get("special_instructions", ""),
                }
            )
        return deepcopy(go)

    def finalize_group_order(
        self,
        group_order_id: str,
        delivery_address_id: str,
        payment_method_id: str,
        tip: float = 0.0,
    ) -> str:
        """
        Finalize a group order and place it as a single delivery order.

        Args:
            group_order_id (str): The group order to finalize.
            delivery_address_id (str): Address ID from your profile to deliver to.
            payment_method_id (str): Payment method ID from your profile to charge.
            tip (float): Courier tip in dollars. Defaults to 0.0.

        Returns:
            str: The new order_id for the finalized group order.
        """
        go = self.group_orders.get(group_order_id)
        if not go:
            raise UberEatsError(
                "GROUP_ORDER_NOT_FOUND",
                f"Group order '{group_order_id}' not found.",
                suggested_action="Check the group order ID and try again.",
                context={"group_order_id": group_order_id},
            )
        if go.get("status") != "open":
            raise UberEatsError(
                "GROUP_ORDER_ALREADY_FINALIZED",
                f"Group order '{group_order_id}' has already been finalized.",
                suggested_action="This group order cannot be finalized again.",
                context={"group_order_id": group_order_id, "status": go.get("status")},
            )

        restaurant_id = go["restaurant_id"]
        restaurant = self._require_restaurant(restaurant_id)
        if not restaurant.get("is_open", False):
            raise UberEatsError(
                "RESTAURANT_CLOSED",
                "Restaurant is currently closed.",
                suggested_action="Choose another restaurant or try again during open hours.",
                context={"restaurant_id": restaurant_id},
            )

        # Collect all items from all participants
        all_items = []
        for p in go.get("participants", []):
            all_items.extend(p.get("items", []))
        if not all_items:
            raise UberEatsError(
                "EMPTY_ORDER",
                "Cannot finalize a group order with no items.",
                suggested_action="Participants must add items before finalizing.",
                context={"group_order_id": group_order_id},
            )

        address = self._require_address(delivery_address_id)
        self._require_payment_method(payment_method_id)

        subtotal = sum(
            float(i.get("price", 0.0)) * int(i.get("quantity", 1)) for i in all_items
        )
        delivery_fee = round(float(restaurant.get("delivery_fee", 2.99)), 2)
        service_fee = round(subtotal * 0.10, 2)
        tax = round(subtotal * 0.095, 2)
        tip_amount = round(max(0.0, float(tip)), 2)
        total = round(
            max(0.0, subtotal + delivery_fee + service_fee + tax + tip_amount), 2
        )

        order_id = self._new_id("order")
        now = _utc_now_iso()

        self.orders[order_id] = {
            "order_id": order_id,
            "restaurant_id": restaurant_id,
            "restaurant_name": restaurant.get("name"),
            "items": deepcopy(all_items),
            "fees": {
                "delivery_fee": delivery_fee,
                "service_fee": service_fee,
                "tax": tax,
                "tip": tip_amount,
            },
            "total": total,
            "status": "preparing",
            "created_at": now,
            "applied_promo": None,
            "delivery_address": {
                "street": address.get("street"),
                "city": address.get("city"),
                "state": address.get("state"),
                "zip": address.get("zip"),
            },
            "eta_min": 30,
            "group_order_id": group_order_id,
        }

        self.delivery_tracking[order_id] = {
            "order_id": order_id,
            "courier_name": "Pending assignment",
            "status": "preparing",
            "eta_min": 30,
            "current_stage": "restaurant_preparing",
        }

        go["status"] = "finalized"
        go["order_id"] = order_id

        return order_id
