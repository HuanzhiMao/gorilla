"""
Amazon Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Marketplace model: products come from multiple sellers with a Buy Box winner.
- Account-level cart (not store-specific), wish lists, product variations,
  shipping options, Prime membership, and gift features.
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


class AmazonError(Exception):
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


# ---------------------------------------------------------------------------
# Amazon API
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
    "sellers": {},
    "wishlists": {},
}


class AmazonAPI(PatchableMixin):
    """
    In-memory dummy implementation of an Amazon-like marketplace.

    Products are listed by multiple sellers, each with their own price and shipping
    terms. A Buy Box seller is the default for each product. Carts are per-user
    (not per-store). Features include wish lists, product variations (size, color),
    shipping options, Prime membership, gift wrapping, and Subscribe & Save.
    """


    def __init__(self):
        self._id_counters = { "order": 0, "return": 0, "review": 0, "wishlist": 0, "address": 0, "payment": 0, }
        self.profile: Dict[str, Any]
        self.cart: Dict[str, Any]
        self.orders: Dict[str, Dict[str, Any]]
        self.returns: Dict[str, Dict[str, Any]]
        self.reviews: Dict[str, Dict[str, Any]]
        self.products: Dict[str, Dict[str, Any]]
        self.offers: Dict[str, Dict[str, Any]]
        self.shipping_options: Dict[str, Dict[str, Any]]
        self.sellers: Dict[str, Dict[str, Any]]
        self.wishlists: Dict[str, Dict[str, Any]]
        self._api_description = (
            "This tool belongs to the Amazon marketplace system, which allows users to "
            "search products from multiple sellers, manage carts and wish lists, select "
            "shipping options, place orders with optional gift wrapping, handle returns, "
            "and write product reviews."
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
        self.sellers = scenario.get("sellers", DEFAULT_STATE_COPY["sellers"])
        self.wishlists = scenario.get("wishlists", DEFAULT_STATE_COPY["wishlists"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, AmazonAPI):
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

    def _require_product(self, product_id: str) -> Dict[str, Any]:
        product = self.products.get(product_id)
        if not product:
            raise AmazonError(
                "PRODUCT_NOT_FOUND",
                f"Product '{product_id}' not found.",
                suggested_action="Use search_products() to find valid product_ids.",
                context={"product_id": product_id},
            )
        return product

    def _require_order(self, order_id: str) -> Dict[str, Any]:
        order = self.orders.get(order_id)
        if not order:
            raise AmazonError(
                "ORDER_NOT_FOUND",
                f"Order '{order_id}' not found.",
                suggested_action="Use get_order_details() with a valid order_id.",
                context={"order_id": order_id},
            )
        return order

    def _get_buy_box_offer(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Return the Buy Box winner offer for a product, or None."""
        product_offers = [
            o for o in self.offers.values()
            if o.get("product_id") == product_id
        ]
        for offer in product_offers:
            if offer.get("is_buy_box") and offer.get("in_stock", True):
                return offer
        # Fallback: cheapest in-stock offer
        in_stock = [o for o in product_offers if o.get("in_stock", True)]
        if in_stock:
            return min(in_stock, key=lambda o: o.get("price", float("inf")))
        return None

    def _resolve_variant(
        self, product: Dict[str, Any], variant_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Look up a specific variant within a product's options list."""
        if not variant_id:
            return None
        for v in product.get("options", []):
            if v.get("variant_id") == variant_id:
                return v
        raise AmazonError(
            "VARIANT_NOT_FOUND",
            f"Variant '{variant_id}' not found for product '{product.get('product_id')}'.",
            suggested_action="Check get_product_details() for valid variant_ids.",
            context={"product_id": product.get("product_id"), "variant_id": variant_id},
        )

    def _compute_cart_subtotal(self) -> int:
        """Compute the subtotal in cents for the current user's cart."""
        items = self.cart.get("items", [])
        total = 0
        for item in items:
            product_id = item["product_id"]
            variant_id = item.get("variant_id")
            seller_id = item.get("seller_id")
            quantity = int(item.get("quantity", 1))

            # Price from variant if applicable
            product = self.products.get(product_id)
            if product and variant_id:
                variant = None
                for v in product.get("options", []):
                    if v.get("variant_id") == variant_id:
                        variant = v
                        break
                if variant:
                    total += int(variant.get("price", 0)) * quantity
                    continue

            # Price from seller offer
            if seller_id:
                product_offers = [
                    o for o in self.offers.values()
                    if o.get("product_id") == product_id
                ]
                for offer in product_offers:
                    if offer.get("seller_id") == seller_id:
                        total += int(offer.get("price", 0)) * quantity
                        break
                else:
                    # Fallback to buy box
                    bb = self._get_buy_box_offer(product_id)
                    if bb:
                        total += int(bb.get("price", 0)) * quantity
            else:
                bb = self._get_buy_box_offer(product_id)
                if bb:
                    total += int(bb.get("price", 0)) * quantity
        return max(0, total)

    # -----------------------------------------------------------------------
    # Product search & browse
    # -----------------------------------------------------------------------

    def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        min_rating: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for products matching a text query with optional filters.

        Args:
            query (str): Free-text search matched against product name, brand, and
                description. Pass an empty string to match all.
            category (str, optional): Filter by product category, e.g. "electronics",
                "books", "clothing", "home", "grocery". None returns all categories.
            min_price (int, optional): Minimum Buy Box price in cents. None for no lower bound.
            max_price (int, optional): Maximum Buy Box price in cents. None for no upper bound.
            min_rating (float, optional): Minimum average star rating (e.g. 4.0). None for no filter.

        Returns:
            List[Dict[str, Any]]: Matching products, each with fields:
                product_id (str), name (str), brand (str), category (str),
                rating (float), review_count (int), buy_box_price (int | None, cents),
                has_variations (bool), prime_eligible (bool).
        """
        results = []
        for p in self.products.values():
            name = p.get("name", "")
            brand = p.get("brand", "")
            desc = p.get("description", "")
            if not (
                _matches_query(name, query)
                or _matches_query(brand, query)
                or _matches_query(desc, query)
            ):
                continue
            if category and p.get("category") != category:
                continue
            if min_rating is not None and float(p.get("rating", 0)) < float(min_rating):
                continue
            bb = self._get_buy_box_offer(p["product_id"])
            bb_price = int(bb["price"]) if bb else None
            if bb_price is not None:
                if min_price is not None and bb_price < int(min_price):
                    continue
                if max_price is not None and bb_price > int(max_price):
                    continue
            # Determine prime eligibility from buy box seller
            prime_eligible = False
            if bb:
                seller = self.sellers.get(bb.get("seller_id", ""))
                if seller:
                    prime_eligible = seller.get("prime_eligible", False)
            results.append(
                {
                    "product_id": p["product_id"],
                    "name": name,
                    "brand": brand,
                    "category": p.get("category", ""),
                    "rating": p.get("rating", 0.0),
                    "review_count": p.get("review_count", 0),
                    "buy_box_price": bb_price,
                    "has_variations": len(p.get("options", [])) > 0,
                    "prime_eligible": prime_eligible,
                }
            )
        return results

    def get_product_details(self, product_id: str) -> Dict[str, Any]:
        """
        Retrieve full details for a product including description, images,
        variations (size, color), and the Buy Box offer.

        Args:
            product_id (str): The product to look up.

        Returns:
            Dict[str, Any]:
                product_id (str), name (str), brand (str), category (str),
                description (str), images (List[str]), rating (float),
                review_count (int), variations (List[Dict] — each with variant_id,
                attributes {size?, color?}, price (int, cents), in_stock (bool)),
                buy_box (Dict | None — seller_id, price, shipping_cost, condition).
        """
        product = self._require_product(product_id)
        bb = self._get_buy_box_offer(product_id)
        buy_box = None
        if bb:
            buy_box = {
                "seller_id": bb.get("seller_id"),
                "price": bb.get("price"),
                "shipping_cost": bb.get("shipping_cost", 0),
                "condition": bb.get("condition", "new"),
            }
        return {
            "product_id": product_id,
            "name": product.get("name", ""),
            "brand": product.get("brand", ""),
            "category": product.get("category", ""),
            "description": product.get("description", ""),
            "images": deepcopy(product.get("images", [])),
            "rating": product.get("rating", 0.0),
            "review_count": product.get("review_count", 0),
            "variations": deepcopy(product.get("options", [])),
            "buy_box": buy_box,
        }

    def get_product_offers(self, product_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all seller offers for a product (the "Other Sellers on Amazon" list).

        Args:
            product_id (str): The product to get offers for.

        Returns:
            List[Dict[str, Any]]: Seller offers, each with:
                seller_id (str), seller_name (str), price (int, cents),
                shipping_cost (int, cents), shipping_speed (str),
                is_buy_box (bool), in_stock (bool), condition (str — "new", "used", "refurbished").
        """
        self._require_product(product_id)
        product_offers = [
            o for o in self.offers.values()
            if o.get("product_id") == product_id
        ]
        results = []
        for o in product_offers:
            seller = self.sellers.get(o.get("seller_id", ""), {})
            results.append(
                {
                    "seller_id": o.get("seller_id"),
                    "seller_name": seller.get("name", "Unknown Seller"),
                    "price": o.get("price", 0),
                    "shipping_cost": o.get("shipping_cost", 0),
                    "shipping_speed": o.get("shipping_speed", "standard"),
                    "is_buy_box": o.get("is_buy_box", False),
                    "in_stock": o.get("in_stock", True),
                    "condition": o.get("condition", "new"),
                }
            )
        return results

    # -----------------------------------------------------------------------
    # Cart management
    # -----------------------------------------------------------------------

    def add_to_cart(
        self,
        product_id: str,
        quantity: int,
        variant_id: Optional[str] = None,
        seller_id: Optional[str] = None,
        gift_wrap: bool = False,
        gift_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a product to the current user's cart. If seller_id is not specified, the Buy Box
        seller is used. If the product has variations, variant_id should be specified.

        Args:
            product_id (str): The product to add.
            quantity (int): Number of units; must be >= 1.
            variant_id (str, optional): Specific variant (size/color). Required for
                products with variations.
            seller_id (str, optional): Specific seller to buy from. Defaults to Buy Box winner.
            gift_wrap (bool): Whether to gift-wrap this item. Defaults to False.
            gift_message (str, optional): Gift message to include (only if gift_wrap is True).

        Returns:
            Dict[str, Any]: Updated cart object including all items and computed subtotal.
        """
        user_id = self.user_id
        product = self._require_product(product_id)

        qty = int(quantity)
        if qty < 1:
            raise AmazonError(
                "INVALID_QUANTITY",
                "Quantity must be >= 1.",
                suggested_action="Provide a quantity of at least 1.",
                context={"quantity": quantity},
            )

        # Resolve variant
        if variant_id:
            variant = self._resolve_variant(product, variant_id)
            if not variant.get("in_stock", True):
                raise AmazonError(
                    "VARIANT_OUT_OF_STOCK",
                    f"Variant '{variant_id}' is out of stock.",
                    suggested_action="Choose a different variant.",
                    context={"product_id": product_id, "variant_id": variant_id},
                )
        elif product.get("options"):
            raise AmazonError(
                "VARIANT_REQUIRED",
                "This product has variations. Please specify a variant_id.",
                suggested_action="Call get_product_details() to see available variants.",
                context={"product_id": product_id},
            )

        # Resolve seller
        if not seller_id:
            bb = self._get_buy_box_offer(product_id)
            if not bb:
                raise AmazonError(
                    "NO_OFFERS_AVAILABLE",
                    "No seller offers available for this product.",
                    suggested_action="Try a different product.",
                    context={"product_id": product_id},
                )
            seller_id = bb["seller_id"]
        else:
            if seller_id not in self.sellers:
                raise AmazonError(
                    "SELLER_NOT_FOUND",
                    f"Seller '{seller_id}' not found.",
                    suggested_action="Use get_product_offers() to find valid seller_ids.",
                    context={"seller_id": seller_id},
                )
            # Verify seller has an offer for this product
            product_offers = [
                o for o in self.offers.values()
                if o.get("product_id") == product_id
            ]
            seller_offer = None
            for o in product_offers:
                if o.get("seller_id") == seller_id and o.get("in_stock", True):
                    seller_offer = o
                    break
            if not seller_offer:
                raise AmazonError(
                    "SELLER_OFFER_UNAVAILABLE",
                    f"Seller '{seller_id}' has no in-stock offer for product '{product_id}'.",
                    suggested_action="Use get_product_offers() to find available sellers.",
                    context={"seller_id": seller_id, "product_id": product_id},
                )

        # Check if same product+variant+seller already in cart
        for item in self.cart["items"]:
            if (
                item["product_id"] == product_id
                and item.get("variant_id") == variant_id
                and item.get("seller_id") == seller_id
            ):
                item["quantity"] += qty
                if gift_wrap:
                    item["gift_wrap"] = True
                if gift_message is not None:
                    item["gift_message"] = gift_message
                self.cart["subtotal"] = self._compute_cart_subtotal()
                return deepcopy(self.cart)

        self.cart["items"].append(
            {
                "product_id": product_id,
                "variant_id": variant_id,
                "seller_id": seller_id,
                "quantity": qty,
                "gift_wrap": gift_wrap,
                "gift_message": gift_message if gift_wrap else None,
            }
        )
        self.cart["subtotal"] = self._compute_cart_subtotal()
        return deepcopy(self.cart)

    def update_cart_item(
        self,
        product_id: str,
        quantity: Optional[int] = None,
        gift_wrap: Optional[bool] = None,
        gift_message: Optional[str] = None,
        variant_id: Optional[str] = None,
        seller_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an item already in the cart. Items are identified by the combination
        of product_id, variant_id, and seller_id.

        Args:
            product_id (str): The product to update.
            quantity (int, optional): New quantity; must be >= 1.
                Use remove_from_cart() to delete an item.
            gift_wrap (bool, optional): Update gift-wrap preference.
            gift_message (str, optional): Update gift message.
            variant_id (str, optional): Variant identifier to match the correct cart item.
            seller_id (str, optional): Seller identifier to match the correct cart item.

        Returns:
            Dict[str, Any]: Updated cart object.
        """
        user_id = self.user_id
        if not self.cart.get("items"):
            raise AmazonError(
                "CART_EMPTY",
                "Cart is empty.",
                suggested_action="Add items with add_to_cart() first.",
                context={"user_id": user_id},
            )
        found = None
        for item in self.cart["items"]:
            if (
                item["product_id"] == product_id
                and item.get("variant_id") == variant_id
                and item.get("seller_id") == seller_id
            ):
                found = item
                break
        if not found:
            raise AmazonError(
                "ITEM_NOT_IN_CART",
                f"Product '{product_id}' (variant={variant_id}, seller={seller_id}) not in cart.",
                suggested_action="Call get_cart() to see current items.",
                context={
                    "product_id": product_id,
                    "variant_id": variant_id,
                    "seller_id": seller_id,
                },
            )
        if quantity is not None:
            q = int(quantity)
            if q < 1:
                raise AmazonError(
                    "INVALID_QUANTITY",
                    "Quantity must be >= 1. Use remove_from_cart() to remove an item.",
                    suggested_action="Provide quantity >= 1 or call remove_from_cart().",
                    context={"quantity": quantity},
                )
            found["quantity"] = q
        if gift_wrap is not None:
            found["gift_wrap"] = bool(gift_wrap)
        if gift_message is not None:
            found["gift_message"] = gift_message
        self.cart["subtotal"] = self._compute_cart_subtotal()
        return deepcopy(self.cart)

    def remove_from_cart(
        self,
        product_id: str,
        variant_id: Optional[str] = None,
        seller_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Remove an item from the cart.

        Args:
            product_id (str): The product to remove.
            variant_id (str, optional): Variant identifier to match the correct cart item.
            seller_id (str, optional): Seller identifier to match the correct cart item.

        Returns:
            Dict[str, Any]: Updated cart object.
        """
        user_id = self.user_id
        if not self.cart.get("items"):
            raise AmazonError(
                "CART_EMPTY",
                "Cart is empty.",
                suggested_action="Nothing to remove.",
                context={"user_id": user_id},
            )
        before = len(self.cart["items"])
        self.cart["items"] = [
            i
            for i in self.cart["items"]
            if not (
                i["product_id"] == product_id
                and i.get("variant_id") == variant_id
                and i.get("seller_id") == seller_id
            )
        ]
        if len(self.cart["items"]) == before:
            raise AmazonError(
                "ITEM_NOT_IN_CART",
                f"Product '{product_id}' (variant={variant_id}, seller={seller_id}) not in cart.",
                suggested_action="Call get_cart() to see current items.",
                context={
                    "product_id": product_id,
                    "variant_id": variant_id,
                    "seller_id": seller_id,
                },
            )
        self.cart["subtotal"] = self._compute_cart_subtotal()
        return deepcopy(self.cart)

    def get_cart(self) -> Dict[str, Any]:
        """
        Retrieve the current state of the current user's cart with a freshly computed subtotal.

        Returns:
            Dict[str, Any]: Cart object including items (List), subtotal (int, cents),
                item_count (int).
        """
        user_id = self.user_id
        self.cart["subtotal"] = self._compute_cart_subtotal()
        self.cart["item_count"] = sum(
            i.get("quantity", 1) for i in self.cart.get("items", [])
        )
        return deepcopy(self.cart)

    # -----------------------------------------------------------------------
    # Wish lists
    # -----------------------------------------------------------------------

    def add_to_wishlist(
        self,
        product_id: str,
        wishlist_id: Optional[str] = None,
        variant_id: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a product to a wish list. If no wishlist_id is specified, the current user's
        default wish list is used (created automatically if it does not exist).

        Args:
            product_id (str): The product to add to the wish list.
            wishlist_id (str, optional): Target wish list. Defaults to the user's default list.
            variant_id (str, optional): Specific variant to wish-list.
            note (str, optional): Personal note about why you want this item.

        Returns:
            Dict[str, Any]: Updated wish list object.
        """
        user_id = self.user_id
        self._require_product(product_id)

        # Find or create default wishlist
        if not wishlist_id:
            for wid, wl in self.wishlists.items():
                if wl.get("user_id") == user_id and wl.get("is_default"):
                    wishlist_id = wid
                    break
            if not wishlist_id:
                wishlist_id = self._new_id("wishlist")
                self.wishlists[wishlist_id] = {
                    "wishlist_id": wishlist_id,
                    "user_id": user_id,
                    "name": "My Wish List",
                    "items": [],
                    "is_default": True,
                    "is_public": False,
                    "created_at": _utc_now_iso(),
                }

        wl = self.wishlists.get(wishlist_id)
        if not wl:
            raise AmazonError(
                "WISHLIST_NOT_FOUND",
                f"Wish list '{wishlist_id}' not found.",
                suggested_action="Use get_wishlist() to see valid wishlist_ids.",
                context={"wishlist_id": wishlist_id},
            )
        if wl.get("user_id") != user_id:
            raise AmazonError(
                "WISHLIST_ACCESS_DENIED",
                "You do not own this wish list.",
                suggested_action="Use your own wishlist_id.",
                context={"wishlist_id": wishlist_id, "user_id": user_id},
            )

        # Check for duplicates
        for existing in wl["items"]:
            if (
                existing["product_id"] == product_id
                and existing.get("variant_id") == variant_id
            ):
                if note is not None:
                    existing["note"] = note
                return deepcopy(wl)

        wl["items"].append(
            {
                "product_id": product_id,
                "variant_id": variant_id,
                "added_at": _utc_now_iso(),
                "note": note,
            }
        )
        return deepcopy(wl)

    def get_wishlist(
        self,
        wishlist_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve a wish list. If no wishlist_id is provided, returns the current user's
        default wish list.

        Args:
            wishlist_id (str, optional): Specific wish list to retrieve. Defaults to
                the user's default list.

        Returns:
            Dict[str, Any]: Wish list object with:
                wishlist_id (str), name (str), items (List[Dict]), is_default (bool),
                is_public (bool).
        """
        user_id = self.user_id
        if wishlist_id:
            wl = self.wishlists.get(wishlist_id)
            if not wl:
                raise AmazonError(
                    "WISHLIST_NOT_FOUND",
                    f"Wish list '{wishlist_id}' not found.",
                    suggested_action="Verify the wishlist_id.",
                    context={"wishlist_id": wishlist_id},
                )
            if wl.get("user_id") != user_id and not wl.get("is_public", False):
                raise AmazonError(
                    "WISHLIST_ACCESS_DENIED",
                    "This wish list is private.",
                    suggested_action="Request access from the wish list owner.",
                    context={"wishlist_id": wishlist_id},
                )
            return deepcopy(wl)
        # Default wishlist
        for wl in self.wishlists.values():
            if wl.get("user_id") == user_id and wl.get("is_default"):
                return deepcopy(wl)
        # No default exists yet
        return {
            "wishlist_id": None,
            "user_id": user_id,
            "name": "My Wish List",
            "items": [],
            "is_default": True,
            "is_public": False,
        }

    def remove_from_wishlist(
        self,
        product_id: str,
        wishlist_id: Optional[str] = None,
        variant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Remove a product from a wish list.

        Args:
            product_id (str): The product to remove.
            wishlist_id (str, optional): Target wish list. Defaults to the user's default list.
            variant_id (str, optional): Specific variant to remove.

        Returns:
            Dict[str, Any]: Updated wish list object.
        """
        user_id = self.user_id
        if not wishlist_id:
            for wid, wl in self.wishlists.items():
                if wl.get("user_id") == user_id and wl.get("is_default"):
                    wishlist_id = wid
                    break
        if not wishlist_id:
            raise AmazonError(
                "WISHLIST_NOT_FOUND",
                "No default wish list found.",
                suggested_action="Create a wish list first by adding an item with add_to_wishlist().",
                context={"user_id": user_id},
            )
        wl = self.wishlists.get(wishlist_id)
        if not wl or wl.get("user_id") != user_id:
            raise AmazonError(
                "WISHLIST_NOT_FOUND",
                f"Wish list '{wishlist_id}' not found or not owned by user.",
                suggested_action="Use get_wishlist() to verify.",
                context={"wishlist_id": wishlist_id, "user_id": user_id},
            )
        before = len(wl["items"])
        wl["items"] = [
            i
            for i in wl["items"]
            if not (i["product_id"] == product_id and i.get("variant_id") == variant_id)
        ]
        if len(wl["items"]) == before:
            raise AmazonError(
                "ITEM_NOT_IN_WISHLIST",
                f"Product '{product_id}' (variant={variant_id}) not in wish list.",
                suggested_action="Call get_wishlist() to see current items.",
                context={"product_id": product_id, "variant_id": variant_id},
            )
        return deepcopy(wl)

    # -----------------------------------------------------------------------
    # Shipping
    # -----------------------------------------------------------------------

    def select_shipping_option(
        self,
        shipping_option: str,
    ) -> Dict[str, Any]:
        """
        Select a shipping option for the current user's cart. The selected option applies to
        the entire order at checkout.

        Args:
            shipping_option (str): Shipping speed key. One of:
                "standard" - 5-8 business days ($5.99).
                "expedited" - 2-3 business days ($12.99).
                "prime_two_day" - 2 days (free, Prime only).
                "prime_one_day" - 1 day (free, Prime only).
                "prime_same_day" - Same day (free, Prime only).

        Returns:
            Dict[str, Any]:
                selected (str): The shipping option that was set.
                cost (int, cents): Shipping cost for this option.
                eta_days (List[int]): Estimated delivery range in days [min, max].
        """
        user_id = self.user_id
        option = self.shipping_options.get(shipping_option)
        if not option:
            raise AmazonError(
                "INVALID_SHIPPING_OPTION",
                f"Shipping option '{shipping_option}' is not valid.",
                suggested_action="Use one of: standard, expedited, prime_two_day, prime_one_day, prime_same_day.",
                context={"shipping_option": shipping_option},
            )
        if option.get("requires_prime") and not self.profile.get("membership", {}).get("prime_member", False):
            raise AmazonError(
                "PRIME_REQUIRED",
                "This shipping option requires an active Prime membership.",
                suggested_action="Use 'standard' or 'expedited' shipping, or upgrade to Prime.",
                context={"shipping_option": shipping_option},
            )
        # Store selection on the cart
        self.cart["shipping_option"] = shipping_option
        return {
            "selected": shipping_option,
            "cost": option.get("cost", 0),
            "eta_days": deepcopy(option.get("eta_days", [5, 8])),
        }

    # -----------------------------------------------------------------------
    # Coupons
    # -----------------------------------------------------------------------

    def apply_coupon(self, coupon_code: str) -> Dict[str, Any]:
        """
        Apply a coupon code to the current user's cart. Validates eligibility without
        consuming the coupon (consumption happens at place_order).

        Args:
            coupon_code (str): The coupon code to apply.

        Returns:
            Dict[str, Any]:
                applied (bool): Whether the coupon was successfully applied.
                reason (str): "OK" or an error code such as COUPON_NOT_FOUND,
                    COUPON_EXPIRED, MIN_ORDER_NOT_MET, PRODUCT_NOT_ELIGIBLE.
                discount_preview (int): Estimated discount in cents (0 if not applied).
        """
        user_id = self.user_id
        subtotal = self._compute_cart_subtotal()
        promos = self.profile.get("promos", {})
        coupon = promos.get(coupon_code)
        if not coupon:
            # Case-insensitive fallback
            for code, c in promos.items():
                if code.upper() == coupon_code.upper():
                    coupon = c
                    coupon_code = code
                    break
        if not coupon:
            return {
                "applied": False,
                "reason": "COUPON_NOT_FOUND",
                "discount_preview": 0,
            }

        expiry = coupon.get("expiry")
        if expiry and _utc_now_iso() > expiry:
            return {"applied": False, "reason": "COUPON_EXPIRED", "discount_preview": 0}

        min_order = int(coupon.get("min_order", coupon.get("min_purchase", 0)))
        if subtotal < min_order:
            return {
                "applied": False,
                "reason": "MIN_ORDER_NOT_MET",
                "discount_preview": 0,
            }

        # Check product eligibility
        eligible_products = coupon.get("applicable_product_ids")
        if not eligible_products:
            # Also check single product_id field
            single_pid = coupon.get("product_id")
            if single_pid:
                eligible_products = [single_pid]
        if eligible_products:
            cart_product_ids = {i["product_id"] for i in self.cart.get("items", [])}
            if not cart_product_ids.intersection(set(eligible_products)):
                return {
                    "applied": False,
                    "reason": "PRODUCT_NOT_ELIGIBLE",
                    "discount_preview": 0,
                }

        # Compute discount preview
        discount = self._compute_coupon_discount(coupon, subtotal)

        self.cart["applied_promo"] = coupon_code
        return {"applied": True, "reason": "OK", "discount_preview": discount}

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
    # Checkout & orders
    # -----------------------------------------------------------------------

    def place_order(
        self,
        address_id: str,
        payment_method_id: str,
    ) -> str:
        """
        Place an order from the current user's cart. Charges the payment method and
        creates an order record. The cart is emptied after a successful order.

        Args:
            address_id (str): Shipping address ID (from list_addresses()).
            payment_method_id (str): Payment method ID (from list_payment_methods()).

        Returns:
            str: The new order_id. The order begins in "processing" status.
        """
        user_id = self.user_id
        if not self.cart.get("items"):
            raise AmazonError(
                "CART_EMPTY",
                "Cannot place an order with an empty cart.",
                suggested_action="Add items to the cart before calling place_order().",
                context={"user_id": user_id},
            )

        # Validate address
        addr = self.profile.get("addresses", {}).get(address_id)
        if not addr:
            raise AmazonError(
                "ADDRESS_NOT_FOUND",
                f"Address '{address_id}' not found for this user.",
                suggested_action="Call list_addresses() to get valid address IDs.",
                context={"address_id": address_id, "user_id": user_id},
            )

        # Validate payment method
        pm = self.profile.get("payment_methods", {}).get(payment_method_id)
        if not pm:
            raise AmazonError(
                "PAYMENT_METHOD_NOT_FOUND",
                f"Payment method '{payment_method_id}' not found for this user.",
                suggested_action="Call list_payment_methods() to get valid method IDs.",
                context={"payment_method_id": payment_method_id, "user_id": user_id},
            )

        subtotal = self._compute_cart_subtotal()
        is_prime = self.profile.get("membership", {}).get("prime_member", False)

        # Shipping
        shipping_key = self.cart.get("shipping_option", "standard")
        shipping_opt = self.shipping_options.get(
            shipping_key, self.shipping_options.get("standard", {})
        )
        if shipping_opt.get("requires_prime") and not is_prime:
            shipping_key = "standard"
            shipping_opt = self.shipping_options.get("standard", {})
        shipping_cost = int(shipping_opt.get("cost", 0))

        # Free standard shipping for Prime members on orders over $25
        if is_prime and subtotal >= 2500:
            shipping_cost = 0

        # Coupon discount
        coupon_discount = 0
        coupon_code = self.cart.get("applied_promo")
        promos = self.profile.get("promos", {})
        if coupon_code and coupon_code in promos:
            coupon_discount = self._compute_coupon_discount(
                promos[coupon_code], subtotal
            )

        tax = int(round(subtotal * 0.087))
        total = max(0, subtotal + shipping_cost + tax - coupon_discount)

        # Compute estimated delivery
        eta_days = shipping_opt.get("eta_days", [5, 8])

        order_id = self._new_id("order")
        now = _utc_now_iso()

        # Generate tracking number
        tracking = f"TRK{self._rng.randint(100000000, 999999999)}"

        self.orders[order_id] = {
            "order_id": order_id,
            "user_id": user_id,
            "items": deepcopy(self.cart["items"]),
            "status": "processing",
            "shipping_option": shipping_key,
            "tracking_number": tracking,
            "address_id": address_id,
            "payment_method_id": payment_method_id,
            "pricing": {
                "subtotal": subtotal,
                "shipping": shipping_cost,
                "tax": tax,
                "coupon_discount": coupon_discount,
                "total": total,
            },
            "placed_at": now,
            "updated_at": now,
            "estimated_delivery_days": deepcopy(eta_days),
        }

        # Clear the cart
        self.cart["items"] = []
        self.cart["subtotal"] = 0
        self.cart["applied_promo"] = None
        self.cart["shipping_option"] = None

        return order_id

    def get_order_details(self, order_id: str) -> Dict[str, Any]:
        """
        Retrieve full details for an order. The order must belong to the current user.

        Args:
            order_id (str): The order to look up.

        Returns:
            Dict[str, Any]:
                order_id (str), user_id (str), items (List[Dict]), status (str —
                    one of: processing, shipped, out_for_delivery, delivered, canceled,
                    returned), shipping_option (str), tracking_number (str | None),
                address_id (str), pricing (Dict), placed_at (str),
                estimated_delivery_days (List[int]).
        """
        order = self._require_order(order_id)
        if order.get("user_id") != self.user_id:
            raise PermissionError("You do not have permission to access this resource.")
        return deepcopy(order)

    def cancel_order(self, order_id: str, reason: str) -> Dict[str, Any]:
        """
        Cancel an order. Only orders in "processing" status can be canceled.
        Orders that have already shipped must go through the return process.
        The order must belong to the current user.

        Args:
            order_id (str): The order to cancel.
            reason (str): Short description of why the order is being canceled.

        Returns:
            Dict[str, Any]:
                order_id (str), canceled (bool), reason (str — "OK" or "NOT_CANCELABLE").
        """
        order = self._require_order(order_id)
        if order.get("user_id") != self.user_id:
            raise PermissionError("You do not have permission to access this resource.")
        status = order.get("status")
        if status != "processing":
            return {
                "order_id": order_id,
                "canceled": False,
                "reason": "NOT_CANCELABLE",
                "message": f"Order is in '{status}' status. Only 'processing' orders can be canceled.",
            }
        order["status"] = "canceled"
        order["updated_at"] = _utc_now_iso()
        order["cancel_reason"] = reason
        return {
            "order_id": order_id,
            "canceled": True,
            "reason": "OK",
        }

    def request_return(
        self,
        order_id: str,
        product_id: str,
        reason: str,
    ) -> str:
        """
        Request a return for a specific product from a delivered order.
        The order must belong to the current user.

        Args:
            order_id (str): The order containing the item to return.
            product_id (str): The product to return.
            reason (str): Reason for the return, e.g. "defective", "wrong_item",
                "not_as_described", "no_longer_needed", "other".

        Returns:
            str: The new return_id for tracking the return.
        """
        order = self._require_order(order_id)
        if order.get("user_id") != self.user_id:
            raise PermissionError("You do not have permission to access this resource.")
        if order.get("status") not in {"delivered", "shipped", "out_for_delivery"}:
            raise AmazonError(
                "RETURN_NOT_ALLOWED",
                f"Cannot return items from an order in '{order.get('status')}' status.",
                suggested_action="Only delivered or shipped orders can be returned.",
                context={"order_id": order_id, "status": order.get("status")},
            )
        # Verify product is in the order
        found = False
        item_price = 0
        for item in order.get("items", []):
            if item["product_id"] == product_id:
                found = True
                # Estimate refund from seller offer
                product_offers = [
                    o for o in self.offers.values()
                    if o.get("product_id") == product_id
                ]
                sid = item.get("seller_id")
                for o in product_offers:
                    if o.get("seller_id") == sid:
                        item_price = int(o.get("price", 0)) * int(
                            item.get("quantity", 1)
                        )
                        break
                if item_price == 0:
                    bb = self._get_buy_box_offer(product_id)
                    if bb:
                        item_price = int(bb.get("price", 0)) * int(
                            item.get("quantity", 1)
                        )
                break
        if not found:
            raise AmazonError(
                "PRODUCT_NOT_IN_ORDER",
                f"Product '{product_id}' is not in order '{order_id}'.",
                suggested_action="Verify the product_id against get_order_details().",
                context={"order_id": order_id, "product_id": product_id},
            )

        return_id = self._new_id("return")
        self.returns[return_id] = {
            "return_id": return_id,
            "order_id": order_id,
            "product_id": product_id,
            "reason": reason,
            "status": "requested",
            "refund_amount": item_price,
            "created_at": _utc_now_iso(),
        }
        return return_id

    def track_shipment(self, order_id: str) -> Dict[str, Any]:
        """
        Get tracking information for a shipped order. The order must belong to
        the current user.

        Args:
            order_id (str): The order to track.

        Returns:
            Dict[str, Any]:
                order_id (str), tracking_number (str), status (str),
                shipping_option (str), estimated_delivery_days (List[int]),
                events (List[Dict] — shipping event history).
        """
        order = self._require_order(order_id)
        if order.get("user_id") != self.user_id:
            raise PermissionError("You do not have permission to access this resource.")
        status = order.get("status")
        tracking = order.get("tracking_number")
        if status == "processing":
            events = [{"event": "Order placed", "timestamp": order.get("placed_at")}]
        elif status == "shipped":
            events = [
                {"event": "Order placed", "timestamp": order.get("placed_at")},
                {"event": "Package shipped", "timestamp": order.get("updated_at")},
            ]
        elif status == "out_for_delivery":
            events = [
                {"event": "Order placed", "timestamp": order.get("placed_at")},
                {"event": "Package shipped", "timestamp": order.get("placed_at")},
                {"event": "Out for delivery", "timestamp": order.get("updated_at")},
            ]
        elif status == "delivered":
            events = [
                {"event": "Order placed", "timestamp": order.get("placed_at")},
                {"event": "Package shipped", "timestamp": order.get("placed_at")},
                {"event": "Out for delivery", "timestamp": order.get("placed_at")},
                {"event": "Delivered", "timestamp": order.get("updated_at")},
            ]
        else:
            events = [
                {"event": f"Order {status}", "timestamp": order.get("updated_at")}
            ]
        return {
            "order_id": order_id,
            "tracking_number": tracking,
            "status": status,
            "shipping_option": order.get("shipping_option"),
            "estimated_delivery_days": deepcopy(
                order.get("estimated_delivery_days", [])
            ),
            "events": events,
        }

    # -----------------------------------------------------------------------
    # Reviews
    # -----------------------------------------------------------------------

    def write_review(
        self,
        product_id: str,
        rating: int,
        title: str,
        body: str,
    ) -> str:
        """
        Write a product review. A user can only write one review per product.

        Args:
            product_id (str): The product being reviewed.
            rating (int): Star rating from 1 (worst) to 5 (best).
            title (str): Short review headline.
            body (str): Detailed review text.

        Returns:
            str: The new review_id.
        """
        user_id = self.user_id
        self._require_product(product_id)
        r = int(rating)
        if r < 1 or r > 5:
            raise AmazonError(
                "INVALID_RATING",
                "Rating must be between 1 and 5.",
                suggested_action="Provide an integer rating in [1, 5].",
                context={"rating": rating},
            )
        # Check for existing review by this user for this product
        for rev in self.reviews.values():
            if rev.get("user_id") == user_id and rev.get("product_id") == product_id:
                raise AmazonError(
                    "DUPLICATE_REVIEW",
                    "You have already reviewed this product.",
                    suggested_action="You can only submit one review per product.",
                    context={"user_id": user_id, "product_id": product_id},
                )

        # Check if user has purchased this product (verified purchase)
        verified = False
        for order in self.orders.values():
            if order.get("user_id") == user_id and order.get("status") in {
                "delivered",
                "shipped",
                "out_for_delivery",
            }:
                for item in order.get("items", []):
                    if item.get("product_id") == product_id:
                        verified = True
                        break
            if verified:
                break

        review_id = self._new_id("review")
        self.reviews[review_id] = {
            "review_id": review_id,
            "product_id": product_id,
            "user_id": user_id,
            "rating": r,
            "title": title,
            "body": body,
            "verified_purchase": verified,
            "created_at": _utc_now_iso(),
        }

        # Update product rating (running average)
        product = self.products.get(product_id)
        if product:
            old_count = int(product.get("review_count", 0))
            old_rating = float(product.get("rating", 0.0))
            new_count = old_count + 1
            new_rating = round(((old_rating * old_count) + r) / new_count, 1)
            product["rating"] = new_rating
            product["review_count"] = new_count

        return review_id

    def get_reviews(
        self,
        product_id: str,
        min_rating: Optional[int] = None,
        verified_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve reviews for a product with optional filters.

        Args:
            product_id (str): The product to get reviews for.
            min_rating (int, optional): Only return reviews with this minimum rating.
            verified_only (bool): If True, only return verified-purchase reviews.

        Returns:
            List[Dict[str, Any]]: Reviews, each with:
                review_id (str), rating (int), title (str), body (str),
                user_id (str), verified_purchase (bool), created_at (str).
        """
        self._require_product(product_id)
        results = []
        for rev in self.reviews.values():
            if rev.get("product_id") != product_id:
                continue
            if min_rating is not None and int(rev.get("rating", 0)) < int(min_rating):
                continue
            if verified_only and not rev.get("verified_purchase", False):
                continue
            results.append(deepcopy(rev))
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    # -----------------------------------------------------------------------
    # Account: addresses
    # -----------------------------------------------------------------------

    def list_addresses(self) -> List[Dict[str, Any]]:
        """
        List all shipping addresses saved to the current user's account.

        Returns:
            List[Dict[str, Any]]: Address objects, each with:
                address_id (str), name (str), street (str), city (str),
                state (str), zip (str), country (str), is_default (bool).
        """
        user_id = self.user_id
        results = []
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
        country: str = "US",
        is_default: bool = False,
    ) -> str:
        """
        Add a new shipping address to the current user's account.

        Args:
            name (str): Recipient name for this address.
            street (str): Street address (e.g. "123 Main St, Apt 4B").
            city (str): City name.
            state (str): State abbreviation (e.g. "WA").
            zip_code (str): ZIP or postal code.
            country (str): Country code. Defaults to "US".
            is_default (bool): If True, set as the default shipping address.

        Returns:
            str: The new address_id.
        """
        user_id = self.user_id
        addresses = self.profile.setdefault("addresses", {})
        address_id = self._new_id("address")
        # If setting as default, un-default all others
        if is_default:
            for addr in addresses.values():
                addr["is_default"] = False
        # If first address, make it default
        if not addresses:
            is_default = True
        addresses[address_id] = {
            "address_id": address_id,
            "name": name,
            "street": street,
            "city": city,
            "state": state,
            "zip": zip_code,
            "country": country,
            "is_default": is_default,
        }
        return address_id

    # -----------------------------------------------------------------------
    # Account: payment methods
    # -----------------------------------------------------------------------

    def list_payment_methods(self) -> List[Dict[str, Any]]:
        """
        List all payment methods saved to the current user's account.

        Returns:
            List[Dict[str, Any]]: Payment method objects, each with:
                payment_method_id (str), type (str), last_four (str),
                is_default (bool).
        """
        user_id = self.user_id
        results = []
        for pm in self.profile.get("payment_methods", {}).values():
            results.append(
                {
                    "payment_method_id": pm["payment_method_id"],
                    "type": pm.get("type", "card"),
                    "last_four": pm.get("last_four", ""),
                    "is_default": pm.get("is_default", False),
                }
            )
        return results

    def add_payment_method(
        self,
        card_number: str,
        expiration_date: str,
        cvv: str,
        billing_address: str,
    ) -> str:
        """
        Add a new credit or debit card as a payment method.

        Args:
            card_number (str): Full card number; only the last 4 digits are stored.
            expiration_date (str): Card expiry in MM/YY format (e.g. "11/28").
            cvv (str): Card security code (3 or 4 digits).
            billing_address (str): Billing address for the card.

        Returns:
            str: The new payment_method_id.
        """
        user_id = self.user_id
        payment_methods = self.profile.setdefault("payment_methods", {})
        last_four = str(card_number).replace(" ", "")[-4:]
        pm_id = self._new_id("payment")
        payment_methods[pm_id] = {
            "payment_method_id": pm_id,
            "type": "card",
            "last_four": last_four,
            "expiration_date": expiration_date,
            "billing_address": billing_address,
            "is_default": len(payment_methods) == 0,
        }
        return pm_id
