"""Runtime patches for GoogleMapReviewAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.google_map_review import GoogleMapReviewAPI, GoogleMapReviewError
from copy import deepcopy
import uuid

# ─── Source: google_map_review_patches.py ───


_CITY_REPLACEMENTS = {
    "Boston": "Providence",
    "San Francisco": "San Jose",
    "New York": "Newark",
    "Los Angeles": "Long Beach",
    "Chicago": "Milwaukee",
    "Seattle": "Tacoma",
    "Austin": "San Antonio",
    "Denver": "Boulder",
    "Miami": "Fort Lauderdale",
    "Portland": "Salem",
}


_WRONG_BUSINESS_REVIEWS = [
    "Great hand wash detail, my car looks brand new!",
    "They did an amazing job on the interior cleaning. Highly recommend their premium package.",
    "Waited 2 hours for a basic wash. Way too long for a car wash.",
    "The wax coating they applied lasted for months. Best car wash in town.",
    "They scratched my bumper during the wash and refused to take responsibility.",
]


# ---------------------------------------------------------------------------
# 1. get_place_reviews_service_unavailable  (permanent)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("get_place_reviews", "service_unavailable")
def get_place_reviews_service_unavailable(self, *args, **kwargs):
    raise GoogleMapReviewError(
        "SERVICE_UNAVAILABLE",
        "Google Reviews service is currently unavailable due to backend migration.",
        "Try again later or use an alternative review service.",
    )


# ---------------------------------------------------------------------------
# 2. search_places_rate_limited  (temporary: fail 1st, succeed 2nd+)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("search_places", "rate_limited")
def search_places_rate_limited(self, *args, **kwargs):
    if self._patch_call_count == 1:
        raise GoogleMapReviewError(
            "RATE_LIMITED",
            "Too many requests. Please retry after a brief wait.",
            "Wait a moment and retry.",
        )
    return self._original_function(*args, **kwargs)


# ---------------------------------------------------------------------------
# 3. add_review_endpoint_suspended  (permanent)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("add_review", "endpoint_suspended")
def add_review_endpoint_suspended(self, *args, **kwargs):
    raise GoogleMapReviewError(
        "ENDPOINT_SUSPENDED",
        "Review posting is temporarily suspended due to anti-spam system overhaul.",
        "Try posting your review on an alternative platform.",
    )


# ---------------------------------------------------------------------------
# 4. get_place_details_upstream_timeout  (temporary: fail 1st, succeed 2nd+)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("get_place_details", "upstream_timeout")
def get_place_details_upstream_timeout(self, *args, **kwargs):
    if self._patch_call_count == 1:
        raise GoogleMapReviewError(
            "UPSTREAM_TIMEOUT",
            "Request timed out due to backend load spike. Please retry.",
            "Retry the request.",
        )
    return self._original_function(*args, **kwargs)


# ---------------------------------------------------------------------------
# 5. get_place_reviews_quota_exhausted  (permanent)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("get_place_reviews", "quota_exhausted")
def get_place_reviews_quota_exhausted(self, *args, **kwargs):
    raise GoogleMapReviewError(
        "QUOTA_EXHAUSTED",
        "API quota for review retrieval has been exhausted for this billing period.",
        "Use an alternative review service.",
    )


# ---------------------------------------------------------------------------
# 6. get_place_reviews_stale_permanent  (permanent)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("get_place_reviews", "stale_permanent")
def get_place_reviews_stale_permanent(self, *args, **kwargs):
    results = self._original_function(*args, **kwargs)
    for idx, review in enumerate(results):
        day = str((idx % 28) + 1).zfill(2)
        review["created_at"] = f"2025-08-{day}T12:00:00Z"
    return results[:3]


# ---------------------------------------------------------------------------
# 7. get_place_details_stale_temporary  (temporary: fail 1st, succeed 2nd+)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("get_place_details", "stale_temporary")
def get_place_details_stale_temporary(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    if self._patch_call_count == 1:
        result["opening_hours"] = "Mon-Sun 08:00-18:00"
    return result


# ---------------------------------------------------------------------------
# 8. get_place_details_stale_permanent  (permanent)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("get_place_details", "stale_permanent")
def get_place_details_stale_permanent(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    current_rating = result.get("rating", 0)
    result["rating"] = round(current_rating - 0.3, 1)
    result["last_updated"] = "2025-10-15T00:00:00Z"
    return result


# ---------------------------------------------------------------------------
# 9. save_place_noop_permanent  (permanent silent no-op)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("save_place", "noop_permanent")
def save_place_noop_permanent(self, *args, **kwargs):
    """Permanent silent no-op. Returns fake success without ever saving the place."""
    business_id = args[0] if args else kwargs.get("business_id")
    place = self.places.get(business_id, {})
    return {
        "business_id": business_id,
        "name": place.get("name", ""),
        "status": "saved",
    }


# ---------------------------------------------------------------------------
# 10. add_review_noop_temporary  (temporary: no-op 1st, succeed 2nd+)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("add_review", "noop_temporary")
def add_review_noop_temporary(self, *args, **kwargs):
    """Temporary silent no-op. On 1st call returns fake success without adding. On 2nd+, works normally."""
    if self._patch_call_count == 1:
        business_id = args[0] if args else kwargs.get("business_id")
        return {
            "review_id": f"review_{uuid.uuid4().hex[:8]}",
            "business_id": business_id,
            "status": "created",
        }
    return self._original_function(*args, **kwargs)


# ---------------------------------------------------------------------------
# 11. delete_review_noop_permanent  (permanent)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("delete_review", "noop_permanent")
def delete_review_noop_permanent(self, *args, **kwargs):
    """Permanent silent no-op. Returns fake deleted status without ever deleting the review."""
    review_id = args[0] if args else kwargs.get("review_id")
    return {"review_id": review_id, "status": "deleted"}


# ---------------------------------------------------------------------------
# 12. mark_review_helpful_noop_permanent  (permanent)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("mark_review_helpful", "noop_permanent")
def mark_review_helpful_noop_permanent(self, *args, **kwargs):
    """Permanent silent no-op. Returns fake success without actually incrementing helpful count."""
    review_id = args[0] if args else kwargs.get("review_id")
    review = self.reviews.get(review_id, {})
    return {
        "review_id": review_id,
        "helpful_count": review.get("helpful_count", 0) + 1,
    }


# ---------------------------------------------------------------------------
# 13. edit_review_noop_temporary  (temporary: no-op 1st, succeed 2nd+)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("edit_review", "noop_temporary")
def edit_review_noop_temporary(self, *args, **kwargs):
    """Temporary silent no-op. On 1st call returns the review as-if edited (but doesn't persist).
    On 2nd+, works normally."""
    if self._patch_call_count == 1:
        review_id = args[0] if args else kwargs.get("review_id")
        review = deepcopy(self.reviews.get(review_id, {}))
        # Return a response that looks like the edit happened, but don't change state
        if kwargs.get("rating"):
            review["rating"] = kwargs["rating"]
        if kwargs.get("text"):
            review["text"] = kwargs["text"]
        return review
    return self._original_function(*args, **kwargs)


# ---------------------------------------------------------------------------
# 14. search_places_wrong_city  (permanent)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("search_places", "wrong_city")
def search_places_wrong_city(self, *args, **kwargs):
    results = self._original_function(*args, **kwargs)
    for place in results:
        address = place.get("address", "")
        for original_city, wrong_city in _CITY_REPLACEMENTS.items():
            if original_city in address:
                place["address"] = address.replace(original_city, wrong_city)
                break
    return results


# ---------------------------------------------------------------------------
# 15. get_place_reviews_truncated_temporary  (temporary: truncate 1st, full 2nd+)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("get_place_reviews", "truncated_temporary")
def get_place_reviews_truncated_temporary(self, *args, **kwargs):
    results = self._original_function(*args, **kwargs)
    if self._patch_call_count == 1:
        for review in results:
            text = review.get("text", "")
            if len(text) > 20:
                review["text"] = text[:20] + "..."
    return results


# ---------------------------------------------------------------------------
# 16. get_place_details_inflated_count  (permanent)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("get_place_details", "inflated_count")
def get_place_details_inflated_count(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    result["review_count"] = result.get("review_count", 0) * 10
    return result


# ---------------------------------------------------------------------------
# 17. get_place_details_swapped_ratings  (temporary: swap 1st, normal 2nd+)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("get_place_details", "swapped_ratings")
def get_place_details_swapped_ratings(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    if self._patch_call_count == 1:
        rating = result.get("rating", 3.0)
        if rating < 4.5:
            new_rating = min(rating + 0.5, 5.0)
        else:
            new_rating = max(rating - 0.5, 1.0)
        result["rating"] = round(new_rating, 1)
    return result


# ---------------------------------------------------------------------------
# 18. search_places_corrupted_rating  (permanent)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("search_places", "corrupted_rating")
def search_places_corrupted_rating(self, *args, **kwargs):
    results = self._original_function(*args, **kwargs)
    if results:
        results[-1]["rating"] = 6.2
    return results


# ---------------------------------------------------------------------------
# 19. get_place_reviews_wrong_business  (permanent)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("get_place_reviews", "wrong_business")
def get_place_reviews_wrong_business(self, *args, **kwargs):
    results = self._original_function(*args, **kwargs)
    for idx, review in enumerate(results):
        review["text"] = _WRONG_BUSINESS_REVIEWS[idx % len(_WRONG_BUSINESS_REVIEWS)]
    return results


# ---------------------------------------------------------------------------
# 20. search_places_invalid_features  (permanent)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("search_places", "invalid_features")
def search_places_invalid_features(self, *args, **kwargs):
    raise GoogleMapReviewError(
        "INVALID_PARAMETER",
        "Feature-style filters are not supported by this search endpoint.",
        "Retry with supported query/location/category filters, then inspect the returned business metadata.",
    )


# ---------------------------------------------------------------------------
# 21. get_place_reviews_wrong_sort_param  (temporary: fail 1st, succeed 2nd+)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("get_place_reviews", "wrong_sort_param")
def get_place_reviews_wrong_sort_param(self, *args, **kwargs):
    if self._patch_call_count == 1:
        sort_by = kwargs.get("sort_by", "")
        if sort_by in ("recent", "newest"):
            raise GoogleMapReviewError(
                "INVALID_PARAMETER",
                "Temporary sort validation failed for this review request.",
                "Retry the same review read using the documented sort_by values, such as sort_by='newest'.",
            )
    return self._original_function(*args, **kwargs)


# ---------------------------------------------------------------------------
# 22. add_review_photo_schema_error  (permanent)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("add_review", "photo_schema_error")
def add_review_photo_schema_error(self, *args, **kwargs):
    photos = kwargs.get("photos") if kwargs else None
    if photos is None and len(args) >= 4:
        photos = args[3]
    if photos:
        raise GoogleMapReviewError(
            "SCHEMA_CHANGED",
            "Photo attachments are currently unavailable on Google Reviews review creation.",
            "Use an alternate review platform if the review must include the photo attachment.",
        )
    return self._original_function(*args, **kwargs)


# ---------------------------------------------------------------------------
# 23. search_places_radius_units  (temporary: fail 1st, succeed 2nd+)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("search_places", "radius_units")
def search_places_radius_units(self, *args, **kwargs):
    if self._patch_call_count == 1:
        raise GoogleMapReviewError(
            "INVALID_RADIUS",
            "The attempted radius filter is not supported by this search endpoint.",
            "Retry with supported location/category filters and filter returned results by proximity or hours metadata.",
        )
    return self._original_function(*args, **kwargs)


# ---------------------------------------------------------------------------
# 24. search_places_open_now_renamed  (temporary: fail 1st, succeed 2nd+)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("search_places", "open_now_renamed")
def search_places_open_now_renamed(self, *args, **kwargs):
    if self._patch_call_count == 1:
        raise GoogleMapReviewError(
            "INVALID_PARAMETER",
            "Open-now filtering is not supported by this search endpoint.",
            "Retry without the open-now filter, then inspect opening_hours in the returned places.",
        )
    return self._original_function(*args, **kwargs)


# ---------------------------------------------------------------------------
# 25. add_review_category_id_required  (temporary: fail 1st, succeed 2nd+)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("add_review", "category_id_required")
def add_review_category_id_required(self, *args, **kwargs):
    if self._patch_call_count == 1:
        raise GoogleMapReviewError(
            "MISSING_PARAMETER",
            "Parameter 'category_id' is now required for review submission. "
            "Use get_place_details() to find the category_id.",
            "Include 'category_id' from the place details.",
        )
    return self._original_function(*args, **kwargs)


# ---------------------------------------------------------------------------
# 26. add_review_numeric_place_id  (temporary: fail 1st, succeed 2nd+)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("add_review", "numeric_place_id")
def add_review_numeric_place_id(self, *args, **kwargs):
    if self._patch_call_count == 1:
        raise GoogleMapReviewError(
            "INVALID_ID_FORMAT",
            "place_id must be a numeric identifier. Use search_places() to "
            "find the numeric place ID.",
            "Use the numeric place ID format.",
        )
    return self._original_function(*args, **kwargs)


# ---------------------------------------------------------------------------
# ft_extra_54: get_place_reviews permission-denied (third-party access revoked)
# ---------------------------------------------------------------------------
@GoogleMapReviewAPI._register_patch("get_place_reviews", "reviews_access_revoked_permanent")
def get_place_reviews_reviews_access_revoked_permanent(self, *args, **kwargs):
    """Permanent. Always raises PERMISSION_DENIED -- the business owner has
    revoked third-party read access to their reviews via Google Business
    Profile. Suggested action steers the agent to a substitute provider
    (e.g. Yelp) rather than retrying."""
    raise GoogleMapReviewError(
        "PERMISSION_DENIED",
        (
            "Reviews access has been revoked by the business owner via Google "
            "Business Profile. The 'google_reviews.read' scope is no longer "
            "granted for this place_id."
        ),
        (
            "Do NOT retry -- the denial is permanent. Pull equivalent reviews "
            "from a substitute provider (e.g. Yelp) for this venue."
        ),
    )
