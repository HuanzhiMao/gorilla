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
    "check_ins": [],
    "collections": {},
    "questions": {},
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
        self.check_ins: List[Dict[str, Any]] = []
        self.collections: Dict[str, Dict[str, Any]] = {}
        self.questions: Dict[str, Dict[str, Any]] = {}
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
        self.check_ins = scenario.get("check_ins", DEFAULT_STATE_COPY["check_ins"])
        self.collections = scenario.get("collections", DEFAULT_STATE_COPY["collections"])
        self.questions = scenario.get("questions", DEFAULT_STATE_COPY["questions"])
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

    # -----------------------------------------------------------------------
    # Check-ins
    # -----------------------------------------------------------------------

    def check_in(self, business_id: str) -> Dict[str, Any]:
        """
        Check in at a business. Validates that the business exists.

        Args:
            business_id (str): The business to check in at.

        Returns:
            Dict[str, Any]:
                business_id (str), business_name (str), timestamp (str),
                status (str).
        """
        biz = self._require_business(business_id)
        timestamp = _utc_now_iso()
        self.check_ins.append({
            "business_id": business_id,
            "business_name": biz.get("name", ""),
            "timestamp": timestamp,
        })
        biz["total_check_ins"] = biz.get("total_check_ins", 0) + 1
        return {
            "business_id": business_id,
            "business_name": biz.get("name", ""),
            "timestamp": timestamp,
            "status": "checked_in",
        }

    def get_check_in_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the current user's check-in history, sorted newest first.

        Args:
            limit (int): Maximum number of check-ins to return. Defaults to 10.

        Returns:
            List[Dict[str, Any]]: Check-in objects with business_id,
                business_name, and timestamp.
        """
        history = list(reversed(self.check_ins))
        return deepcopy(history[:limit])

    def get_check_in_count(self, business_id: str) -> Dict[str, Any]:
        """
        Get the total number of check-ins at a business by all users.

        Args:
            business_id (str): The business to get check-in count for.

        Returns:
            Dict[str, Any]:
                business_id (str), total_check_ins (int).
        """
        biz = self._require_business(business_id)
        return {
            "business_id": business_id,
            "total_check_ins": biz.get("total_check_ins", 0),
        }

    # -----------------------------------------------------------------------
    # Collections (curated lists)
    # -----------------------------------------------------------------------

    def create_collection(
        self, name: str, description: str = ""
    ) -> Dict[str, Any]:
        """
        Create a new collection (curated list of businesses).

        Args:
            name (str): The name of the collection.
            description (str, optional): A description for the collection.
                Defaults to "".

        Returns:
            Dict[str, Any]:
                collection_id (str), name (str), description (str),
                status (str).
        """
        collection_id = self._new_id("collection")
        self.collections[collection_id] = {
            "collection_id": collection_id,
            "name": name,
            "description": description,
            "businesses": [],
            "created_at": _utc_now_iso(),
        }
        return {
            "collection_id": collection_id,
            "name": name,
            "description": description,
            "status": "created",
        }

    def add_to_collection(
        self, collection_id: str, business_id: str, note: str = ""
    ) -> Dict[str, Any]:
        """
        Add a business to a collection with an optional note.

        Args:
            collection_id (str): The collection to add the business to.
            business_id (str): The business to add.
            note (str, optional): A note about why this business is in the
                collection. Defaults to "".

        Returns:
            Dict[str, Any]:
                collection_id (str), business_id (str), status (str).
        """
        collection = self.collections.get(collection_id)
        if not collection:
            raise YelpError(
                "COLLECTION_NOT_FOUND",
                f"Collection '{collection_id}' not found.",
                suggested_action="Use list_collections() to find valid collection IDs.",
                context={"collection_id": collection_id},
            )
        biz = self._require_business(business_id)
        for entry in collection["businesses"]:
            if entry["business_id"] == business_id:
                raise YelpError(
                    "ALREADY_IN_COLLECTION",
                    f"Business '{business_id}' is already in this collection.",
                    suggested_action="Use remove_from_collection() first if you want to re-add.",
                    context={
                        "collection_id": collection_id,
                        "business_id": business_id,
                    },
                )
        collection["businesses"].append({
            "business_id": business_id,
            "business_name": biz.get("name", ""),
            "note": note,
            "added_at": _utc_now_iso(),
        })
        return {
            "collection_id": collection_id,
            "business_id": business_id,
            "status": "added",
        }

    def remove_from_collection(
        self, collection_id: str, business_id: str
    ) -> Dict[str, Any]:
        """
        Remove a business from a collection.

        Args:
            collection_id (str): The collection to remove the business from.
            business_id (str): The business to remove.

        Returns:
            Dict[str, Any]:
                collection_id (str), business_id (str), status (str).
        """
        collection = self.collections.get(collection_id)
        if not collection:
            raise YelpError(
                "COLLECTION_NOT_FOUND",
                f"Collection '{collection_id}' not found.",
                suggested_action="Use list_collections() to find valid collection IDs.",
                context={"collection_id": collection_id},
            )
        for i, entry in enumerate(collection["businesses"]):
            if entry["business_id"] == business_id:
                collection["businesses"].pop(i)
                return {
                    "collection_id": collection_id,
                    "business_id": business_id,
                    "status": "removed",
                }
        raise YelpError(
            "NOT_IN_COLLECTION",
            f"Business '{business_id}' is not in this collection.",
            suggested_action="Use get_collection() to see which businesses are in the collection.",
            context={
                "collection_id": collection_id,
                "business_id": business_id,
            },
        )

    def get_collection(self, collection_id: str) -> Dict[str, Any]:
        """
        View collection details including all businesses in the collection.

        Args:
            collection_id (str): The collection to view.

        Returns:
            Dict[str, Any]: Collection object with collection_id, name,
                description, businesses list, and created_at.
        """
        collection = self.collections.get(collection_id)
        if not collection:
            raise YelpError(
                "COLLECTION_NOT_FOUND",
                f"Collection '{collection_id}' not found.",
                suggested_action="Use list_collections() to find valid collection IDs.",
                context={"collection_id": collection_id},
            )
        return deepcopy(collection)

    def list_collections(self) -> List[Dict[str, Any]]:
        """
        List all user collections.

        Returns:
            List[Dict[str, Any]]: Collection summary objects with
                collection_id, name, description, business_count, and
                created_at.
        """
        results = []
        for col in self.collections.values():
            results.append({
                "collection_id": col["collection_id"],
                "name": col["name"],
                "description": col["description"],
                "business_count": len(col["businesses"]),
                "created_at": col["created_at"],
            })
        return results

    # -----------------------------------------------------------------------
    # Business Q&A
    # -----------------------------------------------------------------------

    def ask_question(
        self, business_id: str, question_text: str
    ) -> Dict[str, Any]:
        """
        Post a question about a business.

        Args:
            business_id (str): The business to ask about.
            question_text (str): The question text.

        Returns:
            Dict[str, Any]:
                question_id (str), business_id (str), question_text (str),
                status (str).
        """
        self._require_business(business_id)
        question_id = self._new_id("question")
        self.questions[question_id] = {
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

    def answer_question(
        self, question_id: str, answer_text: str
    ) -> Dict[str, Any]:
        """
        Answer an existing question about a business.

        Args:
            question_id (str): The question to answer.
            answer_text (str): The answer text.

        Returns:
            Dict[str, Any]:
                question_id (str), answer_text (str), status (str).
        """
        question = self.questions.get(question_id)
        if not question:
            raise YelpError(
                "QUESTION_NOT_FOUND",
                f"Question '{question_id}' not found.",
                suggested_action="Use get_questions() to find valid question IDs.",
                context={"question_id": question_id},
            )
        question["answers"].append({
            "answer_text": answer_text,
            "author": self.profile.get("name", ""),
            "created_at": _utc_now_iso(),
        })
        return {
            "question_id": question_id,
            "answer_text": answer_text,
            "status": "answered",
        }

    def get_questions(
        self, business_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get all questions and answers for a business.

        Args:
            business_id (str): The business to get questions for.
            limit (int): Maximum number of questions to return. Defaults to 10.

        Returns:
            List[Dict[str, Any]]: Question objects with question_id,
                business_id, question_text, author, answers list, and
                created_at, sorted newest first.
        """
        self._require_business(business_id)
        results = [
            deepcopy(q) for q in self.questions.values()
            if q.get("business_id") == business_id
        ]
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results[:limit]
