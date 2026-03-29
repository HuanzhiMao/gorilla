"""
Confluence Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Current-user perspective: no registration or account switching.
- The current user can manage spaces, pages, comments, and sharing.
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


class ConfluenceError(Exception):
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
    "random_seed": 6789,
    "profile": {},
    "spaces": {},
    "pages": {},
    "comments": {},
    "shares": {},
}


class ConfluenceAPI(PatchableMixin):
    """
    In-memory dummy implementation of a Confluence team wiki platform.

    State variables:
    - profile: {user_id, display_name, email, avatar_url, spaces, role}
      — the current user's identity.
    - spaces: Dict of {space_id -> {space_id, name, description, type,
      homepage_id, created_at, page_count, url}}
    - pages: Dict of {page_id -> {page_id, space_id, title, body,
      parent_page_id, version_number, created_at, updated_at,
      created_by, last_edited_by, url, labels}}
    - comments: Dict of {comment_id -> {comment_id, page_id, body,
      created_at, created_by}}
    - shares: Dict of {share_id -> {page_id, shared_with_email,
      permission, shared_at}}

    Current-user perspective: no registration or account switching.
    """


    def __init__(self):
        self._id_counters = {"page": 0, "comment": 0, "share": 0}
        self.profile: Dict[str, Any] = {}
        self.spaces: Dict[str, Dict[str, Any]] = {}
        self.pages: Dict[str, Dict[str, Any]] = {}
        self.comments: Dict[str, Dict[str, Any]] = {}
        self.shares: Dict[str, Dict[str, Any]] = {}
        self._api_description = (
            "This tool belongs to the Confluence API, which provides team "
            "wiki and documentation platform for creating, organizing, and "
            "sharing knowledge with spaces, pages, and collaborative editing."
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
        self.spaces = scenario.get("spaces", DEFAULT_STATE_COPY["spaces"])
        self.pages = scenario.get("pages", DEFAULT_STATE_COPY["pages"])
        self.comments = scenario.get("comments", DEFAULT_STATE_COPY["comments"])
        self.shares = scenario.get("shares", DEFAULT_STATE_COPY["shares"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, ConfluenceAPI):
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

    def _require_space(self, space_id: str) -> Dict[str, Any]:
        space = self.spaces.get(space_id)
        if not space:
            raise ConfluenceError(
                "SPACE_NOT_FOUND",
                f"Space '{space_id}' not found.",
                suggested_action="Use list_spaces() to find valid space IDs.",
                context={"space_id": space_id},
            )
        return space

    def _require_page(self, page_id: str) -> Dict[str, Any]:
        page = self.pages.get(page_id)
        if not page:
            raise ConfluenceError(
                "PAGE_NOT_FOUND",
                f"Page '{page_id}' not found.",
                suggested_action="Use list_pages() or search_content() to find valid page IDs.",
                context={"page_id": page_id},
            )
        return page

    # -----------------------------------------------------------------------
    # Profile
    # -----------------------------------------------------------------------

    def get_user_profile(self) -> Dict[str, Any]:
        """
        Retrieve the current user's Confluence profile.

        Returns:
            Dict[str, Any]:
                user_id (str): The user's unique identifier.
                display_name (str): The user's display name.
                email (str): The user's email address.
                avatar_url (str | None): URL to the user's avatar image.
                spaces (List[str]): List of space IDs the user belongs to.
                role (str): The user's role.
        """
        return deepcopy(self.profile)

    # -----------------------------------------------------------------------
    # Spaces
    # -----------------------------------------------------------------------

    def list_spaces(self) -> List[Dict[str, Any]]:
        """
        List all Confluence spaces accessible to the current user.

        Returns:
            List[Dict[str, Any]]: Space objects, each with fields:
                space_id (str), name (str), type (str "global" or
                "personal"), page_count (int), created_at (str).
        """
        results = []
        for space in self.spaces.values():
            results.append({
                "space_id": space["space_id"],
                "name": space["name"],
                "type": space.get("type", "global"),
                "page_count": space.get("page_count", 0),
                "created_at": space.get("created_at", ""),
            })
        return results

    def get_space(self, space_id: str) -> Dict[str, Any]:
        """
        Retrieve details of a Confluence space by its ID.

        Args:
            space_id (str): The unique identifier of the space to retrieve.

        Returns:
            Dict[str, Any]:
                space_id (str), name (str), description (str),
                type (str "global" or "personal"), homepage_id (str),
                created_at (str), page_count (int), url (str).
        """
        space = self._require_space(space_id)
        return deepcopy(space)

    # -----------------------------------------------------------------------
    # Pages
    # -----------------------------------------------------------------------

    def create_page(
        self,
        space_id: str,
        title: str,
        body: str = "",
        parent_page_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new page in a Confluence space, optionally nested under
        an existing parent page.

        Args:
            space_id (str): The ID of the space to create the page in.
            title (str): Title of the new page.
            body (str): Body content of the page in storage format (XHTML).
                Defaults to empty string.
            parent_page_id (str, optional): ID of the parent page to nest
                this page under. If null, the page is created at the top
                level of the space.

        Returns:
            Dict[str, Any]:
                page_id (str), space_id (str), title (str), body (str),
                parent_page_id (str | None), version_number (int),
                created_at (str), created_by (str), url (str).
        """
        self._require_space(space_id)
        if parent_page_id is not None:
            self._require_page(parent_page_id)

        page_id = self._new_id("page")
        now = _utc_now_iso()
        user_name = self.profile.get("display_name", "")
        page = {
            "page_id": page_id,
            "space_id": space_id,
            "title": title,
            "body": body,
            "parent_page_id": parent_page_id,
            "version_number": 1,
            "created_at": now,
            "updated_at": now,
            "created_by": user_name,
            "last_edited_by": user_name,
            "url": f"https://confluence.example.com/{space_id}/{page_id}",
            "labels": [],
        }
        self.pages[page_id] = page

        # Update space page_count
        space = self.spaces.get(space_id)
        if space:
            space["page_count"] = space.get("page_count", 0) + 1

        return deepcopy(page)

    def get_page(self, page_id: str) -> Dict[str, Any]:
        """
        Retrieve the full details of a Confluence page by its ID.

        Args:
            page_id (str): The unique identifier of the page to retrieve.

        Returns:
            Dict[str, Any]:
                page_id (str), space_id (str), title (str), body (str),
                parent_page_id (str | None), version_number (int),
                created_at (str), updated_at (str), created_by (str),
                last_edited_by (str), url (str), labels (List[str]).
        """
        page = self._require_page(page_id)
        return deepcopy(page)

    def list_pages(self, space_id: str) -> List[Dict[str, Any]]:
        """
        List all pages in a given Confluence space.

        Args:
            space_id (str): The ID of the space whose pages to list.

        Returns:
            List[Dict[str, Any]]: Page summary objects, each with fields:
                page_id (str), title (str), parent_page_id (str | None),
                version_number (int), created_at (str), updated_at (str),
                created_by (str).
        """
        self._require_space(space_id)
        results = []
        for page in self.pages.values():
            if page.get("space_id") == space_id:
                results.append({
                    "page_id": page["page_id"],
                    "title": page["title"],
                    "parent_page_id": page.get("parent_page_id"),
                    "version_number": page.get("version_number", 1),
                    "created_at": page["created_at"],
                    "updated_at": page["updated_at"],
                    "created_by": page.get("created_by", ""),
                })
        return results

    def update_page(
        self,
        page_id: str,
        version_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update the title and/or body of an existing Confluence page. A
        version number must be provided for conflict detection.

        Args:
            page_id (str): The unique identifier of the page to update.
            version_number (int): The current version number of the page.
                Required for optimistic concurrency control.
            title (str, optional): New title for the page. If null, the
                title remains unchanged.
            body (str, optional): New body content in storage format. If
                null, the body remains unchanged.

        Returns:
            Dict[str, Any]:
                page_id (str), title (str), body (str),
                version_number (int), updated_at (str),
                last_edited_by (str).
        """
        page = self._require_page(page_id)
        if page.get("version_number", 1) != version_number:
            raise ConfluenceError(
                "VERSION_CONFLICT",
                f"Version mismatch: expected {page.get('version_number', 1)}, got {version_number}.",
                suggested_action="Retrieve the latest version with get_page() and retry.",
                context={
                    "page_id": page_id,
                    "expected_version": page.get("version_number", 1),
                    "provided_version": version_number,
                },
            )
        if title is not None:
            page["title"] = title
        if body is not None:
            page["body"] = body
        page["version_number"] = version_number + 1
        page["updated_at"] = _utc_now_iso()
        page["last_edited_by"] = self.profile.get("display_name", "")
        return {
            "page_id": page_id,
            "title": page["title"],
            "body": page["body"],
            "version_number": page["version_number"],
            "updated_at": page["updated_at"],
            "last_edited_by": page["last_edited_by"],
        }

    def delete_page(self, page_id: str) -> Dict[str, Any]:
        """
        Delete a Confluence page by its ID. This moves the page to the
        space's trash.

        Args:
            page_id (str): The unique identifier of the page to delete.

        Returns:
            Dict[str, Any]:
                page_id (str), status (str "deleted"), deleted_at (str).
        """
        page = self._require_page(page_id)
        space_id = page.get("space_id")
        del self.pages[page_id]

        # Update space page_count
        space = self.spaces.get(space_id)
        if space:
            space["page_count"] = max(0, space.get("page_count", 1) - 1)

        return {
            "page_id": page_id,
            "status": "deleted",
            "deleted_at": _utc_now_iso(),
        }

    def search_content(
        self,
        query: str,
        space_id: Optional[str] = None,
        type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for content across Confluence spaces using CQL
        (Confluence Query Language) keywords.

        Args:
            query (str): The search query string.
            space_id (str, optional): Limit search to a specific space. If
                null, searches across all spaces.
            type (str, optional): Filter by content type -- "page",
                "blogpost", or "comment". If null, returns all types.

        Returns:
            List[Dict[str, Any]]: Search result objects, each with fields:
                content_type (str), content_id (str), title (str),
                snippet (str), space_id (str), space_name (str),
                updated_at (str), url (str).
        """
        if space_id is not None:
            self._require_space(space_id)

        query_lower = query.lower()
        results = []

        # Search pages
        if type is None or type == "page":
            for page in self.pages.values():
                if space_id is not None and page.get("space_id") != space_id:
                    continue
                if (query_lower in page.get("title", "").lower()
                        or query_lower in page.get("body", "").lower()):
                    space = self.spaces.get(page.get("space_id", ""), {})
                    snippet = page.get("body", "")[:120]
                    results.append({
                        "content_type": "page",
                        "content_id": page["page_id"],
                        "title": page["title"],
                        "snippet": snippet,
                        "space_id": page.get("space_id", ""),
                        "space_name": space.get("name", ""),
                        "updated_at": page.get("updated_at", ""),
                        "url": page.get("url", ""),
                    })

        # Search comments
        if type is None or type == "comment":
            for comment in self.comments.values():
                if query_lower in comment.get("body", "").lower():
                    page = self.pages.get(comment.get("page_id", ""), {})
                    if space_id is not None and page.get("space_id") != space_id:
                        continue
                    space = self.spaces.get(page.get("space_id", ""), {})
                    results.append({
                        "content_type": "comment",
                        "content_id": comment["comment_id"],
                        "title": f"Comment on: {page.get('title', '')}",
                        "snippet": comment.get("body", "")[:120],
                        "space_id": page.get("space_id", ""),
                        "space_name": space.get("name", ""),
                        "updated_at": comment.get("created_at", ""),
                        "url": page.get("url", ""),
                    })

        return results

    # -----------------------------------------------------------------------
    # Comments
    # -----------------------------------------------------------------------

    def add_comment(self, page_id: str, body: str) -> Dict[str, Any]:
        """
        Add a comment to a Confluence page.

        Args:
            page_id (str): The ID of the page to comment on.
            body (str): The comment body text.

        Returns:
            Dict[str, Any]:
                comment_id (str), page_id (str), body (str),
                created_at (str), created_by (str).
        """
        self._require_page(page_id)
        comment_id = self._new_id("comment")
        now = _utc_now_iso()
        user_name = self.profile.get("display_name", "")
        comment = {
            "comment_id": comment_id,
            "page_id": page_id,
            "body": body,
            "created_at": now,
            "created_by": user_name,
        }
        self.comments[comment_id] = comment
        return deepcopy(comment)

    def list_comments(self, page_id: str) -> List[Dict[str, Any]]:
        """
        List all comments on a given Confluence page.

        Args:
            page_id (str): The ID of the page whose comments to list.

        Returns:
            List[Dict[str, Any]]: Comment objects, each with fields:
                comment_id (str), body (str), created_at (str),
                created_by (str).
        """
        self._require_page(page_id)
        results = []
        for comment in self.comments.values():
            if comment.get("page_id") == page_id:
                results.append({
                    "comment_id": comment["comment_id"],
                    "body": comment["body"],
                    "created_at": comment["created_at"],
                    "created_by": comment.get("created_by", ""),
                })
        return results

    # -----------------------------------------------------------------------
    # Sharing
    # -----------------------------------------------------------------------

    def share_page(
        self,
        page_id: str,
        email: str,
        permission: str = "view",
    ) -> Dict[str, Any]:
        """
        Share a Confluence page with another user by email, granting them
        a specified permission level.

        Args:
            page_id (str): The ID of the page to share.
            email (str): Email address of the person to share with.
            permission (str): Permission level to grant -- "view" or
                "edit". Defaults to "view".

        Returns:
            Dict[str, Any]:
                page_id (str), shared_with_email (str),
                permission (str), shared_at (str).
        """
        self._require_page(page_id)
        if permission not in ("view", "edit"):
            raise ConfluenceError(
                "INVALID_PERMISSION",
                f"Permission '{permission}' is not valid.",
                suggested_action="Use 'view' or 'edit'.",
                context={"permission": permission},
            )

        share_id = self._new_id("share")
        now = _utc_now_iso()
        share_record = {
            "page_id": page_id,
            "shared_with_email": email,
            "permission": permission,
            "shared_at": now,
        }
        self.shares[share_id] = share_record
        return deepcopy(share_record)
