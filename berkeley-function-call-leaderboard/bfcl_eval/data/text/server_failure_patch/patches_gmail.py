"""Runtime patches for GmailAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.gmail import GmailAPI, GmailError
import uuid

# ─── Source: socrates ─────────────────────────────────────────────────────────


@GmailAPI._register_patch("send_email", "unavailable_permanent")
def send_email_unavailable_permanent(self, *args, **kwargs):
    """Permanent. Always raises SERVICE_UNAVAILABLE."""
    raise GmailError(
        "SERVICE_UNAVAILABLE",
        "Gmail SMTP service is currently unavailable.",
        "Try using an alternative email service.",
    )


@GmailAPI._register_patch("send_email", "unavailable_temporary")
def send_email_unavailable_temporary(self, *args, **kwargs):
    """Temporary. Fails on calls 1-2, passes through on 3+."""
    if self._patch_call_count <= 2:
        raise GmailError(
            "SERVICE_UNAVAILABLE",
            "Gmail service temporarily unavailable. Please retry.",
            "Retry the request.",
        )
    return self._original_function(*args, **kwargs)


@GmailAPI._register_patch("create_draft", "noop_permanent")
def create_draft_noop_permanent(self, *args, **kwargs):
    """Permanent silent no-op. Returns fake draft without ever creating it.
    The draft never exists, so list_drafts will not show it."""
    return {"draft_id": f"draft_{uuid.uuid4().hex[:8]}", "status": "created"}


@GmailAPI._register_patch("send_email", "noop_permanent")
def send_email_noop_permanent(self, *args, **kwargs):
    """Permanent silent no-op. Returns fake sent email without ever sending it.
    The email never exists, so list_emails/search_emails will not show it."""
    return {
        "email_id": f"email_{uuid.uuid4().hex[:8]}",
        "thread_id": f"thread_{uuid.uuid4().hex[:8]}",
        "status": "sent",
    }


@GmailAPI._register_patch("send_email", "schema_mismatch_temporary")
def send_email_schema_mismatch_temporary(self, *args, **kwargs):
    """Temporary. On first call raises INVALID_PARAMETER about renamed param. On 2nd+, passes through."""
    if self._patch_call_count <= 1:
        raise GmailError(
            "INVALID_PARAMETER",
            "Parameter 'from' has been replaced by 'sender_alias'. Provide sender_alias with your configured alias name.",
            "Use 'sender_alias' parameter.",
        )
    return self._original_function(*args, **kwargs)


# ─── Source: srivatsa ─────────────────────────────────────────────────────────


@GmailAPI._register_patch("send_email", "recipient_corruption")
def send_email_recipient_corruption(self, *args, **kwargs):
    """
    Calls the original send_email and stores the email, but then corrupts
    the stored record by replacing the 'to' field with the sender's own email
    and appending a duplicate subject with garbage characters. Returns 200 OK —
    corruption only surfaces on get_email.
    """
    result = self._original_function(*args, **kwargs)
    email_id = result.get("email_id")
    if email_id and hasattr(self, "emails") and email_id in self.emails:
        email = self.emails[email_id]
        sender = getattr(self, "user_email", "user@myemail.com")
        original_subject = email.get("subject", "")
        email["to"] = [sender]
        email["subject"] = f"{original_subject}{original_subject}#x8k2m"
    return result


@GmailAPI._register_patch("send_email", "content_corruption")
def send_email_content_corruption(self, *args, **kwargs):
    """
    Calls the original send_email and stores the email, but then corrupts
    the stored record by truncating the subject to 10 characters and emptying
    the body. Returns a normal 200 OK — corruption only surfaces on get_email.
    """
    result = self._original_function(*args, **kwargs)
    email_id = result.get("email_id")
    if email_id and hasattr(self, "emails") and email_id in self.emails:
        email = self.emails[email_id]
        email["subject"] = email.get("subject", "")[:10]
        email["body"] = ""
    return result


@GmailAPI._register_patch("send_email", "phantom_send")
def send_email_phantom_send(self, *args, **kwargs):
    """
    Returns a successful 200 OK response with a valid-looking email_id,
    but never actually stores the email anywhere. get_email on the returned
    email_id will return EMAIL_NOT_FOUND and it won't appear in SENT.
    """
    return {
        "email_id": "eml_7k2p",
        "thread_id": "thr_9m1",
        "status": "sent"
    }


@GmailAPI._register_patch("search_emails", "stale_index")
def search_emails_stale_index(self, *args, **kwargs):
    """
    Returns search results but filters out any emails newer than 2026-02-15,
    simulating a stale search index that hasn't indexed recent mail.
    """
    results = self._original_function(*args, **kwargs)
    cutoff = "2026-02-15"
    return [email for email in results if email.get("date", "") <= cutoff]


@GmailAPI._register_patch("search_emails", "stale_index_feb12")
def search_emails_stale_index_feb12(self, *args, **kwargs):
    """
    Returns search results but filters out any emails newer than 2026-02-12,
    simulating a stale search index missing the last 3 weeks of mail.
    """
    results = self._original_function(*args, **kwargs)
    cutoff = "2026-02-12"
    return [email for email in results if email.get("date", "") <= cutoff]


@GmailAPI._register_patch("search_emails", "stale_index_feb20")
def search_emails_stale_index_feb20(self, *args, **kwargs):
    """
    Returns search results but filters out any emails newer than 2026-02-20,
    simulating a stale inbox sync missing the last 2 weeks of mail.
    """
    results = self._original_function(*args, **kwargs)
    cutoff = "2026-02-20"
    return [email for email in results if email.get("date", "") <= cutoff]


@GmailAPI._register_patch("add_label", "corrupt_priority")
def add_label_corrupt_priority(self, email_id, label):
    """
    Calls the original add_label but silently maps 'Priority' to 'SPAM'
    in the stored email. Returns a 200 OK as if the label was applied correctly.
    """
    result = self._original_function(email_id, label)
    if label == "Priority":
        email = self.emails.get(email_id, {})
        labels = email.get("labels", [])
        email["labels"] = [l for l in labels if l != "Priority"] + ["SPAM"]
    return result


@GmailAPI._register_patch("create_filter", "wrong_criteria")
def create_filter_wrong_criteria(self, *args, **kwargs):
    """
    Calls the original create_filter but overwrites the returned filter object
    with corrupted criteria (wrong sender domain) and a destructive TRASH action
    instead of the requested label. Returns 200 OK — corruption is in the response.
    """
    result = self._original_function(*args, **kwargs)
    if isinstance(result, dict) and "filter_id" in result:
        result["criteria"] = {"from": "@spam-newsletter.com"}
        result["actions"] = {"TRASH": True}
    return result


@GmailAPI._register_patch("reply_to_email", "thread_index_failure")
def reply_to_email_thread_index_failure(self, *args, **kwargs):
    """
    Always returns a persistent 500 INTERNAL_ERROR,
    simulating a corrupted threading subsystem index that blocks all reply
    operations. No retry will succeed.
    """
    return {
        "error_code": "INTERNAL_ERROR",
        "message": "Threading subsystem failure - unable to process reply",
        "context": {"subsystem": "thread_index"}
    }


@GmailAPI._register_patch("forward_email", "relay_outage")
def forward_email_relay_outage(self, *args, **kwargs):
    """
    Always returns a persistent 503 SERVICE_UNAVAILABLE,
    simulating a backend outbound mail relay failure. No retry will succeed.
    """
    return {
        "error_code": "SERVICE_UNAVAILABLE",
        "message": "Outbound mail relay is currently unavailable",
        "context": {"subsystem": "outbound_relay"}
    }


@GmailAPI._register_patch("reply_to_email", "reply_all_collapse")
def reply_to_email_reply_all_collapse(self, *args, **kwargs):
    """
    Calls the original reply_to_email and stores the sent email, but then
    collapses the stored recipient list down to only the first 'to' address,
    dropping all CC recipients. Returns a 200 OK response claiming all
    recipients were included — corruption only surfaces on get_email.
    """
    result = self._original_function(*args, **kwargs)
    email_id = result.get("email_id")
    if email_id and hasattr(self, "emails") and email_id in self.emails:
        email = self.emails[email_id]
        full_to = email.get("to", [])
        email["to"] = [full_to[0]] if full_to else []
        email["cc"] = []
        email["bcc"] = []
    return result
