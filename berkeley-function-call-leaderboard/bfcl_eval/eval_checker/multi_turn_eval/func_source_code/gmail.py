"""
Gmail Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Folder-based organization with fixed system folders.
- Thread-based conversation view where emails are grouped by thread_id.
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


class GmailError(Exception):
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
    "drafts",
    "starred",
    "important",
    "unread",
    "snoozed",
    "category_primary",
    "category_social",
    "category_promotions",
)


DEFAULT_STATE = {
    "random_seed": 1234,
    "profile": {},
    "emails": {},
    "contacts": {},
    "folders": {},
    "snoozed_emails": {},
    "scheduled_emails": {},
    "templates": {},
}


class GmailAPI(PatchableMixin):
    """
    In-memory dummy implementation of a Gmail-like email service.

    State variables:
    - profile: Dict of {name, email}
    - emails: Dict of {email_id -> {email_id, thread_id, from, to[], cc[],
      bcc[], subject, body, attachments[], labels[], read, starred,
      important, status ("sent" | "draft"), created_at}}
      (Drafts live in this same dict, distinguished by status="draft" and
      labels=["drafts"]; saved via send_email with empty `to`.)
    - contacts: Dict of {name, email}
    - folders: Dict of {folder_name -> [email_id, ...]}

    Supports multi-user switching via switch_user().
    """


    def __init__(self):
        self._id_counters = {"email": 0, "thread": 0}
        self.profile: Dict[str, Dict[str, Any]] = {}
        self.emails: Dict[str, Dict[str, Any]] = {}
        self.contacts: Dict[str, Dict[str, Any]] = {}
        self.folders: Dict[str, List[str]] = {}
        self.snoozed_emails: Dict[str, str] = {}
        self.scheduled_emails: Dict[str, Dict[str, Any]] = {}
        self.templates: Dict[str, Dict[str, Any]] = {}
        self._api_description = (
            "This tool belongs to the Gmail API, which provides functionality for "
            "sending, receiving, and organizing emails using a label-based system "
            "with thread-based conversation grouping."
        )


    def _new_id(self, prefix: str) -> str:
        """Generate the next sequential ID for *prefix* (e.g. ``order_1``)."""
        self._id_counters[prefix] = self._id_counters.get(prefix, 0) + 1
        return f"{prefix}_{self._id_counters[prefix]}"

    def _load_scenario(
        self,
        scenario: Dict[str, Any],
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
        self.contacts = scenario.get("contacts", DEFAULT_STATE_COPY["contacts"])
        self.folders = scenario.get("folders", DEFAULT_STATE_COPY["folders"])
        self.snoozed_emails = scenario.get("snoozed_emails", DEFAULT_STATE_COPY["snoozed_emails"])
        self.scheduled_emails = scenario.get("scheduled_emails", DEFAULT_STATE_COPY["scheduled_emails"])
        self.templates = scenario.get("templates", DEFAULT_STATE_COPY["templates"])
        # Auto-activate the sole user when the profile is single-user so that
        # self.user_id is set before any method that calls _require_user runs.
        # Multi-user profiles still require the agent to call switch_user().
        if len(self.profile) == 1:
            self.user_id = next(iter(self.profile))
        else:
            self.user_id = None

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, GmailAPI):
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
            raise GmailError(
                "USER_NOT_FOUND",
                f"User '{user_id}' not found.",
                suggested_action="Verify the user_id or use switch_user().",
                context={"user_id": user_id},
            )
        return user

    def _require_email(self, email_id: str) -> Dict[str, Any]:
        email = self.emails.get(email_id)
        if not email:
            raise GmailError(
                "EMAIL_NOT_FOUND",
                f"Email '{email_id}' not found.",
                suggested_action="Use list_emails() or search_emails() to find valid email IDs.",
                context={"email_id": email_id},
            )
        return email

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
        for prefix in ("re: ", "fwd: "):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :]
                break

        for em in self.emails.values():
            em_subj = (em.get("subject", "") or "").strip().lower()
            for prefix in ("re: ", "fwd: "):
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

    def switch_user(self, username: str) -> Dict[str, Any]:
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

    def list_emails(
        self,
        folder: str = "inbox",
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List emails in a given folder.

        Args:
            folder (str): Folder name (e.g. "inbox", "sent", "starred").
                Defaults to "inbox".
            max_results (int): Maximum number of emails to return. Defaults to 20.

        Returns:
            List[Dict[str, Any]]: Email objects sorted by created_at descending.
        """
        self._require_user(self.user_id)
        folder_list = self.folders.get(folder)
        if folder_list is None:
            raise GmailError(
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

    def get_email(self, email_id: str) -> Dict[str, Any]:
        """
        Retrieve the full content of a single email by its ID.

        Args:
            email_id (str): The unique identifier of the email.

        Returns:
            Dict[str, Any]: Full email object.
        """
        em = self._require_email(email_id)
        return deepcopy(em)

    def get_thread(self, thread_id: str) -> Dict[str, Any]:
        """
        Retrieve all emails in a conversation thread.

        Args:
            thread_id (str): The unique thread identifier.

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
            raise GmailError(
                "THREAD_NOT_FOUND",
                f"Thread '{thread_id}' not found.",
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

    def send_email(
        self,
        to: Optional[List[str]] = None,
        subject: str = "",
        body: str = "",
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Compose and send an email, or save it as a draft.

        Behavior depends on the `to` argument:
          * `to` non-empty  → the email is sent immediately and stored
            in the "sent" folder with status="sent".
          * `to` empty/None → the email is saved as a draft (no recipient
            yet) and stored in the "drafts" folder with status="draft".
            Subject, body, cc, bcc, and attachments are all preserved.

        This is the single entry point for both compose-and-send and
        compose-without-sending — there is no separate create_draft /
        send_draft pair.

        Args:
            to (List[str], optional): Recipient email addresses. Empty
                or None saves the email as a draft.
            subject (str): Subject line. Defaults to "".
            body (str): Body text. Defaults to "".
            cc (List[str], optional): Carbon copy recipients.
            bcc (List[str], optional): Blind carbon copy recipients.
            attachments (List[str], optional): Attachment filenames or IDs.

        Returns:
            Dict[str, Any]:
                email_id (str), thread_id (str | None),
                status (str — "sent" or "draft").
        """
        user = self._require_user(self.user_id)
        to = to or []
        cc = cc or []
        bcc = bcc or []
        is_draft = not to

        now = _utc_now_iso()
        sender = user.get("email_address", self.user_id)

        if is_draft:
            thread_id = None
            target_folder = "drafts"
            status = "draft"
            labels = ["drafts"]
            self.folders.setdefault("drafts", [])
        else:
            all_participants = list(set([sender] + to + cc))
            thread_id = self._get_or_create_thread_id(subject, all_participants)
            target_folder = "sent"
            status = "sent"
            labels = ["sent"]

        email_id = self._new_id("email")
        email_obj = {
            "email_id": email_id,
            "thread_id": thread_id,
            "from": sender,
            "to": to,
            "cc": cc,
            "bcc": bcc,
            "subject": subject,
            "body": body,
            "attachments": attachments or [],
            "labels": labels,
            "read": True,
            "starred": False,
            "important": False,
            "created_at": now,
            "status": status,
        }

        self.emails[email_id] = email_obj
        self._add_to_folder(target_folder, email_id)

        return {
            "email_id": email_id,
            "thread_id": thread_id,
            "status": status,
        }

    def reply_to_email(
        self,
        email_id: str,
        body: str,
        reply_all: bool = False,
    ) -> Dict[str, Any]:
        """
        Reply to an existing email. The reply is added to the same thread.

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
            subject = f"Re: {subject}"

        return self.send_email(to=recipients, subject=subject, body=body)

    def forward_email(
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
            raise GmailError(
                "NO_RECIPIENTS",
                "At least one forwarding recipient is required.",
                suggested_action="Provide at least one email address in the 'to' field.",
                context={"email_id": email_id},
            )

        subject = original.get("subject", "")
        if not subject.lower().startswith("fwd:"):
            subject = f"Fwd: {subject}"

        fwd_body = additional_message
        if additional_message:
            fwd_body += "\n\n"
        fwd_body += "---------- Forwarded message ----------\n"
        fwd_body += f"From: {original.get('from', '')}\n"
        fwd_body += f"Date: {original.get('created_at', '')}\n"
        fwd_body += f"Subject: {original.get('subject', '')}\n"
        fwd_body += f"To: {', '.join(original.get('to', []))}\n\n"
        fwd_body += original.get("body", "")

        return self.send_email(
            to=to,
            subject=subject,
            body=fwd_body,
            attachments=original.get("attachments"),
        )

    # -----------------------------------------------------------------------
    # Label / folder management
    # -----------------------------------------------------------------------

    def create_label(self, label_name: str) -> Dict[str, Any]:
        """
        Create a new custom label. Custom labels are user-defined buckets
        that emails can be tagged into via add_label/remove_label. System
        labels (inbox, sent, drafts, starred, important, unread, snoozed,
        trash, spam, category_*) are reserved and managed by their dedicated
        functions (star_email, archive_email, mark_as_unread, etc.).

        Args:
            label_name (str): The custom label name to create.

        Returns:
            Dict[str, Any]:
                label (str), status (str).
        """
        self._require_user(self.user_id)
        if label_name in SYSTEM_FOLDER_NAMES:
            raise GmailError(
                "INVALID_LABEL",
                f"'{label_name}' is a reserved system label and cannot be created.",
                suggested_action=(
                    "Choose a different name. System labels are managed by the "
                    "dedicated functions (star_email, archive_email, mark_as_unread, etc.)."
                ),
                context={"label_name": label_name},
            )
        if label_name in self.folders:
            raise GmailError(
                "LABEL_EXISTS",
                f"Label '{label_name}' already exists.",
                suggested_action="Use a different name or proceed with add_label().",
                context={"label_name": label_name},
            )
        self.folders[label_name] = []
        return {"label": label_name, "status": "created"}

    def add_label(self, email_id: str, label: str) -> Dict[str, Any]:
        """
        Add a custom label to an email. The label must already exist
        (create it with create_label first). System labels (starred,
        important, unread, etc.) cannot be added here — use the
        dedicated functions (star_email, mark_as_unread, archive_email,
        ...) for those.

        Args:
            email_id (str): The email to label.
            label (str): The custom label name to add.

        Returns:
            Dict[str, Any]:
                email_id (str), labels (List[str]).
        """
        em = self._require_email(email_id)
        if label in SYSTEM_FOLDER_NAMES:
            raise GmailError(
                "INVALID_LABEL",
                f"'{label}' is a system label; add_label only accepts custom labels.",
                suggested_action=(
                    "Use the dedicated function for this label "
                    "(star_email, mark_as_unread, archive_email, etc.)."
                ),
                context={"label": label},
            )
        if label not in self.folders:
            raise GmailError(
                "LABEL_NOT_FOUND",
                f"Label '{label}' does not exist.",
                suggested_action=f"Call create_label('{label}') first.",
                context={"label": label},
            )
        self._add_to_folder(label, email_id)
        return {"email_id": email_id, "labels": list(em.get("labels", []))}

    def remove_label(self, email_id: str, label: str) -> Dict[str, Any]:
        """
        Remove a custom label from an email. System labels cannot be
        removed here — use the dedicated inverse functions (unstar_email,
        mark_as_read, etc.).

        Args:
            email_id (str): The email to modify.
            label (str): The custom label name to remove.

        Returns:
            Dict[str, Any]:
                email_id (str), labels (List[str]).
        """
        em = self._require_email(email_id)
        if label in SYSTEM_FOLDER_NAMES:
            raise GmailError(
                "INVALID_LABEL",
                f"'{label}' is a system label; remove_label only accepts custom labels.",
                suggested_action=(
                    "Use the dedicated inverse function "
                    "(unstar_email, mark_as_read, etc.)."
                ),
                context={"label": label},
            )
        if label not in self.folders:
            raise GmailError(
                "LABEL_NOT_FOUND",
                f"Label '{label}' does not exist.",
                suggested_action="Use list_labels() to see existing custom labels.",
                context={"label": label},
            )
        self._remove_from_folder(label, email_id)
        return {"email_id": email_id, "labels": list(em.get("labels", []))}

    def list_labels(self) -> List[str]:
        """
        List all custom labels (system labels are excluded).

        Returns:
            List[str]: Custom label names.
        """
        self._require_user(self.user_id)
        return [name for name in self.folders if name not in SYSTEM_FOLDER_NAMES]

    # -----------------------------------------------------------------------
    # Inbox actions
    # -----------------------------------------------------------------------

    def archive_email(self, email_id: str) -> Dict[str, Any]:
        """
        Archive an email by removing it from the inbox folder.

        Args:
            email_id (str): The email to archive.

        Returns:
            Dict[str, Any]:
                email_id (str), status (str), labels (List[str]).
        """
        em = self._require_email(email_id)
        self._remove_from_folder("inbox", email_id)
        return {
            "email_id": email_id,
            "status": "archived",
            "labels": list(em.get("labels", [])),
        }

    def trash_email(self, email_id: str) -> Dict[str, Any]:
        """
        Move an email to Trash, removing it from all other folders.

        Args:
            email_id (str): The email to trash.

        Returns:
            Dict[str, Any]:
                email_id (str), status (str).
        """
        em = self._require_email(email_id)
        for label in list(em.get("labels", [])):
            self._remove_from_folder(label, email_id)
        em["labels"] = ["trash"]
        self._add_to_folder("trash", email_id)
        return {"email_id": email_id, "status": "trashed"}

    def mark_as_read(self, email_id: str) -> Dict[str, Any]:
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

    def mark_as_unread(self, email_id: str) -> Dict[str, Any]:
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

    def star_email(self, email_id: str) -> Dict[str, Any]:
        """
        Star an email.

        Args:
            email_id (str): The email to star.

        Returns:
            Dict[str, Any]:
                email_id (str), starred (bool).
        """
        em = self._require_email(email_id)
        em["starred"] = True
        self._add_to_folder("starred", email_id)
        return {"email_id": email_id, "starred": True}

    def unstar_email(self, email_id: str) -> Dict[str, Any]:
        """
        Remove the star from an email.

        Args:
            email_id (str): The email to unstar.

        Returns:
            Dict[str, Any]:
                email_id (str), starred (bool).
        """
        em = self._require_email(email_id)
        em["starred"] = False
        self._remove_from_folder("starred", email_id)
        return {"email_id": email_id, "starred": False}

    # -----------------------------------------------------------------------
    # Search
    # -----------------------------------------------------------------------

    def search_emails(
        self,
        query: str,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search emails using Gmail-style query operators: from:, to:, subject:,
        has:attachment, label:, is:unread, is:starred, is:important.
        Free text is matched against subject and body.

        Args:
            query (str): Search query string. Examples:
                "from:alice@example.com subject:meeting"
                "has:attachment label:inbox"
                "is:unread is:starred"
                "quarterly report" (free text)
            max_results (int): Maximum results. Defaults to 20.

        Returns:
            List[Dict[str, Any]]: Matching email objects sorted by created_at
                descending.
        """
        self._require_user(self.user_id)

        parts = query.split()
        operators = {}
        free_text_parts = []
        for part in parts:
            if ":" in part:
                key, val = part.split(":", 1)
                key_lower = key.lower()
                if key_lower in ("from", "to", "subject", "has", "label", "is"):
                    operators[key_lower] = val.lower()
                else:
                    free_text_parts.append(part)
            else:
                free_text_parts.append(part)
        free_text = " ".join(free_text_parts).lower()

        results = []
        for eid, em in self.emails.items():
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

            if "label" in operators:
                label_q = operators["label"]
                if label_q not in [l.lower() for l in em.get("labels", [])]:
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

    def list_contacts(self) -> List[Dict[str, Any]]:
        """
        List all contacts.

        Returns:
            List[Dict[str, Any]]: Contact objects with name and email_address.
        """
        self._require_user(self.user_id)
        return [deepcopy(c) for c in self.contacts.values()]

    def add_contact(
        self,
        name: str,
        email_address: str,
    ) -> Dict[str, Any]:
        """
        Add a new contact.

        Args:
            name (str): Full name of the contact.
            email_address (str): Email address of the contact.

        Returns:
            Dict[str, Any]:
                name (str), email_address (str).
        """
        self._require_user(self.user_id)
        if email_address in self.contacts:
            raise GmailError(
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
    # Snooze
    # -----------------------------------------------------------------------

    def snooze_email(self, email_id: str, snooze_until: str) -> Dict[str, Any]:
        """
        Snooze an email until a specified datetime. The email is moved to the
        snoozed folder and will reappear in the inbox after the snooze time.

        Args:
            email_id (str): The email to snooze.
            snooze_until (str): ISO 8601 datetime string for when the snooze
                should end (e.g. "2025-03-01T09:00:00Z").

        Returns:
            Dict[str, Any]:
                email_id (str), snooze_until (str), status (str).
        """
        em = self._require_email(email_id)
        try:
            datetime.fromisoformat(snooze_until.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            raise GmailError(
                "INVALID_DATETIME",
                f"'{snooze_until}' is not a valid ISO 8601 datetime.",
                suggested_action="Provide a valid ISO datetime string (e.g. '2025-03-01T09:00:00Z').",
                context={"snooze_until": snooze_until},
            )
        self._remove_from_folder("inbox", email_id)
        self._add_to_folder("snoozed", email_id)
        self.snoozed_emails[email_id] = snooze_until
        return {
            "email_id": email_id,
            "snooze_until": snooze_until,
            "status": "snoozed",
        }

    def list_snoozed_emails(self) -> List[Dict[str, Any]]:
        """
        List all currently snoozed emails with their snooze-until times.

        Returns:
            List[Dict[str, Any]]: Snoozed email objects, each including a
                snooze_until field.
        """
        self._require_user(self.user_id)
        results = []
        for email_id, snooze_until in self.snoozed_emails.items():
            em = self.emails.get(email_id)
            if em:
                entry = deepcopy(em)
                entry["snooze_until"] = snooze_until
                results.append(entry)
        return results

    def unsnooze_email(self, email_id: str) -> Dict[str, Any]:
        """
        Cancel the snooze on an email and return it to the inbox.

        Args:
            email_id (str): The email to unsnooze.

        Returns:
            Dict[str, Any]:
                email_id (str), status (str).
        """
        em = self._require_email(email_id)
        if email_id not in self.snoozed_emails:
            raise GmailError(
                "NOT_SNOOZED",
                f"Email '{email_id}' is not currently snoozed.",
                suggested_action="Use list_snoozed_emails() to find snoozed email IDs.",
                context={"email_id": email_id},
            )
        del self.snoozed_emails[email_id]
        self._remove_from_folder("snoozed", email_id)
        self._add_to_folder("inbox", email_id)
        return {"email_id": email_id, "status": "unsnoozed"}

    # -----------------------------------------------------------------------
    # Schedule send
    # -----------------------------------------------------------------------

    def schedule_send(
        self,
        to: List[str],
        subject: str,
        body: str,
        send_at: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Compose and schedule an email for future delivery.

        Args:
            to (List[str]): Recipient email addresses.
            subject (str): Subject line.
            body (str): Body text.
            send_at (str): ISO 8601 datetime string for scheduled send time.
            cc (List[str], optional): Carbon copy recipients.
            bcc (List[str], optional): Blind carbon copy recipients.
            attachments (List[str], optional): Attachment filenames or IDs.

        Returns:
            Dict[str, Any]:
                scheduled_id (str), send_at (str), status (str).
        """
        self._require_user(self.user_id)
        if not to:
            raise GmailError(
                "NO_RECIPIENTS",
                "At least one recipient is required.",
                suggested_action="Provide at least one email address in the 'to' field.",
                context={"user_id": self.user_id},
            )
        try:
            datetime.fromisoformat(send_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            raise GmailError(
                "INVALID_DATETIME",
                f"'{send_at}' is not a valid ISO 8601 datetime.",
                suggested_action="Provide a valid ISO datetime string (e.g. '2025-03-01T09:00:00Z').",
                context={"send_at": send_at},
            )
        scheduled_id = self._new_id("scheduled")
        self.scheduled_emails[scheduled_id] = {
            "scheduled_id": scheduled_id,
            "to": to or [],
            "cc": cc or [],
            "bcc": bcc or [],
            "subject": subject,
            "body": body,
            "attachments": attachments or [],
            "send_at": send_at,
            "created_at": _utc_now_iso(),
        }
        return {
            "scheduled_id": scheduled_id,
            "send_at": send_at,
            "status": "scheduled",
        }

    def list_scheduled_emails(self) -> List[Dict[str, Any]]:
        """
        List all scheduled but not yet sent emails.

        Returns:
            List[Dict[str, Any]]: Scheduled email objects sorted by send_at
                ascending.
        """
        self._require_user(self.user_id)
        results = [deepcopy(s) for s in self.scheduled_emails.values()]
        results.sort(key=lambda x: x.get("send_at", ""))
        return results

    def cancel_scheduled_email(self, scheduled_id: str) -> Dict[str, Any]:
        """
        Cancel a scheduled send and move the content to drafts via
        send_email's draft mode (empty recipient).

        Args:
            scheduled_id (str): The scheduled email to cancel.

        Returns:
            Dict[str, Any]:
                scheduled_id (str), draft_email_id (str), status (str).
        """
        scheduled = self.scheduled_emails.get(scheduled_id)
        if not scheduled:
            raise GmailError(
                "SCHEDULED_NOT_FOUND",
                f"Scheduled email '{scheduled_id}' not found.",
                suggested_action="Use list_scheduled_emails() to find valid scheduled IDs.",
                context={"scheduled_id": scheduled_id},
            )
        # Save the content as a draft by calling send_email with no
        # recipient. cc/bcc/attachments/subject/body are preserved.
        draft_result = self.send_email(
            to=[],
            subject=scheduled.get("subject", ""),
            body=scheduled.get("body", ""),
            cc=scheduled.get("cc"),
            bcc=scheduled.get("bcc"),
            attachments=scheduled.get("attachments"),
        )
        del self.scheduled_emails[scheduled_id]
        return {
            "scheduled_id": scheduled_id,
            "draft_email_id": draft_result["email_id"],
            "status": "cancelled_to_draft",
        }

    # -----------------------------------------------------------------------
    # Email templates
    # -----------------------------------------------------------------------

    def create_template(self, name: str, subject: str, body: str) -> Dict[str, Any]:
        """
        Save an email template for reuse.

        Args:
            name (str): Template display name.
            subject (str): Template subject line.
            body (str): Template body text.

        Returns:
            Dict[str, Any]:
                template_id (str), name (str), status (str).
        """
        self._require_user(self.user_id)
        template_id = self._new_id("template")
        self.templates[template_id] = {
            "template_id": template_id,
            "name": name,
            "subject": subject,
            "body": body,
            "created_at": _utc_now_iso(),
        }
        return {
            "template_id": template_id,
            "name": name,
            "status": "created",
        }

    def list_templates(self) -> List[Dict[str, Any]]:
        """
        List all saved email templates.

        Returns:
            List[Dict[str, Any]]: Template objects with template_id, name,
                subject, and body.
        """
        self._require_user(self.user_id)
        return [deepcopy(t) for t in self.templates.values()]

    def send_from_template(
        self,
        template_id: str,
        to: List[str],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Send an email using a saved template's subject and body.

        Args:
            template_id (str): The template to use.
            to (List[str]): Recipient email addresses.
            cc (List[str], optional): Carbon copy recipients.
            bcc (List[str], optional): Blind carbon copy recipients.

        Returns:
            Dict[str, Any]:
                email_id (str), thread_id (str), status (str).
        """
        template = self.templates.get(template_id)
        if not template:
            raise GmailError(
                "TEMPLATE_NOT_FOUND",
                f"Template '{template_id}' not found.",
                suggested_action="Use list_templates() to find valid template IDs.",
                context={"template_id": template_id},
            )
        return self.send_email(
            to=to,
            subject=template["subject"],
            body=template["body"],
            cc=cc,
            bcc=bcc,
        )

    def delete_template(self, template_id: str) -> Dict[str, Any]:
        """
        Delete an email template.

        Args:
            template_id (str): The template to delete.

        Returns:
            Dict[str, Any]:
                template_id (str), status (str).
        """
        if template_id not in self.templates:
            raise GmailError(
                "TEMPLATE_NOT_FOUND",
                f"Template '{template_id}' not found.",
                suggested_action="Use list_templates() to find valid template IDs.",
                context={"template_id": template_id},
            )
        del self.templates[template_id]
        return {"template_id": template_id, "status": "deleted"}
