"""
Outlook Email Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Folder-based organization with fixed system folders.
- Conversation-based view where emails are grouped by thread_id.
- Multi-user support with user switching.
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


class OutlookError(Exception):
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


# ---------------------------------------------------------------------------
# System folder constants
# ---------------------------------------------------------------------------

SYSTEM_FOLDER_NAMES = (
    "inbox",
    "sent",
    "spam",
    "trash",
    "starred",
    "important",
    "unread",
    "category_primary",
    "category_social",
    "category_promotions",
)


DEFAULT_STATE = {
    "random_seed": 5678,
    "profile": {},
    "emails": {},
    "drafts": {},
    "contacts": {},
    "folders": {},
    "quick_steps": {},
    "categories": [],
    "pinned_emails": [],
}


class OutlookAPI(PatchableMixin):
    """
    In-memory dummy implementation of an Outlook-like email service.

    State variables:
    - profile: Dict of {name, email}
    - emails: Dict of {email_id -> {email_id, thread_id, from, to[], cc[],
      bcc[], subject, body, attachments[], labels[], read, starred, important,
      created_at}}
    - drafts: Dict of {draft_id -> {draft_id, to[], cc[], bcc[], subject, body,
      attachments[], created_at}}
    - contacts: Dict of {name, email}
    - folders: Dict of {folder_name -> [email_id, ...]}

    Supports multi-user switching via switch_user().
    Uses Outlook-style conventions (RE: prefix, FW: prefix, move_to_folder).
    """


    def __init__(self):
        self._id_counters = {"email": 0, "thread": 0, "draft": 0}
        self.profile: Dict[str, Dict[str, Any]] = {}
        self.emails: Dict[str, Dict[str, Any]] = {}
        self.drafts: Dict[str, Dict[str, Any]] = {}
        self.contacts: Dict[str, Dict[str, Any]] = {}
        self.folders: Dict[str, List[str]] = {}
        self.quick_steps: Dict[str, Dict[str, Any]] = {}
        self.categories: List[Dict[str, str]] = []
        self.pinned_emails: List[str] = []
        self._api_description = (
            "This tool belongs to the Outlook Email API, which provides "
            "functionality for sending, receiving, and organizing emails using "
            "a folder-based system with conversation grouping."
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
        self.emails = scenario.get("emails", DEFAULT_STATE_COPY["emails"])
        self.drafts = scenario.get("drafts", DEFAULT_STATE_COPY["drafts"])
        self.contacts = scenario.get("contacts", DEFAULT_STATE_COPY["contacts"])
        self.folders = scenario.get("folders", DEFAULT_STATE_COPY["folders"])
        self.quick_steps = scenario.get("quick_steps", DEFAULT_STATE_COPY["quick_steps"])
        self.categories = scenario.get("categories", DEFAULT_STATE_COPY["categories"])
        self.pinned_emails = scenario.get("pinned_emails", DEFAULT_STATE_COPY["pinned_emails"])
        self.long_context = long_context
        # Auto-activate the sole user when the profile is single-user so that
        # self.user_id is set before any method that calls _require_user runs.
        # Multi-user profiles still require the agent to call switch_user().
        if len(self.profile) == 1:
            self.user_id = next(iter(self.profile))
        else:
            self.user_id = None

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, OutlookAPI):
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

    def _require_user(self, user_id: str) -> Dict[str, Any]:
        user = self.profile.get(user_id)
        if not user:
            raise OutlookError(
                "USER_NOT_FOUND",
                f"User '{user_id}' not found.",
                suggested_action="Verify the user_id or use switch_user().",
                context={"user_id": user_id},
            )
        return user

    def _require_email(self, email_id: str) -> Dict[str, Any]:
        email = self.emails.get(email_id)
        if not email:
            raise OutlookError(
                "EMAIL_NOT_FOUND",
                f"Email '{email_id}' not found.",
                suggested_action="Use list_emails() or search_emails() to find valid email IDs.",
                context={"email_id": email_id},
            )
        return email

    def _require_draft(self, draft_id: str) -> Dict[str, Any]:
        draft = self.drafts.get(draft_id)
        if not draft:
            raise OutlookError(
                "DRAFT_NOT_FOUND",
                f"Draft '{draft_id}' not found.",
                suggested_action="Use create_draft() to create a draft first.",
                context={"draft_id": draft_id},
            )
        return draft

    def _add_to_folder(self, folder_name: str, email_id: str) -> None:
        """Add an email_id to a folder list and the email's labels."""
        folder_list = self.folders.get(folder_name)
        if folder_list is not None and email_id not in folder_list:
            folder_list.append(email_id)
        em = self.emails.get(email_id)
        if em is not None and folder_name not in em.get("labels", []):
            em.setdefault("labels", []).append(folder_name)

    def _remove_from_folder(self, folder_name: str, email_id: str) -> None:
        """Remove an email_id from a folder list and the email's labels."""
        folder_list = self.folders.get(folder_name)
        if folder_list is not None and email_id in folder_list:
            folder_list.remove(email_id)
        em = self.emails.get(email_id)
        if em is not None and folder_name in em.get("labels", []):
            em["labels"].remove(folder_name)

    def _get_or_create_thread_id(self, subject: str, participants: List[str]) -> str:
        """Find an existing thread_id by subject/participant match, or create new."""
        normalized = (subject or "").strip().lower()
        for prefix in ("re: ", "fw: "):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :]
                break

        for em in self.emails.values():
            em_subj = (em.get("subject", "") or "").strip().lower()
            for prefix in ("re: ", "fw: "):
                if em_subj.startswith(prefix):
                    em_subj = em_subj[len(prefix) :]
                    break
            if em_subj == normalized:
                em_parts = set()
                em_parts.add(em.get("from", ""))
                em_parts.update(em.get("to", []))
                em_parts.update(em.get("cc", []))
                if em_parts & set(participants):
                    return em.get("thread_id", self._new_id("thread"))
        return self._new_id("thread")

    # -----------------------------------------------------------------------
    # User switching
    # -----------------------------------------------------------------------

    def set_active_user(self, username: str) -> Dict[str, Any]:
        """
        Switch the active user account.

        Args:
            username (str): The username to switch to. Must exist in the users dict.

        Returns:
            Dict[str, Any]:
                username (str): The active username.
                name (str): The user's display name.
                email_address (str): The user's email address.
        """
        user = self._require_user(username)
        self.user_id = username
        return {
            "username": user.get("username", username),
            "name": user.get("name", ""),
            "email_address": user.get("email_address", ""),
        }

    # -----------------------------------------------------------------------
    # Email listing & reading
    # -----------------------------------------------------------------------

    def list_mail_items(
        self,
        folder: str = "inbox",
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List emails in a specific folder.

        Args:
            folder (str): Folder name (e.g. "inbox", "sent", "trash").
                Defaults to "inbox".
            max_results (int): Maximum number of emails to return. Defaults to 20.

        Returns:
            List[Dict[str, Any]]: Email objects sorted by created_at descending.
        """
        self._require_user(self.user_id)
        folder_list = self.folders.get(folder)
        if folder_list is None:
            raise OutlookError(
                "FOLDER_NOT_FOUND",
                f"Folder '{folder}' not found.",
                suggested_action=f"Use one of: {', '.join(SYSTEM_FOLDER_NAMES)}.",
                context={"folder": folder},
            )
        results = []
        for eid in folder_list:
            em = self.emails.get(eid)
            if not em:
                continue
            results.append(deepcopy(em))
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results[:max_results]

    def get_mail_item(self, email_id: str) -> Dict[str, Any]:
        """
        Retrieve the full content of a single email by its ID.

        Args:
            email_id (str): The unique identifier of the email.

        Returns:
            Dict[str, Any]: Full email object.
        """
        em = self._require_email(email_id)
        return deepcopy(em)

    def get_conversation(self, thread_id: str) -> Dict[str, Any]:
        """
        Retrieve all emails in a conversation (thread).

        Args:
            thread_id (str): The unique thread/conversation identifier.

        Returns:
            Dict[str, Any]:
                thread_id (str), subject (str),
                emails (List[Dict]) — in chronological order.
        """
        self._require_user(self.user_id)
        emails = []
        for em in self.emails.values():
            if em.get("thread_id") == thread_id:
                emails.append(deepcopy(em))
        if not emails:
            raise OutlookError(
                "CONVERSATION_NOT_FOUND",
                f"Conversation '{thread_id}' not found.",
                suggested_action="Use a valid thread_id from an email.",
                context={"thread_id": thread_id},
            )
        emails.sort(key=lambda x: x.get("created_at", ""))
        return {
            "thread_id": thread_id,
            "subject": emails[0].get("subject", ""),
            "emails": emails,
        }

    # -----------------------------------------------------------------------
    # Composing & sending
    # -----------------------------------------------------------------------

    def send_mail_item(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Compose and send an email immediately. The sent email is placed in
        the sent folder.

        Args:
            to (List[str]): Recipient email addresses.
            subject (str): Subject line.
            body (str): Body text.
            cc (List[str], optional): Carbon copy recipients.
            bcc (List[str], optional): Blind carbon copy recipients.
            attachments (List[str], optional): Attachment filenames or IDs.

        Returns:
            Dict[str, Any]:
                email_id (str), thread_id (str), status (str).
        """
        user = self._require_user(self.user_id)
        if not to:
            raise OutlookError(
                "NO_RECIPIENTS",
                "At least one recipient is required.",
                suggested_action="Provide at least one email address in the 'to' field.",
                context={"user_id": self.user_id},
            )

        now = _utc_now_iso()
        sender = user.get("email_address", self.user_id)
        all_participants = list(set([sender] + (to or []) + (cc or [])))
        thread_id = self._get_or_create_thread_id(subject, all_participants)

        email_id = self._new_id("email")
        email_obj = {
            "email_id": email_id,
            "thread_id": thread_id,
            "from": sender,
            "to": to or [],
            "cc": cc or [],
            "bcc": bcc or [],
            "subject": subject,
            "body": body,
            "attachments": attachments or [],
            "labels": ["sent"],
            "read": True,
            "starred": False,
            "important": False,
            "created_at": now,
        }

        self.emails[email_id] = email_obj
        self._add_to_folder("sent", email_id)

        return {
            "email_id": email_id,
            "thread_id": thread_id,
            "status": "sent",
        }

    def compose_draft(
        self,
        to: Optional[List[str]] = None,
        subject: str = "",
        body: str = "",
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new email draft.

        Args:
            to (List[str], optional): Intended recipients.
            subject (str): Subject line. Defaults to "".
            body (str): Body text. Defaults to "".
            cc (List[str], optional): CC recipients.
            bcc (List[str], optional): BCC recipients.

        Returns:
            Dict[str, Any]:
                draft_id (str), status (str).
        """
        self._require_user(self.user_id)
        now = _utc_now_iso()
        draft_id = self._new_id("draft")
        self.drafts[draft_id] = {
            "draft_id": draft_id,
            "to": to or [],
            "cc": cc or [],
            "bcc": bcc or [],
            "subject": subject,
            "body": body,
            "attachments": [],
            "created_at": now,
        }
        return {"draft_id": draft_id, "status": "created"}

    def update_composed_draft(
        self,
        draft_id: str,
        to: Optional[List[str]] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing draft with new content.

        Args:
            draft_id (str): The draft to update.
            to (List[str], optional): Updated recipients. None keeps current.
            subject (str, optional): Updated subject. None keeps current.
            body (str, optional): Updated body. None keeps current.
            cc (List[str], optional): Updated CC. None keeps current.
            bcc (List[str], optional): Updated BCC. None keeps current.
            attachments (List[str], optional): Updated attachments. None keeps current.

        Returns:
            Dict[str, Any]: The updated draft object.
        """
        draft = self._require_draft(draft_id)
        if to is not None:
            draft["to"] = to
        if subject is not None:
            draft["subject"] = subject
        if body is not None:
            draft["body"] = body
        if cc is not None:
            draft["cc"] = cc
        if bcc is not None:
            draft["bcc"] = bcc
        if attachments is not None:
            draft["attachments"] = attachments
        return deepcopy(draft)

    def send_composed_draft(self, draft_id: str) -> Dict[str, Any]:
        """
        Send a previously created draft. The draft is removed after sending.

        Args:
            draft_id (str): The draft to send.

        Returns:
            Dict[str, Any]:
                email_id (str), thread_id (str), status (str).
        """
        draft = self._require_draft(draft_id)
        if not draft.get("to"):
            raise OutlookError(
                "NO_RECIPIENTS",
                "Draft has no recipients.",
                suggested_action="Call update_draft() to add recipients first.",
                context={"draft_id": draft_id},
            )

        result = self.send_mail_item(
            to=draft["to"],
            subject=draft.get("subject", ""),
            body=draft.get("body", ""),
            cc=draft.get("cc"),
            bcc=draft.get("bcc"),
            attachments=draft.get("attachments"),
        )

        del self.drafts[draft_id]
        return result

    def reply_to_conversation(
        self,
        email_id: str,
        body: str,
        reply_all: bool = False,
    ) -> Dict[str, Any]:
        """
        Reply to an existing email. The reply is added to the same conversation.

        Args:
            email_id (str): The email to reply to.
            body (str): The reply body text.
            reply_all (bool): If True, reply to all recipients. Defaults to False.

        Returns:
            Dict[str, Any]:
                email_id (str), thread_id (str), status (str).
        """
        original = self._require_email(email_id)
        user = self._require_user(self.user_id)
        sender = user.get("email_address", self.user_id)

        if reply_all:
            recipients = list(
                set(
                    [original["from"]] + original.get("to", []) + original.get("cc", [])
                )
            )
            if sender in recipients:
                recipients.remove(sender)
        else:
            recipients = [original["from"]]

        subject = original.get("subject", "")
        if not subject.lower().startswith("re:"):
            subject = f"RE: {subject}"

        return self.send_mail_item(to=recipients, subject=subject, body=body)

    def forward_mail_item(
        self,
        email_id: str,
        to: List[str],
        additional_message: str = "",
    ) -> Dict[str, Any]:
        """
        Forward an email to new recipients.

        Args:
            email_id (str): The email to forward.
            to (List[str]): Forwarding recipient email addresses.
            additional_message (str): Optional message to prepend.

        Returns:
            Dict[str, Any]:
                email_id (str), thread_id (str), status (str).
        """
        original = self._require_email(email_id)
        self._require_user(self.user_id)
        if not to:
            raise OutlookError(
                "NO_RECIPIENTS",
                "At least one forwarding recipient is required.",
                suggested_action="Provide at least one email address in the 'to' field.",
                context={"email_id": email_id},
            )

        subject = original.get("subject", "")
        if not subject.lower().startswith("fw:"):
            subject = f"FW: {subject}"

        fwd_body = additional_message
        if additional_message:
            fwd_body += "\n\n"
        fwd_body += "________________________________\n"
        fwd_body += f"From: {original.get('from', '')}\n"
        fwd_body += f"Sent: {original.get('created_at', '')}\n"
        fwd_body += f"To: {'; '.join(original.get('to', []))}\n"
        fwd_body += f"Subject: {original.get('subject', '')}\n\n"
        fwd_body += original.get("body", "")

        return self.send_mail_item(
            to=to,
            subject=subject,
            body=fwd_body,
            attachments=original.get("attachments"),
        )

    # -----------------------------------------------------------------------
    # Folder management
    # -----------------------------------------------------------------------

    def move_to_folder(self, email_id: str, folder: str) -> Dict[str, Any]:
        """
        Move an email to a different folder. Removes the email from its current
        primary folders (inbox, sent, spam, trash) and adds it to the target.
        Flag-based folders (starred, important, unread) are not affected.

        Args:
            email_id (str): The email to move.
            folder (str): The destination folder name.

        Returns:
            Dict[str, Any]:
                email_id (str), folder (str), previous_labels (List[str]),
                status (str).
        """
        em = self._require_email(email_id)
        if folder not in self.folders:
            raise OutlookError(
                "FOLDER_NOT_FOUND",
                f"Folder '{folder}' not found.",
                suggested_action=f"Use one of: {', '.join(SYSTEM_FOLDER_NAMES)}.",
                context={"folder": folder},
            )

        previous_labels = list(em.get("labels", []))
        primary_folders = ("inbox", "sent", "spam", "trash")
        for pf in primary_folders:
            self._remove_from_folder(pf, email_id)
        self._add_to_folder(folder, email_id)

        return {
            "email_id": email_id,
            "folder": folder,
            "previous_labels": previous_labels,
            "status": "moved",
        }

    # -----------------------------------------------------------------------
    # Email actions
    # -----------------------------------------------------------------------

    def delete_email(self, email_id: str) -> Dict[str, Any]:
        """
        Move an email to Trash. If already in Trash, permanently delete it.

        Args:
            email_id (str): The email to delete.

        Returns:
            Dict[str, Any]:
                email_id (str), status (str).
        """
        em = self._require_email(email_id)

        if "trash" in em.get("labels", []):
            for label in list(em.get("labels", [])):
                self._remove_from_folder(label, email_id)
            del self.emails[email_id]
            return {"email_id": email_id, "status": "permanently_deleted"}

        for label in list(em.get("labels", [])):
            self._remove_from_folder(label, email_id)
        em["labels"] = ["trash"]
        self._add_to_folder("trash", email_id)
        return {"email_id": email_id, "status": "moved_to_deleted"}

    def set_as_read(self, email_id: str) -> Dict[str, Any]:
        """
        Mark an email as read.

        Args:
            email_id (str): The email to mark as read.

        Returns:
            Dict[str, Any]:
                email_id (str), read (bool).
        """
        em = self._require_email(email_id)
        em["read"] = True
        self._remove_from_folder("unread", email_id)
        return {"email_id": email_id, "read": True}

    def set_as_unread(self, email_id: str) -> Dict[str, Any]:
        """
        Mark an email as unread.

        Args:
            email_id (str): The email to mark as unread.

        Returns:
            Dict[str, Any]:
                email_id (str), read (bool).
        """
        em = self._require_email(email_id)
        em["read"] = False
        self._add_to_folder("unread", email_id)
        return {"email_id": email_id, "read": False}

    def flag_email(self, email_id: str) -> Dict[str, Any]:
        """
        Flag an email for follow-up (sets starred to True).

        Args:
            email_id (str): The email to flag.

        Returns:
            Dict[str, Any]:
                email_id (str), starred (bool).
        """
        em = self._require_email(email_id)
        em["starred"] = True
        self._add_to_folder("starred", email_id)
        return {"email_id": email_id, "starred": True}

    def unflag_email(self, email_id: str) -> Dict[str, Any]:
        """
        Remove the flag from an email (sets starred to False).

        Args:
            email_id (str): The email to unflag.

        Returns:
            Dict[str, Any]:
                email_id (str), starred (bool).
        """
        em = self._require_email(email_id)
        em["starred"] = False
        self._remove_from_folder("starred", email_id)
        return {"email_id": email_id, "starred": False}

    def mark_as_important(self, email_id: str) -> Dict[str, Any]:
        """
        Mark an email as important.

        Args:
            email_id (str): The email to mark as important.

        Returns:
            Dict[str, Any]:
                email_id (str), important (bool).
        """
        em = self._require_email(email_id)
        em["important"] = True
        self._add_to_folder("important", email_id)
        return {"email_id": email_id, "important": True}

    def mark_as_not_important(self, email_id: str) -> Dict[str, Any]:
        """
        Remove importance from an email.

        Args:
            email_id (str): The email to mark as not important.

        Returns:
            Dict[str, Any]:
                email_id (str), important (bool).
        """
        em = self._require_email(email_id)
        em["important"] = False
        self._remove_from_folder("important", email_id)
        return {"email_id": email_id, "important": False}

    # -----------------------------------------------------------------------
    # Search
    # -----------------------------------------------------------------------

    def query_mail_items(
        self,
        query: str,
        folder: Optional[str] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search emails using query operators: from:, to:, subject:,
        has:attachment, folder:, is:unread, is:starred, is:important.
        Free text is matched against subject and body.

        Args:
            query (str): Search query string. Examples:
                "from:alice@example.com subject:meeting"
                "has:attachment folder:inbox"
                "is:unread is:starred"
                "quarterly report" (free text)
            folder (str, optional): Restrict search to a specific folder.
                If None, search all folders.
            max_results (int): Maximum results. Defaults to 20.

        Returns:
            List[Dict[str, Any]]: Matching email objects sorted by created_at
                descending.
        """
        self._require_user(self.user_id)
        if folder and folder not in self.folders:
            raise OutlookError(
                "FOLDER_NOT_FOUND",
                f"Folder '{folder}' not found.",
                suggested_action=f"Use one of: {', '.join(SYSTEM_FOLDER_NAMES)}.",
                context={"folder": folder},
            )

        parts = query.split()
        operators = {}
        free_text_parts = []
        for part in parts:
            if ":" in part:
                key, val = part.split(":", 1)
                key_lower = key.lower()
                if key_lower in ("from", "to", "subject", "has", "folder", "is"):
                    operators[key_lower] = val.lower()
                else:
                    free_text_parts.append(part)
            else:
                free_text_parts.append(part)
        free_text = " ".join(free_text_parts).lower()

        # If a folder argument is given, restrict to those email_ids
        candidate_eids = None
        if folder:
            candidate_eids = set(self.folders.get(folder, []))

        results = []
        for eid, em in self.emails.items():
            if candidate_eids is not None and eid not in candidate_eids:
                continue

            match = True

            if "from" in operators:
                if operators["from"] not in (em.get("from", "")).lower():
                    match = False

            if "to" in operators:
                to_combined = " ".join(em.get("to", [])).lower()
                if operators["to"] not in to_combined:
                    match = False

            if "subject" in operators:
                if operators["subject"] not in (em.get("subject", "")).lower():
                    match = False

            if "has" in operators:
                if operators["has"] == "attachment":
                    if not em.get("attachments"):
                        match = False

            if "folder" in operators:
                folder_q = operators["folder"]
                if folder_q not in [l.lower() for l in em.get("labels", [])]:
                    match = False

            if "is" in operators:
                is_val = operators["is"]
                if is_val == "unread" and em.get("read", False):
                    match = False
                if is_val == "starred" and not em.get("starred", False):
                    match = False
                if is_val == "read" and not em.get("read", False):
                    match = False
                if is_val == "important" and not em.get("important", False):
                    match = False

            if free_text:
                text_blob = (em.get("subject", "") + " " + em.get("body", "")).lower()
                if free_text not in text_blob:
                    match = False

            if match:
                results.append(deepcopy(em))

        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results[:max_results]

    # -----------------------------------------------------------------------
    # Contacts
    # -----------------------------------------------------------------------

    def list_people(self) -> List[Dict[str, Any]]:
        """
        List all contacts.

        Returns:
            List[Dict[str, Any]]: Contact objects with name and email_address.
        """
        self._require_user(self.user_id)
        return [deepcopy(c) for c in self.contacts.values()]

    def add_person(
        self,
        name: str,
        email_address: str,
    ) -> Dict[str, Any]:
        """
        Add a new contact to the address book.

        Args:
            name (str): Full name of the contact.
            email_address (str): Email address of the contact.

        Returns:
            Dict[str, Any]:
                name (str), email_address (str).
        """
        self._require_user(self.user_id)
        if email_address in self.contacts:
            raise OutlookError(
                "CONTACT_EXISTS",
                f"A contact with email '{email_address}' already exists.",
                suggested_action="Use a different email address or update the existing contact.",
                context={"email_address": email_address},
            )
        self.contacts[email_address] = {
            "name": name,
            "email_address": email_address,
        }
        return {"name": name, "email_address": email_address}

    # -----------------------------------------------------------------------
    # Quick Steps (multi-action macros)
    # -----------------------------------------------------------------------

    def create_quick_step(
        self,
        name: str,
        actions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Create a Quick Step — a reusable macro that performs multiple actions
        on an email in sequence.

        Args:
            name (str): Display name for the Quick Step.
            actions (List[Dict[str, Any]]): Ordered list of action objects.
                Each action has:
                    type (str): One of "move_to_folder", "mark_read", "flag",
                        "categorize", "forward_to".
                    params (Dict): Parameters for the action (e.g.
                        {"folder": "archive"} for move_to_folder,
                        {"email": "boss@co.com"} for forward_to,
                        {"category": "Red Category"} for categorize).

        Returns:
            Dict[str, Any]:
                quick_step_id (str), name (str), status (str).
        """
        self._require_user(self.user_id)
        valid_types = ("move_to_folder", "mark_read", "flag", "categorize", "forward_to")
        for action in actions:
            if action.get("type") not in valid_types:
                raise OutlookError(
                    "INVALID_ACTION_TYPE",
                    f"Action type '{action.get('type')}' is not valid.",
                    suggested_action=f"Use one of: {', '.join(valid_types)}.",
                    context={"action": action},
                )
        quick_step_id = self._new_id("quick_step")
        self.quick_steps[quick_step_id] = {
            "quick_step_id": quick_step_id,
            "name": name,
            "actions": actions,
            "created_at": _utc_now_iso(),
        }
        return {
            "quick_step_id": quick_step_id,
            "name": name,
            "status": "created",
        }

    def list_quick_steps(self) -> List[Dict[str, Any]]:
        """
        List all Quick Steps.

        Returns:
            List[Dict[str, Any]]: Quick Step objects with quick_step_id, name,
                and actions.
        """
        self._require_user(self.user_id)
        return [deepcopy(qs) for qs in self.quick_steps.values()]

    def run_quick_step(
        self,
        quick_step_id: str,
        email_id: str,
    ) -> Dict[str, Any]:
        """
        Execute a Quick Step on an email, performing each action in sequence.

        Args:
            quick_step_id (str): The Quick Step to run.
            email_id (str): The email to apply the Quick Step to.

        Returns:
            Dict[str, Any]:
                quick_step_id (str), email_id (str),
                actions_performed (List[str]), status (str).
        """
        qs = self.quick_steps.get(quick_step_id)
        if not qs:
            raise OutlookError(
                "QUICK_STEP_NOT_FOUND",
                f"Quick Step '{quick_step_id}' not found.",
                suggested_action="Use list_quick_steps() to find valid IDs.",
                context={"quick_step_id": quick_step_id},
            )
        em = self._require_email(email_id)
        actions_performed = []
        for action in qs.get("actions", []):
            action_type = action.get("type")
            params = action.get("params", {})
            if action_type == "move_to_folder":
                folder = params.get("folder", "inbox")
                self.move_to_folder(email_id, folder)
                actions_performed.append(f"move_to_folder:{folder}")
            elif action_type == "mark_read":
                self.set_as_read(email_id)
                actions_performed.append("mark_read")
            elif action_type == "flag":
                self.flag_email(email_id)
                actions_performed.append("flag")
            elif action_type == "categorize":
                category = params.get("category", "")
                self.assign_category(email_id, category)
                actions_performed.append(f"categorize:{category}")
            elif action_type == "forward_to":
                fwd_email = params.get("email", "")
                if fwd_email:
                    self.forward_mail_item(email_id, [fwd_email])
                    actions_performed.append(f"forward_to:{fwd_email}")
        return {
            "quick_step_id": quick_step_id,
            "email_id": email_id,
            "actions_performed": actions_performed,
            "status": "executed",
        }

    def delete_quick_step(self, quick_step_id: str) -> Dict[str, Any]:
        """
        Delete a Quick Step.

        Args:
            quick_step_id (str): The Quick Step to delete.

        Returns:
            Dict[str, Any]:
                quick_step_id (str), status (str).
        """
        if quick_step_id not in self.quick_steps:
            raise OutlookError(
                "QUICK_STEP_NOT_FOUND",
                f"Quick Step '{quick_step_id}' not found.",
                suggested_action="Use list_quick_steps() to find valid IDs.",
                context={"quick_step_id": quick_step_id},
            )
        del self.quick_steps[quick_step_id]
        return {"quick_step_id": quick_step_id, "status": "deleted"}

    # -----------------------------------------------------------------------
    # Categories with colors
    # -----------------------------------------------------------------------

    VALID_CATEGORY_COLORS = ("red", "orange", "yellow", "green", "blue", "purple")

    def create_category(self, name: str, color: str) -> Dict[str, Any]:
        """
        Create a new category with a color.

        Args:
            name (str): Category display name.
            color (str): Category color. Must be one of "red", "orange",
                "yellow", "green", "blue", "purple".

        Returns:
            Dict[str, Any]:
                name (str), color (str), status (str).
        """
        self._require_user(self.user_id)
        if color not in self.VALID_CATEGORY_COLORS:
            raise OutlookError(
                "INVALID_COLOR",
                f"Color '{color}' is not valid.",
                suggested_action=f"Use one of: {', '.join(self.VALID_CATEGORY_COLORS)}.",
                context={"color": color},
            )
        for cat in self.categories:
            if cat["name"] == name:
                raise OutlookError(
                    "CATEGORY_EXISTS",
                    f"Category '{name}' already exists.",
                    suggested_action="Use a different name or list_categories() to see existing ones.",
                    context={"name": name},
                )
        self.categories.append({"name": name, "color": color})
        return {"name": name, "color": color, "status": "created"}

    def list_categories(self) -> List[Dict[str, str]]:
        """
        List all categories.

        Returns:
            List[Dict[str, str]]: Category objects with name and color.
        """
        self._require_user(self.user_id)
        return deepcopy(self.categories)

    def assign_category(self, email_id: str, category_name: str) -> Dict[str, Any]:
        """
        Assign a category to an email.

        Args:
            email_id (str): The email to categorize.
            category_name (str): The category name to assign. Must exist.

        Returns:
            Dict[str, Any]:
                email_id (str), categories (List[str]), status (str).
        """
        em = self._require_email(email_id)
        if not any(c["name"] == category_name for c in self.categories):
            raise OutlookError(
                "CATEGORY_NOT_FOUND",
                f"Category '{category_name}' not found.",
                suggested_action="Use create_category() to create it first.",
                context={"category_name": category_name},
            )
        email_cats = em.setdefault("categories", [])
        if category_name not in email_cats:
            email_cats.append(category_name)
        return {
            "email_id": email_id,
            "categories": list(email_cats),
            "status": "category_assigned",
        }

    def remove_category(self, email_id: str, category_name: str) -> Dict[str, Any]:
        """
        Remove a category from an email.

        Args:
            email_id (str): The email to modify.
            category_name (str): The category name to remove.

        Returns:
            Dict[str, Any]:
                email_id (str), categories (List[str]), status (str).
        """
        em = self._require_email(email_id)
        email_cats = em.get("categories", [])
        if category_name not in email_cats:
            raise OutlookError(
                "CATEGORY_NOT_ASSIGNED",
                f"Category '{category_name}' is not assigned to email '{email_id}'.",
                suggested_action="Use assign_category() to assign it first.",
                context={"email_id": email_id, "category_name": category_name},
            )
        email_cats.remove(category_name)
        return {
            "email_id": email_id,
            "categories": list(email_cats),
            "status": "category_removed",
        }

    def get_emails_by_category(
        self,
        category_name: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List all emails with a specific category assigned.

        Args:
            category_name (str): The category to filter by.
            limit (int): Maximum number of emails to return. Defaults to 20.

        Returns:
            List[Dict[str, Any]]: Matching email objects sorted by created_at
                descending.
        """
        self._require_user(self.user_id)
        if not any(c["name"] == category_name for c in self.categories):
            raise OutlookError(
                "CATEGORY_NOT_FOUND",
                f"Category '{category_name}' not found.",
                suggested_action="Use create_category() to create it first.",
                context={"category_name": category_name},
            )
        results = []
        for em in self.emails.values():
            if category_name in em.get("categories", []):
                results.append(deepcopy(em))
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results[:limit]

    # -----------------------------------------------------------------------
    # Pin emails
    # -----------------------------------------------------------------------

    def pin_email(self, email_id: str) -> Dict[str, Any]:
        """
        Pin an email to the top of the folder view.

        Args:
            email_id (str): The email to pin.

        Returns:
            Dict[str, Any]:
                email_id (str), pinned (bool), status (str).
        """
        em = self._require_email(email_id)
        em["pinned"] = True
        if email_id not in self.pinned_emails:
            self.pinned_emails.append(email_id)
        return {"email_id": email_id, "pinned": True, "status": "pinned"}

    def unpin_email(self, email_id: str) -> Dict[str, Any]:
        """
        Unpin an email from the top of the folder view.

        Args:
            email_id (str): The email to unpin.

        Returns:
            Dict[str, Any]:
                email_id (str), pinned (bool), status (str).
        """
        em = self._require_email(email_id)
        em["pinned"] = False
        if email_id in self.pinned_emails:
            self.pinned_emails.remove(email_id)
        return {"email_id": email_id, "pinned": False, "status": "unpinned"}

    def list_pinned_emails(self) -> List[Dict[str, Any]]:
        """
        List all pinned emails.

        Returns:
            List[Dict[str, Any]]: Pinned email objects.
        """
        self._require_user(self.user_id)
        results = []
        for email_id in self.pinned_emails:
            em = self.emails.get(email_id)
            if em:
                results.append(deepcopy(em))
        return results
