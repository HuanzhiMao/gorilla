"""
Yelp Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Current-user perspective: no registration or account switching.
- The current user can browse businesses, read any review, and write/edit/delete
  only their own reviews. One review per business per user.
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


class YelpError(Exception):
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


DEFAULT_STATE = {
    "random_seed": 7890,
    "profile": {},
    "businesses": {},
    "reviews": {},
    "saved_places": {},
}


class YelpAPI(PatchableMixin):
    """
    In-memory dummy implementation of a Yelp-like restaurant review service.

    State variables:
    - profile: {name, email} — the current user's identity.
    - businesses: Dict of {business_id -> {business_id, name, category, address,
      rating, review_count, price_level, opening_hours, phone, website}}
    - reviews: Dict of {review_id -> {review_id, business_id,
      author{name, is_current_user}, rating, text, photos[], created_at,
      helpful_count}}
    - saved_places: Dict of {business_id -> {business_id, name}}

    Current-user perspective: no registration or account switching.
    """


    def __init__(self):
        self._id_counters = {"review": 0}
        self.profile: Dict[str, Any] = {}
        self.businesses: Dict[str, Dict[str, Any]] = {}
        self.reviews: Dict[str, Dict[str, Any]] = {}
        self.saved_places: Dict[str, Dict[str, Any]] = {}
        self._api_description = (
            "This tool belongs to the Yelp API, which provides functionality "
            "for searching businesses, reading and writing reviews, and "
            "managing saved/bookmarked businesses."
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
        self.businesses = scenario.get("businesses", DEFAULT_STATE_COPY["businesses"])
        self.reviews = scenario.get("reviews", DEFAULT_STATE_COPY["reviews"])
        self.saved_places = scenario.get("saved_places", DEFAULT_STATE_COPY["saved_places"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, YelpAPI):
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

    def _require_business(self, business_id: str) -> Dict[str, Any]:
        biz = self.businesses.get(business_id)
        if not biz:
            raise YelpError(
                "BUSINESS_NOT_FOUND",
                f"Business '{business_id}' not found.",
                suggested_action="Use search_businesses() to find valid business IDs.",
                context={"business_id": business_id},
            )
        return biz

    def _require_review(self, review_id: str) -> Dict[str, Any]:
        review = self.reviews.get(review_id)
        if not review:
            raise YelpError(
                "REVIEW_NOT_FOUND",
                f"Review '{review_id}' not found.",
                suggested_action="Use get_reviews_for_business() to find valid review IDs.",
                context={"review_id": review_id},
            )
        return review

    def _require_own_review(self, review_id: str) -> Dict[str, Any]:
        review = self._require_review(review_id)
        if not review.get("author", {}).get("is_current_user"):
            raise YelpError(
                "NOT_YOUR_REVIEW",
                "You can only modify your own reviews.",
                suggested_action="Use get_my_reviews() to find your review IDs.",
                context={"review_id": review_id},
            )
        return review

    def _recalculate_business_rating(self, business_id: str) -> None:
        """Recompute average rating and review_count for a business."""
        biz = self.businesses.get(business_id)
        if not biz:
            return
        ratings = [
            r.get("rating", 0)
            for r in self.reviews.values()
            if r.get("business_id") == business_id
        ]
        if ratings:
            biz["rating"] = round(sum(ratings) / len(ratings), 1)
            biz["review_count"] = len(ratings)
        else:
            biz["rating"] = 0
            biz["review_count"] = 0

    # -----------------------------------------------------------------------
    # Profile
    # -----------------------------------------------------------------------

    def get_yelp_profile(self) -> Dict[str, Any]:
        """
        Get the current user's Yelp profile.

        Returns:
            Dict[str, Any]:
                name (str): The user's display name.
                email (str): The user's email address.
        """
        return deepcopy(self.profile)

    # -----------------------------------------------------------------------
    # Business discovery
    # -----------------------------------------------------------------------

    def search_businesses(
        self,
        query: Optional[str] = None,
        location: Optional[str] = None,
        category: Optional[str] = None,
        price_level: Optional[str] = None,
        min_rating: Optional[float] = None,
        sort_by: str = "rating",
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search for businesses by name, location, category, or other criteria.

        Args:
            query (str, optional): Text to match against business name.
            location (str, optional): Text to match against business address.
            category (str, optional): Exact category match
                (e.g. "restaurant", "cafe", "bar").
            price_level (str, optional): Exact price level match
                (e.g. "$", "$$", "$$$", "$$$$").
            min_rating (float, optional): Minimum average rating (1.0–5.0).
            sort_by (str): Sort order. One of "rating", "review_count", "name".
                Defaults to "rating".
            max_results (int): Maximum results to return. Defaults to 20.

        Returns:
            List[Dict[str, Any]]: Matching business objects.
        """
        if sort_by not in ("rating", "review_count", "name"):
            raise YelpError(
                "INVALID_SORT",
                f"sort_by '{sort_by}' is not valid.",
                suggested_action="Use 'rating', 'review_count', or 'name'.",
                context={"sort_by": sort_by},
            )

        results = []
        for biz in self.businesses.values():
            match = True
            if query and query.lower() not in biz.get("name", "").lower():
                match = False
            if location and location.lower() not in biz.get("address", "").lower():
                match = False
            if category and biz.get("category", "").lower() != category.lower():
                match = False
            if price_level is not None and biz.get("price_level") != price_level:
                match = False
            if min_rating is not None and biz.get("rating", 0) < min_rating:
                match = False
            if match:
                results.append(deepcopy(biz))

        if sort_by == "rating":
            results.sort(key=lambda x: x.get("rating", 0), reverse=True)
        elif sort_by == "review_count":
            results.sort(key=lambda x: x.get("review_count", 0), reverse=True)
        elif sort_by == "name":
            results.sort(key=lambda x: x.get("name", ""))
        return results[:max_results]

    def get_business(self, business_id: str) -> Dict[str, Any]:
        """
        Get the full details of a business.

        Args:
            business_id (str): The unique identifier of the business.

        Returns:
            Dict[str, Any]: Business object including business_id, name,
                category, address, rating, review_count, price_level,
                opening_hours, phone, website.
        """
        biz = self._require_business(business_id)
        return deepcopy(biz)

    # -----------------------------------------------------------------------
    # Reviews — reading
    # -----------------------------------------------------------------------

    def get_reviews_for_business(
        self,
        business_id: str,
        max_results: int = 20,
        sort_by: str = "newest",
    ) -> List[Dict[str, Any]]:
        """
        Get reviews for a specific business.

        Args:
            business_id (str): The business to get reviews for.
            max_results (int): Maximum reviews to return. Defaults to 20.
            sort_by (str): Sort order. One of "newest", "oldest", "highest",
                "lowest", "most_helpful". Defaults to "newest".

        Returns:
            List[Dict[str, Any]]: Review objects sorted as requested.
        """
        self._require_business(business_id)
        if sort_by not in ("newest", "oldest", "highest", "lowest", "most_helpful"):
            raise YelpError(
                "INVALID_SORT",
                f"sort_by '{sort_by}' is not valid.",
                suggested_action="Use 'newest', 'oldest', 'highest', 'lowest', or 'most_helpful'.",
                context={"sort_by": sort_by},
            )

        results = [
            deepcopy(r) for r in self.reviews.values()
            if r.get("business_id") == business_id
        ]

        if sort_by == "newest":
            results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        elif sort_by == "oldest":
            results.sort(key=lambda x: x.get("created_at", ""))
        elif sort_by == "highest":
            results.sort(key=lambda x: x.get("rating", 0), reverse=True)
        elif sort_by == "lowest":
            results.sort(key=lambda x: x.get("rating", 0))
        elif sort_by == "most_helpful":
            results.sort(key=lambda x: x.get("helpful_count", 0), reverse=True)
        return results[:max_results]

    def get_review_details(self, review_id: str) -> Dict[str, Any]:
        """
        Get the full details of a specific review by ID.

        Args:
            review_id (str): The unique identifier of the review.

        Returns:
            Dict[str, Any]: Full review object.
        """
        review = self._require_review(review_id)
        return deepcopy(review)

    def get_my_yelp_reviews(self) -> List[Dict[str, Any]]:
        """
        Get all Yelp reviews written by the current user.

        Returns:
            List[Dict[str, Any]]: The current user's reviews, newest first.
        """
        results = [
            deepcopy(r) for r in self.reviews.values()
            if r.get("author", {}).get("is_current_user")
        ]
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    # -----------------------------------------------------------------------
    # Reviews — writing (current user only)
    # -----------------------------------------------------------------------

    def compose_review(
        self,
        business_id: str,
        rating: int,
        text: str,
        photos: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Write a review for a business. Each user can only post one review per
        business. Use update_review() to modify an existing review.

        Args:
            business_id (str): The business to review.
            rating (int): Star rating from 1 to 5.
            text (str): Review text content.
            photos (List[str], optional): Photo URLs or filenames to attach.

        Returns:
            Dict[str, Any]:
                review_id (str), business_id (str), status (str).
        """
        self._require_business(business_id)
        if not isinstance(rating, int) or not 1 <= rating <= 5:
            raise YelpError(
                "INVALID_RATING",
                "Rating must be an integer between 1 and 5.",
                suggested_action="Provide a rating of 1, 2, 3, 4, or 5.",
                context={"rating": rating},
            )

        for r in self.reviews.values():
            if (r.get("business_id") == business_id
                    and r.get("author", {}).get("is_current_user")):
                raise YelpError(
                    "ALREADY_REVIEWED",
                    "You have already reviewed this business.",
                    suggested_action="Use update_review() to modify your existing review.",
                    context={
                        "business_id": business_id,
                        "existing_review_id": r["review_id"],
                    },
                )

        review_id = self._new_id("review")
        self.reviews[review_id] = {
            "review_id": review_id,
            "business_id": business_id,
            "author": {
                "name": self.profile.get("name", ""),
                "is_current_user": True,
            },
            "rating": rating,
            "text": text,
            "photos": photos or [],
            "created_at": _utc_now_iso(),
            "helpful_count": 0,
        }
        self._recalculate_business_rating(business_id)
        return {
            "review_id": review_id,
            "business_id": business_id,
            "status": "created",
        }

    def update_review(
        self,
        review_id: str,
        rating: Optional[int] = None,
        text: Optional[str] = None,
        photos: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Update one of your own reviews. Only the current user's reviews can be
        modified.

        Args:
            review_id (str): The review to update.
            rating (int, optional): New star rating (1–5). None keeps current.
            text (str, optional): New review text. None keeps current.
            photos (List[str], optional): New photo list. None keeps current.

        Returns:
            Dict[str, Any]: The updated review object.
        """
        review = self._require_own_review(review_id)
        if rating is not None:
            if not isinstance(rating, int) or not 1 <= rating <= 5:
                raise YelpError(
                    "INVALID_RATING",
                    "Rating must be an integer between 1 and 5.",
                    suggested_action="Provide a rating of 1, 2, 3, 4, or 5.",
                    context={"rating": rating},
                )
            review["rating"] = rating
        if text is not None:
            review["text"] = text
        if photos is not None:
            review["photos"] = photos
        self._recalculate_business_rating(review["business_id"])
        return deepcopy(review)

    def remove_review(self, review_id: str) -> Dict[str, Any]:
        """
        Remove one of your own Yelp reviews. Only the current user's reviews
        can be removed.

        Args:
            review_id (str): The review to remove.

        Returns:
            Dict[str, Any]:
                review_id (str), status (str).
        """
        review = self._require_own_review(review_id)
        business_id = review["business_id"]
        del self.reviews[review_id]
        self._recalculate_business_rating(business_id)
        return {"review_id": review_id, "status": "deleted"}

    # -----------------------------------------------------------------------
    # Review interaction
    # -----------------------------------------------------------------------

    def mark_review_useful(self, review_id: str) -> Dict[str, Any]:
        """
        Mark a review as useful. You cannot mark your own review.

        Args:
            review_id (str): The review to mark as useful.

        Returns:
            Dict[str, Any]:
                review_id (str), helpful_count (int).
        """
        review = self._require_review(review_id)
        if review.get("author", {}).get("is_current_user"):
            raise YelpError(
                "CANNOT_REACT_OWN_REVIEW",
                "You cannot mark your own review as useful.",
                suggested_action="Mark another user's review instead.",
                context={"review_id": review_id},
            )
        review["helpful_count"] = review.get("helpful_count", 0) + 1
        return {
            "review_id": review_id,
            "helpful_count": review["helpful_count"],
        }

    # -----------------------------------------------------------------------
    # Saved businesses
    # -----------------------------------------------------------------------

    def save_business(self, business_id: str) -> Dict[str, Any]:
        """
        Save (bookmark) a business for later reference.

        Args:
            business_id (str): The business to save.

        Returns:
            Dict[str, Any]:
                business_id (str), name (str), status (str).
        """
        biz = self._require_business(business_id)
        if business_id in self.saved_places:
            raise YelpError(
                "ALREADY_SAVED",
                f"Business '{business_id}' is already saved.",
                suggested_action="Use unsave_business() to remove it first.",
                context={"business_id": business_id},
            )
        self.saved_places[business_id] = {
            "business_id": business_id,
            "name": biz.get("name", ""),
        }
        return {
            "business_id": business_id,
            "name": biz.get("name", ""),
            "status": "saved",
        }

    def unsave_business(self, business_id: str) -> Dict[str, Any]:
        """
        Remove a business from saved/bookmarked list.

        Args:
            business_id (str): The business to unsave.

        Returns:
            Dict[str, Any]:
                business_id (str), status (str).
        """
        if business_id not in self.saved_places:
            raise YelpError(
                "NOT_SAVED",
                f"Business '{business_id}' is not in your saved list.",
                suggested_action="Use save_business() to save it first.",
                context={"business_id": business_id},
            )
        del self.saved_places[business_id]
        return {"business_id": business_id, "status": "unsaved"}

    def list_saved_businesses(self) -> List[Dict[str, Any]]:
        """
        List all saved/bookmarked businesses.

        Returns:
            List[Dict[str, Any]]: Saved place objects with business_id and name.
        """
        return [deepcopy(s) for s in self.saved_places.values()]
