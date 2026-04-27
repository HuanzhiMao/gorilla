"""Runtime patches for NotionAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.notion import (
    NotionAPI,
    NotionError,
)
from copy import deepcopy
from datetime import datetime, timezone
import uuid

# ─── Source: notion_patches.py ───


@NotionAPI._register_patch("update_page", "noop_permanent")
def update_page_noop_permanent(self, page_id, title=None, content=None, *args, **kwargs):
    """Permanent silent no-op. Returns fake success without ever updating the page."""
    page = self.pages.get(page_id, {})
    result = deepcopy(page)
    if title:
        result["title"] = title
    result["status"] = "updated"
    result["updated_at"] = datetime.now(timezone.utc).isoformat()
    return result


@NotionAPI._register_patch("create_page", "noop_permanent")
def create_page_noop_permanent(self, *args, **kwargs):
    """Permanent silent no-op. Returns fake page creation without ever creating it.
    The page never exists, so get_page will not find it."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "page_id": f"page_{uuid.uuid4().hex[:8]}",
        "status": "created",
        "created_at": now,
        "updated_at": now,
    }


# ---------- add_database_entry ----------


# ft_extra_27 -- add_database_entry echoes the full input payload in its
# response but only persists fields that exist in the cached schema. Any
# user-supplied field not present in the database's declared properties
# is silently dropped from self.database_entries[entry_id]['fields'].
@NotionAPI._register_patch("add_database_entry", "drop_unknown_columns_permanent")
def add_database_entry_drop_unknown_columns_permanent(
    self, database_id, fields, *args, **kwargs
):
    """Permanent silent corruption. The response includes every field the
    user supplied so the call looks successful, but only fields whose names
    appear in the database's declared properties are written to the durable
    row. Re-reading the entry via get_database_entry / get_database surfaces
    the dropped columns. Mirrors a real-world Notion bug where a stale schema
    cache silently filtered new property names."""
    db = self._require_database(database_id)
    declared_props = set((db.get("properties") or {}).keys())
    persisted_fields = {k: v for k, v in (fields or {}).items() if k in declared_props}
    entry_id = self._new_id("entry")
    now = datetime.now(timezone.utc).isoformat()
    # Persist with the filtered fields so verification shows the dropped column.
    self.database_entries[entry_id] = {
        "entry_id": entry_id,
        "database_id": database_id,
        "fields": persisted_fields,
        "created_at": now,
        "url": f"https://notion.example.com/{db['workspace_id']}/{database_id}/{entry_id}",
    }
    # Misleading echo: tell the caller the full payload made it.
    return {
        "entry_id": entry_id,
        "database_id": database_id,
        "fields": deepcopy(fields or {}),
        "created_at": now,
        "url": f"https://notion.example.com/{db['workspace_id']}/{database_id}/{entry_id}",
    }


# ---------- search_workspace ----------


# ft_extra_28 -- First call returns a stale snapshot of the search index
# (anything updated_at > 2026-03-10 is filtered out). Second call falls
# through to the live search. Agent should retry or cross-check.
@NotionAPI._register_patch("search_workspace", "stale_index_temporary")
def search_workspace_stale_index_temporary(self, *args, **kwargs):
    """Temporary. The first call returns a list filtered to entries whose
    updated_at <= 2026-03-10 (i.e. the search index is showing a snapshot
    from a few weeks ago). Second call returns the live results from the
    original implementation."""
    if self._patch_call_count <= 1:
        full = self._original_function(*args, **kwargs)
        cutoff = "2026-03-10T23:59:59"
        return [r for r in full if (r.get("updated_at") or "") <= cutoff]
    return self._original_function(*args, **kwargs)


# ---------- share_page ----------


# ft_extra_96 -- share_page returns a fake share_id and looks successful
# but the underlying self.shares dict is not updated. A follow-up read
# of shares will not show the recipient. Permanent silent no-op.
@NotionAPI._register_patch("share_page", "share_noop_permanent")
def share_page_share_noop_permanent(self, page_id, email, permission="view", *args, **kwargs):
    """Permanent silent no-op. Echoes a plausible share record without
    persisting it. Recovery: the agent should warn the user the share did
    not actually take effect."""
    import uuid
    from datetime import datetime, timezone
    self._require_page(page_id)
    return {
        "share_id": f"share_{uuid.uuid4().hex[:8]}",
        "page_id": page_id,
        "email": email,
        "permission": permission,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

