"""
Google Maps Review Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Current-user perspective: no registration or account switching.
- The current user can browse places, read any review, and write/edit/delete
  only their own reviews. One review per place per user.
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


class GoogleMapReviewError(Exception):
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
    "random_seed": 3456,
    "profile": {},
    "businesses": {},
    "reviews": {},
    "saved_places": {},
}


class GoogleMapReviewAPI(BaseServiceAPI):
    """
    In-memory dummy implementation of a Google Maps review service.

    State variables:
    - profile: {name, email} — the current user's identity.
    - businesses: Dict of {business_id -> {business_id, name, category, address,
      rating, review_count, price_level, opening_hours, phone, website}}
    - reviews: Dict of {review_id -> {review_id, business_id,
      author{name, is_current_user}, rating, text, photos[], created_at,
      helpful_count}}
    - saved_places: Dict of {business_id -> {business_id, name}}

    Current-user perspective: no registration or account switching.
    Uses Google Maps terminology (places, contributions).
    """

    _STATE_KEYS = ("profile", "businesses", "reviews", "saved_places")
    _ID_COUNTER_DEFAULTS = {"review": 0}
    _DEFAULT_SEED = 3456

    def __init__(self):
        super().__init__()
        self.profile: Dict[str, Any] = {}
        self.businesses: Dict[str, Dict[str, Any]] = {}
        self.reviews: Dict[str, Dict[str, Any]] = {}
        self.saved_places: Dict[str, Dict[str, Any]] = {}
        self._api_description = (
            "This tool belongs to the Google Maps Review API, which provides "
            "functionality for searching places, reading and writing reviews, "
            "and managing saved places."
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
        self.businesses = scenario.get("businesses", DEFAULT_STATE_COPY["businesses"])
        self.reviews = scenario.get("reviews", DEFAULT_STATE_COPY["reviews"])
        self.saved_places = scenario.get("saved_places", DEFAULT_STATE_COPY["saved_places"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, GoogleMapReviewAPI):
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

    def _require_place(self, business_id: str) -> Dict[str, Any]:
        place = self.businesses.get(business_id)
        if not place:
            raise GoogleMapReviewError(
                "PLACE_NOT_FOUND",
                f"Place '{business_id}' not found.",
                suggested_action="Use search_places() to find valid place IDs.",
                context={"business_id": business_id},
            )
        return place

    def _require_review(self, review_id: str) -> Dict[str, Any]:
        review = self.reviews.get(review_id)
        if not review:
            raise GoogleMapReviewError(
                "REVIEW_NOT_FOUND",
                f"Review '{review_id}' not found.",
                suggested_action="Use get_place_reviews() to find valid review IDs.",
                context={"review_id": review_id},
            )
        return review

    def _require_own_review(self, review_id: str) -> Dict[str, Any]:
        review = self._require_review(review_id)
        if not review.get("author", {}).get("is_current_user"):
            raise GoogleMapReviewError(
                "NOT_YOUR_REVIEW",
                "You can only modify your own reviews.",
                suggested_action="Use get_my_reviews() to find your review IDs.",
                context={"review_id": review_id},
            )
        return review

    def _recalculate_place_rating(self, business_id: str) -> None:
        """Recompute average rating and review_count for a place."""
        place = self.businesses.get(business_id)
        if not place:
            return
        ratings = [
            r.get("rating", 0)
            for r in self.reviews.values()
            if r.get("business_id") == business_id
        ]
        if ratings:
            place["rating"] = round(sum(ratings) / len(ratings), 1)
            place["review_count"] = len(ratings)
        else:
            place["rating"] = 0
            place["review_count"] = 0

    # -----------------------------------------------------------------------
    # Profile
    # -----------------------------------------------------------------------

    def get_profile(self) -> Dict[str, Any]:
        """
        Get the current user's profile.

        Returns:
            Dict[str, Any]:
                name (str): The user's display name.
                email (str): The user's email address.
        """
        return deepcopy(self.profile)

    # -----------------------------------------------------------------------
    # Place discovery
    # -----------------------------------------------------------------------

    def search_places(
        self,
        query: Optional[str] = None,
        location: Optional[str] = None,
        category: Optional[str] = None,
        price_level: Optional[int] = None,
        min_rating: Optional[float] = None,
        sort_by: str = "rating",
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search for places by name, location, category, or other criteria.

        Args:
            query (str, optional): Text to match against place name.
            location (str, optional): Text to match against place address.
            category (str, optional): Exact category match
                (e.g. "restaurant", "cafe", "bar").
            price_level (int, optional): Price level filter (1–4, where
                1 is cheapest and 4 is most expensive).
            min_rating (float, optional): Minimum average rating (1.0–5.0).
            sort_by (str): Sort order. One of "rating", "review_count", "name".
                Defaults to "rating".
            max_results (int): Maximum results to return. Defaults to 20.

        Returns:
            List[Dict[str, Any]]: Matching place objects.
        """
        if sort_by not in ("rating", "review_count", "name"):
            raise GoogleMapReviewError(
                "INVALID_SORT",
                f"sort_by '{sort_by}' is not valid.",
                suggested_action="Use 'rating', 'review_count', or 'name'.",
                context={"sort_by": sort_by},
            )

        results = []
        for place in self.businesses.values():
            match = True
            if query and query.lower() not in place.get("name", "").lower():
                match = False
            if location and location.lower() not in place.get("address", "").lower():
                match = False
            if category and place.get("category", "").lower() != category.lower():
                match = False
            if price_level is not None and place.get("price_level") != price_level:
                match = False
            if min_rating is not None and place.get("rating", 0) < min_rating:
                match = False
            if match:
                results.append(deepcopy(place))

        if sort_by == "rating":
            results.sort(key=lambda x: x.get("rating", 0), reverse=True)
        elif sort_by == "review_count":
            results.sort(key=lambda x: x.get("review_count", 0), reverse=True)
        elif sort_by == "name":
            results.sort(key=lambda x: x.get("name", ""))
        return results[:max_results]

    def get_place_details(self, business_id: str) -> Dict[str, Any]:
        """
        Get the full details of a place.

        Args:
            business_id (str): The unique identifier of the place.

        Returns:
            Dict[str, Any]: Place object including business_id, name,
                category, address, rating, review_count, price_level,
                opening_hours, phone, website.
        """
        place = self._require_place(business_id)
        return deepcopy(place)

    # -----------------------------------------------------------------------
    # Reviews — reading
    # -----------------------------------------------------------------------

    def get_place_reviews(
        self,
        business_id: str,
        max_results: int = 20,
        sort_by: str = "newest",
    ) -> List[Dict[str, Any]]:
        """
        Get reviews for a specific place.

        Args:
            business_id (str): The place to get reviews for.
            max_results (int): Maximum reviews to return. Defaults to 20.
            sort_by (str): Sort order. One of "newest", "oldest", "highest",
                "lowest", "most_helpful". Defaults to "newest".

        Returns:
            List[Dict[str, Any]]: Review objects sorted as requested.
        """
        self._require_place(business_id)
        if sort_by not in ("newest", "oldest", "highest", "lowest", "most_helpful"):
            raise GoogleMapReviewError(
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

    def get_review(self, review_id: str) -> Dict[str, Any]:
        """
        Get a specific review by ID.

        Args:
            review_id (str): The unique identifier of the review.

        Returns:
            Dict[str, Any]: Full review object.
        """
        review = self._require_review(review_id)
        return deepcopy(review)

    def get_my_reviews(self) -> List[Dict[str, Any]]:
        """
        Get all reviews written by the current user (your contributions).

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

    def add_review(
        self,
        business_id: str,
        rating: int,
        text: str,
        photos: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Add a review for a place. Each user can only post one review per
        place. Use edit_review() to modify an existing review.

        Args:
            business_id (str): The place to review.
            rating (int): Star rating from 1 to 5.
            text (str): Review text content.
            photos (List[str], optional): Photo URLs or filenames to attach.

        Returns:
            Dict[str, Any]:
                review_id (str), business_id (str), status (str).
        """
        self._require_place(business_id)
        if not isinstance(rating, int) or not 1 <= rating <= 5:
            raise GoogleMapReviewError(
                "INVALID_RATING",
                "Rating must be an integer between 1 and 5.",
                suggested_action="Provide a rating of 1, 2, 3, 4, or 5.",
                context={"rating": rating},
            )

        for r in self.reviews.values():
            if (r.get("business_id") == business_id
                    and r.get("author", {}).get("is_current_user")):
                raise GoogleMapReviewError(
                    "ALREADY_REVIEWED",
                    "You have already reviewed this place.",
                    suggested_action="Use edit_review() to modify your existing review.",
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
        self._recalculate_place_rating(business_id)
        return {
            "review_id": review_id,
            "business_id": business_id,
            "status": "created",
        }

    def edit_review(
        self,
        review_id: str,
        rating: Optional[int] = None,
        text: Optional[str] = None,
        photos: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Edit one of your own reviews. Only the current user's reviews can be
        modified.

        Args:
            review_id (str): The review to edit.
            rating (int, optional): New star rating (1–5). None keeps current.
            text (str, optional): New review text. None keeps current.
            photos (List[str], optional): New photo list. None keeps current.

        Returns:
            Dict[str, Any]: The updated review object.
        """
        review = self._require_own_review(review_id)
        if rating is not None:
            if not isinstance(rating, int) or not 1 <= rating <= 5:
                raise GoogleMapReviewError(
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
        self._recalculate_place_rating(review["business_id"])
        return deepcopy(review)

    def delete_review(self, review_id: str) -> Dict[str, Any]:
        """
        Delete one of your own reviews. Only the current user's reviews can be
        deleted.

        Args:
            review_id (str): The review to delete.

        Returns:
            Dict[str, Any]:
                review_id (str), status (str).
        """
        review = self._require_own_review(review_id)
        business_id = review["business_id"]
        del self.reviews[review_id]
        self._recalculate_place_rating(business_id)
        return {"review_id": review_id, "status": "deleted"}

    # -----------------------------------------------------------------------
    # Review interaction
    # -----------------------------------------------------------------------

    def mark_review_helpful(self, review_id: str) -> Dict[str, Any]:
        """
        Mark a review as helpful (thumbs up). You cannot mark your own review.

        Args:
            review_id (str): The review to mark as helpful.

        Returns:
            Dict[str, Any]:
                review_id (str), helpful_count (int).
        """
        review = self._require_review(review_id)
        if review.get("author", {}).get("is_current_user"):
            raise GoogleMapReviewError(
                "CANNOT_REACT_OWN_REVIEW",
                "You cannot mark your own review as helpful.",
                suggested_action="Mark another user's review instead.",
                context={"review_id": review_id},
            )
        review["helpful_count"] = review.get("helpful_count", 0) + 1
        return {
            "review_id": review_id,
            "helpful_count": review["helpful_count"],
        }

    # -----------------------------------------------------------------------
    # Saved places
    # -----------------------------------------------------------------------

    def save_place(self, business_id: str) -> Dict[str, Any]:
        """
        Save a place to your saved list for later reference.

        Args:
            business_id (str): The place to save.

        Returns:
            Dict[str, Any]:
                business_id (str), name (str), status (str).
        """
        place = self._require_place(business_id)
        if business_id in self.saved_places:
            raise GoogleMapReviewError(
                "ALREADY_SAVED",
                f"Place '{business_id}' is already saved.",
                suggested_action="Use remove_saved_place() to remove it first.",
                context={"business_id": business_id},
            )
        self.saved_places[business_id] = {
            "business_id": business_id,
            "name": place.get("name", ""),
        }
        return {
            "business_id": business_id,
            "name": place.get("name", ""),
            "status": "saved",
        }

    def remove_saved_place(self, business_id: str) -> Dict[str, Any]:
        """
        Remove a place from your saved list.

        Args:
            business_id (str): The place to remove.

        Returns:
            Dict[str, Any]:
                business_id (str), status (str).
        """
        if business_id not in self.saved_places:
            raise GoogleMapReviewError(
                "NOT_SAVED",
                f"Place '{business_id}' is not in your saved list.",
                suggested_action="Use save_place() to save it first.",
                context={"business_id": business_id},
            )
        del self.saved_places[business_id]
        return {"business_id": business_id, "status": "removed"}

    def list_saved_places(self) -> List[Dict[str, Any]]:
        """
        List all saved places.

        Returns:
            List[Dict[str, Any]]: Saved place objects with business_id and name.
        """
        return [deepcopy(s) for s in self.saved_places.values()]
