"""Runtime patches for ConfluenceAPI methods.

This is the first patch module registered on ConfluenceAPI -- prior to
2026-04-21 Confluence had zero scenario-injected failures, which made it a
"silent healthy" server in the benchmark. Scenarios that pivot on Confluence
failing should hang off the patches registered here.
"""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.confluence import (
    ConfluenceAPI,
    ConfluenceError,
)
import uuid
from datetime import datetime, timezone

# ---------- publish_content ----------


# ft_extra_29 -- publish_content returns a fake page_id and an optimistic
# success payload, but the page is never written to self.pages. A follow-up
# fetch_content or list_space_content will correctly fail to locate it.
@ConfluenceAPI._register_patch("publish_content", "publish_noop_permanent")
def publish_content_publish_noop_permanent(
    self, space_id, title, body="", parent_page_id=None, *args, **kwargs
):
    """Permanent silent no-op. Returns a plausible page record without ever
    persisting it. Mirrors VenmoAPI.send_money/phantom_permanent and
    NotionAPI.create_page/noop_permanent. Agent must verify with
    fetch_content or list_space_content and flag the miss to the user."""
    now = datetime.now(timezone.utc).isoformat()
    fake_id = f"page_{uuid.uuid4().hex[:8]}"
    return {
        "page_id": fake_id,
        "space_id": space_id,
        "title": title,
        "body": body,
        "parent_page_id": parent_page_id,
        "version_number": 1,
        "created_at": now,
        "updated_at": now,
        "created_by": self.profile.get("display_name", ""),
        "last_edited_by": self.profile.get("display_name", ""),
        "url": f"https://confluence.example.com/{space_id}/{fake_id}",
        "labels": [],
    }


# ---------- add_comment ----------


# ft_extra_55 -- add_comment reports a successful comment with a fresh
# comment_id and the full body echoed back in the response, but actually
# persists the comment with body="" (an overzealous HTML sanitizer strips
# every character). list_comments on the page will therefore show a
# zero-content comment row under the user's name. Permanent.
@ConfluenceAPI._register_patch("add_comment", "comment_noop_permanent")
def add_comment_comment_noop_permanent(self, page_id, body, *args, **kwargs):
    """Permanent silent corruption framed as a noop for the content. The
    comment row is written but with an empty body, so verification via
    list_comments shows the comment 'landed' under the user's name while the
    message they intended to leave is lost."""
    self._require_page(page_id)
    comment_id = self._new_id("comment")
    now = datetime.now(timezone.utc).isoformat()
    user_name = self.profile.get("display_name", "")
    self.comments[comment_id] = {
        "comment_id": comment_id,
        "page_id": page_id,
        "body": "",
        "created_at": now,
        "created_by": user_name,
    }
    # Misleading echo: tell the caller the full body made it.
    return {
        "comment_id": comment_id,
        "page_id": page_id,
        "body": body,
        "created_at": now,
        "created_by": user_name,
    }


# ---------- revise_content ----------


# ft_extra_93 -- revise_content first call raises a transient
# VERSION_CONFLICT (the platform briefly held a stale version pointer
# during a deploy). Second call falls through to the real implementation
# and the supplied version_number now matches.
@ConfluenceAPI._register_patch("revise_content", "stale_version_pointer_temporary")
def revise_content_stale_version_pointer_temporary(self, page_id, version_number, title=None, body=None, *args, **kwargs):
    """Temporary availability_denial. First call raises VERSION_CONFLICT
    even when the supplied version_number is correct (the server held a
    stale pointer briefly). Second call falls through to the real
    implementation. Recovery: re-fetch via fetch_content, retry."""
    if self._patch_call_count <= 1:
        page = self._require_page(page_id)
        actual = page.get("version_number", 1)
        raise ConfluenceError(
            "VERSION_CONFLICT",
            f"Version pointer momentarily stale; expected {actual}, got {version_number}.",
            suggested_action="Re-fetch with fetch_content() and retry.",
            context={
                "page_id": page_id,
                "expected_version": actual,
                "provided_version": version_number,
                "retryable": True,
            },
        )
    return self._original_function(page_id, version_number, title, body)


# ---------- grant_content_access ----------


# ft_extra_94 -- grant_content_access reports success but the share row
# is never written to self.shares. A follow-up read of the share list
# will not include the recipient. Permanent silent no-op.
@ConfluenceAPI._register_patch("grant_content_access", "grant_noop_permanent")
def grant_content_access_grant_noop_permanent(self, page_id, email, permission="view", *args, **kwargs):
    """Permanent silent no-op. Returns a fake share record without
    persisting it. Recovery: the agent should warn the user the grant did
    not durably take and recommend a manual re-share."""
    self._require_page(page_id)
    fake_id = f"share_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    return {
        "share_id": fake_id,
        "page_id": page_id,
        "email": email,
        "permission": permission,
        "status": "active",
        "created_at": now,
    }


# ---------- fetch_content ----------


# ft_extra_95 -- fetch_content first call raises CACHE_MISS marked as
# retryable (the page exists but is briefly absent from the read cache).
# Second call falls through to the real implementation.
@ConfluenceAPI._register_patch("fetch_content", "cache_miss_temporary")
def fetch_content_cache_miss_temporary(self, page_id, *args, **kwargs):
    """Temporary availability_denial. First call raises CACHE_MISS even
    though the page exists in self.pages. Second call falls through.
    Recovery: retry once."""
    if self._patch_call_count <= 1:
        raise ConfluenceError(
            "CACHE_MISS",
            f"Read cache miss for page {page_id}; warmup in progress.",
            suggested_action="Retry after a short delay (~5s).",
            context={"page_id": page_id, "retryable": True, "retry_after_seconds": 5},
        )
    return self._original_function(page_id, *args, **kwargs)

