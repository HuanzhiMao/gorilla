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

from .server_patch_mixin import PatchableMixin


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
    "lists": {},
    "local_guide": {},
    "photo_contributions": [],
    "place_questions": {},
}


class GoogleMapReviewAPI(PatchableMixin):
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


    def __init__(self):
        self._id_counters = {"review": 0}
        self.profile: Dict[str, Any] = {}
        self.businesses: Dict[str, Dict[str, Any]] = {}
        self.reviews: Dict[str, Dict[str, Any]] = {}
        self.saved_places: Dict[str, Dict[str, Any]] = {}
        self.lists: Dict[str, Dict[str, Any]] = {}
        self.local_guide: Dict[str, Any] = {}
        self.photo_contributions: List[Dict[str, Any]] = []
        self.place_questions: Dict[str, Dict[str, Any]] = {}
        self._api_description = (
            "This tool belongs to the Google Maps Review API, which provides "
            "functionality for searching places, reading and writing reviews, "
            "and managing saved places."
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
        self.lists = scenario.get("lists", DEFAULT_STATE_COPY["lists"])
        self.local_guide = scenario.get("local_guide", DEFAULT_STATE_COPY["local_guide"])
        self.photo_contributions = scenario.get("photo_contributions", DEFAULT_STATE_COPY["photo_contributions"])
        self.place_questions = scenario.get("place_questions", DEFAULT_STATE_COPY["place_questions"])
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

    def get_reviewer_profile(self) -> Dict[str, Any]:
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
        # Normalize: models may pass empty strings instead of omitting optional params
        if price_level == "" or price_level == 0:
            price_level = None
        elif price_level is not None:
            try:
                price_level = int(price_level)
            except (ValueError, TypeError):
                price_level = None

        if min_rating == "" or min_rating == 0 or min_rating == 0.0:
            min_rating = None
        elif min_rating is not None:
            try:
                min_rating = float(min_rating)
            except (ValueError, TypeError):
                min_rating = None

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

    def unpin_place(self, business_id: str) -> Dict[str, Any]:
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

    # -----------------------------------------------------------------------
    # Custom Lists
    # -----------------------------------------------------------------------

    def create_list(self, name: str, description: str = "") -> Dict[str, Any]:
        """
        Create a custom place list.

        Args:
            name (str): The name of the list.
            description (str, optional): A description for the list.
                Defaults to "".

        Returns:
            Dict[str, Any]:
                list_id (str), name (str), description (str), status (str).
        """
        list_id = self._new_id("list")
        self.lists[list_id] = {
            "list_id": list_id,
            "name": name,
            "description": description,
            "places": [],
            "created_at": _utc_now_iso(),
        }
        return {
            "list_id": list_id,
            "name": name,
            "description": description,
            "status": "created",
        }

    def add_to_list(
        self, list_id: str, business_id: str, note: str = ""
    ) -> Dict[str, Any]:
        """
        Add a place to a custom list with an optional note.

        Args:
            list_id (str): The list to add the place to.
            business_id (str): The place to add.
            note (str, optional): A note about this place. Defaults to "".

        Returns:
            Dict[str, Any]:
                list_id (str), business_id (str), status (str).
        """
        lst = self.lists.get(list_id)
        if not lst:
            raise GoogleMapReviewError(
                "LIST_NOT_FOUND",
                f"List '{list_id}' not found.",
                suggested_action="Use get_all_lists() to find valid list IDs.",
                context={"list_id": list_id},
            )
        place = self._require_place(business_id)
        for entry in lst["places"]:
            if entry["business_id"] == business_id:
                raise GoogleMapReviewError(
                    "ALREADY_IN_LIST",
                    f"Place '{business_id}' is already in this list.",
                    suggested_action="Use remove_from_list() first if you want to re-add.",
                    context={"list_id": list_id, "business_id": business_id},
                )
        lst["places"].append({
            "business_id": business_id,
            "business_name": place.get("name", ""),
            "note": note,
            "added_at": _utc_now_iso(),
        })
        return {
            "list_id": list_id,
            "business_id": business_id,
            "status": "added",
        }

    def remove_from_list(
        self, list_id: str, business_id: str
    ) -> Dict[str, Any]:
        """
        Remove a place from a custom list.

        Args:
            list_id (str): The list to remove the place from.
            business_id (str): The place to remove.

        Returns:
            Dict[str, Any]:
                list_id (str), business_id (str), status (str).
        """
        lst = self.lists.get(list_id)
        if not lst:
            raise GoogleMapReviewError(
                "LIST_NOT_FOUND",
                f"List '{list_id}' not found.",
                suggested_action="Use get_all_lists() to find valid list IDs.",
                context={"list_id": list_id},
            )
        for i, entry in enumerate(lst["places"]):
            if entry["business_id"] == business_id:
                lst["places"].pop(i)
                return {
                    "list_id": list_id,
                    "business_id": business_id,
                    "status": "removed",
                }
        raise GoogleMapReviewError(
            "NOT_IN_LIST",
            f"Place '{business_id}' is not in this list.",
            suggested_action="Use get_list() to see which places are in the list.",
            context={"list_id": list_id, "business_id": business_id},
        )

    def get_list(self, list_id: str) -> Dict[str, Any]:
        """
        View a custom list with all places.

        Args:
            list_id (str): The list to view.

        Returns:
            Dict[str, Any]: List object with list_id, name, description,
                places list, and created_at.
        """
        lst = self.lists.get(list_id)
        if not lst:
            raise GoogleMapReviewError(
                "LIST_NOT_FOUND",
                f"List '{list_id}' not found.",
                suggested_action="Use get_all_lists() to find valid list IDs.",
                context={"list_id": list_id},
            )
        return deepcopy(lst)

    def get_all_lists(self) -> List[Dict[str, Any]]:
        """
        List all user-created custom lists.

        Returns:
            List[Dict[str, Any]]: List summary objects with list_id, name,
                description, place_count, and created_at.
        """
        results = []
        for lst in self.lists.values():
            results.append({
                "list_id": lst["list_id"],
                "name": lst["name"],
                "description": lst["description"],
                "place_count": len(lst["places"]),
                "created_at": lst["created_at"],
            })
        return results

    # -----------------------------------------------------------------------
    # Local Guide Contributions & Levels
    # -----------------------------------------------------------------------

    def get_local_guide_status(self) -> Dict[str, Any]:
        """
        Get the current user's Local Guide status including level, points,
        contribution counts, and points needed for next level.

        Returns:
            Dict[str, Any]:
                level (int), points (int), contributions (dict with reviews,
                photos, answers counts), points_to_next_level (int).
        """
        guide = self.local_guide
        level = guide.get("level", 1)
        points = guide.get("points", 0)
        contributions = guide.get("contributions", {
            "reviews": 0,
            "photos": 0,
            "answers": 0,
        })
        # Level thresholds: level 1=0, 2=15, 3=75, 4=200, 5=500, 6=1500,
        # 7=5000, 8=15000, 9=50000, 10=100000
        thresholds = [0, 15, 75, 200, 500, 1500, 5000, 15000, 50000, 100000]
        if level < 10:
            points_to_next = thresholds[level] - points
            if points_to_next < 0:
                points_to_next = 0
        else:
            points_to_next = 0
        return {
            "level": level,
            "points": points,
            "contributions": deepcopy(contributions),
            "points_to_next_level": points_to_next,
        }

    def get_contribution_history(
        self, type: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get past contributions (reviews, photos, answers) optionally filtered
        by type.

        Args:
            type (str, optional): Filter by contribution type. One of
                "reviews", "photos", "answers". None returns all types.
                Defaults to None.
            limit (int): Maximum contributions to return. Defaults to 10.

        Returns:
            List[Dict[str, Any]]: Contribution objects sorted newest first.
        """
        contributions = []
        if type is None or type == "reviews":
            for r in self.reviews.values():
                if r.get("author", {}).get("is_current_user"):
                    contributions.append({
                        "type": "reviews",
                        "business_id": r["business_id"],
                        "detail": r.get("text", ""),
                        "created_at": r.get("created_at", ""),
                    })
        if type is None or type == "photos":
            for p in self.photo_contributions:
                contributions.append({
                    "type": "photos",
                    "business_id": p["business_id"],
                    "detail": p.get("caption", ""),
                    "created_at": p.get("created_at", ""),
                })
        if type is None or type == "answers":
            for q in self.place_questions.values():
                for ans in q.get("answers", []):
                    if ans.get("author") == self.profile.get("name", ""):
                        contributions.append({
                            "type": "answers",
                            "business_id": q["business_id"],
                            "detail": ans.get("answer_text", ""),
                            "created_at": ans.get("created_at", ""),
                        })
        contributions.sort(
            key=lambda x: x.get("created_at", ""), reverse=True
        )
        return contributions[:limit]

    def add_photo(
        self, business_id: str, photo_url: str, caption: str = ""
    ) -> Dict[str, Any]:
        """
        Add a photo to a place. Awards Local Guide points.

        Args:
            business_id (str): The place to add a photo to.
            photo_url (str): The URL of the photo.
            caption (str, optional): A caption for the photo. Defaults to "".

        Returns:
            Dict[str, Any]:
                business_id (str), photo_url (str), caption (str),
                points_awarded (int), status (str).
        """
        self._require_place(business_id)
        self.photo_contributions.append({
            "business_id": business_id,
            "photo_url": photo_url,
            "caption": caption,
            "created_at": _utc_now_iso(),
        })
        points_awarded = 5
        if not self.local_guide:
            self.local_guide = {
                "level": 1,
                "points": 0,
                "contributions": {"reviews": 0, "photos": 0, "answers": 0},
            }
        self.local_guide["points"] = (
            self.local_guide.get("points", 0) + points_awarded
        )
        contributions = self.local_guide.get(
            "contributions", {"reviews": 0, "photos": 0, "answers": 0}
        )
        contributions["photos"] = contributions.get("photos", 0) + 1
        self.local_guide["contributions"] = contributions
        return {
            "business_id": business_id,
            "photo_url": photo_url,
            "caption": caption,
            "points_awarded": points_awarded,
            "status": "added",
        }

    # -----------------------------------------------------------------------
    # Place Q&A
    # -----------------------------------------------------------------------

    def ask_place_question(
        self, business_id: str, question_text: str
    ) -> Dict[str, Any]:
        """
        Ask a question about a place.

        Args:
            business_id (str): The place to ask about.
            question_text (str): The question text.

        Returns:
            Dict[str, Any]:
                question_id (str), business_id (str), question_text (str),
                status (str).
        """
        self._require_place(business_id)
        question_id = self._new_id("question")
        self.place_questions[question_id] = {
            "question_id": question_id,
            "business_id": business_id,
            "question_text": question_text,
            "author": self.profile.get("name", ""),
            "answers": [],
            "created_at": _utc_now_iso(),
        }
        return {
            "question_id": question_id,
            "business_id": business_id,
            "question_text": question_text,
            "status": "posted",
        }

    def answer_place_question(
        self, question_id: str, answer_text: str
    ) -> Dict[str, Any]:
        """
        Answer an existing question about a place.

        Args:
            question_id (str): The question to answer.
            answer_text (str): The answer text.

        Returns:
            Dict[str, Any]:
                question_id (str), answer_text (str), status (str).
        """
        question = self.place_questions.get(question_id)
        if not question:
            raise GoogleMapReviewError(
                "QUESTION_NOT_FOUND",
                f"Question '{question_id}' not found.",
                suggested_action="Use get_place_questions() to find valid question IDs.",
                context={"question_id": question_id},
            )
        question["answers"].append({
            "answer_text": answer_text,
            "author": self.profile.get("name", ""),
            "created_at": _utc_now_iso(),
        })
        # Award Local Guide points for answering
        if not self.local_guide:
            self.local_guide = {
                "level": 1,
                "points": 0,
                "contributions": {"reviews": 0, "photos": 0, "answers": 0},
            }
        self.local_guide["points"] = self.local_guide.get("points", 0) + 3
        contributions = self.local_guide.get(
            "contributions", {"reviews": 0, "photos": 0, "answers": 0}
        )
        contributions["answers"] = contributions.get("answers", 0) + 1
        self.local_guide["contributions"] = contributions
        return {
            "question_id": question_id,
            "answer_text": answer_text,
            "status": "answered",
        }

    def get_place_questions(
        self, business_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get all questions and answers for a place.

        Args:
            business_id (str): The place to get questions for.
            limit (int): Maximum number of questions to return. Defaults to 10.

        Returns:
            List[Dict[str, Any]]: Question objects with question_id,
                business_id, question_text, author, answers list, and
                created_at, sorted newest first.
        """
        self._require_place(business_id)
        results = [
            deepcopy(q) for q in self.place_questions.values()
            if q.get("business_id") == business_id
        ]
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results[:limit]
