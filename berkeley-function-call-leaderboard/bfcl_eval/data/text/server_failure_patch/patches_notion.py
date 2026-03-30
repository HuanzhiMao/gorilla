"""Runtime patches for NotionAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.notion import NotionAPI
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
