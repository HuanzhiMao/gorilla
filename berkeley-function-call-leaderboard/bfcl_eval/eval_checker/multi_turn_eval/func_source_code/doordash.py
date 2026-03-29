"""
DoorDash Dummy API (in-memory, deterministic, benchmark-friendly)

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

from .base_service import BaseServiceAPI


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


class DoorDashError(Exception):
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
# DoorDash API
# ---------------------------------------------------------------------------


DEFAULT_STATE = {
    "random_seed": 9012,
    "profile": {},
    "orders": {},
    "restaurants": {},
    "menu": {},
    "offers": {},
    "delivery_tracking": {},
}


class DoorDashAPI(BaseServiceAPI):
    """
    In-memory dummy implementation of a DoorDash-like food delivery service.
    Single-user perspective: profile represents the current user.
    """

    _STATE_KEYS = (
        "profile",
        "orders",
        "restaurants",
        "menu",
        "offers",
        "delivery_tracking",
    )
    _ID_COUNTER_DEFAULTS = {"order": 0}
    _DEFAULT_SEED = 9012

    def __init__(self):
        super().__init__()
        self.profile: Dict[str, Any] = {}
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.restaurants: Dict[str, Dict[str, Any]] = {}
        self.menu: Dict[str, Dict[str, Any]] = {}
        self.offers: Dict[str, Dict[str, Any]] = {}
        self.delivery_tracking: Dict[str, Dict[str, Any]] = {}
        self._api_description = (
            "This tool belongs to the DoorDash food delivery system, which allows users to "
            "browse restaurants, view menus, place and track food delivery orders, manage "
            "their profile and payment methods, apply promotional offers, reorder past meals, "
            "and manage favorite restaurants."
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
        self.orders = scenario.get("orders", DEFAULT_STATE_COPY["orders"])
        self.restaurants = scenario.get("restaurants", DEFAULT_STATE_COPY["restaurants"])
        self.menu = scenario.get("menu", DEFAULT_STATE_COPY["menu"])
        self.offers = scenario.get("offers", DEFAULT_STATE_COPY["offers"])
        self.delivery_tracking = scenario.get("delivery_tracking", DEFAULT_STATE_COPY["delivery_tracking"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, DoorDashAPI):
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
            raise DoorDashError(
                "RESTAURANT_NOT_FOUND",
                f"Restaurant '{restaurant_id}' not found.",
                suggested_action="Use search_restaurants() to find a valid restaurant_id.",
                context={"restaurant_id": restaurant_id},
            )
        return r

    def _require_order(self, order_id: str) -> Dict[str, Any]:
        o = self.orders.get(order_id)
        if not o:
            raise DoorDashError(
                "ORDER_NOT_FOUND",
                f"Order '{order_id}' not found.",
                suggested_action="Use get_order_history() to see valid order IDs.",
                context={"order_id": order_id},
            )
        return o

    def _require_menu_item(self, item_id: str) -> Dict[str, Any]:
        item = self.menu.get(item_id)
        if not item:
            raise DoorDashError(
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
        raise DoorDashError(
            "ADDRESS_NOT_FOUND",
            f"Address '{address_id}' not found in profile.",
            suggested_action="Add the address with add_address() or check get_profile().",
            context={"address_id": address_id},
        )

    def _require_payment_method(self, method_id: str) -> Dict[str, Any]:
        for m in self.profile.get("payment_method", []):
            if m.get("method_id") == method_id:
                return m
        raise DoorDashError(
            "PAYMENT_METHOD_NOT_FOUND",
            f"Payment method '{method_id}' not found in profile.",
            suggested_action="Use list_payment_methods() to see valid method IDs.",
            context={"method_id": method_id},
        )

    # -----------------------------------------------------------------------
    # Profile & account
    # -----------------------------------------------------------------------

    def get_profile(self) -> Dict[str, Any]:
        """
        Retrieve the current user's profile information.

        Returns:
            Dict[str, Any]: Profile with fields:
                name (str), email (str), phone (str),
                address (List[Dict] — saved delivery addresses),
                payment_method (List[Dict] — saved payment methods),
                promo (List[str] — offer_ids in the promo wallet),
                dashpass (bool — DashPass membership status),
                favorites (List[str] — favorited restaurant IDs).
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

    def add_address(
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

    def list_payment_methods(self) -> List[Dict[str, Any]]:
        """
        List all payment methods saved to the user's profile.

        Returns:
            List[Dict[str, Any]]: Payment methods, each with:
                method_id (str), type (str), last4 (str),
                expiration_date (str), billing_name (str), is_default (bool).
        """
        return deepcopy(self.profile.get("payment_method", []))

    def add_payment_method(
        self,
        card_number: str,
        expiration_date: str,
        cvv: str,
        billing_name: str,
    ) -> str:
        """
        Add a new credit or debit card as a payment method.

        Args:
            card_number (str): Full card number; only the last 4 digits are stored.
            expiration_date (str): Card expiry in MM/YY format (e.g. "08/27").
            cvv (str): Card security code (3 or 4 digits); not stored.
            billing_name (str): Cardholder name as it appears on the card.

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
                "billing_name": billing_name,
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

    def place_order(
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
            tip (float): Dasher tip in dollars. Defaults to 0.0.
            offer_id (str, optional): Offer ID from your promo wallet to apply.

        Returns:
            str: The new order_id. The order begins in "preparing" status.
        """
        restaurant = self._require_restaurant(restaurant_id)
        if not restaurant.get("is_open", False):
            raise DoorDashError(
                "RESTAURANT_CLOSED",
                "Restaurant is currently closed.",
                suggested_action="Choose another restaurant or try again during open hours.",
                context={"restaurant_id": restaurant_id},
            )
        if not items:
            raise DoorDashError(
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
                raise DoorDashError(
                    "ITEM_UNAVAILABLE",
                    f"Item '{item_id}' is currently unavailable.",
                    suggested_action="Choose a different item from get_menu().",
                    context={"item_id": item_id},
                )
            if item.get("restaurant_id") != restaurant_id:
                raise DoorDashError(
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
                raise DoorDashError(
                    "OFFER_NOT_FOUND",
                    f"Offer '{offer_id}' not found.",
                    suggested_action="Check get_available_offers() for valid offer IDs.",
                    context={"offer_id": offer_id},
                )
            profile_promos = self.profile.get("promo", [])
            if offer_id not in profile_promos:
                raise DoorDashError(
                    "OFFER_NOT_IN_WALLET",
                    f"Offer '{offer_id}' is not in your promo wallet.",
                    suggested_action="Only offers in your promo wallet can be applied.",
                    context={"offer_id": offer_id},
                )
            min_order = float(offer.get("min_order", 0.0))
            if subtotal < min_order:
                raise DoorDashError(
                    "OFFER_MIN_ORDER_NOT_MET",
                    f"Order subtotal ${subtotal:.2f} is below the minimum ${min_order:.2f} for this offer.",
                    suggested_action="Add more items to meet the minimum order requirement.",
                    context={
                        "offer_id": offer_id,
                        "min_order": min_order,
                        "subtotal": subtotal,
                    },
                )
            if offer.get("dashpass") and not self.profile.get("dashpass", False):
                raise DoorDashError(
                    "DASHPASS_REQUIRED",
                    "This offer requires an active DashPass membership.",
                    suggested_action="Subscribe to DashPass to use this offer.",
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
            "eta_min": 35,
        }

        self.delivery_tracking[order_id] = {
            "order_id": order_id,
            "courier_name": "Pending assignment",
            "status": "preparing",
            "eta_min": 35,
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

    def cancel_order(self, order_id: str, reason: str) -> Dict[str, Any]:
        """
        Cancel an active order. A small fee applies if the restaurant has already started preparing.

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

        fee = 2.99 if status == "preparing" else 0.0
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
                dasher_assigned / dasher_picking_up / en_route / delivered / canceled).
        """
        self._require_order(order_id)
        tracking = self.delivery_tracking.get(order_id)
        if not tracking:
            raise DoorDashError(
                "TRACKING_NOT_FOUND",
                f"No tracking information found for order '{order_id}'.",
                suggested_action="Ensure the order was placed successfully.",
                context={"order_id": order_id},
            )
        return deepcopy(tracking)

    def reorder(
        self,
        order_id: str,
        delivery_address_id: str,
        payment_method_id: str,
        tip: float = 0.0,
    ) -> str:
        """
        Quickly re-place a past order with the same items at the same restaurant.

        Args:
            order_id (str): The past order to repeat.
            delivery_address_id (str): Address ID from your profile for this new delivery.
            payment_method_id (str): Payment method ID from your profile to charge.
            tip (float): Dasher tip in dollars. Defaults to 0.0.

        Returns:
            str: The new order_id for the repeated order.
        """
        past = self._require_order(order_id)
        restaurant_id = past["restaurant_id"]
        restaurant = self._require_restaurant(restaurant_id)
        if not restaurant.get("is_open", False):
            raise DoorDashError(
                "RESTAURANT_CLOSED",
                "Restaurant is currently closed.",
                suggested_action="Try again during open hours.",
                context={"restaurant_id": restaurant_id},
            )
        # Re-use the items from the past order (without special instructions)
        items = [
            {"item_id": i["item_id"], "quantity": i["quantity"]}
            for i in past.get("items", [])
        ]
        return self.place_order(
            restaurant_id=restaurant_id,
            items=items,
            delivery_address_id=delivery_address_id,
            payment_method_id=payment_method_id,
            tip=tip,
        )

    def rate_order(
        self,
        order_id: str,
        rating: int,
        dasher_rating: Optional[int] = None,
        comment: str = "",
    ) -> Dict[str, Any]:
        """
        Submit a rating and optional comment for a completed order.

        Args:
            order_id (str): The delivered order to rate.
            rating (int): Overall food satisfaction score from 1 (worst) to 5 (best).
            dasher_rating (int, optional): Dasher-specific rating from 1 to 5.
            comment (str): Free-text review. Defaults to empty string.

        Returns:
            Dict[str, Any]: Updated order object including the submitted rating.
        """
        o = self._require_order(order_id)
        if o.get("status") != "delivered":
            raise DoorDashError(
                "ORDER_NOT_DELIVERED",
                "Orders can only be rated after delivery is complete.",
                suggested_action="Wait until the order status is 'delivered'.",
                context={"order_id": order_id, "status": o.get("status")},
            )
        r = int(rating)
        if r < 1 or r > 5:
            raise DoorDashError(
                "INVALID_RATING",
                "Rating must be between 1 and 5.",
                suggested_action="Provide an integer rating in [1, 5].",
                context={"rating": rating},
            )
        rating_record: Dict[str, Any] = {"food_rating": r, "comment": comment}
        if dasher_rating is not None:
            dr = int(dasher_rating)
            if dr < 1 or dr > 5:
                raise DoorDashError(
                    "INVALID_RATING",
                    "Dasher rating must be between 1 and 5.",
                    suggested_action="Provide an integer dasher_rating in [1, 5].",
                    context={"dasher_rating": dasher_rating},
                )
            rating_record["dasher_rating"] = dr
        o["rating"] = rating_record
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
                dashpass (bool — DashPass membership required to use),
                in_wallet (bool — True if this offer is already in your promo wallet).
        """
        wallet = set(self.profile.get("promo", []))
        return [
            {
                "offer_id": o["offer_id"],
                "discount": o.get("discount"),
                "min_order": o.get("min_order"),
                "dashpass": o.get("dashpass", False),
                "in_wallet": o["offer_id"] in wallet,
            }
            for o in self.offers.values()
        ]

    def get_dashpass_status(self) -> Dict[str, Any]:
        """
        Retrieve DashPass membership status and associated benefits.

        Returns:
            Dict[str, Any]:
                dashpass (bool): Whether the user has an active DashPass subscription.
                benefits (List[str]): Active benefit descriptions (empty list if no membership).
        """
        dashpass = bool(self.profile.get("dashpass", False))
        benefits = (
            [
                "$0 delivery fee on eligible orders",
                "reduced service fees",
                "member-only deals",
            ]
            if dashpass
            else []
        )
        return {"dashpass": dashpass, "benefits": benefits}

    # -----------------------------------------------------------------------
    # Favorites
    # -----------------------------------------------------------------------

    def add_favorite_restaurant(self, restaurant_id: str) -> Dict[str, Any]:
        """
        Add a restaurant to the user's list of favorite restaurants.

        Args:
            restaurant_id (str): The restaurant to favorite.

        Returns:
            Dict[str, Any]: favorites (List[str] — current list of favorited restaurant IDs).
        """
        self._require_restaurant(restaurant_id)
        favorites = self.profile.setdefault("favorites", [])
        if restaurant_id not in favorites:
            favorites.append(restaurant_id)
        return {"favorites": deepcopy(favorites)}

    def remove_favorite_restaurant(self, restaurant_id: str) -> Dict[str, Any]:
        """
        Remove a restaurant from the user's list of favorite restaurants.

        Args:
            restaurant_id (str): The restaurant to unfavorite.

        Returns:
            Dict[str, Any]: favorites (List[str] — updated list of favorited restaurant IDs).
        """
        favorites = self.profile.get("favorites", [])
        self.profile["favorites"] = [r for r in favorites if r != restaurant_id]
        return {"favorites": deepcopy(self.profile["favorites"])}

    def get_favorite_restaurants(self) -> List[Dict[str, Any]]:
        """
        Retrieve summaries for all favorited restaurants.

        Returns:
            List[Dict[str, Any]]: Restaurant summaries, each with:
                restaurant_id (str), name (str), category (str),
                rating (float), is_open (bool).
                Returns an empty list if the user has no favorites.
        """
        favorites = self.profile.get("favorites", [])
        out = []
        for rid in favorites:
            r = self.restaurants.get(rid)
            if r:
                out.append(
                    {
                        "restaurant_id": r["restaurant_id"],
                        "name": r.get("name"),
                        "category": r.get("category"),
                        "rating": r.get("rating"),
                        "is_open": r.get("is_open"),
                    }
                )
        return deepcopy(out)
