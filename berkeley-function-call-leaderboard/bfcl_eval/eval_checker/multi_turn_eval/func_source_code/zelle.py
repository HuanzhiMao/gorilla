"""
Zelle Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Bank-to-bank direct transfer model: no stored wallet balance.
- Current-user perspective: no registration or account switching.
- Daily ($2,500) and monthly ($20,000) transfer limits.
- Only bank accounts can be used as funding sources (no cards).
"""

from __future__ import annotations

import copy
import random
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .server_patch_mixin import PatchableMixin


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


class ZelleError(Exception):
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
# Zelle API
# ---------------------------------------------------------------------------


DEFAULT_STATE = {
    "random_seed": 5001,
    "profile": {},
    "contacts": {},
    "transactions": {},
    "requests": {},
    "funding_sources": {},
    "scheduled_payments": {},
}


class ZelleAPI(PatchableMixin):
    """
    In-memory dummy implementation of a Zelle-like bank-to-bank payment service.

    State variables:
    - profile: {name, username, email, phone, linked_bank_accounts[],
      linked_cards[], balance}
    - contacts: Dict of {contact_id -> {contact_id, name, username, email, phone}}
    - transactions: Dict of {transaction_id -> {transaction_id, type,
      counterparty{contact_id, name, username}, amount, note, status,
      created_at, funding_source, visibility}}
    - requests: Dict of {request_id -> {request_id, direction,
      counterparty{contact_id, name, username}, amount, note, status,
      created_at}}
    - funding_sources: Dict of {source_id -> {source_id, type, name, last4,
      balance, active}}

    Bank-to-bank model: no wallet balance, only bank accounts as funding
    sources, daily/monthly transfer limits, all transactions private.
    """

    _DAILY_LIMIT = 2500.0
    _MONTHLY_LIMIT = 20000.0

    def __init__(self):
        self._id_counters = { "contact": 0, "transaction": 0, "request": 0, "funding_source": 0, "scheduled_payment": 0, }
        self.profile: Dict[str, Any] = {}
        self.contacts: Dict[str, Dict[str, Any]] = {}
        self.transactions: Dict[str, Dict[str, Any]] = {}
        self.requests: Dict[str, Dict[str, Any]] = {}
        self.funding_sources: Dict[str, Dict[str, Any]] = {}
        self.scheduled_payments: Dict[str, Dict[str, Any]] = {}
        self._api_description = (
            "This tool belongs to the Zelle payment API, which provides "
            "bank-to-bank money transfers, payment requests, and contact "
            "management with daily and monthly transfer limits."
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
        self.contacts = scenario.get("contacts", DEFAULT_STATE_COPY["contacts"])
        self.transactions = scenario.get("transactions", DEFAULT_STATE_COPY["transactions"])
        self.requests = scenario.get("requests", DEFAULT_STATE_COPY["requests"])
        self.funding_sources = scenario.get("funding_sources", DEFAULT_STATE_COPY["funding_sources"])
        self.scheduled_payments = scenario.get("scheduled_payments", DEFAULT_STATE_COPY["scheduled_payments"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, ZelleAPI):
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

    def _require_contact(self, contact_id: str) -> Dict[str, Any]:
        contact = self.contacts.get(contact_id)
        if not contact:
            raise ZelleError(
                "CONTACT_NOT_FOUND",
                f"Contact '{contact_id}' not found.",
                suggested_action="Use list_contacts() to find valid contact IDs.",
                context={"contact_id": contact_id},
            )
        return contact

    def _require_transaction(self, transaction_id: str) -> Dict[str, Any]:
        txn = self.transactions.get(transaction_id)
        if not txn:
            raise ZelleError(
                "TRANSACTION_NOT_FOUND",
                f"Transaction '{transaction_id}' not found.",
                suggested_action="Use list_transactions() to find valid transaction IDs.",
                context={"transaction_id": transaction_id},
            )
        return txn

    def _require_request(self, request_id: str) -> Dict[str, Any]:
        req = self.requests.get(request_id)
        if not req:
            raise ZelleError(
                "REQUEST_NOT_FOUND",
                f"Request '{request_id}' not found.",
                suggested_action="Use list_requests() to find valid request IDs.",
                context={"request_id": request_id},
            )
        return req

    def _require_funding_source(self, source_id: str) -> Dict[str, Any]:
        src = self.funding_sources.get(source_id)
        if not src:
            raise ZelleError(
                "FUNDING_SOURCE_NOT_FOUND",
                f"Funding source '{source_id}' not found.",
                suggested_action="Use list_funding_sources() to find valid source IDs.",
                context={"source_id": source_id},
            )
        return src

    def _get_default_bank_account(self) -> Optional[Dict[str, Any]]:
        """Return the first active bank account from profile.linked_bank_accounts."""
        for sid in self.profile.get("linked_bank_accounts", []):
            src = self.funding_sources.get(sid)
            if src and src.get("active", True):
                return src
        return None

    def _make_counterparty(self, contact: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "contact_id": contact.get("contact_id", ""),
            "name": contact.get("name", ""),
            "username": contact.get("username", ""),
        }

    def _calculate_daily_spent(self) -> float:
        today = datetime.now(timezone.utc).date().isoformat()
        total = 0.0
        for txn in self.transactions.values():
            if (txn.get("type") == "send"
                    and txn.get("status") in ("completed", "pending")
                    and txn.get("created_at", "")[:10] == today):
                total += txn.get("amount", 0)
        return total

    def _calculate_monthly_spent(self) -> float:
        month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
        total = 0.0
        for txn in self.transactions.values():
            if (txn.get("type") == "send"
                    and txn.get("status") in ("completed", "pending")
                    and txn.get("created_at", "")[:7] == month_prefix):
                total += txn.get("amount", 0)
        return total

    # -----------------------------------------------------------------------
    # Profile
    # -----------------------------------------------------------------------

    def get_account_profile(self) -> Dict[str, Any]:
        """
        Get the current user's Zelle profile.

        Returns:
            Dict[str, Any]: Profile with name, username, email, phone,
                linked_bank_accounts, linked_cards, balance.
        """
        return deepcopy(self.profile)

    # -----------------------------------------------------------------------
    # Contacts
    # -----------------------------------------------------------------------

    def add_recipient(
        self,
        name: str,
        username: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a new contact for quick transfers.

        Args:
            name (str): Contact's display name.
            username (str): Contact's username.
            email (str, optional): Contact's email address.
            phone (str, optional): Contact's phone number.
                At least one of email or phone is required.

        Returns:
            Dict[str, Any]: The created contact object.
        """
        if not email and not phone:
            raise ZelleError(
                "NO_IDENTIFIER",
                "At least one of email or phone is required.",
                suggested_action="Provide an email address or phone number.",
            )

        contact_id = self._new_id("contact")
        self.contacts[contact_id] = {
            "contact_id": contact_id,
            "name": name,
            "username": username,
            "email": email,
            "phone": phone,
        }
        return deepcopy(self.contacts[contact_id])

    def list_recipients(self) -> List[Dict[str, Any]]:
        """
        List all saved contacts.

        Returns:
            List[Dict[str, Any]]: Contact objects.
        """
        return [deepcopy(c) for c in self.contacts.values()]

    def get_recipient(self, contact_id: str) -> Dict[str, Any]:
        """
        Get a specific contact by ID.

        Args:
            contact_id (str): The contact's unique identifier.

        Returns:
            Dict[str, Any]: The contact object.
        """
        contact = self._require_contact(contact_id)
        return deepcopy(contact)

    def remove_recipient(self, contact_id: str) -> Dict[str, Any]:
        """
        Remove a contact from the saved list.

        Args:
            contact_id (str): The contact to remove.

        Returns:
            Dict[str, Any]:
                contact_id (str), status (str).
        """
        self._require_contact(contact_id)
        del self.contacts[contact_id]
        return {"contact_id": contact_id, "status": "removed"}

    # -----------------------------------------------------------------------
    # Sending money
    # -----------------------------------------------------------------------

    def send_transfer(
        self,
        contact_id: str,
        amount: float,
        note: str = "",
        funding_source_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send money to a contact via bank-to-bank transfer. Only bank accounts
        can be used. Subject to daily ($2,500) and monthly ($20,000) limits.

        Args:
            contact_id (str): The recipient contact.
            amount (float): Amount to send (must be > 0).
            note (str): Optional memo for the transfer.
            funding_source_id (str, optional): Bank account to send from.
                Defaults to the first active linked bank account.

        Returns:
            Dict[str, Any]:
                transaction_id (str), amount (float), status (str), note (str).
        """
        contact = self._require_contact(contact_id)
        if amount <= 0:
            raise ZelleError(
                "INVALID_AMOUNT",
                "Amount must be greater than zero.",
                suggested_action="Provide a positive amount.",
                context={"amount": amount},
            )

        # Resolve funding source
        if funding_source_id:
            src = self._require_funding_source(funding_source_id)
            if src.get("type") != "bank_account":
                raise ZelleError(
                    "INVALID_SOURCE_TYPE",
                    "Zelle only supports bank account transfers.",
                    suggested_action="Use a bank account funding source.",
                    context={"source_id": funding_source_id, "type": src.get("type")},
                )
            if not src.get("active", True):
                raise ZelleError(
                    "SOURCE_INACTIVE",
                    "This funding source is not active.",
                    suggested_action="Activate the funding source or use a different one.",
                    context={"source_id": funding_source_id},
                )
        else:
            src = self._get_default_bank_account()
            if not src:
                raise ZelleError(
                    "NO_BANK_ACCOUNT",
                    "No active bank account found.",
                    suggested_action="Add a bank account with add_funding_source().",
                )

        # Check limits
        daily_spent = self._calculate_daily_spent()
        if daily_spent + amount > self._DAILY_LIMIT:
            raise ZelleError(
                "DAILY_LIMIT_EXCEEDED",
                f"This transfer would exceed the daily limit of ${self._DAILY_LIMIT:.2f}.",
                suggested_action="Reduce the amount or try again tomorrow.",
                context={"daily_limit": self._DAILY_LIMIT, "daily_spent": daily_spent, "amount": amount},
            )
        monthly_spent = self._calculate_monthly_spent()
        if monthly_spent + amount > self._MONTHLY_LIMIT:
            raise ZelleError(
                "MONTHLY_LIMIT_EXCEEDED",
                f"This transfer would exceed the monthly limit of ${self._MONTHLY_LIMIT:.2f}.",
                suggested_action="Reduce the amount or wait until next month.",
                context={"monthly_limit": self._MONTHLY_LIMIT, "monthly_spent": monthly_spent, "amount": amount},
            )

        # Check balance on funding source
        src_balance = src.get("balance", 0)
        if src_balance < amount:
            raise ZelleError(
                "INSUFFICIENT_FUNDS",
                "Insufficient funds in the bank account.",
                suggested_action="Add funds to your bank account or use a different one.",
                context={"balance": src_balance, "amount": amount},
            )

        # Deduct from source
        src["balance"] = src_balance - amount

        now = _utc_now_iso()
        txn_id = self._new_id("transaction")
        self.transactions[txn_id] = {
            "transaction_id": txn_id,
            "type": "send",
            "counterparty": self._make_counterparty(contact),
            "amount": amount,
            "note": note,
            "status": "completed",
            "created_at": now,
            "funding_source": src["source_id"],
            "visibility": "private",
        }

        return {
            "transaction_id": txn_id,
            "amount": amount,
            "status": "completed",
            "note": note,
        }

    def cancel_transfer(self, transaction_id: str) -> Dict[str, Any]:
        """
        Cancel a pending transaction. Only pending transactions can be
        cancelled. The amount is refunded to the original funding source.

        Args:
            transaction_id (str): The transaction to cancel.

        Returns:
            Dict[str, Any]:
                transaction_id (str), status (str), refunded_amount (float).
        """
        txn = self._require_transaction(transaction_id)
        if txn.get("status") != "pending":
            raise ZelleError(
                "CANNOT_CANCEL",
                f"Cannot cancel a transaction with status '{txn.get('status')}'.",
                suggested_action="Only pending transactions can be cancelled.",
                context={"status": txn.get("status")},
            )

        txn["status"] = "cancelled"

        # Refund to funding source
        src = self.funding_sources.get(txn.get("funding_source", ""))
        if src and src.get("balance") is not None:
            src["balance"] += txn.get("amount", 0)

        return {
            "transaction_id": transaction_id,
            "status": "cancelled",
            "refunded_amount": txn.get("amount", 0),
        }

    def get_transfer(self, transaction_id: str) -> Dict[str, Any]:
        """
        Get full details of a transaction.

        Args:
            transaction_id (str): The unique transaction identifier.

        Returns:
            Dict[str, Any]: Full transaction object.
        """
        txn = self._require_transaction(transaction_id)
        return deepcopy(txn)

    def list_transfers(
        self,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List transactions, optionally filtered by status.

        Args:
            status (str, optional): Filter by status (completed/pending/
                cancelled/failed). None returns all.
            limit (int): Maximum number of results. Defaults to 20.

        Returns:
            List[Dict[str, Any]]: Transactions sorted newest first.
        """
        results = []
        for txn in self.transactions.values():
            if status and txn.get("status") != status:
                continue
            results.append(deepcopy(txn))
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results[:limit]

    # -----------------------------------------------------------------------
    # Money requests
    # -----------------------------------------------------------------------

    def request_transfer(
        self,
        contact_id: str,
        amount: float,
        note: str = "",
    ) -> Dict[str, Any]:
        """
        Request money from a contact.

        Args:
            contact_id (str): The contact to request money from.
            amount (float): Amount to request (must be > 0).
            note (str): Optional memo describing the request.

        Returns:
            Dict[str, Any]:
                request_id (str), amount (float), status (str), note (str).
        """
        contact = self._require_contact(contact_id)
        if amount <= 0:
            raise ZelleError(
                "INVALID_AMOUNT",
                "Amount must be greater than zero.",
                suggested_action="Provide a positive amount.",
                context={"amount": amount},
            )

        now = _utc_now_iso()
        req_id = self._new_id("request")
        self.requests[req_id] = {
            "request_id": req_id,
            "direction": "outgoing",
            "counterparty": self._make_counterparty(contact),
            "amount": amount,
            "note": note,
            "status": "pending",
            "created_at": now,
        }

        return {
            "request_id": req_id,
            "amount": amount,
            "status": "pending",
            "note": note,
        }

    def respond_to_transfer_request(
        self,
        request_id: str,
        action: str,
        funding_source_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Respond to an incoming money request — either pay or decline.

        Args:
            request_id (str): The request to respond to.
            action (str): "pay" to send the money, or "decline" to reject.
            funding_source_id (str, optional): Bank account to pay from.
                Defaults to first active linked bank account.

        Returns:
            Dict[str, Any]:
                request_id (str), status (str),
                transaction_id (str | None) — set if action is "pay".
        """
        req = self._require_request(request_id)
        if req.get("direction") != "incoming":
            raise ZelleError(
                "CANNOT_RESPOND",
                "You can only respond to incoming requests.",
                suggested_action="Use cancel_request() for outgoing requests.",
                context={"request_id": request_id, "direction": req.get("direction")},
            )
        if req.get("status") != "pending":
            raise ZelleError(
                "REQUEST_NOT_PENDING",
                f"This request has already been {req.get('status')}.",
                suggested_action="Only pending requests can be responded to.",
                context={"status": req.get("status")},
            )
        if action not in ("pay", "decline"):
            raise ZelleError(
                "INVALID_ACTION",
                f"Invalid action '{action}'. Must be 'pay' or 'decline'.",
                suggested_action="Use 'pay' or 'decline'.",
                context={"action": action},
            )

        if action == "decline":
            req["status"] = "declined"
            return {
                "request_id": request_id,
                "status": "declined",
                "transaction_id": None,
            }

        # Pay the request — create a transaction
        counterparty = req.get("counterparty", {})
        # Build a pseudo-contact for send_money's counterparty
        contact_for_txn = {
            "contact_id": counterparty.get("contact_id", ""),
            "name": counterparty.get("name", ""),
            "username": counterparty.get("username", ""),
        }

        # Resolve funding source
        if funding_source_id:
            src = self._require_funding_source(funding_source_id)
            if src.get("type") != "bank_account":
                raise ZelleError(
                    "INVALID_SOURCE_TYPE",
                    "Zelle only supports bank account transfers.",
                    suggested_action="Use a bank account funding source.",
                    context={"source_id": funding_source_id},
                )
        else:
            src = self._get_default_bank_account()
            if not src:
                raise ZelleError(
                    "NO_BANK_ACCOUNT",
                    "No active bank account found.",
                    suggested_action="Add a bank account with add_funding_source().",
                )

        amount = req.get("amount", 0)

        # Check balance
        src_balance = src.get("balance", 0)
        if src_balance < amount:
            raise ZelleError(
                "INSUFFICIENT_FUNDS",
                "Insufficient funds in the bank account.",
                suggested_action="Add funds or use a different account.",
                context={"balance": src_balance, "amount": amount},
            )

        src["balance"] = src_balance - amount

        now = _utc_now_iso()
        txn_id = self._new_id("transaction")
        self.transactions[txn_id] = {
            "transaction_id": txn_id,
            "type": "send",
            "counterparty": contact_for_txn,
            "amount": amount,
            "note": req.get("note", ""),
            "status": "completed",
            "created_at": now,
            "funding_source": src["source_id"],
            "visibility": "private",
        }

        req["status"] = "paid"
        return {
            "request_id": request_id,
            "status": "paid",
            "transaction_id": txn_id,
        }

    def cancel_transfer_request(self, request_id: str) -> Dict[str, Any]:
        """
        Cancel an outgoing money request that you created.

        Args:
            request_id (str): The request to cancel.

        Returns:
            Dict[str, Any]:
                request_id (str), status (str).
        """
        req = self._require_request(request_id)
        if req.get("direction") != "outgoing":
            raise ZelleError(
                "CANNOT_CANCEL",
                "You can only cancel your own outgoing requests.",
                suggested_action="Use respond_to_request() for incoming requests.",
                context={"request_id": request_id},
            )
        if req.get("status") != "pending":
            raise ZelleError(
                "REQUEST_NOT_PENDING",
                f"This request has already been {req.get('status')}.",
                suggested_action="Only pending requests can be cancelled.",
                context={"status": req.get("status")},
            )
        req["status"] = "cancelled"
        return {"request_id": request_id, "status": "cancelled"}

    def get_transfer_request(self, request_id: str) -> Dict[str, Any]:
        """
        Get full details of a money request.

        Args:
            request_id (str): The unique request identifier.

        Returns:
            Dict[str, Any]: Full request object.
        """
        req = self._require_request(request_id)
        return deepcopy(req)

    def list_transfer_requests(
        self,
        direction: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List money requests, optionally filtered by direction and status.

        Args:
            direction (str, optional): "outgoing" for requests you sent,
                "incoming" for requests you received. None returns all.
            status (str, optional): Filter by status (pending/paid/declined/
                cancelled). None returns all.

        Returns:
            List[Dict[str, Any]]: Requests sorted newest first.
        """
        results = []
        for req in self.requests.values():
            if direction and req.get("direction") != direction:
                continue
            if status and req.get("status") != status:
                continue
            results.append(deepcopy(req))
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    # -----------------------------------------------------------------------
    # Funding sources
    # -----------------------------------------------------------------------

    def link_bank_account(
        self,
        name: str,
        last4: str,
        balance: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Add a bank account as a funding source. Zelle only supports bank
        accounts — cards are not allowed.

        Args:
            name (str): Display name (e.g. "Chase Checking").
            last4 (str): Last 4 digits of the account number.
            balance (float): Current account balance. Defaults to 0.0.

        Returns:
            Dict[str, Any]: The created funding source object.
        """
        source_id = self._new_id("funding_source")
        self.funding_sources[source_id] = {
            "source_id": source_id,
            "type": "bank_account",
            "name": name,
            "last4": last4,
            "balance": balance,
            "active": True,
        }
        self.profile.setdefault("linked_bank_accounts", []).append(source_id)
        return deepcopy(self.funding_sources[source_id])

    def list_enrolled_banks(self) -> List[Dict[str, Any]]:
        """
        List all funding sources (bank accounts).

        Returns:
            List[Dict[str, Any]]: Funding source objects.
        """
        return [deepcopy(s) for s in self.funding_sources.values()]

    def enroll_bank_account(self, source_id: str) -> Dict[str, Any]:
        """
        Activate a funding source so it can be used for transfers.

        Args:
            source_id (str): The funding source to activate.

        Returns:
            Dict[str, Any]:
                source_id (str), active (bool), status (str).
        """
        src = self._require_funding_source(source_id)
        src["active"] = True
        return {"source_id": source_id, "active": True, "status": "activated"}

    def unenroll_bank_account(self, source_id: str) -> Dict[str, Any]:
        """
        Deactivate a funding source so it cannot be used for transfers.

        Args:
            source_id (str): The funding source to deactivate.

        Returns:
            Dict[str, Any]:
                source_id (str), active (bool), status (str).
        """
        src = self._require_funding_source(source_id)
        src["active"] = False
        return {"source_id": source_id, "active": False, "status": "deactivated"}

    # -----------------------------------------------------------------------
    # Limits
    # -----------------------------------------------------------------------

    def get_daily_limit(self) -> Dict[str, Any]:
        """
        Check the remaining daily sending limit.

        Returns:
            Dict[str, Any]:
                daily_limit (float), daily_spent (float),
                daily_remaining (float).
        """
        spent = self._calculate_daily_spent()
        return {
            "daily_limit": self._DAILY_LIMIT,
            "daily_spent": spent,
            "daily_remaining": max(0, self._DAILY_LIMIT - spent),
        }

    def get_monthly_limit(self) -> Dict[str, Any]:
        """
        Check the remaining monthly sending limit.

        Returns:
            Dict[str, Any]:
                monthly_limit (float), monthly_spent (float),
                monthly_remaining (float).
        """
        spent = self._calculate_monthly_spent()
        return {
            "monthly_limit": self._MONTHLY_LIMIT,
            "monthly_spent": spent,
            "monthly_remaining": max(0, self._MONTHLY_LIMIT - spent),
        }

    # -----------------------------------------------------------------------
    # Scheduled payments
    # -----------------------------------------------------------------------

    _VALID_CATEGORIES = (
        "rent", "utilities", "food", "entertainment", "travel",
        "healthcare", "other",
    )

    def schedule_payment(
        self,
        contact_id: str,
        amount: float,
        scheduled_date: str,
        note: Optional[str] = None,
        funding_source_id: Optional[str] = None,
        recurring: bool = False,
    ) -> Dict[str, Any]:
        """
        Schedule a future payment to a contact, optionally recurring monthly.
        Validates contact exists, amount > 0, date is in the future, and
        the payment is within daily/monthly limits.

        Args:
            contact_id (str): The recipient contact.
            amount (float): Amount to send (must be > 0).
            scheduled_date (str): Date to send the payment in YYYY-MM-DD
                format. Must be in the future.
            note (str, optional): Optional memo for the payment.
            funding_source_id (str, optional): Bank account to send from.
                Defaults to the first active linked bank account.
            recurring (bool): If True, the payment recurs monthly.
                Defaults to False.

        Returns:
            Dict[str, Any]:
                scheduled_payment_id (str), contact_id (str), amount (float),
                scheduled_date (str), recurring (bool), status (str).
        """
        contact = self._require_contact(contact_id)
        if amount <= 0:
            raise ZelleError(
                "INVALID_AMOUNT",
                "Amount must be greater than zero.",
                suggested_action="Provide a positive amount.",
                context={"amount": amount},
            )

        # Validate date format and that it is in the future
        try:
            sched_dt = datetime.strptime(scheduled_date, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            raise ZelleError(
                "INVALID_DATE_FORMAT",
                f"Invalid date format '{scheduled_date}'. Use YYYY-MM-DD.",
                suggested_action="Provide a date in YYYY-MM-DD format.",
                context={"scheduled_date": scheduled_date},
            )

        today = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        if sched_dt <= today:
            raise ZelleError(
                "DATE_NOT_IN_FUTURE",
                "Scheduled date must be in the future.",
                suggested_action="Provide a future date.",
                context={"scheduled_date": scheduled_date},
            )

        # Resolve funding source
        if funding_source_id:
            src = self._require_funding_source(funding_source_id)
            if src.get("type") != "bank_account":
                raise ZelleError(
                    "INVALID_SOURCE_TYPE",
                    "Zelle only supports bank account transfers.",
                    suggested_action="Use a bank account funding source.",
                    context={"source_id": funding_source_id, "type": src.get("type")},
                )
            if not src.get("active", True):
                raise ZelleError(
                    "SOURCE_INACTIVE",
                    "This funding source is not active.",
                    suggested_action="Activate the funding source or use a different one.",
                    context={"source_id": funding_source_id},
                )
        else:
            src = self._get_default_bank_account()
            if not src:
                raise ZelleError(
                    "NO_BANK_ACCOUNT",
                    "No active bank account found.",
                    suggested_action="Add a bank account with add_funding_source().",
                )

        # Check limits
        daily_spent = self._calculate_daily_spent()
        if daily_spent + amount > self._DAILY_LIMIT:
            raise ZelleError(
                "DAILY_LIMIT_EXCEEDED",
                f"This payment would exceed the daily limit of ${self._DAILY_LIMIT:.2f}.",
                suggested_action="Reduce the amount or try again tomorrow.",
                context={"daily_limit": self._DAILY_LIMIT, "daily_spent": daily_spent, "amount": amount},
            )
        monthly_spent = self._calculate_monthly_spent()
        if monthly_spent + amount > self._MONTHLY_LIMIT:
            raise ZelleError(
                "MONTHLY_LIMIT_EXCEEDED",
                f"This payment would exceed the monthly limit of ${self._MONTHLY_LIMIT:.2f}.",
                suggested_action="Reduce the amount or wait until next month.",
                context={"monthly_limit": self._MONTHLY_LIMIT, "monthly_spent": monthly_spent, "amount": amount},
            )

        now = _utc_now_iso()
        sp_id = self._new_id("scheduled_payment")
        self.scheduled_payments[sp_id] = {
            "scheduled_payment_id": sp_id,
            "contact_id": contact_id,
            "counterparty": self._make_counterparty(contact),
            "amount": amount,
            "scheduled_date": scheduled_date,
            "note": note or "",
            "funding_source": src["source_id"],
            "recurring": recurring,
            "status": "pending",
            "created_at": now,
        }

        return {
            "scheduled_payment_id": sp_id,
            "contact_id": contact_id,
            "amount": amount,
            "scheduled_date": scheduled_date,
            "recurring": recurring,
            "status": "pending",
        }

    def list_scheduled_payments(self) -> List[Dict[str, Any]]:
        """
        List all pending scheduled payments.

        Returns:
            List[Dict[str, Any]]: Scheduled payment objects sorted by
                scheduled_date ascending.
        """
        results = []
        for sp in self.scheduled_payments.values():
            if sp.get("status") == "pending":
                results.append(deepcopy(sp))
        results.sort(key=lambda x: x.get("scheduled_date", ""))
        return results

    def cancel_scheduled_payment(
        self, scheduled_payment_id: str,
    ) -> Dict[str, Any]:
        """
        Cancel a scheduled payment. Only pending scheduled payments can
        be cancelled.

        Args:
            scheduled_payment_id (str): The scheduled payment to cancel.

        Returns:
            Dict[str, Any]:
                scheduled_payment_id (str), status (str).
        """
        sp = self.scheduled_payments.get(scheduled_payment_id)
        if not sp:
            raise ZelleError(
                "SCHEDULED_PAYMENT_NOT_FOUND",
                f"Scheduled payment '{scheduled_payment_id}' not found.",
                suggested_action="Use list_scheduled_payments() to find valid IDs.",
                context={"scheduled_payment_id": scheduled_payment_id},
            )
        if sp.get("status") != "pending":
            raise ZelleError(
                "CANNOT_CANCEL",
                f"Cannot cancel a scheduled payment with status '{sp.get('status')}'.",
                suggested_action="Only pending scheduled payments can be cancelled.",
                context={"status": sp.get("status")},
            )
        sp["status"] = "cancelled"
        return {
            "scheduled_payment_id": scheduled_payment_id,
            "status": "cancelled",
        }

    # -----------------------------------------------------------------------
    # Transaction search & categories
    # -----------------------------------------------------------------------

    def search_transactions(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search transactions by memo text, category, or date range.

        Args:
            query (str, optional): Text to search for in transaction notes/
                memos. Case-insensitive substring match.
            category (str, optional): Filter by category (rent, utilities,
                food, entertainment, travel, healthcare, other).
            date_from (str, optional): Start date in YYYY-MM-DD format
                (inclusive).
            date_to (str, optional): End date in YYYY-MM-DD format
                (inclusive).

        Returns:
            List[Dict[str, Any]]: Matching transactions sorted newest first.
        """
        if category and category not in self._VALID_CATEGORIES:
            raise ZelleError(
                "INVALID_CATEGORY",
                f"Invalid category '{category}'.",
                suggested_action=f"Use one of: {', '.join(self._VALID_CATEGORIES)}.",
                context={"category": category},
            )

        results = []
        for txn in self.transactions.values():
            if query:
                note = txn.get("note", "") or txn.get("memo", "")
                if query.lower() not in note.lower():
                    continue
            if category:
                if txn.get("category") != category:
                    continue
            created = txn.get("created_at", "")[:10]
            if date_from and created < date_from:
                continue
            if date_to and created > date_to:
                continue
            results.append(deepcopy(txn))
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    def categorize_transaction(
        self,
        transaction_id: str,
        category: str,
    ) -> Dict[str, Any]:
        """
        Assign a category to a transaction for spending tracking.

        Args:
            transaction_id (str): The transaction to categorize.
            category (str): Category to assign — one of rent, utilities,
                food, entertainment, travel, healthcare, other.

        Returns:
            Dict[str, Any]:
                transaction_id (str), category (str), status (str).
        """
        txn = self._require_transaction(transaction_id)
        if category not in self._VALID_CATEGORIES:
            raise ZelleError(
                "INVALID_CATEGORY",
                f"Invalid category '{category}'.",
                suggested_action=f"Use one of: {', '.join(self._VALID_CATEGORIES)}.",
                context={"category": category},
            )
        txn["category"] = category
        return {
            "transaction_id": transaction_id,
            "category": category,
            "status": "categorized",
        }

    def get_spending_summary(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get a spending breakdown by category for the given date range.

        Args:
            date_from (str, optional): Start date in YYYY-MM-DD format
                (inclusive).
            date_to (str, optional): End date in YYYY-MM-DD format
                (inclusive).

        Returns:
            Dict[str, Any]:
                summary (Dict[str, float]): Spending totals by category.
                total (float): Total spending across all categories.
                uncategorized (float): Spending not assigned a category.
        """
        summary: Dict[str, float] = {cat: 0.0 for cat in self._VALID_CATEGORIES}
        uncategorized = 0.0

        for txn in self.transactions.values():
            if txn.get("type") != "send":
                continue
            if txn.get("status") not in ("completed", "pending"):
                continue
            created = txn.get("created_at", "")[:10]
            if date_from and created < date_from:
                continue
            if date_to and created > date_to:
                continue
            cat = txn.get("category")
            amount = txn.get("amount", 0)
            if cat and cat in summary:
                summary[cat] += amount
            else:
                uncategorized += amount

        total = sum(summary.values()) + uncategorized
        return {
            "summary": summary,
            "total": total,
            "uncategorized": uncategorized,
        }
