"""Runtime patches for OutlookAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.outlook import (
    OutlookAPI,
    OutlookError,
)

# ─── Source: srivatsa ───
# These "blocked" patches close off alternate paths the LLM might take to the
# same end-state, so the must_be_called_functions deterministic check is not
# defeated by a valid-but-different recovery sequence.


@OutlookAPI._register_patch("compose_draft", "blocked")
def compose_draft_blocked(self, *args, **kwargs):
    raise OutlookError(
        "FEATURE_DISABLED",
        "Draft composition is temporarily unavailable. Use send_mail_item directly.",
    )


@OutlookAPI._register_patch("send_composed_draft", "blocked")
def send_composed_draft_blocked(self, *args, **kwargs):
    raise OutlookError(
        "FEATURE_DISABLED",
        "Sending composed drafts is temporarily unavailable. Use send_mail_item directly.",
    )


@OutlookAPI._register_patch("forward_mail_item", "blocked")
def forward_mail_item_blocked(self, *args, **kwargs):
    raise OutlookError(
        "FEATURE_DISABLED",
        "Forwarding is temporarily unavailable. Compose and send a new mail item instead.",
    )


@OutlookAPI._register_patch("reply_to_conversation", "blocked")
def reply_to_conversation_blocked(self, *args, **kwargs):
    raise OutlookError(
        "FEATURE_DISABLED",
        "Conversation replies are temporarily unavailable. Use send_mail_item to compose a new message.",
    )


@OutlookAPI._register_patch("mark_as_important", "blocked")
def mark_as_important_blocked(self, *args, **kwargs):
    raise OutlookError(
        "FEATURE_DISABLED",
        "Marking as important is temporarily unavailable. Use flag_email instead.",
    )


@OutlookAPI._register_patch("list_mail_items", "blocked")
def list_mail_items_blocked(self, *args, **kwargs):
    raise OutlookError(
        "FEATURE_DISABLED",
        "Listing mail items is temporarily unavailable. Use query_mail_items instead.",
    )


@OutlookAPI._register_patch("send_mail_item", "blocked")
def send_mail_item_blocked(self, *args, **kwargs):
    raise OutlookError(
        "FEATURE_DISABLED",
        "Sending a new mail item is temporarily unavailable. Use forward_mail_item instead.",
    )


# ---------- send_mail_item (cc_recipient_limit_permanent) ----------


# ft_extra_48 -- schema_mismatch/permanent. The Outlook send_mail_item
# endpoint has shipped a hard CC-recipient cap (max 5 entries). Sends
# with more than 5 CC recipients are permanently rejected with
# CC_LIMIT_EXCEEDED. Agent must split the recipient list into batches
# or pivot to GmailAPI.send_email rather than retrying the same payload.
@OutlookAPI._register_patch("send_mail_item", "cc_recipient_limit_permanent")
def send_mail_item_cc_recipient_limit_permanent(
    self, to=None, cc=None, bcc=None, subject="", body="", *args, **kwargs
):
    """Permanent. Always raises CC_LIMIT_EXCEEDED if cc has more than 5
    entries. If cc is short enough, falls through to original. The patch
    is registered to surface the error in the failing scenario; the
    scenario crafts a >5-CC payload to exercise it deterministically."""
    cc_list = cc or []
    if isinstance(cc_list, str):
        cc_list = [cc_list]
    if len(cc_list) > 5:
        raise OutlookError(
            "CC_LIMIT_EXCEEDED",
            (
                f"send_mail_item rejected: CC list has {len(cc_list)} "
                "entries; the new policy caps CC recipients at 5."
            ),
            (
                "Do NOT retry the same payload. Split the recipients into "
                "smaller batches or pivot to GmailAPI.send_email."
            ),
        )
    return self._original_function(
        to=to, cc=cc, bcc=bcc, subject=subject, body=body, *args, **kwargs
    )
