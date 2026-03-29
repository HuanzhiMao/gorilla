"""
Notion Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Current-user perspective: no registration or account switching.
- The current user can manage workspaces, pages, databases, and sharing.
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


class NotionError(Exception):
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
    "random_seed": 5678,
    "profile": {},
    "workspaces": {},
    "pages": {},
    "databases": {},
    "database_entries": {},
    "shares": {},
}


class NotionAPI(BaseServiceAPI):
    """
    In-memory dummy implementation of a Notion workspace platform.

    State variables:
    - profile: {user_id, name, email, avatar_url, workspaces, plan}
      — the current user's identity.
    - workspaces: Dict of {workspace_id -> {workspace_id, name, icon,
      member_count, plan}}
    - pages: Dict of {page_id -> {page_id, workspace_id, title, content,
      parent_page_id, created_at, updated_at, created_by, last_edited_by,
      url, shared_with}}
    - databases: Dict of {database_id -> {database_id, workspace_id, title,
      properties, created_at, updated_at, url}}
    - database_entries: Dict of {entry_id -> {entry_id, database_id, fields,
      created_at, url}}
    - shares: Dict of {share_id -> {page_id, shared_with_email, permission,
      shared_at}}

    Current-user perspective: no registration or account switching.
    """

    _STATE_KEYS = ("profile", "workspaces", "pages", "databases", "database_entries", "shares")
    _ID_COUNTER_DEFAULTS = {"page": 0, "database": 0, "entry": 0, "share": 0}
    _DEFAULT_SEED = 5678

    def __init__(self):
        super().__init__()
        self.profile: Dict[str, Any] = {}
        self.workspaces: Dict[str, Dict[str, Any]] = {}
        self.pages: Dict[str, Dict[str, Any]] = {}
        self.databases: Dict[str, Dict[str, Any]] = {}
        self.database_entries: Dict[str, Dict[str, Any]] = {}
        self.shares: Dict[str, Dict[str, Any]] = {}
        self._api_description = (
            "This tool belongs to the Notion API, which provides workspace "
            "platform for notes, documents, wikis, and project management "
            "with collaborative editing and database functionality."
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
        self.workspaces = scenario.get("workspaces", DEFAULT_STATE_COPY["workspaces"])
        self.pages = scenario.get("pages", DEFAULT_STATE_COPY["pages"])
        self.databases = scenario.get("databases", DEFAULT_STATE_COPY["databases"])
        self.database_entries = scenario.get("database_entries", DEFAULT_STATE_COPY["database_entries"])
        self.shares = scenario.get("shares", DEFAULT_STATE_COPY["shares"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, NotionAPI):
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

    def _require_workspace(self, workspace_id: str) -> Dict[str, Any]:
        ws = self.workspaces.get(workspace_id)
        if not ws:
            raise NotionError(
                "WORKSPACE_NOT_FOUND",
                f"Workspace '{workspace_id}' not found.",
                suggested_action="Use list_workspaces() to find valid workspace IDs.",
                context={"workspace_id": workspace_id},
            )
        return ws

    def _require_page(self, page_id: str) -> Dict[str, Any]:
        page = self.pages.get(page_id)
        if not page:
            raise NotionError(
                "PAGE_NOT_FOUND",
                f"Page '{page_id}' not found.",
                suggested_action="Use list_pages() or search_workspace() to find valid page IDs.",
                context={"page_id": page_id},
            )
        return page

    def _require_database(self, database_id: str) -> Dict[str, Any]:
        db = self.databases.get(database_id)
        if not db:
            raise NotionError(
                "DATABASE_NOT_FOUND",
                f"Database '{database_id}' not found.",
                suggested_action="Use search_workspace() to find valid database IDs.",
                context={"database_id": database_id},
            )
        return db

    # -----------------------------------------------------------------------
    # Profile
    # -----------------------------------------------------------------------

    def get_user_profile(self) -> Dict[str, Any]:
        """
        Retrieve the current user's Notion profile.

        Returns:
            Dict[str, Any]:
                user_id (str): The user's unique identifier.
                name (str): The user's display name.
                email (str): The user's email address.
                avatar_url (str | None): URL to the user's avatar image.
                workspaces (List[str]): List of workspace IDs the user belongs to.
                plan (str): The user's subscription plan.
        """
        return deepcopy(self.profile)

    # -----------------------------------------------------------------------
    # Workspaces
    # -----------------------------------------------------------------------

    def list_workspaces(self) -> List[Dict[str, Any]]:
        """
        List all workspaces accessible to the current user.

        Returns:
            List[Dict[str, Any]]: Workspace objects, each with fields:
                workspace_id (str), name (str), icon (str | None),
                member_count (int), plan (str).
        """
        return [deepcopy(ws) for ws in self.workspaces.values()]

    # -----------------------------------------------------------------------
    # Pages
    # -----------------------------------------------------------------------

    def create_page(
        self,
        workspace_id: str,
        title: str,
        content: str = "",
        parent_page_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new page in a workspace, optionally nested under an
        existing parent page.

        Args:
            workspace_id (str): The ID of the workspace to create the page in.
            title (str): Title of the new page.
            content (str): Body content of the page in markdown format.
                Defaults to empty string.
            parent_page_id (str, optional): ID of the parent page to nest
                this page under. If null, the page is created at the top
                level of the workspace.

        Returns:
            Dict[str, Any]:
                page_id (str), workspace_id (str), title (str),
                content (str), parent_page_id (str | None),
                created_at (str), updated_at (str), created_by (str),
                url (str).
        """
        self._require_workspace(workspace_id)
        if parent_page_id is not None:
            self._require_page(parent_page_id)

        page_id = self._new_id("page")
        now = _utc_now_iso()
        user_name = self.profile.get("name", "")
        page = {
            "page_id": page_id,
            "workspace_id": workspace_id,
            "title": title,
            "content": content,
            "parent_page_id": parent_page_id,
            "created_at": now,
            "updated_at": now,
            "created_by": user_name,
            "last_edited_by": user_name,
            "url": f"https://notion.example.com/{workspace_id}/{page_id}",
            "shared_with": [],
        }
        self.pages[page_id] = page
        return deepcopy(page)

    def get_page(self, page_id: str) -> Dict[str, Any]:
        """
        Retrieve the full details of a page by its ID.

        Args:
            page_id (str): The unique identifier of the page to retrieve.

        Returns:
            Dict[str, Any]:
                page_id (str), workspace_id (str), title (str),
                content (str), parent_page_id (str | None),
                created_at (str), updated_at (str), created_by (str),
                last_edited_by (str), url (str),
                shared_with (List[Dict]).
        """
        page = self._require_page(page_id)
        return deepcopy(page)

    def list_pages(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        List all pages in a given workspace.

        Args:
            workspace_id (str): The ID of the workspace whose pages to list.

        Returns:
            List[Dict[str, Any]]: Page summary objects, each with fields:
                page_id (str), title (str), parent_page_id (str | None),
                created_at (str), updated_at (str), created_by (str).
        """
        self._require_workspace(workspace_id)
        results = []
        for page in self.pages.values():
            if page.get("workspace_id") == workspace_id:
                results.append({
                    "page_id": page["page_id"],
                    "title": page["title"],
                    "parent_page_id": page.get("parent_page_id"),
                    "created_at": page["created_at"],
                    "updated_at": page["updated_at"],
                    "created_by": page.get("created_by", ""),
                })
        return results

    def update_page(
        self,
        page_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update the title and/or content of an existing page.

        Args:
            page_id (str): The unique identifier of the page to update.
            title (str, optional): New title for the page. If null, the
                title remains unchanged.
            content (str, optional): New body content for the page in
                markdown format. If null, the content remains unchanged.

        Returns:
            Dict[str, Any]:
                page_id (str), title (str), content (str),
                updated_at (str), last_edited_by (str).
        """
        page = self._require_page(page_id)
        if title is not None:
            page["title"] = title
        if content is not None:
            page["content"] = content
        page["updated_at"] = _utc_now_iso()
        page["last_edited_by"] = self.profile.get("name", "")
        return {
            "page_id": page_id,
            "title": page["title"],
            "content": page["content"],
            "updated_at": page["updated_at"],
            "last_edited_by": page["last_edited_by"],
        }

    def delete_page(self, page_id: str) -> Dict[str, Any]:
        """
        Delete a page by its ID. This moves the page to trash.

        Args:
            page_id (str): The unique identifier of the page to delete.

        Returns:
            Dict[str, Any]:
                page_id (str), status (str "deleted"), deleted_at (str).
        """
        self._require_page(page_id)
        del self.pages[page_id]
        return {
            "page_id": page_id,
            "status": "deleted",
            "deleted_at": _utc_now_iso(),
        }

    def search_workspace(
        self,
        query: str,
        workspace_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Search for pages and databases within a workspace by keyword query.

        Args:
            query (str): The search query string.
            workspace_id (str): The ID of the workspace to search in.

        Returns:
            List[Dict[str, Any]]: Search result objects, each with fields:
                object_type (str "page" or "database"), object_id (str),
                title (str), snippet (str), updated_at (str), url (str).
        """
        self._require_workspace(workspace_id)
        query_lower = query.lower()
        results = []

        for page in self.pages.values():
            if page.get("workspace_id") != workspace_id:
                continue
            if (query_lower in page.get("title", "").lower()
                    or query_lower in page.get("content", "").lower()):
                snippet = page.get("content", "")[:120]
                results.append({
                    "object_type": "page",
                    "object_id": page["page_id"],
                    "title": page["title"],
                    "snippet": snippet,
                    "updated_at": page.get("updated_at", ""),
                    "url": page.get("url", ""),
                })

        for db in self.databases.values():
            if db.get("workspace_id") != workspace_id:
                continue
            if query_lower in db.get("title", "").lower():
                results.append({
                    "object_type": "database",
                    "object_id": db["database_id"],
                    "title": db["title"],
                    "snippet": "",
                    "updated_at": db.get("updated_at", ""),
                    "url": db.get("url", ""),
                })

        return results

    # -----------------------------------------------------------------------
    # Databases
    # -----------------------------------------------------------------------

    def create_database(
        self,
        workspace_id: str,
        title: str,
        properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Create a new database (structured table) in a workspace with
        defined property columns.

        Args:
            workspace_id (str): The ID of the workspace to create the
                database in.
            title (str): Title of the new database.
            properties (Dict[str, str]): Dictionary mapping property names
                to their types (e.g. {"Status": "select", "Due Date":
                "date", "Assignee": "person"}).

        Returns:
            Dict[str, Any]:
                database_id (str), workspace_id (str), title (str),
                properties (Dict[str, str]), created_at (str), url (str).
        """
        self._require_workspace(workspace_id)
        database_id = self._new_id("database")
        now = _utc_now_iso()
        db = {
            "database_id": database_id,
            "workspace_id": workspace_id,
            "title": title,
            "properties": properties,
            "created_at": now,
            "updated_at": now,
            "url": f"https://notion.example.com/{workspace_id}/{database_id}",
        }
        self.databases[database_id] = db
        return deepcopy(db)

    def get_database(self, database_id: str) -> Dict[str, Any]:
        """
        Retrieve details and schema of a database by its ID.

        Args:
            database_id (str): The unique identifier of the database to
                retrieve.

        Returns:
            Dict[str, Any]:
                database_id (str), workspace_id (str), title (str),
                properties (Dict[str, str]), entry_count (int),
                created_at (str), updated_at (str), url (str).
        """
        db = self._require_database(database_id)
        result = deepcopy(db)
        result["entry_count"] = sum(
            1 for e in self.database_entries.values()
            if e.get("database_id") == database_id
        )
        return result

    def add_database_entry(
        self,
        database_id: str,
        fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Add a new row/entry to an existing database.

        Args:
            database_id (str): The ID of the database to add the entry to.
            fields (Dict[str, Any]): Dictionary mapping property names to
                their values (e.g. {"Name": "Task A", "Status":
                "In Progress", "Due Date": "2026-04-01"}).

        Returns:
            Dict[str, Any]:
                entry_id (str), database_id (str),
                fields (Dict[str, Any]), created_at (str), url (str).
        """
        db = self._require_database(database_id)
        entry_id = self._new_id("entry")
        now = _utc_now_iso()
        entry = {
            "entry_id": entry_id,
            "database_id": database_id,
            "fields": fields,
            "created_at": now,
            "url": f"https://notion.example.com/{db['workspace_id']}/{database_id}/{entry_id}",
        }
        self.database_entries[entry_id] = entry
        return deepcopy(entry)

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
        Share a page with another user by email, granting them a specified
        permission level.

        Args:
            page_id (str): The ID of the page to share.
            email (str): Email address of the person to share with.
            permission (str): Permission level to grant -- "view",
                "comment", or "edit". Defaults to "view".

        Returns:
            Dict[str, Any]:
                page_id (str), shared_with_email (str),
                permission (str), shared_at (str).
        """
        page = self._require_page(page_id)
        if permission not in ("view", "comment", "edit"):
            raise NotionError(
                "INVALID_PERMISSION",
                f"Permission '{permission}' is not valid.",
                suggested_action="Use 'view', 'comment', or 'edit'.",
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

        page.setdefault("shared_with", []).append({
            "email": email,
            "permission": permission,
        })

        return deepcopy(share_record)
